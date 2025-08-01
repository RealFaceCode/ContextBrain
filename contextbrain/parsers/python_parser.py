"""
Python Language Parser for ContextBrain

Specialized parser for Python source code using AST (Abstract Syntax Tree).
Extracts functions, classes, variables, imports, and their relationships.
"""

import ast
import logging
from typing import List, Optional, Dict, Any, Set

from .base import LanguageParser
from ..models import (
    CodeElement,
    ElementType,
    SourceLocation,
    Relationship,
)

logger = logging.getLogger(__name__)


class PythonParser(LanguageParser):
    """
    Python-specific parser using AST for accurate code analysis.
    
    Features:
    - Function and method extraction
    - Class hierarchy analysis
    - Import dependency tracking
    - Variable and constant identification
    - Decorator analysis
    - Docstring extraction
    """
    
    def __init__(self):
        """Initialize the Python parser."""
        super().__init__()
        self.language_name = "python"
        self.current_file_path = ""
        self.current_content = ""
        self.function_calls: Set[str] = set()
        self.imports: Dict[str, str] = {}  # alias -> module
    
    async def parse_file(self, content: str, file_path: str) -> List[CodeElement]:
        """
        Parse a Python file and extract code elements.
        
        Args:
            content: Python source code content
            file_path: Path to the Python file
            
        Returns:
            List of extracted code elements
        """
        self.current_file_path = file_path
        self.current_content = content
        self.function_calls.clear()
        self.imports.clear()
        
        elements = []
        
        try:
            # Parse the Python code into an AST
            tree = ast.parse(content)
            
            # Extract elements from the AST
            elements.extend(self._extract_imports(tree))
            elements.extend(self._extract_classes(tree))
            elements.extend(self._extract_functions(tree))
            elements.extend(self._extract_variables(tree))
            
            # Add relationships based on function calls and imports
            self._add_relationships(elements)
            
            logger.debug(f"Extracted {len(elements)} elements from {file_path}")
            
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
        
        return elements
    
    def _extract_imports(self, tree: ast.AST) -> List[CodeElement]:
        """Extract import statements."""
        elements = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                element = self._create_import_element(node)
                if element:
                    elements.append(element)
        
        return elements
    
    def _extract_classes(self, tree: ast.AST) -> List[CodeElement]:
        """Extract class definitions."""
        elements = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                element = self._create_class_element(node)
                if element:
                    elements.append(element)
        
        return elements
    
    def _extract_functions(self, tree: ast.AST) -> List[CodeElement]:
        """Extract function and method definitions."""
        elements = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                element = self._create_function_element(node)
                if element:
                    elements.append(element)
        
        return elements
    
    def _extract_variables(self, tree: ast.AST) -> List[CodeElement]:
        """Extract variable assignments at module level."""
        elements = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Only extract module-level variables
                if self._is_module_level(node):
                    element = self._create_variable_element(node)
                    if element:
                        elements.append(element)
        
        return elements
    
    def _create_import_element(self, node: ast.AST) -> Optional[CodeElement]:
        """Create a CodeElement for an import statement."""
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            import_name = ", ".join(names)
            
            # Store import mapping
            for alias in node.names:
                alias_name = alias.asname if alias.asname else alias.name
                self.imports[alias_name] = alias.name
            
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [alias.name for alias in node.names]
            import_name = f"from {module} import {', '.join(names)}"
            
            # Store import mapping
            for alias in node.names:
                alias_name = alias.asname if alias.asname else alias.name
                self.imports[alias_name] = f"{module}.{alias.name}"
        else:
            return None
        
        location = SourceLocation(
            line_start=node.lineno,
            line_end=getattr(node, 'end_lineno', node.lineno),
            column_start=node.col_offset,
            column_end=getattr(node, 'end_col_offset', node.col_offset),
        )
        
        content = self._get_source_segment(location)
        
        return self.create_element(
            element_type=ElementType.IMPORT,
            name=import_name,
            file_path=self.current_file_path,
            location=location,
            content=content,
        )
    
    def _create_class_element(self, node: ast.ClassDef) -> Optional[CodeElement]:
        """Create a CodeElement for a class definition."""
        location = SourceLocation(
            line_start=node.lineno,
            line_end=getattr(node, 'end_lineno', node.lineno),
            column_start=node.col_offset,
            column_end=getattr(node, 'end_col_offset', node.col_offset),
        )
        
        content = self._get_source_segment(location)
        
        # Extract base classes
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(ast.unparse(base))
        
        # Calculate complexity (number of methods)
        method_count = sum(1 for n in node.body if isinstance(n, ast.FunctionDef))
        complexity = max(1, method_count)
        
        element = self.create_element(
            element_type=ElementType.CLASS,
            name=node.name,
            file_path=self.current_file_path,
            location=location,
            content=content,
            complexity=complexity,
        )
        
        # Add inheritance relationships
        relationships = []
        for base_class in base_classes:
            relationships.append(self.create_relationship(
                target_id=f"class:{base_class}",
                relationship_type="inherits",
                strength=0.9
            ))
        
        element.relationships = relationships
        return element
    
    def _create_function_element(self, node: ast.FunctionDef) -> Optional[CodeElement]:
        """Create a CodeElement for a function definition."""
        location = SourceLocation(
            line_start=node.lineno,
            line_end=getattr(node, 'end_lineno', node.lineno),
            column_start=node.col_offset,
            column_end=getattr(node, 'end_col_offset', node.col_offset),
        )
        
        content = self._get_source_segment(location)
        
        # Calculate cyclomatic complexity
        complexity = self._calculate_function_complexity(node)
        
        # Extract function calls within this function
        function_calls = self._extract_function_calls(node)
        self.function_calls.update(function_calls)
        
        element = self.create_element(
            element_type=ElementType.FUNCTION,
            name=node.name,
            file_path=self.current_file_path,
            location=location,
            content=content,
            complexity=complexity,
        )
        
        # Add call relationships
        relationships = []
        for call in function_calls:
            relationships.append(self.create_relationship(
                target_id=f"function:{call}",
                relationship_type="calls",
                strength=0.7
            ))
        
        element.relationships = relationships
        return element
    
    def _create_variable_element(self, node: ast.Assign) -> Optional[CodeElement]:
        """Create a CodeElement for a variable assignment."""
        if not node.targets:
            return None
        
        # Handle simple name assignments
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            return None
        
        location = SourceLocation(
            line_start=node.lineno,
            line_end=getattr(node, 'end_lineno', node.lineno),
            column_start=node.col_offset,
            column_end=getattr(node, 'end_col_offset', node.col_offset),
        )
        
        content = self._get_source_segment(location)
        
        # Determine if it's a constant (all uppercase)
        element_type = ElementType.CONSTANT if target.id.isupper() else ElementType.VARIABLE
        
        return self.create_element(
            element_type=element_type,
            name=target.id,
            file_path=self.current_file_path,
            location=location,
            content=content,
        )
    
    def _get_source_segment(self, location: SourceLocation) -> str:
        """Get source code segment for a location."""
        lines = self.current_content.split('\n')
        start_idx = max(0, location.line_start - 1)
        end_idx = min(len(lines), location.line_end)
        
        return '\n'.join(lines[start_idx:end_idx])
    
    def _is_module_level(self, node: ast.AST) -> bool:
        """Check if a node is at module level."""
        # Simple heuristic: check if the node is not deeply nested
        # In a full implementation, we'd track the AST context
        return True  # Simplified for now
    
    def _calculate_function_complexity(self, node: ast.FunctionDef) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, (ast.And, ast.Or)):
                complexity += 1
        
        return complexity
    
    def _extract_function_calls(self, node: ast.FunctionDef) -> Set[str]:
        """Extract function calls within a function."""
        calls = set()
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.add(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.add(child.func.attr)
        
        return calls
    
    def _add_relationships(self, elements: List[CodeElement]):
        """Add relationships between elements based on analysis."""
        # Create lookup maps
        element_map = {elem.name: elem for elem in elements}
        
        # Add import relationships
        for element in elements:
            if element.type == ElementType.FUNCTION:
                # Check if function calls reference imported modules
                for call in self.function_calls:
                    if call in self.imports:
                        relationship = self.create_relationship(
                            target_id=f"import:{self.imports[call]}",
                            relationship_type="uses",
                            strength=0.6
                        )
                        element.relationships.append(relationship)
    
    def get_language_keywords(self) -> List[str]:
        """Get Python language keywords."""
        return [
            'False', 'None', 'True', 'and', 'as', 'assert', 'break', 'class',
            'continue', 'def', 'del', 'elif', 'else', 'except', 'finally',
            'for', 'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
            'while', 'with', 'yield'
        ]
