"""
Tests for IndexingEngine.
"""

import pytest
import asyncio
import tempfile
import shutil
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Mock heavy dependencies before importing
with patch.dict('sys.modules', {
    'sentence_transformers': Mock(),
    'transformers': Mock(),
    'torch': Mock(),
    'tensorflow': Mock(),
}):
    from contextbrain.indexing import IndexingEngine
    from contextbrain.storage.structured_index import StructuredIndex
    from contextbrain.storage.vector_store import VectorStore
    from contextbrain.models import (
        CodeElement, ElementType, SourceLocation, ElementMetadata,
        IndexConfiguration
    )


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = Mock(spec=VectorStore)
    store.initialize = AsyncMock()
    store.store_elements = AsyncMock()
    store.close = AsyncMock()
    store.get_collection_stats = AsyncMock(return_value={"count": 0})
    store.collection = Mock()
    store.collection.name = "test_collection"
    store.client = Mock()
    store.client.delete_collection = Mock()
    store.client.create_collection = Mock(return_value=store.collection)
    return store


@pytest.fixture
def mock_structured_index():
    """Create a mock structured index."""
    index = Mock(spec=StructuredIndex)
    index.initialize = AsyncMock()
    index.store_elements = AsyncMock()
    index.close = AsyncMock()
    index.get_stats = AsyncMock(return_value={"total_elements": 0})

    # Mock database connection and cursor
    mock_cursor = Mock()
    mock_cursor.fetchone = Mock(return_value={"count": 0})
    mock_cursor.execute = Mock()

    mock_connection = Mock()
    mock_connection.cursor = Mock(return_value=mock_cursor)
    mock_connection.commit = Mock()

    index.connection = mock_connection
    return index


@pytest.fixture
def indexing_engine(mock_vector_store, mock_structured_index):
    """Create an IndexingEngine with mocked dependencies."""
    engine = IndexingEngine(mock_vector_store, mock_structured_index)
    return engine


@pytest.fixture
def sample_python_file():
    """Create a temporary Python file for testing."""
    content = '''"""Sample module for testing."""

def calculate_sum(a, b):
    """Calculate the sum of two numbers."""
    return a + b

class Calculator:
    """A simple calculator class."""
    
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        """Add two numbers."""
        result = a + b
        self.history.append(f"{a} + {b} = {result}")
        return result
'''
    
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False)
    temp_file.write(content)
    temp_file.close()
    
    yield Path(temp_file.name)
    
    # Cleanup
    Path(temp_file.name).unlink()


