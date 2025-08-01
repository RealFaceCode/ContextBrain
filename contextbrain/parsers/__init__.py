"""
Language Parsers for ContextBrain

Provides syntax-aware parsing for multiple programming languages using Tree-sitter.
Extracts code elements, relationships, and semantic information.
"""

from .base import LanguageParser
from .python_parser import PythonParser
from .javascript_parser import JavaScriptParser
from .generic_parser import GenericParser

# Registry of available parsers
PARSER_REGISTRY = {
    'python': PythonParser,
    'javascript': JavaScriptParser,
    'typescript': JavaScriptParser,  # TypeScript uses same parser as JavaScript
    'java': GenericParser,
    'cpp': GenericParser,
    'c': GenericParser,
    'csharp': GenericParser,
    'go': GenericParser,
    'rust': GenericParser,
    'php': GenericParser,
    'ruby': GenericParser,
    'swift': GenericParser,
    'kotlin': GenericParser,
    'scala': GenericParser,
    'bash': GenericParser,
    'sql': GenericParser,
    'html': GenericParser,
    'css': GenericParser,
    'json': GenericParser,
    'yaml': GenericParser,
    'xml': GenericParser,
    'markdown': GenericParser,
    'rst': GenericParser,
}


def get_parser_for_language(language: str) -> LanguageParser:
    """
    Get a parser instance for the specified language.
    
    Args:
        language: Programming language name
        
    Returns:
        LanguageParser instance for the language
        
    Raises:
        ValueError: If language is not supported
    """
    if language not in PARSER_REGISTRY:
        raise ValueError(f"Unsupported language: {language}")
    
    parser_class = PARSER_REGISTRY[language]
    return parser_class()


def get_supported_languages() -> list[str]:
    """Get list of supported programming languages."""
    return list(PARSER_REGISTRY.keys())


__all__ = [
    "LanguageParser",
    "PythonParser", 
    "JavaScriptParser",
    "GenericParser",
    "get_parser_for_language",
    "get_supported_languages",
]
