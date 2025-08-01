"""
Data models for ContextBrain.

Defines the core data structures used throughout the system.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ElementType(Enum):
    """Types of code elements that can be indexed."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    IMPORT = "import"
    MODULE = "module"
    COMMENT = "comment"
    DOCSTRING = "docstring"
    # Markdown document elements
    DOCUMENT_HEADING = "document_heading"
    H1 = "h1"
    H2 = "h2"
    H3 = "h3"
    H4 = "h4"
    H5 = "h5"
    H6 = "h6"


class SourceLocation(BaseModel):
    """Location information for a code element."""
    line_start: int
    line_end: int
    column_start: int = 0
    column_end: int = 0


class ElementMetadata(BaseModel):
    """Metadata for a code element."""
    language: str
    complexity: Optional[int] = None
    lines_of_code: Optional[int] = None
    author: Optional[str] = None
    last_modified: Optional[str] = None


class CodeElement(BaseModel):
    """A code element with its metadata and content."""
    id: str
    type: ElementType
    name: str
    content: str
    file_path: str
    location: SourceLocation
    metadata: ElementMetadata
    embedding: Optional[List[float]] = None
    dependencies: List[str] = Field(default_factory=list)
    relationships: Dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    """Result from a search operation."""
    element: CodeElement
    score: float
    snippet: str = ""
    context: Dict[str, Any] = Field(default_factory=dict)


class QueryResult(BaseModel):
    """Result from a query operation."""
    elements: List[CodeElement]
    confidence: float
    explanation: str
    sources: List[str] = Field(default_factory=list)
    related_queries: List[str] = Field(default_factory=list)
    context_suggestions: List[str] = Field(default_factory=list)


class ProjectStatistics(BaseModel):
    """Statistics about a project index."""
    total_files: int = 0
    total_elements: int = 0
    languages: List[str] = Field(default_factory=list)
    processing_time: float = 0.0


class ProjectIndex(BaseModel):
    """Complete project index information."""
    project_path: str
    statistics: ProjectStatistics
    created_at: str
    updated_at: str
    version: str = "1.0.0"


class DependencyAnalysis(BaseModel):
    """Analysis of dependencies for a code element."""
    target: str
    dependencies: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)
    depth: int = 1
    external_dependencies: List[str] = Field(default_factory=list)


class ArchitectureOverview(BaseModel):
    """High-level architecture overview of a project."""
    modules: List[str] = Field(default_factory=list)
    key_components: List[str] = Field(default_factory=list)
    relationships: Dict[str, List[str]] = Field(default_factory=dict)
    complexity_metrics: Dict[str, Any] = Field(default_factory=dict)


class IndexConfiguration(BaseModel):
    """Configuration for indexing operations."""
    use_default_exclusions: bool = True
    exclusion_verbosity: str = "info"
    enable_dependency_scanning: bool = True
    show_progress_bars: bool = True
    verbose_output: bool = False
    embedding_batch_size: int = 32
