"""
JavaScript/TypeScript Language Parser for ContextBrain

Parser for JavaScript and TypeScript source code using regex patterns and
simple AST-like analysis for extracting functions, classes, and imports.
"""

import re
import logging
from typing import List, Optional, Dict, Set

from .base import LanguageParser
from ..models import (
    CodeElement,
    ElementType,
    SourceLocation,
    Relationship,
)

logger = logging.getLogger(__name__)


class JavaScriptParser(LanguageParser):
    """
    JavaScript/TypeScript parser using regex patterns.
    
    Features:
    - Function and arrow function extraction
    - Class and method identification
    - Import/export statement parsing
    - Variable and constant detection
    - Basic relationship tracking
    """
    
    def __init__(self):
        """Initialize the JavaScript parser."""
        super().__init__()
        self.language_name = "javascript"
        self.current_file_path = ""
        self.current_content = ""
        self.current_lines = []
    
    async def parse_file(self, content: str, file_path: str) -> List[CodeElement]:
        """
        Parse a JavaScript/TypeScript file and extract code elements.
        
        Args:
            content: JavaScript/TypeScript source code content
            file_path: Path to the source file
            
        Returns:
            List of extracted code elements
        """
        self.current_file_path = file_path
        self.current_content = content
        self.current_lines = content.split('\n')
        
        elements = []
        
        try:
            # Extract different types of elements
            elements.extend(self._extract_imports())
            elements.extend(self._extract_exports())
            elements.extend(self._extract_classes())
            elements.extend(self._extract_functions())
            elements.extend(self._extract_variables())
            
            logger.debug(f"Extracted {len(elements)} elements from {file_path}")
            
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
        
        return elements
    
    def _extract_imports(self) -> List[CodeElement]:
        """Extract import statements."""
        elements = []
        
        # Patterns for different import styles
        patterns = [
            r'import\s+(.+?)\s+from\s+[\'"](.+?)[\'"]',  # import x from 'module'
            r'import\s+[\'"](.+?)[\'"]',  # import 'module'
            r'const\s+(.+?)\s*=\s*require\([\'"](.+?)[\'"]\)',  # const x = require('module')
            r'import\s*\(\s*[\'"](.+?)[\'"]\s*\)',  # dynamic import()
        ]
        
        for i, line in enumerate(self.current_lines):
            line = line.strip()
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    if len(match.groups()) == 2:
                        imported_name = match.group(1).strip()
                        module_name = match.group(2).strip()
                        import_text = f"import {imported_name} from '{module_name}'"
                    else:
                        module_name = match.group(1).strip()
                        import_text = f"import '{module_name}'"
                    
                    location = SourceLocation(
                        line_start=i + 1,
                        line_end=i + 1,
                        column_start=0,
                        column_end=len(line),
                    )
                    
                    element = self.create_element(
                        element_type=ElementType.IMPORT,
                        name=import_text,
                        file_path=self.current_file_path,
                        location=location,
                        content=line,
                    )
                    elements.append(element)
                    break
        
        return elements
    
    def _extract_exports(self) -> List[CodeElement]:
        """Extract export statements."""
        elements = []
        
        patterns = [
            r'export\s+default\s+(.+)',  # export default
            r'export\s+\{(.+?)\}',  # export { x, y }
            r'export\s+(const|let|var|function|class)\s+(\w+)',  # export const/function/class
        ]
        
        for i, line in enumerate(self.current_lines):
            line = line.strip()
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    if 'default' in pattern:
                        export_name = f"default export: {match.group(1).strip()}"
                    elif '{' in pattern:
                        export_name = f"export {{{match.group(1).strip()}}}"
                    else:
                        export_name = f"export {match.group(1)} {match.group(2)}"
                    
                    location = SourceLocation(
                        line_start=i + 1,
                        line_end=i + 1,
                        column_start=0,
                        column_end=len(line),
                    )
                    
                    element = self.create_element(
                        element_type=ElementType.IMPORT,  # Using IMPORT type for exports too
                        name=export_name,
                        file_path=self.current_file_path,
                        location=location,
                        content=line,
                    )
                    elements.append(element)
                    break
        
        return elements
    
    def _extract_classes(self) -> List[CodeElement]:
        """Extract class definitions."""
        elements = []
        
        # Pattern for class declarations
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{'
        
        for i, line in enumerate(self.current_lines):
            match = re.search(class_pattern, line)
            if match:
                class_name = match.group(1)
                extends_class = match.group(2) if match.group(2) else None
                
                # Find the end of the class (simplified - just find matching brace)
                end_line = self._find_block_end(i, '{', '}')
                
                location = SourceLocation(
                    line_start=i + 1,
                    line_end=end_line + 1,
                    column_start=0,
                    column_end=len(self.current_lines[end_line]) if end_line < len(self.current_lines) else 0,
                )
                
                content = '\n'.join(self.current_lines[i:end_line + 1])
                
                # Calculate complexity (number of methods)
                method_count = len(re.findall(r'\b\w+\s*\([^)]*\)\s*\{', content))
                complexity = max(1, method_count)
                
                element = self.create_element(
                    element_type=ElementType.CLASS,
                    name=class_name,
                    file_path=self.current_file_path,
                    location=location,
                    content=content,
                    complexity=complexity,
                )
                
                # Add inheritance relationship
                if extends_class:
                    relationship = self.create_relationship(
                        target_id=f"class:{extends_class}",
                        relationship_type="inherits",
                        strength=0.9
                    )
                    element.relationships.append(relationship)
                
                elements.append(element)
        
        return elements
    
    def _extract_functions(self) -> List[CodeElement]:
        """Extract function definitions."""
        elements = []
        
        # Patterns for different function styles
        patterns = [
            r'function\s+(\w+)\s*\([^)]*\)\s*\{',  # function name() {}
            r'(\w+)\s*:\s*function\s*\([^)]*\)\s*\{',  # name: function() {}
            r'(\w+)\s*:\s*\([^)]*\)\s*=>\s*\{',  # name: () => {}
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*\{',  # const name = () => {}
            r'(\w+)\s*\([^)]*\)\s*\{',  # method() {} (in class)
        ]
        
        for i, line in enumerate(self.current_lines):
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    function_name = match.group(1)
                    
                    # Skip if this looks like a class declaration
                    if 'class' in line:
                        continue
                    
                    # Find the end of the function
                    end_line = self._find_block_end(i, '{', '}')
                    
                    location = SourceLocation(
                        line_start=i + 1,
                        line_end=end_line + 1,
                        column_start=0,
                        column_end=len(self.current_lines[end_line]) if end_line < len(self.current_lines) else 0,
                    )
                    
                    content = '\n'.join(self.current_lines[i:end_line + 1])
                    
                    # Calculate complexity
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
    
    def _extract_variables(self) -> List[CodeElement]:
        """Extract variable declarations."""
        elements = []
        
        # Patterns for variable declarations
        patterns = [
            r'const\s+([A-Z_][A-Z0-9_]*)\s*=',  # const CONSTANT = (constants)
            r'(const|let|var)\s+(\w+)\s*=',  # const/let/var name =
        ]
        
        for i, line in enumerate(self.current_lines):
            line = line.strip()
            
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    if len(match.groups()) == 1:
                        # Constant pattern
                        var_name = match.group(1)
                        element_type = ElementType.CONSTANT
                    else:
                        # Regular variable pattern
                        var_name = match.group(2)
                        # Determine if it's a constant based on naming convention
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
    
    def _find_block_end(self, start_line: int, open_char: str, close_char: str) -> int:
        """Find the end of a code block."""
        brace_count = 0
        found_open = False
        
        for i in range(start_line, len(self.current_lines)):
            line = self.current_lines[i]
            
            for char in line:
                if char == open_char:
                    brace_count += 1
                    found_open = True
                elif char == close_char:
                    brace_count -= 1
                    
                    if found_open and brace_count == 0:
                        return i
        
        # If we can't find the end, return a reasonable default
        return min(start_line + 10, len(self.current_lines) - 1)
    
    def calculate_complexity(self, content: str) -> int:
        """Calculate cyclomatic complexity for JavaScript."""
        complexity_keywords = [
            r'\bif\b', r'\belse\b', r'\bfor\b', r'\bwhile\b', r'\bdo\b',
            r'\bswitch\b', r'\bcase\b', r'\btry\b', r'\bcatch\b',
            r'\b\?\s*:', r'\b&&\b', r'\b\|\|\b'  # ternary, logical operators
        ]
        
        complexity = 1  # Base complexity
        
        for pattern in complexity_keywords:
            matches = re.findall(pattern, content, re.IGNORECASE)
            complexity += len(matches)
        
        return complexity
    
    def get_language_keywords(self) -> List[str]:
        """Get JavaScript language keywords."""
        return [
            'break', 'case', 'catch', 'class', 'const', 'continue', 'debugger',
            'default', 'delete', 'do', 'else', 'export', 'extends', 'finally',
            'for', 'function', 'if', 'import', 'in', 'instanceof', 'let', 'new',
            'return', 'super', 'switch', 'this', 'throw', 'try', 'typeof', 'var',
            'void', 'while', 'with', 'yield', 'async', 'await', 'of'
        ]
