# Contributing to ContextBrain

Thank you for your interest in contributing to ContextBrain! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Virtual environment tool (venv, conda, etc.)

### Development Setup

1. **Fork and clone the repository:**
```bash
git clone https://github.com/your-username/contextbrain.git
cd contextbrain
```

2. **Create a development environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies
```

3. **Run tests to ensure everything works:**
```bash
python simple_test.py
python demo.py
```

## 🎯 How to Contribute

### Reporting Issues

Before creating an issue, please:

1. **Search existing issues** to avoid duplicates
2. **Use the issue templates** when available
3. **Provide detailed information** including:
   - Python version
   - Operating system
   - Steps to reproduce
   - Expected vs actual behavior
   - Error messages and stack traces

### Suggesting Features

We welcome feature suggestions! Please:

1. **Check the roadmap** in the README
2. **Open a feature request** with:
   - Clear description of the feature
   - Use cases and benefits
   - Possible implementation approach
   - Any relevant examples or references

### Code Contributions

#### Types of Contributions

- **Bug fixes**: Fix existing issues
- **New features**: Implement new functionality
- **Language parsers**: Add support for new programming languages
- **Documentation**: Improve docs, examples, and guides
- **Tests**: Add or improve test coverage
- **Performance**: Optimize existing code

#### Development Workflow

1. **Create a feature branch:**
```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes:**
   - Follow the coding standards (see below)
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes:**
```bash
python simple_test.py
pytest test_contextbrain.py -v
python demo.py
```

4. **Commit your changes:**
```bash
git add .
git commit -m "feat: add support for Go language parsing"
```

5. **Push and create a pull request:**
```bash
git push origin feature/your-feature-name
```

## 📝 Coding Standards

### Python Style Guide

We follow PEP 8 with some modifications:

- **Line length**: 100 characters (not 79)
- **Imports**: Use absolute imports, group by standard/third-party/local
- **Type hints**: Required for all public functions and methods
- **Docstrings**: Google-style docstrings for all public APIs

### Code Structure

```python
"""
Module docstring explaining the purpose.
"""

import asyncio
import logging
from typing import List, Optional

from third_party_package import SomeClass

from .local_module import LocalClass

logger = logging.getLogger(__name__)


class ExampleClass:
    """
    Class docstring explaining the purpose and usage.
    
    Attributes:
        attribute_name: Description of the attribute.
    """
    
    def __init__(self, param: str):
        """Initialize the class."""
        self.attribute_name = param
    
    async def async_method(self, param: Optional[str] = None) -> List[str]:
        """
        Method docstring explaining purpose, parameters, and return value.
        
        Args:
            param: Optional parameter description.
            
        Returns:
            List of strings representing the result.
            
        Raises:
            ValueError: When param is invalid.
        """
        if param is None:
            raise ValueError("Parameter cannot be None")
        
        return [param]
```

### Testing Guidelines

- **Unit tests**: Test individual functions and methods
- **Integration tests**: Test component interactions
- **End-to-end tests**: Test complete workflows
- **Test naming**: Use descriptive names like `test_parser_extracts_functions_correctly`
- **Test structure**: Arrange, Act, Assert pattern

Example test:

```python
async def test_python_parser_extracts_functions():
    """Test that Python parser correctly extracts function definitions."""
    # Arrange
    parser = PythonParser()
    code = '''
def example_function(param: str) -> str:
    """Example function."""
    return param.upper()
'''
    
    # Act
    elements = await parser.parse_file(code, "test.py")
    
    # Assert
    assert len(elements) == 1
    assert elements[0].type == ElementType.FUNCTION
    assert elements[0].name == "example_function"
```

## 🏗️ Architecture Guidelines

### Adding New Language Parsers

To add support for a new programming language:

1. **Create a new parser class** in `contextbrain/parsers/`:
```python
from .base import LanguageParser
from ..models import CodeElement, ElementType

class NewLanguageParser(LanguageParser):
    def __init__(self):
        super().__init__()
        self.language_name = "newlang"
    
    async def parse_file(self, content: str, file_path: str) -> List[CodeElement]:
        # Implementation here
        pass
```

2. **Register the parser** in `contextbrain/parsers/__init__.py`:
```python
PARSER_REGISTRY = {
    # ... existing parsers
    'newlang': NewLanguageParser,
}
```

3. **Add file extension mapping** in `config.py`:
```python
supported_extensions: Dict[str, str] = {
    # ... existing extensions
    '.newext': 'newlang',
}
```

4. **Add tests** for the new parser
5. **Update documentation** with the new language support

### Adding New MCP Resources/Tools/Prompts

1. **Add to the server class** in `contextbrain/server.py`
2. **Follow the existing patterns** for parameter handling
3. **Add comprehensive docstrings** explaining the functionality
4. **Add tests** for the new functionality
5. **Update the README** with the new capabilities

## 🧪 Testing

### Running Tests

```bash
# Quick functionality test
python simple_test.py

# Full test suite
pytest test_contextbrain.py -v

# Test with coverage
pytest --cov=contextbrain test_contextbrain.py

# Demo test
python demo.py
```

### Writing Tests

- **Test files**: Name test files `test_*.py`
- **Test functions**: Name test functions `test_*`
- **Async tests**: Use `async def` for async functionality
- **Fixtures**: Use pytest fixtures for common setup
- **Mocking**: Mock external dependencies appropriately

## 📚 Documentation

### Documentation Standards

- **README**: Keep the main README up-to-date
- **Docstrings**: Google-style for all public APIs
- **Type hints**: Use comprehensive type annotations
- **Examples**: Include usage examples in docstrings
- **Comments**: Explain complex logic, not obvious code

### Documentation Structure

```
docs/
├── installation.md      # Installation instructions
├── configuration.md     # Configuration reference
├── api.md              # API documentation
├── development.md      # Development guide
├── troubleshooting.md  # Common issues and solutions
└── examples/           # Usage examples
    ├── basic_usage.py
    ├── custom_parser.py
    └── client_integration.py
```

## 🔍 Code Review Process

### Pull Request Guidelines

1. **Clear title and description** explaining the changes
2. **Link to related issues** using keywords like "Fixes #123"
3. **Small, focused changes** are easier to review
4. **Include tests** for new functionality
5. **Update documentation** as needed

### Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass and cover new functionality
- [ ] Documentation is updated
- [ ] No breaking changes (or properly documented)
- [ ] Performance impact is considered
- [ ] Security implications are addressed

## 🚀 Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Release Checklist

1. Update version in `__init__.py`
2. Update CHANGELOG.md
3. Run full test suite
4. Create release tag
5. Update documentation
6. Announce release

## 🤝 Community Guidelines

### Code of Conduct

- **Be respectful** and inclusive
- **Be constructive** in feedback
- **Be patient** with newcomers
- **Be collaborative** and helpful

### Communication

- **GitHub Issues**: Bug reports and feature requests
- **Pull Requests**: Code contributions and discussions
- **Discussions**: General questions and ideas

## 📞 Getting Help

If you need help:

1. **Check the documentation** first
2. **Search existing issues** for similar problems
3. **Create a new issue** with detailed information
4. **Join the discussion** in existing threads

Thank you for contributing to ContextBrain! 🧠✨
