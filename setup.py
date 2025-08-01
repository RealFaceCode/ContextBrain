#!/usr/bin/env python3
"""
Setup script for ContextBrain MCP Server
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# Read requirements
requirements = []
requirements_file = this_directory / "requirements.txt"
if requirements_file.exists():
    requirements = requirements_file.read_text().strip().split('\n')
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith('#')]

setup(
    name="contextbrain",
    version="1.0.0",
    author="ContextBrain Development Team",
    author_email="dev@contextbrain.ai",
    description="MCP Server for intelligent project context management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/contextbrain/contextbrain",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Text Processing :: Indexing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "docs": [
            "mkdocs>=1.4.0",
            "mkdocs-material>=9.0.0",
            "mkdocstrings[python]>=0.20.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "contextbrain=main:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "contextbrain": [
            "py.typed",
        ],
    },
    keywords=[
        "mcp",
        "model-context-protocol", 
        "ai",
        "code-analysis",
        "semantic-search",
        "project-indexing",
        "developer-tools",
        "code-intelligence",
    ],
    project_urls={
        "Bug Reports": "https://github.com/contextbrain/contextbrain/issues",
        "Source": "https://github.com/contextbrain/contextbrain",
        "Documentation": "https://contextbrain.readthedocs.io/",
    },
)
