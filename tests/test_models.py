"""
Tests for ContextBrain models.
"""

import pytest
from pydantic import ValidationError
from contextbrain.models import (
    ElementType, SourceLocation, ElementMetadata, CodeElement,
    SearchResult, QueryResult, ProjectStatistics, ProjectIndex,
    DependencyAnalysis, ArchitectureOverview, IndexConfiguration
)


class TestElementType:
    """Test ElementType enum."""
    
    def test_element_type_values(self):
        """Test that all element types have correct values."""
        assert ElementType.FUNCTION.value == "function"
        assert ElementType.CLASS.value == "class"
        assert ElementType.METHOD.value == "method"
        assert ElementType.VARIABLE.value == "variable"
        assert ElementType.IMPORT.value == "import"
        assert ElementType.MODULE.value == "module"
        assert ElementType.COMMENT.value == "comment"
        assert ElementType.DOCSTRING.value == "docstring"


class TestSourceLocation:
    """Test SourceLocation model."""
    
    def test_source_location_creation(self):
        """Test creating a SourceLocation."""
        location = SourceLocation(line_start=1, line_end=10)
        assert location.line_start == 1
        assert location.line_end == 10
        assert location.column_start == 0  # default value
        assert location.column_end == 0    # default value
    
    def test_source_location_with_columns(self):
        """Test creating a SourceLocation with columns."""
        location = SourceLocation(
            line_start=1, line_end=10,
            column_start=5, column_end=15
        )
        assert location.line_start == 1
        assert location.line_end == 10
        assert location.column_start == 5
        assert location.column_end == 15
    
    def test_source_location_validation(self):
        """Test SourceLocation validation."""
        with pytest.raises(ValidationError):
            SourceLocation()  # Missing required fields


class TestElementMetadata:
    """Test ElementMetadata model."""
    
    def test_element_metadata_minimal(self):
        """Test creating ElementMetadata with minimal data."""
        metadata = ElementMetadata(language="python")
        assert metadata.language == "python"
        assert metadata.complexity is None
        assert metadata.lines_of_code is None
        assert metadata.author is None
        assert metadata.last_modified is None
    
    def test_element_metadata_full(self):
        """Test creating ElementMetadata with all fields."""
        metadata = ElementMetadata(
            language="python",
            complexity=5,
            lines_of_code=20,
            author="test_user",
            last_modified="2023-01-01"
        )
        assert metadata.language == "python"
        assert metadata.complexity == 5
        assert metadata.lines_of_code == 20
        assert metadata.author == "test_user"
        assert metadata.last_modified == "2023-01-01"


class TestCodeElement:
    """Test CodeElement model."""
    
    def test_code_element_creation(self):
        """Test creating a CodeElement."""
        location = SourceLocation(line_start=1, line_end=10)
        metadata = ElementMetadata(language="python")
        
        element = CodeElement(
            id="test_id",
            type=ElementType.FUNCTION,
            name="test_function",
            content="def test_function(): pass",
            file_path="/test/file.py",
            location=location,
            metadata=metadata
        )
        
        assert element.id == "test_id"
        assert element.type == ElementType.FUNCTION
        assert element.name == "test_function"
        assert element.content == "def test_function(): pass"
        assert element.file_path == "/test/file.py"
        assert element.location == location
        assert element.metadata == metadata
        assert element.embedding is None
        assert element.dependencies == []
        assert element.relationships == {}
    
    def test_code_element_with_optional_fields(self):
        """Test creating a CodeElement with optional fields."""
        location = SourceLocation(line_start=1, line_end=10)
        metadata = ElementMetadata(language="python")
        
        element = CodeElement(
            id="test_id",
            type=ElementType.FUNCTION,
            name="test_function",
            content="def test_function(): pass",
            file_path="/test/file.py",
            location=location,
            metadata=metadata,
            embedding=[0.1, 0.2, 0.3],
            dependencies=["dep1", "dep2"],
            relationships={"calls": ["func1", "func2"]}
        )
        
        assert element.embedding == [0.1, 0.2, 0.3]
        assert element.dependencies == ["dep1", "dep2"]
        assert element.relationships == {"calls": ["func1", "func2"]}


class TestSearchResult:
    """Test SearchResult model."""
    
    def test_search_result_creation(self):
        """Test creating a SearchResult."""
        location = SourceLocation(line_start=1, line_end=10)
        metadata = ElementMetadata(language="python")
        element = CodeElement(
            id="test_id",
            type=ElementType.FUNCTION,
            name="test_function",
            content="def test_function(): pass",
            file_path="/test/file.py",
            location=location,
            metadata=metadata
        )
        
        result = SearchResult(element=element, score=0.85)
        assert result.element == element
        assert result.score == 0.85
        assert result.snippet == ""
        assert result.context == {}
    
    def test_search_result_with_optional_fields(self):
        """Test creating a SearchResult with optional fields."""
        location = SourceLocation(line_start=1, line_end=10)
        metadata = ElementMetadata(language="python")
        element = CodeElement(
            id="test_id",
            type=ElementType.FUNCTION,
            name="test_function",
            content="def test_function(): pass",
            file_path="/test/file.py",
            location=location,
            metadata=metadata
        )
        
        result = SearchResult(
            element=element,
            score=0.85,
            snippet="def test_function():",
            context={"file": "test.py"}
        )
        assert result.snippet == "def test_function():"
        assert result.context == {"file": "test.py"}


