"""
Generic Language Parser for ContextBrain

Fallback parser for languages without specialized implementations.
Uses simple pattern matching and heuristics to extract basic code elements.
"""

import re
import logging
from typing import List, Optional, Dict, Set

from .base import LanguageParser
from ..models import (
    CodeElement,
    ElementType,
    SourceLocation,
)

logger = logging.getLogger(__name__)


class GenericParser(LanguageParser):
    """
    Generic parser for languages without specialized implementations.
    
    Features:
    - Basic function detection using common patterns
    - Simple class/struct identification
    - Comment extraction
    - Import/include statement detection
    - Variable assignment recognition
    """
    
    def __init__(self):
        """Initialize the generic parser."""
        super().__init__()
        self.language_name = "generic"
        self.current_file_path = ""
        self.current_content = ""
        self.current_lines = []
    
    async def parse_file(self, content: str, file_path: str) -> List[CodeElement]:
        """
        Parse a source file using generic patterns.
        
        Args:
            content: Source code content
            file_path: Path to the source file
            
        Returns:
            List of extracted code elements
        """
        self.current_file_path = file_path
        self.current_content = content
        self.current_lines = content.split('\n')
        
        # Determine language from file extension
        self._detect_language(file_path)
        
        elements = []
        
        try:
            # Extract different types of elements using generic patterns
            elements.extend(self._extract_imports())
            elements.extend(self._extract_functions())
            elements.extend(self._extract_classes())
            elements.extend(self._extract_variables())
            elements.extend(self._extract_comments())
            
            logger.debug(f"Extracted {len(elements)} elements from {file_path}")
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
        
        return elements
    
    def _detect_language(self, file_path: str):
        """Detect language from file extension."""
        extension_map = {
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sh': 'bash',
            '.sql': 'sql',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.md': 'markdown',
            '.rst': 'rst',
        }
        
        for ext, lang in extension_map.items():
            if file_path.lower().endswith(ext):
                self.language_name = lang
                break
    
    def _extract_imports(self) -> List[CodeElement]:
        """Extract import/include statements using generic patterns."""
        elements = []
        
        # Common import/include patterns across languages
        patterns = [
            r'#include\s*[<"]([^>"]+)[>"]',  # C/C++ includes
            r'import\s+([^;]+);?',  # Java/Scala imports
            r'using\s+([^;]+);',  # C# using
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',  # Various require statements
            r'from\s+(\S+)\s+import',  # Python-style imports
            r'@import\s+[\'"]([^\'"]+)[\'"]',  # CSS/SCSS imports
        ]
        
        for i, line in enumerate(self.current_lines):
            line = line.strip()
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    import_name = match.group(1).strip()
                    
                    location = SourceLocation(
                        line_start=i + 1,
                        line_end=i + 1,
                        column_start=0,
                        column_end=len(line),
                    )
                    
                    element = self.create_element(
                        element_type=ElementType.IMPORT,
                        name=import_name,
                        file_path=self.current_file_path,
                        location=location,
                        content=line,
                    )
                    elements.append(element)
                    break
        
        return elements
    
    def _extract_functions(self) -> List[CodeElement]:
        """Extract function definitions using generic patterns."""
        elements = []
        
        # Common function patterns across languages
        patterns = [
            r'(?:public|private|protected|static)?\s*(?:\w+\s+)?(\w+)\s*\([^)]*\)\s*\{',  # Java/C#/C++ style
            r'def\s+(\w+)\s*\([^)]*\):',  # Python style
            r'function\s+(\w+)\s*\([^)]*\)',  # JavaScript style
            r'fn\s+(\w+)\s*\([^)]*\)',  # Rust style
            r'func\s+(\w+)\s*\([^)]*\)',  # Go style
            r'(\w+)\s*::\s*(\w+)\s*\([^)]*\)',  # C++ method
        ]
        
        for i, line in enumerate(self.current_lines):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('//') or line.startswith('#'):
                continue
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    # Get the function name (last group in match)
                    function_name = match.groups()[-1]
                    
                    # Skip common keywords that might match
                    if function_name.lower() in ['if', 'for', 'while', 'class', 'struct']:
                        continue
                    
                    # Find approximate end of function
                    end_line = self._find_function_end(i)
                    
                    location = SourceLocation(
                        line_start=i + 1,
                        line_end=end_line + 1,
                        column_start=0,
                        column_end=len(self.current_lines[end_line]) if end_line < len(self.current_lines) else 0,
                    )
                    
                    content = '\n'.join(self.current_lines[i:end_line + 1])
                    complexity = self.calculate_complexity(content)
                    
                    element = self.create_element(
                        element_type=ElementType.FUNCTION,
                        name=function_name,
                        file_path=self.current_file_path,
                        location=location,
                        content=content,
                        complexity=complexity,
                    )
                    
                    elements.append(element)
                    break
        
        return elements
    
    def _extract_classes(self) -> List[CodeElement]:
        """Extract class/struct definitions using generic patterns."""
        elements = []
        
        # Common class/struct patterns
        patterns = [
            r'class\s+(\w+)(?:\s*:\s*[\w\s,]+)?\s*\{',  # C++/C#/Java class
            r'struct\s+(\w+)\s*\{',  # C/C++ struct
            r'interface\s+(\w+)\s*\{',  # Interface
            r'enum\s+(\w+)\s*\{',  # Enum
            r'type\s+(\w+)\s+struct\s*\{',  # Go struct
        ]
        
        for i, line in enumerate(self.current_lines):
            line = line.strip()
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    class_name = match.group(1)
                    
                    # Find end of class/struct
                    end_line = self._find_block_end(i)
                    
                    location = SourceLocation(
                        line_start=i + 1,
                        line_end=end_line + 1,
                        column_start=0,
                        column_end=len(self.current_lines[end_line]) if end_line < len(self.current_lines) else 0,
                    )
                    
                    content = '\n'.join(self.current_lines[i:end_line + 1])
                    
                    # Estimate complexity based on number of methods/fields
                    method_count = len(re.findall(r'\w+\s*\([^)]*\)\s*[{;]', content))
                    complexity = max(1, method_count)
                    
                    element = self.create_element(
                        element_type=ElementType.CLASS,
                        name=class_name,
                        file_path=self.current_file_path,
                        location=location,
                        content=content,
                        complexity=complexity,
                    )
                    
                    elements.append(element)
                    break
        
        return elements
    
    def _extract_variables(self) -> List[CodeElement]:
        """Extract variable declarations using generic patterns."""
        elements = []
        
        # Common variable patterns
        patterns = [
            r'(?:const|final|static)\s+(?:\w+\s+)?([A-Z_][A-Z0-9_]*)\s*[=;]',  # Constants
            r'(?:var|let|const)\s+(\w+)\s*=',  # JavaScript-style
            r'(?:int|string|bool|float|double)\s+(\w+)\s*[=;]',  # C-style
            r'(\w+)\s*:=\s*',  # Go-style
            r'let\s+(\w+)\s*[=:]',  # Rust/Swift style
        ]
        
        for i, line in enumerate(self.current_lines):
            line = line.strip()
            
            # Skip comments
            if line.startswith('//') or line.startswith('#'):
                continue
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    var_name = match.group(1)
                    
                    # Determine if it's a constant
                    element_type = ElementType.CONSTANT if var_name.isupper() else ElementType.VARIABLE
                    
                    location = SourceLocation(
                        line_start=i + 1,
                        line_end=i + 1,
                        column_start=0,
                        column_end=len(line),
                    )
                    
                    element = self.create_element(
                        element_type=element_type,
                        name=var_name,
                        file_path=self.current_file_path,
                        location=location,
                        content=line,
                    )
                    
                    elements.append(element)
                    break
        
        return elements
    
    def _extract_comments(self) -> List[CodeElement]:
        """Extract significant comments (documentation, etc.)."""
        elements = []
        
        # Look for documentation comments
        doc_patterns = [
            r'/\*\*(.*?)\*/',  # /** ... */ (JavaDoc style)
            r'///\s*(.*)',  # /// (C# XML docs)
            r'##\s*(.*)',  # ## (some documentation styles)
        ]
        
        for i, line in enumerate(self.current_lines):
            line = line.strip()
            
            for pattern in doc_patterns:
                match = re.search(pattern, line, re.DOTALL)
                if match:
                    comment_text = match.group(1).strip()
                    
                    # Only include substantial comments
                    if len(comment_text) > 20:
                        location = SourceLocation(
                            line_start=i + 1,
                            line_end=i + 1,
                            column_start=0,
                            column_end=len(line),
                        )
                        
                        element = self.create_element(
                            element_type=ElementType.COMMENT,
                            name=f"Documentation comment",
                            file_path=self.current_file_path,
                            location=location,
                            content=comment_text,
                        )
                        
                        elements.append(element)
                        break
        
        return elements
    
    def _find_function_end(self, start_line: int) -> int:
        """Find the approximate end of a function."""
        brace_count = 0
        found_open_brace = False
        
        for i in range(start_line, len(self.current_lines)):
            line = self.current_lines[i]
            
            # Count braces
            for char in line:
                if char == '{':
                    brace_count += 1
                    found_open_brace = True
                elif char == '}':
                    brace_count -= 1
                    
                    if found_open_brace and brace_count == 0:
                        return i
        
        # Fallback: return a reasonable number of lines
        return min(start_line + 20, len(self.current_lines) - 1)
    
    def _find_block_end(self, start_line: int) -> int:
        """Find the end of a code block (class, struct, etc.)."""
        return self._find_function_end(start_line)
