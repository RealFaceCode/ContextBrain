"""
ContextBrain MCP Server Implementation

Main server class that implements the Model Context Protocol for project context management.
Provides resources, tools, and prompts for intelligent code analysis and retrieval.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.prompts import base
from mcp.types import PromptMessage
from pydantic import BaseModel, Field

from .indexing import IndexingEngine
from .storage import VectorStore, StructuredIndex
from .monitoring import FileWatcher
from .models import (
    ProjectIndex,
    CodeElement,
    QueryResult,
    SearchResult,
    DependencyAnalysis,
    ArchitectureOverview,
)

logger = logging.getLogger(__name__)


class AppContext(BaseModel):
    """Application context with typed dependencies and lazy initialization."""
    indexing_engine: Optional[IndexingEngine] = None
    vector_store: Optional[VectorStore] = None
    structured_index: Optional[StructuredIndex] = None
    file_watcher: Optional[FileWatcher] = None
    _initialized: bool = False

    class Config:
        arbitrary_types_allowed = True
    
    async def ensure_initialized(self):
        """Lazy initialization of components to prevent startup timeouts."""
        if self._initialized:
            return
        
        logger.info("Lazy initializing ContextBrain components...")
        
        # Initialize storage components
        self.vector_store = VectorStore()
        self.structured_index = StructuredIndex()
        
        await self.vector_store.initialize()
        await self.structured_index.initialize()
        
        # Initialize indexing engine (without heavy model loading yet)
        self.indexing_engine = IndexingEngine(self.vector_store, self.structured_index)
        
        # Initialize file watcher
        self.file_watcher = FileWatcher(self.indexing_engine)
        
        self._initialized = True
        logger.info("Components initialized successfully")


class ContextBrainServer:
    """
    ContextBrain MCP Server for intelligent project context management.
    
    Provides semantic search, structural analysis, and real-time synchronization
    of project codebases through the Model Context Protocol.
    """
    
    def __init__(self, name: str = "ContextBrain", host: str = "127.0.0.1", port: int = 8000):
        """Initialize the ContextBrain server."""
        self.name = name
        self.mcp = FastMCP(name, lifespan=self._app_lifespan, host=host, port=port)
        self._setup_resources()
        self._setup_tools()
        self._setup_prompts()
        
    @asynccontextmanager
    async def _app_lifespan(self, server: FastMCP) -> AsyncIterator[AppContext]:
        """Manage application lifecycle with lazy initialization to prevent timeouts."""
        logger.info("Starting ContextBrain server (lazy mode)...")
        
        # Create context without heavy initialization to prevent VS Code timeouts
        app_context = AppContext()
        
        try:
            yield app_context
        finally:
            logger.info("Shutting down ContextBrain server...")
            if app_context.file_watcher:
                await app_context.file_watcher.stop()
            if app_context.vector_store:
                await app_context.vector_store.close()
            if app_context.structured_index:
                await app_context.structured_index.close()
    
    def _setup_resources(self):
        """Setup MCP resources for project information."""
        
        @self.mcp.resource("project://index")
        async def get_project_index() -> str:
            """Get the current project index information."""
            return "Project index information available"
        
        @self.mcp.resource("project://structure")
        async def get_project_structure() -> str:
            """Get the project directory structure."""
            return "Project structure information"
        
        @self.mcp.resource("project://dependencies")
        async def get_project_dependencies() -> str:
            """Get project dependencies and their relationships."""
            return "Project dependencies information"
    
    def _setup_tools(self):
        """Setup MCP tools for project operations."""
        
        @self.mcp.tool()
        async def index_project(
            path: str,
            exclude_patterns: Optional[List[str]] = None,
            include_languages: Optional[List[str]] = None,  # Kept for backward compatibility
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Initialize or re-index a project directory with progress updates.

            Note: include_languages parameter is kept for backward compatibility but not used
            as the indexing engine now auto-detects file types.
            """
            app_ctx = ctx.request_context.lifespan_context
            
            try:
                # Ensure components are initialized before heavy operations
                await ctx.info("Initializing ContextBrain components...")
                await app_ctx.ensure_initialized()
                
                await ctx.info(f"Starting indexing of project: {path}")

                # Create progress callback for detailed updates
                async def progress_callback(message: str):
                    await ctx.info(message)

                # Initialize the heavy embedding model only when needed
                if not app_ctx.indexing_engine.embedding_model:
                    await app_ctx.indexing_engine.initialize(progress_callback=progress_callback)

                # Use timeout protection for the indexing operation
                result = await asyncio.wait_for(
                    app_ctx.indexing_engine.index_project(
                        Path(path),
                        exclude_patterns=exclude_patterns or [],
                        progress_callback=progress_callback
                    ),
                    timeout=300.0  # 5 minute timeout
                )
                
                await ctx.info("Indexing completed successfully!")
                await ctx.info(f"Statistics: {result.statistics}")
                return result.model_dump()
                
            except asyncio.TimeoutError:
                await ctx.info("Indexing operation timed out after 5 minutes")
                return {
                    "status": "timeout",
                    "message": "Indexing operation timed out but may have partially completed",
                    "statistics": {"total_files": 0, "total_elements": 0}
                }
            except Exception as e:
                await ctx.info(f"Indexing failed: {str(e)}")
                return {
                    "status": "error", 
                    "message": f"Indexing failed: {str(e)}",
                    "statistics": {"total_files": 0, "total_elements": 0}
                }
        
        @self.mcp.tool()
        async def search_semantic(
            query: str,
            similarity_threshold: float = 0.3,
            max_results: int = 10,
            ctx: Context = None
        ) -> QueryResult:
            """Semantic search across project content."""
            app_ctx = ctx.request_context.lifespan_context
            await app_ctx.ensure_initialized()
            
            await ctx.debug(f"Performing semantic search: {query}")
            
            search_results = await app_ctx.vector_store.search(
                query=query,
                threshold=similarity_threshold,
                limit=max_results
            )
            
            # Extract CodeElement objects from SearchResult objects (Pydantic fix)
            elements = [search_result.element for search_result in search_results]
            
            return QueryResult(
                elements=elements,
                confidence=0.9,
                explanation=f"Found {len(search_results)} semantically similar results",
                sources=[],
                related_queries=[],
                context_suggestions=[]
            )
        
        @self.mcp.tool()
        async def search_structural(
            element_type: str,
            name_pattern: str,
            scope: Optional[str] = None,
            ctx: Context = None
        ) -> List[CodeElement]:
            """Search by code structure (classes, functions, modules)."""
            app_ctx = ctx.request_context.lifespan_context
            await app_ctx.ensure_initialized()
            
            await ctx.debug(f"Structural search: {element_type} matching {name_pattern}")
            
            return await app_ctx.structured_index.search_structural(
                element_type=element_type,
                name_pattern=name_pattern,
                scope=scope
            )
        
        @self.mcp.tool()
        async def analyze_dependencies(
            target_file: str,
            depth: int = 2,
            include_external: bool = False,
            ctx: Context = None
        ) -> DependencyAnalysis:
            """Analyze dependencies for a specific file or module."""
            app_ctx = ctx.request_context.lifespan_context
            await app_ctx.ensure_initialized()
            
            await ctx.debug(f"Analyzing dependencies for: {target_file}")
            
            return await app_ctx.indexing_engine.analyze_dependencies(
                target_file=target_file,
                depth=depth,
                include_external=include_external
            )

        @self.mcp.tool()
        async def clean_database_entries(
            project_path: str,
            confirm: bool = False,
            dry_run: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Clean all database entries for a specific project path.

            Args:
                project_path: Path to the project to clean
                confirm: Must be True to actually perform the cleanup
                dry_run: If True, only shows what would be cleaned without doing it

            Returns:
                Dictionary with cleanup results and statistics
            """
            app_ctx = ctx.request_context.lifespan_context
            await app_ctx.ensure_initialized()

            await ctx.debug(f"Clean database request: {project_path} (dry_run={dry_run}, confirm={confirm})")

            try:
                from pathlib import Path

                target_path = Path(project_path).resolve()
                target_path_str = str(target_path)

                # Safety check
                if not confirm and not dry_run:
                    return {
                        "error": "cleanup_not_confirmed",
                        "message": "Set confirm=True to actually perform cleanup, or use dry_run=True to preview",
                        "project_path": target_path_str,
                        "elements_found": 0,
                        "files_affected": []
                    }

                # Count elements to be cleaned
                cursor = app_ctx.structured_index.connection.cursor()

                # Find elements for this project
                cursor.execute("""
                    SELECT file_path, COUNT(*) as count
                    FROM elements
                    WHERE file_path LIKE ? OR file_path LIKE ?
                    GROUP BY file_path
                    ORDER BY file_path
                """, (f"{target_path_str}%", f"%{target_path.name}%"))

                file_stats = cursor.fetchall()

                # Get total count
                cursor.execute("""
                    SELECT COUNT(*) as total
                    FROM elements
                    WHERE file_path LIKE ? OR file_path LIKE ?
                """, (f"{target_path_str}%", f"%{target_path.name}%"))

                total_elements = cursor.fetchone()["total"]

                files_affected = [{"file_path": row["file_path"], "elements": row["count"]} for row in file_stats]

                result = {
                    "project_path": target_path_str,
                    "dry_run": dry_run,
                    "confirmed": confirm,
                    "elements_found": total_elements,
                    "files_affected": files_affected,
                    "files_count": len(files_affected)
                }

                if dry_run:
                    result["message"] = f"DRY RUN: Would clean {total_elements} elements from {len(files_affected)} files"
                    result["action"] = "preview_only"
                elif confirm:
                    # Perform actual cleanup
                    cleaned_count = await app_ctx.indexing_engine.clear_project_data(target_path)

                    result["elements_cleaned"] = cleaned_count
                    result["message"] = f"Successfully cleaned {cleaned_count} elements from project"
                    result["action"] = "cleanup_completed"
                else:
                    result["message"] = "Set confirm=True to perform cleanup"
                    result["action"] = "confirmation_required"

                return result

            except Exception as e:
                await ctx.error(f"Database cleanup failed: {e}")
                return {
                    "error": "cleanup_failed",
                    "message": str(e),
                    "project_path": project_path,
                    "elements_found": 0,
                    "files_affected": []
                }

        @self.mcp.tool()
        async def get_context_for_file(
            file_path: str,
            context_size: int = 5,
            include_dependencies: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get relevant context for a specific file."""
            app_ctx = ctx.request_context.lifespan_context
            await app_ctx.ensure_initialized()
            
            await ctx.debug(f"Getting context for file: {file_path}")
            
            return await app_ctx.indexing_engine.get_file_context(
                file_path=file_path,
                context_size=context_size,
                include_dependencies=include_dependencies
            )

        @self.mcp.tool()
        async def clean_database_entries(
            project_path: str = ".",
            confirm: bool = False,
            dry_run: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Clean all indexed data for a specific project path.

            Args:
                project_path: Path to the project to clean (default: current directory)
                confirm: Set to True to actually perform the cleanup (safety measure)
                dry_run: If True, only reports what would be cleaned without actually doing it

            Returns:
                Dictionary with cleanup results and statistics
            """
            app_ctx = ctx.request_context.lifespan_context
            await app_ctx.ensure_initialized()

            try:
                from pathlib import Path

                project_path_obj = Path(project_path).resolve()

                await ctx.debug(f"Clean database request: {project_path_obj}, confirm={confirm}, dry_run={dry_run}")

                if not confirm and not dry_run:
                    return {
                        "status": "error",
                        "message": "Must set confirm=True to perform actual cleanup, or use dry_run=True to preview",
                        "elements_removed": 0,
                        "files_affected": 0
                    }

                # Get current statistics before cleanup
                cursor = app_ctx.structured_index.connection.cursor()

                # Count elements that would be affected
                cursor.execute("SELECT COUNT(*) as count FROM elements")
                total_elements_before = cursor.fetchone()["count"]

                cursor.execute("SELECT COUNT(DISTINCT file_path) as count FROM elements")
                total_files_before = cursor.fetchone()["count"]

                if dry_run:
                    await ctx.info(f"DRY RUN: Would clean {total_elements_before} elements from {total_files_before} files")
                    return {
                        "status": "dry_run",
                        "message": f"Would clean all indexed data for project: {project_path_obj}",
                        "elements_to_remove": total_elements_before,
                        "files_to_affect": total_files_before,
                        "project_path": str(project_path_obj)
                    }

                # Perform actual cleanup
                await ctx.info(f"Cleaning database entries for project: {project_path_obj}")

                # Clean structured index
                cursor.execute("DELETE FROM elements")
                elements_removed = cursor.rowcount
                app_ctx.structured_index.connection.commit()

                # Clean vector store using the efficient clear_collection method
                try:
                    cleared_count = await app_ctx.vector_store.clear_collection()
                    vector_cleaned = True
                    await ctx.info(f"Vector store cleaned successfully - cleared {cleared_count} elements")
                except Exception as e:
                    await ctx.warning(f"Vector store cleanup warning: {e}")
                    vector_cleaned = False

                # Get statistics after cleanup
                cursor.execute("SELECT COUNT(*) as count FROM elements")
                total_elements_after = cursor.fetchone()["count"]

                await ctx.info(f"Cleanup completed: {elements_removed} elements removed")

                return {
                    "status": "success",
                    "message": f"Successfully cleaned database entries for project: {project_path_obj}",
                    "elements_removed": elements_removed,
                    "files_affected": total_files_before,
                    "elements_before": total_elements_before,
                    "elements_after": total_elements_after,
                    "vector_store_cleaned": vector_cleaned,
                    "project_path": str(project_path_obj)
                }

            except Exception as e:
                logger.error(f"Error cleaning database entries: {e}")
                await ctx.error(f"Database cleanup failed: {e}")
                return {
                    "status": "error",
                    "message": f"Error cleaning database: {str(e)}",
                    "elements_removed": 0,
                    "files_affected": 0
                }

        @self.mcp.tool()
        async def get_architecture_overview(
            focus_area: Optional[str] = None,
            detail_level: str = "medium",
            ctx: Context = None
        ) -> ArchitectureOverview:
            """Get an overview of the project architecture."""
            app_ctx = ctx.request_context.lifespan_context
            await app_ctx.ensure_initialized()
            
            await ctx.debug(f"Generating architecture overview: {focus_area}")
            
            return await app_ctx.indexing_engine.get_architecture_overview(
                focus_area=focus_area,
                detail_level=detail_level
            )
    
    def _setup_prompts(self):
        """Setup MCP prompts for common development tasks."""
        
        @self.mcp.prompt()
        async def code_review_context(
            file_path: str,
            ctx: Context = None
        ) -> PromptMessage:
            """Generate context for code review."""
            app_ctx = ctx.request_context.lifespan_context
            await app_ctx.ensure_initialized()
            
            context = await app_ctx.indexing_engine.get_file_context(
                file_path=file_path,
                context_size=10,
                include_dependencies=True
            )
            
            return PromptMessage(
                role="user",
                content=f"Code review context for {file_path}: {context}"
            )
        
        @self.mcp.prompt()
        async def refactoring_suggestions(
            target_element: str,
            ctx: Context = None
        ) -> PromptMessage:
            """Generate refactoring suggestions for a code element."""
            app_ctx = ctx.request_context.lifespan_context
            await app_ctx.ensure_initialized()
            
            # Search for the element
            results = await app_ctx.structured_index.search_structural(
                element_type="function",
                name_pattern=target_element
            )
            
            if results:
                element = results[0]
                return PromptMessage(
                    role="user",
                    content=f"Refactoring suggestions for {element.name}: {element.content}"
                )
            else:
                return PromptMessage(
                    role="user",
                    content=f"Element {target_element} not found"
                )
    
    def run(self, transport: str = "stdio", mount_path: str = None):
        """Run the ContextBrain server."""
        logger.info(f"Starting ContextBrain server with {transport} transport")

        # Map 'http' to 'streamable-http' for backward compatibility
        if transport == "http":
            transport = "streamable-http"

        # Run the server with correct parameters
        if mount_path:
            self.mcp.run(transport=transport, mount_path=mount_path)
        else:
            self.mcp.run(transport=transport)
    
    def get_app(self):
        """Get the FastMCP application for ASGI deployment."""
        return self.mcp
