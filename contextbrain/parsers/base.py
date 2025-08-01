"""
Base Language Parser for ContextBrain

Abstract base class for language-specific parsers that extract code elements
and relationships from source files.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..models import (
    CodeElement,
    ElementType,
    SourceLocation,
    ElementMetadata,
)

logger = logging.getLogger(__name__)


class LanguageParser(ABC):
    """
    Abstract base class for language-specific parsers.
    
    Each parser implementation should:
    1. Parse source code using appropriate tools (Tree-sitter, AST, etc.)
    2. Extract code elements (functions, classes, variables, etc.)
    3. Identify relationships between elements
    4. Generate semantic metadata
    """
    
    def __init__(self):
        """Initialize the parser."""
        self.language_name = "unknown"
    
    @abstractmethod
    async def parse_file(self, content: str, file_path: str) -> List[CodeElement]:
        """
        Parse a source file and extract code elements.
        
        Args:
            content: Source code content
            file_path: Path to the source file
            
        Returns:
            List of extracted code elements
        """
        pass
    
    def generate_element_id(self, element_name: str, file_path: str, line_start: int) -> str:
        """
        Generate a unique ID for a code element.
        
        Args:
            element_name: Name of the element
            file_path: File path containing the element
            line_start: Starting line number
            
        Returns:
            Unique element ID
        """
        id_string = f"{file_path}:{element_name}:{line_start}"
        return hashlib.md5(id_string.encode()).hexdigest()
    
    def create_element(
        self,
        element_type: ElementType,
        name: str,
        file_path: str,
        location: SourceLocation,
        content: str,
        complexity: Optional[int] = None,
        relationships: Optional[List[str]] = None
    ) -> CodeElement:
        """
        Create a CodeElement with standard metadata.
        
        Args:
            element_type: Type of the code element
            name: Name of the element
            file_path: File path containing the element
            location: Source location information
            content: Source code content
            complexity: Cyclomatic complexity (if available)
            relationships: List of relationships to other elements
            
        Returns:
            CodeElement instance
        """
        element_id = self.generate_element_id(name, file_path, location.line_start)
        
        metadata = ElementMetadata(
            language=self.language_name,
            complexity=complexity,
            lines_of_code=location.line_end - location.line_start + 1,
            last_modified=datetime.now(),
            tags=[],
        )
        
        return CodeElement(
            id=element_id,
            type=element_type,
            name=name,
            file_path=file_path,
            location=location,
            content=content,
            embedding=[],  # Will be populated by indexing engine
            relationships=relationships or [],
            metadata=metadata,
        )
    
    def extract_imports(self, content: str) -> List[str]:
        """
        Extract import statements from source code.
        
        Args:
            content: Source code content
            
        Returns:
            List of imported modules/packages
        """
        # Default implementation - should be overridden by specific parsers
        imports = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                imports.append(line)
        
        return imports
    
    def calculate_complexity(self, content: str) -> int:
        """
        Calculate cyclomatic complexity of code.
        
        Args:
            content: Source code content
            
        Returns:
            Cyclomatic complexity score
        """
        # Simple complexity calculation based on control flow keywords
        complexity_keywords = [
            'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally',
            'switch', 'case', 'catch', 'do', 'break', 'continue', 'return'
        ]
        
        complexity = 1  # Base complexity
        words = content.lower().split()
        
        for word in words:
            if word in complexity_keywords:
                complexity += 1
        
        return complexity
    
    def extract_comments(self, content: str) -> List[str]:
        """
        Extract comments from source code.
        
        Args:
            content: Source code content
            
        Returns:
            List of comment strings
        """
        # Default implementation - should be overridden by specific parsers
        comments = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('#') or line.startswith('//'):
                comments.append(line)
        
        return comments
    
    def find_function_calls(self, content: str) -> List[str]:
        """
        Find function calls in the code.
        
        Args:
            content: Source code content
            
        Returns:
            List of function names being called
        """
        # Simple pattern matching - should be improved with proper parsing
        import re
        
        # Pattern to match function calls: word followed by opening parenthesis
        pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, content)
        
        # Filter out common keywords that aren't function calls
        keywords = {'if', 'for', 'while', 'with', 'try', 'except', 'class', 'def'}
        function_calls = [match for match in matches if match not in keywords]
        
        return list(set(function_calls))  # Remove duplicates
    
    def create_relationship_id(
        self,
        target_id: str,
        relationship_type: str,
        strength: float = 1.0
    ) -> str:
        """
        Create a relationship identifier to another code element.

        Args:
            target_id: ID of the target element
            relationship_type: Type of relationship (calls, imports, extends, etc.)
            strength: Strength of the relationship (0.0-1.0)

        Returns:
            Relationship identifier string
        """
        return f"{relationship_type}:{target_id}:{strength}"
    
    def get_language_keywords(self) -> List[str]:
        """
        Get language-specific keywords.
        
        Returns:
            List of language keywords
        """
        # Default empty list - should be overridden by specific parsers
        return []
    
    def is_test_file(self, file_path: str) -> bool:
        """
        Check if a file is a test file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file appears to be a test file
        """
        test_indicators = ['test_', '_test', 'tests/', '/test/', 'spec_', '_spec']
        file_lower = file_path.lower()
        
        return any(indicator in file_lower for indicator in test_indicators)
    
    def get_element_signature(self, element: CodeElement) -> str:
        """
        Generate a signature string for an element.
        
        Args:
            element: Code element
            
        Returns:
            Signature string
        """
        if element.type == ElementType.FUNCTION:
            # Extract function signature from content
            lines = element.content.split('\n')
            if lines:
                return lines[0].strip()
        elif element.type == ElementType.CLASS:
            # Extract class declaration
            lines = element.content.split('\n')
            if lines:
                return lines[0].strip()
        
        return f"{element.type.value} {element.name}"