class TestQueryResult:
    """Test QueryResult model."""
    
    def test_query_result_creation(self):
        """Test creating a QueryResult."""
        location = SourceLocation(line_start=1, line_end=10)
        metadata = ElementMetadata(language="python")
        element = CodeElement(
            id="test_id",
            type=ElementType.FUNCTION,
            name="test_function",
            content="def test_function(): pass",
            file_path="/test/file.py",
            location=location,
            metadata=metadata
        )
        
        result = QueryResult(
            elements=[element],
            confidence=0.9,
            explanation="Found matching function"
        )
        
        assert len(result.elements) == 1
        assert result.elements[0] == element
        assert result.confidence == 0.9
        assert result.explanation == "Found matching function"
        assert result.sources == []
        assert result.related_queries == []
        assert result.context_suggestions == []


class TestProjectStatistics:
    """Test ProjectStatistics model."""
    
    def test_project_statistics_defaults(self):
        """Test ProjectStatistics with default values."""
        stats = ProjectStatistics()
        assert stats.total_files == 0
        assert stats.total_elements == 0
        assert stats.languages == []
        assert stats.processing_time == 0.0
    
    def test_project_statistics_with_data(self):
        """Test ProjectStatistics with data."""
        stats = ProjectStatistics(
            total_files=10,
            total_elements=100,
            languages=["python", "javascript"],
            processing_time=5.5
        )
        assert stats.total_files == 10
        assert stats.total_elements == 100
        assert stats.languages == ["python", "javascript"]
        assert stats.processing_time == 5.5


class TestProjectIndex:
    """Test ProjectIndex model."""
    
    def test_project_index_creation(self):
        """Test creating a ProjectIndex."""
        stats = ProjectStatistics(total_files=10, total_elements=100)
        index = ProjectIndex(
            project_path="/test/project",
            statistics=stats,
            created_at="2023-01-01T00:00:00",
            updated_at="2023-01-01T00:00:00"
        )
        
        assert index.project_path == "/test/project"
        assert index.statistics == stats
        assert index.created_at == "2023-01-01T00:00:00"
        assert index.updated_at == "2023-01-01T00:00:00"
        assert index.version == "1.0.0"  # default value


class TestDependencyAnalysis:
    """Test DependencyAnalysis model."""
    
    def test_dependency_analysis_creation(self):
        """Test creating a DependencyAnalysis."""
        analysis = DependencyAnalysis(target="test_function")
        assert analysis.target == "test_function"
        assert analysis.dependencies == []
        assert analysis.dependents == []
        assert analysis.depth == 1
        assert analysis.external_dependencies == []
    
    def test_dependency_analysis_with_data(self):
        """Test creating a DependencyAnalysis with data."""
        analysis = DependencyAnalysis(
            target="test_function",
            dependencies=["dep1", "dep2"],
            dependents=["user1", "user2"],
            depth=2,
            external_dependencies=["numpy", "pandas"]
        )
        assert analysis.target == "test_function"
        assert analysis.dependencies == ["dep1", "dep2"]
        assert analysis.dependents == ["user1", "user2"]
        assert analysis.depth == 2
        assert analysis.external_dependencies == ["numpy", "pandas"]


class TestArchitectureOverview:
    """Test ArchitectureOverview model."""
    
    def test_architecture_overview_defaults(self):
        """Test ArchitectureOverview with default values."""
        overview = ArchitectureOverview()
        assert overview.modules == []
        assert overview.key_components == []
        assert overview.relationships == {}
        assert overview.complexity_metrics == {}
    
    def test_architecture_overview_with_data(self):
        """Test ArchitectureOverview with data."""
        overview = ArchitectureOverview(
            modules=["module1", "module2"],
            key_components=["component1", "component2"],
            relationships={"module1": ["component1"]},
            complexity_metrics={"cyclomatic": 5}
        )
        assert overview.modules == ["module1", "module2"]
        assert overview.key_components == ["component1", "component2"]
        assert overview.relationships == {"module1": ["component1"]}
        assert overview.complexity_metrics == {"cyclomatic": 5}


class TestIndexConfiguration:
    """Test IndexConfiguration model."""
    
    def test_index_configuration_defaults(self):
        """Test IndexConfiguration with default values."""
        config = IndexConfiguration()
        assert config.use_default_exclusions is True
        assert config.exclusion_verbosity == "info"
        assert config.enable_dependency_scanning is True
        assert config.show_progress_bars is True
        assert config.verbose_output is False
        assert config.embedding_batch_size == 32
    
    def test_index_configuration_custom(self):
        """Test IndexConfiguration with custom values."""
        config = IndexConfiguration(
            use_default_exclusions=False,
            exclusion_verbosity="debug",
            enable_dependency_scanning=False,
            show_progress_bars=False,
            verbose_output=True,
            embedding_batch_size=64
        )
        assert config.use_default_exclusions is False
        assert config.exclusion_verbosity == "debug"
        assert config.enable_dependency_scanning is False
        assert config.show_progress_bars is False
        assert config.verbose_output is True
        assert config.embedding_batch_size == 64
