"""
Indexing engine for ContextBrain.

Handles project indexing, file parsing, and embedding generation.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
import concurrent.futures
import ast
import inspect

# Import aiofiles for async file operations
try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

# Import heavy dependencies at module level to avoid import delays
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from .models import (
    CodeElement, ElementType, SourceLocation, ElementMetadata,
    ProjectIndex, ProjectStatistics, IndexConfiguration,
    DependencyAnalysis, ArchitectureOverview
)
from .storage import VectorStore, StructuredIndex

# Import configuration for default supported extensions
try:
    from config import get_settings
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

logger = logging.getLogger(__name__)


class IndexingEngine:
    """Main indexing engine for processing projects."""
    
    def __init__(self, vector_store: VectorStore, structured_index: StructuredIndex):
        """Initialize the indexing engine."""
        self.vector_store = vector_store
        self.structured_index = structured_index
        self.embedding_model = None
    
    async def initialize(self, progress_callback=None):
        """Initialize the embedding model with non-blocking async loading."""
        logger.info("Initializing indexing engine...")

        async def update_progress(message: str):
            """Send progress update if callback provided."""
            if progress_callback:
                await progress_callback(message)
            logger.info(message)
            # Force immediate delivery
            await asyncio.sleep(0.001)

        try:
            # Send immediate progress update
            await update_progress("Initializing embedding model...")

            # Check if sentence transformers is available
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                raise ImportError("sentence-transformers package not available")

            await update_progress("Setting up model loading...")

            # Run the blocking SentenceTransformer initialization in a thread pool
            # This prevents it from blocking the event loop
            loop = asyncio.get_event_loop()

            def load_model():
                """Load the model in a separate thread."""
                return SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

            await update_progress("Loading embedding model in background thread...")

            # Use thread pool to run the blocking operation
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                # This runs in a separate thread and doesn't block the event loop
                self.embedding_model = await loop.run_in_executor(executor, load_model)

            await update_progress("Embedding model loaded successfully")
            logger.info("Initialized with embedding model")

        except Exception as e:
            await update_progress(f"Failed to initialize embedding model: {e}")
            logger.error(f"Failed to initialize indexing engine: {e}")
            raise
    
    async def clear_project_data(self, project_path: Path) -> int:
        """Clear all existing data for a project before re-indexing."""
        try:
            # Clear from structured index
            cursor = self.structured_index.connection.cursor()

            # For current directory, clear all elements (since paths are relative)
            if project_path.resolve() == Path(".").resolve():
                # Count all elements
                cursor.execute("SELECT COUNT(*) as count FROM elements")
                structured_count = cursor.fetchone()["count"]

                # Delete all elements
                cursor.execute("DELETE FROM elements")

                # Try to delete all dependencies if the table exists
                try:
                    cursor.execute("DELETE FROM dependencies")
                except Exception as dep_error:
                    logger.debug(f"Dependencies table cleanup skipped: {dep_error}")
            else:
                # For specific subdirectories, use relative path matching
                project_name = project_path.name

                # Count elements to be deleted
                cursor.execute("SELECT COUNT(*) as count FROM elements WHERE file_path LIKE ?", (f"{project_name}%",))
                structured_count = cursor.fetchone()["count"]

                # Delete elements
                cursor.execute("DELETE FROM elements WHERE file_path LIKE ?", (f"{project_name}%",))

                # Try to delete dependencies if the table exists
                try:
                    cursor.execute("DELETE FROM dependencies WHERE source_element_id LIKE ?", (f"%{project_name}%",))
                except Exception as dep_error:
                    logger.debug(f"Dependencies table cleanup skipped: {dep_error}")

            self.structured_index.connection.commit()

            # Clear from vector store using the dedicated method
            try:
                cleared_count = await self.vector_store.clear_collection()
                logger.info(f"Cleared {cleared_count} elements from vector store")
            except Exception as vs_error:
                logger.warning(f"Vector store clearing failed: {vs_error}")
                # Fallback: try to recreate the collection if clearing failed
                try:
                    if hasattr(self.vector_store, 'collection') and self.vector_store.collection:
                        collection_name = self.vector_store.collection.name
                        self.vector_store.client.delete_collection(collection_name)
                        # Recreate with consistent metadata
                        self.vector_store.collection = self.vector_store.client.create_collection(
                            name=collection_name,
                            metadata={"description": "ContextBrain code elements", "hnsw:space": "cosine"}
                        )
                        logger.info("Recreated vector store collection as fallback")
                except Exception as fallback_error:
                    logger.error(f"Vector store fallback recreation failed: {fallback_error}")

            logger.info(f"Cleared {structured_count} existing elements for project: {project_path}")
            return structured_count

        except Exception as e:
            logger.warning(f"Failed to clear project data: {e}")
            return 0

    async def index_project(self, project_path: Path, exclude_patterns: List[str] = None, progress_callback=None, clear_existing: bool = True, config: Optional[IndexConfiguration] = None) -> ProjectIndex:
        """Index a complete project with optional progress callback and configuration."""
        logger.info(f"Starting project indexing: {project_path}")
        start_time = time.time()

        async def update_progress(message: str):
            """Send progress update if callback provided."""
            if progress_callback:
                await progress_callback(message)
            logger.info(message)

        try:
            # Clear existing data if requested
            if clear_existing:
                await update_progress("Clearing existing project data...")
                cleared_count = await self.clear_project_data(project_path)
                if cleared_count > 0:
                    await update_progress(f"Cleared {cleared_count} existing elements")

            # Discover files
            await update_progress("Discovering files...")
            files = self._discover_files(project_path, exclude_patterns or [], config)
            await update_progress(f"Found {len(files)} files to index")

            # Process files and extract elements
            await update_progress("Processing files and extracting code elements...")
            all_elements = []
            processed_count = 0

            for file_path in files:
                try:
                    elements = await self._process_file(file_path, project_path)
                    all_elements.extend(elements)
                    processed_count += 1

                    # Progress update every 10 files
                    if processed_count % 10 == 0 or processed_count == len(files):
                        await update_progress(f"Processed {processed_count}/{len(files)} files...")

                except Exception as e:
                    logger.warning(f"Failed to process {file_path}: {e}")

            await update_progress(f"Extracted {len(all_elements)} code elements")

            # Generate embeddings
            if all_elements:
                await update_progress("Generating semantic embeddings...")
                await self._generate_embeddings_batch(all_elements, progress_callback=progress_callback)
                await update_progress(f"Generated embeddings for {len(all_elements)} elements")

            # Store elements
            await update_progress("Storing elements in databases...")
            await update_progress("Storing in structured index...")
            await self.structured_index.store_elements(all_elements)

            await update_progress("Storing in vector database...")
            # Use smaller batch size for vector store to prevent timeouts
            batch_size = min(100, len(all_elements))
            await self.vector_store.store_elements(all_elements, batch_size=batch_size)

            # Create project index
            processing_time = time.time() - start_time

            statistics = ProjectStatistics(
                total_files=len(files),
                total_elements=len(all_elements),
                languages=list({elem.metadata.language for elem in all_elements}),
                processing_time=processing_time
            )

            project_index = ProjectIndex(
                project_path=str(project_path),
                statistics=statistics,
                created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
                updated_at=time.strftime("%Y-%m-%d %H:%M:%S")
            )

            await update_progress(f"Project indexing completed in {processing_time:.2f}s")
            return project_index

        except Exception as e:
            await update_progress(f"Project indexing failed: {e}")
            logger.error(f"Project indexing failed: {e}")
            raise
    
    def _discover_files(self, project_path: Path, exclude_patterns: List[str], config: Optional[IndexConfiguration] = None) -> List[Path]:
        """Discover files to index based on supported extensions."""
        files = []

        # Get supported extensions from configuration or use defaults
        supported_extensions = self._get_supported_extensions(config)

        logger.info(f"Discovering files with extensions: {list(supported_extensions.keys())}")

        # Search for files with supported extensions
        for extension in supported_extensions.keys():
            pattern = f"*{extension}"
            for file_path in project_path.rglob(pattern):
                if file_path.is_file() and not self._should_exclude_file(file_path, exclude_patterns):
                    files.append(file_path)

        # Log discovered file types for debugging
        if files:
            file_types = {}
            for file_path in files:
                ext = file_path.suffix.lower()
                file_types[ext] = file_types.get(ext, 0) + 1
            logger.info(f"Discovered files by type: {file_types}")

        return files

    def _get_supported_extensions(self, config: Optional[IndexConfiguration] = None) -> Dict[str, str]:
        """Get supported file extensions and their language mappings."""
        # Default supported extensions (fallback if config is not available)
        default_extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.cxx': 'cpp',
            '.cc': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sh': 'bash',
            '.bash': 'bash',
            '.zsh': 'bash',
            '.sql': 'sql',
            '.html': 'html',
            '.htm': 'html',
            '.css': 'css',
            '.scss': 'css',
            '.sass': 'css',
            '.less': 'css',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.md': 'markdown',
            '.markdown': 'markdown',
            '.rst': 'rst',
            '.txt': 'text',
            '.r': 'r',
            '.R': 'r',
            '.ps1': 'powershell',
            '.psm1': 'powershell',
        }

        # Try to get extensions from global configuration
        if CONFIG_AVAILABLE:
            try:
                settings = get_settings()
                if hasattr(settings, 'indexing') and hasattr(settings.indexing, 'supported_extensions'):
                    config_extensions = settings.indexing.supported_extensions
                    if config_extensions:
                        logger.info(f"Using supported extensions from configuration: {len(config_extensions)} types")
                        return config_extensions
            except Exception as e:
                logger.warning(f"Failed to load extensions from configuration: {e}")

        logger.info(f"Using default supported extensions: {len(default_extensions)} types")
        return default_extensions

    def _should_exclude_file(self, file_path: Path, exclude_patterns: List[str]) -> bool:
        """Check if a file should be excluded from indexing."""
        file_str = str(file_path)

        # Check exclude patterns
        for pattern in exclude_patterns:
            if pattern in file_str:
                return True

        # Skip common directories
        common_excludes = ["__pycache__", ".git", "venv", "node_modules"]
        return any(part in file_str for part in common_excludes)
    
    async def _process_file(self, file_path: Path, project_root: Path) -> List[CodeElement]:
        """Process a single file and extract code elements using AST parsing."""
        elements = []

        try:
            # Read file content asynchronously if aiofiles is available
            if AIOFILES_AVAILABLE:
                async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = await f.read()
            else:
                # Fallback to synchronous read if aiofiles is not available
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

            relative_path = str(file_path.relative_to(project_root))

            # Parse files using appropriate parser based on language
            language = self._detect_language(file_path)

            if file_path.suffix == '.py':
                # Use specialized Python AST parser
                elements.extend(await self._parse_python_file(content, relative_path))
            else:
                # Use language-specific parser or generic parser for non-Python files
                try:
                    parsed_elements = await self._parse_with_language_parser(content, relative_path, language)
                    if parsed_elements:
                        elements.extend(parsed_elements)
                    else:
                        # Fallback: create a simple file element if parser returns nothing
                        elements.append(self._create_file_element(content, file_path, relative_path, language))
                except Exception as parser_error:
                    logger.warning(f"Parser failed for {file_path} ({language}): {parser_error}")
                    # Fallback: create a simple file element
                    elements.append(self._create_file_element(content, file_path, relative_path, language))

        except Exception as e:
            logger.warning(f"Failed to process file {file_path}: {e}")

        return elements

    async def _parse_with_language_parser(self, content: str, file_path: str, language: str) -> List[CodeElement]:
        """Parse file using appropriate language parser."""
        try:
            # Import parsers dynamically to avoid circular imports
            from .parsers import get_parser_for_language

            # Get appropriate parser for the language
            parser = get_parser_for_language(language)

            # Parse the file content
            elements = await parser.parse_file(content, file_path)

            logger.debug(f"Parsed {len(elements)} elements from {file_path} using {language} parser")
            return elements

        except ValueError as e:
            # Language not supported by parser system
            logger.debug(f"No specialized parser for {language}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Parser error for {file_path} ({language}): {e}")
            return []

    def _create_file_element(self, content: str, file_path: Path, relative_path: str, language: str) -> CodeElement:
        """Create a simple file-level element for files that couldn't be parsed."""
        # Normalize file path for consistent ID generation
        normalized_path = self._normalize_file_path(relative_path)

        # Truncate content for storage but keep meaningful parts
        truncated_content = content[:1000] if len(content) > 1000 else content

        return CodeElement(
            id=f"file_{normalized_path}",
            type=ElementType.MODULE,
            name=file_path.stem,
            content=truncated_content,
            file_path=relative_path,
            location=SourceLocation(
                line_start=1,
                line_end=len(content.split('\n')),
                column_start=0,
                column_end=0
            ),
            metadata=ElementMetadata(
                language=language,
                lines_of_code=len(content.split('\n'))
            )
        )

    async def _parse_python_file(self, content: str, file_path: str) -> List[CodeElement]:
        """Parse Python file using AST to extract code elements."""
        elements = []

        try:
            # Parse the Python code into an AST
            tree = ast.parse(content)
            lines = content.split('\n')

            # Create module element
            # Normalize file path for consistent ID generation
            normalized_path = self._normalize_file_path(file_path)

            module_element = CodeElement(
                id=f"module_{normalized_path}",
                type=ElementType.MODULE,
                name=Path(file_path).stem,
                content=content[:1000],  # Truncate for storage
                file_path=file_path,
                location=SourceLocation(line_start=1, line_end=len(lines), column_start=0, column_end=0),
                metadata=ElementMetadata(
                    language="python",
                    lines_of_code=len(lines)
                )
            )
            elements.append(module_element)

            # Walk the AST to extract code elements (only top-level to avoid duplicates)
            for node in tree.body:
                element = self._extract_element_from_node(node, lines, file_path)
                if element:
                    elements.append(element)

                # For classes, also extract their methods
                if isinstance(node, ast.ClassDef):
                    for class_node in node.body:
                        if isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_element = self._create_function_element(class_node, lines, file_path)
                            if method_element:
                                # Update the element to be a method
                                # Normalize file path for consistent ID generation
                                normalized_path = self._normalize_file_path(file_path)
                                method_element.type = ElementType.METHOD
                                method_element.id = f"method_{normalized_path}_{node.name}_{class_node.name}_{class_node.lineno}"
                                elements.append(method_element)

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Failed to parse Python file {file_path}: {e}")

        return elements

    def _extract_element_from_node(self, node: ast.AST, lines: List[str], file_path: str) -> Optional[CodeElement]:
        """Extract a code element from an AST node."""
        try:
            if isinstance(node, ast.ClassDef):
                return self._create_class_element(node, lines, file_path)
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                return self._create_function_element(node, lines, file_path)
            elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                return self._create_import_element(node, lines, file_path)
        except Exception as e:
            logger.debug(f"Failed to extract element from node: {e}")

        return None

    def _create_class_element(self, node: ast.ClassDef, lines: List[str], file_path: str) -> CodeElement:
        """Create a class element from an AST ClassDef node."""
        # Get class content
        start_line = node.lineno - 1
        end_line = node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else start_line + 1
        content = '\n'.join(lines[start_line:end_line])

        # Get docstring if available
        docstring = ast.get_docstring(node) or ""

        # Normalize file path for consistent ID generation
        normalized_path = self._normalize_file_path(file_path)

        return CodeElement(
            id=f"class_{normalized_path}_{node.name}_{node.lineno}",
            type=ElementType.CLASS,
            name=node.name,
            content=content[:1000],  # Truncate for storage
            file_path=file_path,
            location=SourceLocation(
                line_start=node.lineno,
                line_end=end_line,
                column_start=node.col_offset,
                column_end=getattr(node, 'end_col_offset', 0)
            ),
            metadata=ElementMetadata(
                language="python",
                lines_of_code=end_line - start_line,
                docstring=docstring,
                base_classes=[base.id if hasattr(base, 'id') else str(base) for base in node.bases]
            )
        )

    def _create_function_element(self, node: ast.FunctionDef, lines: List[str], file_path: str) -> CodeElement:
        """Create a function element from an AST FunctionDef node."""
        # Get function content
        start_line = node.lineno - 1
        end_line = node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else start_line + 1
        content = '\n'.join(lines[start_line:end_line])

        # Get docstring if available
        docstring = ast.get_docstring(node) or ""

        # Get function arguments
        args = [arg.arg for arg in node.args.args]

        # Normalize file path for consistent ID generation
        normalized_path = self._normalize_file_path(file_path)

        return CodeElement(
            id=f"function_{normalized_path}_{node.name}_{node.lineno}",
            type=ElementType.FUNCTION,
            name=node.name,
            content=content[:1000],  # Truncate for storage
            file_path=file_path,
            location=SourceLocation(
                line_start=node.lineno,
                line_end=end_line,
                column_start=node.col_offset,
                column_end=getattr(node, 'end_col_offset', 0)
            ),
            metadata=ElementMetadata(
                language="python",
                lines_of_code=end_line - start_line,
                docstring=docstring,
                parameters=args,
                is_async=isinstance(node, ast.AsyncFunctionDef)
            )
        )

    def _create_import_element(self, node: ast.AST, lines: List[str], file_path: str) -> CodeElement:
        """Create an import element from an AST Import node."""
        start_line = node.lineno - 1
        content = lines[start_line] if start_line < len(lines) else ""

        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            import_type = "import"
        else:  # ast.ImportFrom
            names = [alias.name for alias in node.names]
            import_type = f"from {node.module}"

        # Create deterministic ID based on file path, line number, and import names
        # Use import names instead of content for more stable hashing
        import_key = f"{import_type}_{','.join(sorted(names))}"
        # Use hashlib for deterministic hashing across Python sessions
        import hashlib
        content_hash = int(hashlib.md5(import_key.encode()).hexdigest()[:4], 16)
        normalized_content = content.strip()

        # Normalize file path for consistent ID generation
        normalized_path = self._normalize_file_path(file_path)

        return CodeElement(
            id=f"import_{normalized_path}_{node.lineno}_{content_hash}",
            type=ElementType.IMPORT,
            name=f"{import_type} {', '.join(names)}",
            content=normalized_content,
            file_path=file_path,
            location=SourceLocation(
                line_start=node.lineno,
                line_end=node.lineno,
                column_start=node.col_offset,
                column_end=getattr(node, 'end_col_offset', len(content))
            ),
            metadata=ElementMetadata(
                language="python",
                lines_of_code=1,
                imported_names=names
            )
        )

    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.sql': 'sql',
            '.sh': 'bash',
            '.ps1': 'powershell',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.md': 'markdown',
            '.txt': 'text'
        }
        return extension_map.get(file_path.suffix.lower(), 'unknown')

    async def _generate_embeddings_batch(self, elements: List[CodeElement], batch_size: int = 32, progress_callback=None):
        """Generate embeddings for elements in batches with progress updates."""
        if not self.embedding_model:
            logger.warning("Embedding model not initialized")
            return

        logger.info(f"Generating embeddings for {len(elements)} elements...")

        # Prepare texts for embedding with improved semantic content
        texts = []
        for element in elements:
            # Create improved text for better semantic embeddings
            text = self._create_embedding_text(element)
            texts.append(text)

        # Generate embeddings in batches with progress updates
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_elements = elements[i:i + batch_size]
            batch_num = (i // batch_size) + 1

            # Progress update for embedding batches
            if progress_callback and total_batches > 1:
                await progress_callback(f"Generating embeddings batch {batch_num}/{total_batches}...")

            # Generate embeddings
            embeddings = self.embedding_model.encode(
                batch_texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )

            # Assign embeddings to elements
            for j, element in enumerate(batch_elements):
                element.embedding = embeddings[j].tolist()

            # Yield control to prevent blocking
            await asyncio.sleep(0.01)

    def _create_embedding_text(self, element: CodeElement) -> str:
        """Create improved text for embedding generation with better semantic content."""
        from pathlib import Path

        # Start with element type and name
        parts = [f"{element.type.value} {element.name}"]

        # Add file context
        file_name = Path(element.file_path).stem
        parts.append(f"in {file_name}")

        # Extract meaningful content based on element type
        if element.type.value == 'class':
            # For classes, focus on docstring and method names
            docstring = self._extract_docstring(element.content)
            if docstring:
                parts.append(f"description: {docstring}")

            # Add method names from content
            method_names = self._extract_method_names(element.content)
            if method_names:
                parts.append(f"methods: {', '.join(method_names[:5])}")  # Limit to 5 methods

        elif element.type.value in ['method', 'function']:
            # For functions/methods, focus on docstring and parameters
            docstring = self._extract_docstring(element.content)
            if docstring:
                parts.append(f"description: {docstring}")

            # Extract parameters
            params = self._extract_parameters(element.content)
            if params:
                parts.append(f"parameters: {', '.join(params[:3])}")  # Limit to 3 params

        elif element.type.value == 'import':
            # For imports, keep it simple but descriptive
            parts = [f"import statement: {element.name}"]

        # Add some cleaned original content
        cleaned_content = self._clean_content_for_embedding(element.content)
        if cleaned_content:
            parts.append(cleaned_content[:200])  # Limit content length

        return ' '.join(parts)

    def _extract_docstring(self, content: str) -> str:
        """Extract docstring from code content."""
        try:
            lines = content.split('\n')
            in_docstring = False
            docstring_lines = []

            for line in lines:
                line = line.strip()
                if '"""' in line or "'''" in line:
                    if not in_docstring:
                        in_docstring = True
                        # Get text after opening quotes
                        if '"""' in line:
                            after_quotes = line.split('"""', 1)[1]
                        else:
                            after_quotes = line.split("'''", 1)[1]

                        if after_quotes.strip():
                            docstring_lines.append(after_quotes.strip())
                    else:
                        # End of docstring
                        if '"""' in line:
                            before_quotes = line.split('"""')[0]
                        else:
                            before_quotes = line.split("'''")[0]

                        if before_quotes.strip():
                            docstring_lines.append(before_quotes.strip())
                        break
                elif in_docstring:
                    if line:
                        docstring_lines.append(line)

            if docstring_lines:
                return ' '.join(docstring_lines)[:150]  # Limit docstring length
        except (AttributeError, IndexError, ValueError):
            pass

        return ""

    def _extract_method_names(self, content: str) -> List[str]:
        """Extract method names from class content."""
        try:
            lines = content.split('\n')
            method_names = []

            for line in lines:
                line = line.strip()
                if line.startswith('def ') or line.startswith('async def '):
                    method_name = line.split('(')[0].replace('def ', '').replace('async ', '').strip()
                    if method_name and not method_name.startswith('_'):  # Skip private methods
                        method_names.append(method_name)

            return method_names
        except (AttributeError, IndexError, ValueError):
            return []

    def _extract_parameters(self, content: str) -> List[str]:
        """Extract parameters from function/method content."""
        try:
            if '(' in content and ')' in content:
                param_start = content.find('(')
                param_end = content.find(')', param_start)
                if param_end > param_start:
                    params = content[param_start+1:param_end].strip()
                    if params and params != 'self':
                        # Clean up parameters
                        param_list = [p.split(':')[0].split('=')[0].strip() for p in params.split(',')]
                        param_list = [p for p in param_list if p and p != 'self']
                        return param_list
        except (AttributeError, IndexError, ValueError):
            pass

        return []

    def _clean_content_for_embedding(self, content: str) -> str:
        """Clean content to focus on meaningful text for embedding."""
        try:
            lines = content.split('\n')
            meaningful_lines = []

            for line in lines:
                line = line.strip()
                # Skip empty lines, comments, and very short lines
                if len(line) < 3:
                    continue
                if line.startswith('#'):
                    continue
                if line in ['{', '}', '(', ')', '[', ']']:
                    continue

                # Keep lines with meaningful content
                if any(keyword in line.lower() for keyword in ['def', 'class', 'return', 'if', 'for', 'while', 'try', 'except']):
                    meaningful_lines.append(line)
                elif len(line) > 10 and any(c.isalpha() for c in line):
                    meaningful_lines.append(line)

            return ' '.join(meaningful_lines[:5])  # Limit to 5 meaningful lines
        except (AttributeError, IndexError, ValueError):
            return content[:100]  # Fallback to first 100 chars

    def _normalize_file_path(self, file_path: str) -> str:
        """Normalize file path for consistent database queries and ID generation."""
        # Remove leading ./ and normalize path separators to match database storage
        normalized = file_path.replace('./', '')

        # Convert forward slashes to backslashes to match Windows storage format
        # This ensures consistency with how paths are stored in the database
        normalized = normalized.replace('/', '\\')

        # For ID generation consistency, always use the full path format
        # If it's just a filename without directory, keep it as-is for backward compatibility
        # but ensure consistent format for paths with directories
        return normalized

    def _extract_module_from_import(self, import_name: str, import_content: str) -> str:
        """Extract module name from import statement."""
        try:
            # Handle different import formats
            if import_content.startswith('from '):
                # from module import something
                parts = import_content.split()
                if len(parts) >= 2:
                    return parts[1]  # module name
            elif import_content.startswith('import '):
                # import module
                parts = import_content.split()
                if len(parts) >= 2:
                    return parts[1].split('.')[0]  # base module name

            # Fallback to import_name processing
            if 'import' in import_name:
                return import_name.split()[-1]

            return import_name
        except (IndexError, AttributeError, ValueError):
            return import_name

    def _is_internal_module(self, module_name: str) -> bool:
        """Check if a module is internal to the project."""
        internal_prefixes = ['contextbrain', '.', 'main']
        return any(module_name.startswith(prefix) for prefix in internal_prefixes)

    def _file_path_to_module(self, file_path: str) -> str:
        """Convert file path to module name."""
        try:
            # Remove file extension and convert path separators
            module_path = file_path.replace('.py', '').replace('\\', '.').replace('/', '.')

            # Remove leading dots
            while module_path.startswith('.'):
                module_path = module_path[1:]

            return module_path
        except (AttributeError, ValueError):
            return file_path

    def _module_to_file_path(self, module_name: str) -> str:
        """Convert module name to file path."""
        try:
            # Convert dots to path separators and add .py extension
            file_path = module_name.replace('.', '/') + '.py'
            return file_path
        except (AttributeError, ValueError):
            return module_name

    async def analyze_dependencies(self, target_file: str, depth: int = 2, include_external: bool = False) -> DependencyAnalysis:
        """Analyze dependencies for a file with comprehensive import tracking."""
        try:
            cursor = self.structured_index.connection.cursor()

            # Normalize target file path
            normalized_target = self._normalize_file_path(target_file)

            # Find direct dependencies (what the target file imports)
            dependencies = []
            cursor.execute("""
                SELECT DISTINCT name, content FROM elements
                WHERE file_path = ? AND type = 'import'
                ORDER BY name
            """, (normalized_target,))

            direct_imports = cursor.fetchall()

            for imp in direct_imports:
                import_name = imp['name']
                import_content = imp['content']

                # Parse import to extract module name
                module_name = self._extract_module_from_import(import_name, import_content)

                if module_name:
                    # Filter external imports if not requested
                    if include_external or self._is_internal_module(module_name):
                        dependencies.append(module_name)

            # Remove duplicates while preserving order
            dependencies = list(dict.fromkeys(dependencies))

            # Find dependents (what imports from the target file)
            dependents = []

            # Extract module name from target file for dependent search
            target_module = self._file_path_to_module(normalized_target)

            if target_module:
                cursor.execute("""
                    SELECT DISTINCT file_path FROM elements
                    WHERE type = 'import' AND (
                        name LIKE ? OR
                        content LIKE ? OR
                        name LIKE ? OR
                        content LIKE ?
                    )
                    AND file_path != ?
                    ORDER BY file_path
                """, (
                    f"%{target_module}%",
                    f"%{target_module}%",
                    f"%{target_file}%",
                    f"%{target_file}%",
                    normalized_target
                ))

                dependent_files = cursor.fetchall()
                dependents = [dep['file_path'] for dep in dependent_files]

            # Separate internal and external dependencies
            internal_deps = [dep for dep in dependencies if self._is_internal_module(dep)]
            external_deps = [dep for dep in dependencies if not self._is_internal_module(dep)]

            return DependencyAnalysis(
                target=target_file,
                dependencies=internal_deps if not include_external else dependencies,
                dependents=dependents,
                depth=depth,
                external_dependencies=external_deps
            )

        except Exception as e:
            logger.error(f"Failed to analyze dependencies for {target_file}: {e}")
            # Return empty result on error
            return DependencyAnalysis(
                target=target_file,
                dependencies=[],
                dependents=[],
                depth=depth,
                external_dependencies=[]
            )
    
    async def get_file_context(self, file_path: str, context_size: int = 5, include_dependencies: bool = True) -> Dict[str, Any]:
        """Get comprehensive context for a specific file."""
        try:
            cursor = self.structured_index.connection.cursor()

            # Normalize file path
            normalized_path = self._normalize_file_path(file_path)

            # Get file elements
            cursor.execute("""
                SELECT type, name, content, line_start, line_end
                FROM elements
                WHERE file_path = ?
                ORDER BY line_start
            """, (normalized_path,))

            file_elements = cursor.fetchall()

            if not file_elements:
                return {
                    "file_path": file_path,
                    "context": f"File {file_path} not found in index",
                    "related_files": [],
                    "dependencies": [],
                    "elements": []
                }

            # Build context summary
            element_summary = {}
            for element in file_elements:
                elem_type = element['type']
                if elem_type not in element_summary:
                    element_summary[elem_type] = []
                element_summary[elem_type].append(element['name'])

            # Create context description
            context_parts = []
            for elem_type, names in element_summary.items():
                if len(names) <= context_size:
                    context_parts.append(f"{elem_type}s: {', '.join(names)}")
                else:
                    context_parts.append(f"{elem_type}s: {', '.join(names[:context_size])} and {len(names) - context_size} more")

            context_description = "; ".join(context_parts)

            # Get dependencies if requested
            dependencies = []
            related_files = []

            if include_dependencies:
                try:
                    dep_analysis = await self.analyze_dependencies(normalized_path, depth=1, include_external=False)
                    dependencies = dep_analysis.dependencies
                    related_files = dep_analysis.dependents
                except Exception as e:
                    logger.warning(f"Failed to get dependencies for {file_path}: {e}")

            # Get related files through imports
            cursor.execute("""
                SELECT DISTINCT file_path FROM elements
                WHERE type = 'import' AND (name LIKE ? OR content LIKE ?)
                AND file_path != ?
                LIMIT ?
            """, (f"%{normalized_path}%", f"%{normalized_path}%", normalized_path, context_size))

            import_related = [row['file_path'] for row in cursor.fetchall()]
            related_files.extend(import_related)

            # Remove duplicates and limit
            related_files = list(dict.fromkeys(related_files))[:context_size]

            return {
                "file_path": file_path,
                "context": context_description,
                "related_files": related_files,
                "dependencies": dependencies[:context_size] if dependencies else [],
                "elements": [
                    {
                        "type": elem['type'],
                        "name": elem['name'],
                        "line_start": elem['line_start'],
                        "line_end": elem['line_end']
                    }
                    for elem in file_elements[:context_size * 2]  # Show more elements
                ]
            }

        except Exception as e:
            logger.error(f"Failed to get file context for {file_path}: {e}")
            return {
                "file_path": file_path,
                "context": f"Error getting context: {str(e)}",
                "related_files": [],
                "dependencies": [],
                "elements": []
            }
    
    async def get_architecture_overview(self, focus_area: Optional[str] = None, detail_level: str = "medium") -> ArchitectureOverview:
        """Get comprehensive architecture overview of the codebase."""
        try:
            cursor = self.structured_index.connection.cursor()

            # Get all modules
            cursor.execute("SELECT DISTINCT file_path FROM elements WHERE type = 'module' ORDER BY file_path")
            all_modules = [row['file_path'] for row in cursor.fetchall()]

            # Filter for core modules based on detail level
            if detail_level == "low":
                # Only core contextbrain modules
                core_modules = [m for m in all_modules if 'contextbrain' in m and not any(test in m.lower() for test in ['test', 'debug', 'diagnose'])]
            elif detail_level == "medium":
                # Core modules plus important supporting files
                core_modules = [m for m in all_modules if any(core in m.lower() for core in ['contextbrain', 'main', 'config', 'setup']) and not any(test in m.lower() for test in ['test', 'debug', 'diagnose'])]
            else:  # high
                # All modules except test files
                core_modules = [m for m in all_modules if not any(test in m.lower() for test in ['test', 'debug', 'diagnose'])]

            # Get key components (classes with architectural significance)
            cursor.execute("SELECT DISTINCT name, file_path FROM elements WHERE type = 'class' ORDER BY name")
            all_classes = cursor.fetchall()

            key_components = []
            architectural_keywords = ['engine', 'store', 'index', 'server', 'context', 'watcher', 'config', 'manager', 'handler', 'processor']

            for cls in all_classes:
                class_name = cls['name']
                file_path = cls['file_path']

                # Include if it's an architectural component or in core modules
                if (any(keyword in class_name.lower() for keyword in architectural_keywords) or
                    any(core in file_path for core in ['contextbrain', 'main', 'config'])):

                    # Avoid test classes unless high detail
                    if detail_level != "high" and any(test in file_path.lower() for test in ['test', 'debug', 'diagnose']):
                        continue

                    key_components.append(class_name)

            # Remove duplicates while preserving order
            key_components = list(dict.fromkeys(key_components))

            # Get relationships (import dependencies)
            cursor.execute("""
                SELECT name, file_path FROM elements
                WHERE type = 'import' AND (name LIKE '%contextbrain%' OR name LIKE '%from contextbrain%')
                ORDER BY file_path
            """)
            internal_imports = cursor.fetchall()

            relationships = {}
            for imp in internal_imports:
                file_path = imp['file_path']
                import_name = imp['name']

                # Skip test files for low/medium detail
                if detail_level != "high" and any(test in file_path.lower() for test in ['test', 'debug', 'diagnose']):
                    continue

                if file_path not in relationships:
                    relationships[file_path] = []

                # Clean up import name for better readability
                clean_import = import_name.replace('from ', '').replace('import ', '').strip()
                if clean_import not in relationships[file_path]:
                    relationships[file_path].append(clean_import)

            # Calculate complexity metrics
            cursor.execute("SELECT COUNT(*) as total_elements FROM elements")
            total_elements = cursor.fetchone()['total_elements']

            cursor.execute("SELECT type, COUNT(*) as count FROM elements GROUP BY type")
            type_counts = {row['type']: row['count'] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(DISTINCT file_path) as total_files FROM elements")
            total_files = cursor.fetchone()['total_files']

            complexity_metrics = {
                "total_elements": total_elements,
                "total_files": total_files,
                "element_types": type_counts,
                "modules_count": len(core_modules),
                "components_count": len(key_components),
                "relationships_count": len(relationships),
                "avg_elements_per_file": round(total_elements / max(total_files, 1), 2)
            }

            # Add focus area filtering if specified
            if focus_area:
                focus_lower = focus_area.lower()
                core_modules = [m for m in core_modules if focus_lower in m.lower()]
                key_components = [c for c in key_components if focus_lower in c.lower()]
                relationships = {k: v for k, v in relationships.items() if focus_lower in k.lower()}

            return ArchitectureOverview(
                modules=core_modules,
                key_components=key_components,
                relationships=relationships,
                complexity_metrics=complexity_metrics
            )

        except Exception as e:
            logger.error(f"Failed to get architecture overview: {e}")
            # Return empty result on error
            return ArchitectureOverview(
                modules=[],
                key_components=[],
                relationships={},
                complexity_metrics={}
            )