class TestIndexingEngine:
    """Test IndexingEngine functionality."""
    
    def test_initialization(self, mock_vector_store, mock_structured_index):
        """Test IndexingEngine initialization."""
        engine = IndexingEngine(mock_vector_store, mock_structured_index)
        
        assert engine.vector_store == mock_vector_store
        assert engine.structured_index == mock_structured_index
        assert engine.embedding_model is None
    
    @pytest.mark.asyncio
    @patch('contextbrain.indexing.SENTENCE_TRANSFORMERS_AVAILABLE', True)
    @patch('contextbrain.indexing.SentenceTransformer')
    async def test_initialize_with_embedding_model(self, mock_sentence_transformer, indexing_engine):
        """Test initializing the engine with embedding model."""
        mock_model = Mock()
        mock_sentence_transformer.return_value = mock_model
        
        progress_messages = []
        async def progress_callback(message):
            progress_messages.append(message)
        
        await indexing_engine.initialize(progress_callback)
        
        assert indexing_engine.embedding_model == mock_model
        assert len(progress_messages) > 0
        assert any("Initializing embedding model" in msg for msg in progress_messages)
    
    @pytest.mark.asyncio
    @patch('contextbrain.indexing.SENTENCE_TRANSFORMERS_AVAILABLE', False)
    async def test_initialize_without_sentence_transformers(self, indexing_engine):
        """Test initialization when sentence-transformers is not available."""
        with pytest.raises(ImportError, match="sentence-transformers package not available"):
            await indexing_engine.initialize()
    
    @pytest.mark.asyncio
    async def test_clear_project_data_current_directory(self, indexing_engine):
        """Test clearing project data for current directory."""
        # Mock the cursor to return a count
        mock_cursor = indexing_engine.structured_index.connection.cursor.return_value
        mock_cursor.fetchone.return_value = {"count": 5}
        
        project_path = Path(".")
        cleared_count = await indexing_engine.clear_project_data(project_path)
        
        assert cleared_count == 5
        
        # Verify SQL operations were called
        mock_cursor.execute.assert_any_call("SELECT COUNT(*) as count FROM elements")
        mock_cursor.execute.assert_any_call("DELETE FROM elements")
        indexing_engine.structured_index.connection.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_clear_project_data_specific_directory(self, indexing_engine):
        """Test clearing project data for specific directory."""
        mock_cursor = indexing_engine.structured_index.connection.cursor.return_value
        mock_cursor.fetchone.return_value = {"count": 3}
        
        project_path = Path("test_project")
        cleared_count = await indexing_engine.clear_project_data(project_path)
        
        assert cleared_count == 3
        
        # Verify SQL operations were called with project name
        mock_cursor.execute.assert_any_call(
            "SELECT COUNT(*) as count FROM elements WHERE file_path LIKE ?",
            ("test_project%",)
        )
        mock_cursor.execute.assert_any_call(
            "DELETE FROM elements WHERE file_path LIKE ?",
            ("test_project%",)
        )
    
    @pytest.mark.asyncio
    async def test_parse_python_file(self, indexing_engine, sample_python_file):
        """Test parsing a Python file."""
        # Mock the embedding model
        mock_model = Mock()
        mock_model.encode = Mock(return_value=[[0.1, 0.2, 0.3, 0.4, 0.5]])
        indexing_engine.embedding_model = mock_model
        
        elements = await indexing_engine._parse_python_file(sample_python_file)
        
        # Should find functions, classes, and methods
        assert len(elements) > 0
        
        # Check for specific elements
        element_names = [elem.name for elem in elements]
        assert "calculate_sum" in element_names
        assert "Calculator" in element_names
        assert "add" in element_names
        
        # Check element types
        function_elements = [elem for elem in elements if elem.type == ElementType.FUNCTION]
        class_elements = [elem for elem in elements if elem.type == ElementType.CLASS]
        method_elements = [elem for elem in elements if elem.type == ElementType.METHOD]
        
        assert len(function_elements) >= 1  # calculate_sum
        assert len(class_elements) >= 1     # Calculator
        assert len(method_elements) >= 2    # __init__, add
    
    @pytest.mark.asyncio
    async def test_parse_python_file_without_embedding_model(self, indexing_engine, sample_python_file):
        """Test parsing a Python file without embedding model."""
        # Don't set embedding_model (should be None)
        elements = await indexing_engine._parse_python_file(sample_python_file)
        
        # Should still parse elements but without embeddings
        assert len(elements) > 0
        
        # Check that elements don't have embeddings
        for element in elements:
            assert element.embedding is None
    
    @pytest.mark.asyncio
    async def test_generate_embeddings(self, indexing_engine):
        """Test generating embeddings for elements."""
        # Mock the embedding model
        mock_model = Mock()
        mock_model.encode = Mock(return_value=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        indexing_engine.embedding_model = mock_model
        
        # Create test elements
        location = SourceLocation(line_start=1, line_end=5)
        metadata = ElementMetadata(language="python")
        
        elements = [
            CodeElement(
                id="elem1",
                type=ElementType.FUNCTION,
                name="func1",
                content="def func1(): pass",
                file_path="/test.py",
                location=location,
                metadata=metadata
            ),
            CodeElement(
                id="elem2",
                type=ElementType.FUNCTION,
                name="func2",
                content="def func2(): pass",
                file_path="/test.py",
                location=location,
                metadata=metadata
            )
        ]
        
        await indexing_engine._generate_embeddings(elements)
        
        # Check that embeddings were added
        assert elements[0].embedding == [0.1, 0.2, 0.3]
        assert elements[1].embedding == [0.4, 0.5, 0.6]
        
        # Verify model was called with correct texts
        mock_model.encode.assert_called_once()
        call_args = mock_model.encode.call_args[0][0]
        assert len(call_args) == 2
        assert "func1" in call_args[0]
        assert "func2" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_without_model(self, indexing_engine):
        """Test generating embeddings without embedding model."""
        location = SourceLocation(line_start=1, line_end=5)
        metadata = ElementMetadata(language="python")
        
        elements = [
            CodeElement(
                id="elem1",
                type=ElementType.FUNCTION,
                name="func1",
                content="def func1(): pass",
                file_path="/test.py",
                location=location,
                metadata=metadata
            )
        ]
        
        # Should not raise an error, just skip embedding generation
        await indexing_engine._generate_embeddings(elements)
        
        # Element should still not have embedding
        assert elements[0].embedding is None
    
    @pytest.mark.asyncio
    async def test_store_elements(self, indexing_engine):
        """Test storing elements in both stores."""
        location = SourceLocation(line_start=1, line_end=5)
        metadata = ElementMetadata(language="python")
        
        elements = [
            CodeElement(
                id="elem1",
                type=ElementType.FUNCTION,
                name="func1",
                content="def func1(): pass",
                file_path="/test.py",
                location=location,
                metadata=metadata,
                embedding=[0.1, 0.2, 0.3]
            )
        ]
        
        await indexing_engine._store_elements(elements)
        
        # Verify both stores were called
        indexing_engine.structured_index.store_elements.assert_called_once_with(elements)
        indexing_engine.vector_store.store_elements.assert_called_once_with(elements, batch_size=32)
    
    @pytest.mark.asyncio
    async def test_get_default_exclusions(self, indexing_engine):
        """Test getting default exclusions."""
        exclusions = indexing_engine._get_default_exclusions()
        
        # Should include common patterns
        assert any("__pycache__" in pattern for pattern in exclusions)
        assert any("*.pyc" in pattern for pattern in exclusions)
        assert any(".git" in pattern for pattern in exclusions)
        assert any("node_modules" in pattern for pattern in exclusions)
    
    def test_should_exclude_file(self, indexing_engine):
        """Test file exclusion logic."""
        exclusions = ["*.pyc", "__pycache__", ".git/*"]
        
        # Should exclude
        assert indexing_engine._should_exclude_file(Path("test.pyc"), exclusions)
        assert indexing_engine._should_exclude_file(Path("__pycache__/test.py"), exclusions)
        assert indexing_engine._should_exclude_file(Path(".git/config"), exclusions)
        
        # Should not exclude
        assert not indexing_engine._should_exclude_file(Path("test.py"), exclusions)
        assert not indexing_engine._should_exclude_file(Path("src/main.py"), exclusions)
    
    @pytest.mark.asyncio
    async def test_index_configuration_defaults(self, indexing_engine):
        """Test that IndexConfiguration defaults work correctly."""
        config = IndexConfiguration()
        
        assert config.use_default_exclusions is True
        assert config.exclusion_verbosity == "info"
        assert config.enable_dependency_scanning is True
        assert config.show_progress_bars is True
        assert config.verbose_output is False
        assert config.embedding_batch_size == 32
