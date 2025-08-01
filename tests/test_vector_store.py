"""
Tests for VectorStore.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import shutil
from pathlib import Path

from contextbrain.storage.vector_store import VectorStore
from contextbrain.models import (
    CodeElement, ElementType, SourceLocation, ElementMetadata, SearchResult
)


@pytest_asyncio.fixture
async def temp_vector_store():
    """Create a temporary vector store for testing."""
    temp_dir = tempfile.mkdtemp()

    try:
        store = VectorStore(persist_directory=temp_dir)
        await store.initialize()
        yield store
        await store.close()

        # Give ChromaDB time to release file handles
        await asyncio.sleep(0.1)
    finally:
        # Cleanup - try to remove but don't fail if it doesn't work on Windows
        if Path(temp_dir).exists():
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                # On Windows, ChromaDB might still have file handles open
                pass


@pytest.fixture
def sample_element_with_embedding():
    """Create a sample CodeElement with embedding for testing."""
    location = SourceLocation(line_start=1, line_end=10)
    metadata = ElementMetadata(
        language="python",
        complexity=3,
        lines_of_code=10,
        author="test_user"
    )
    
    return CodeElement(
        id="test_function_1",
        type=ElementType.FUNCTION,
        name="test_function",
        content="def test_function():\n    pass",
        file_path="/test/file.py",
        location=location,
        metadata=metadata,
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5]  # Simple 5-dimensional embedding
    )


@pytest.fixture
def sample_elements_with_embeddings():
    """Create multiple sample CodeElements with embeddings for testing."""
    elements = []
    
    # Function element
    location1 = SourceLocation(line_start=1, line_end=10)
    metadata1 = ElementMetadata(language="python", complexity=3)
    elements.append(CodeElement(
        id="func_1",
        type=ElementType.FUNCTION,
        name="calculate_sum",
        content="def calculate_sum(a, b):\n    return a + b",
        file_path="/test/math.py",
        location=location1,
        metadata=metadata1,
        embedding=[0.1, 0.2, 0.3, 0.4, 0.5]
    ))
    
    # Class element
    location2 = SourceLocation(line_start=15, line_end=30)
    metadata2 = ElementMetadata(language="python", complexity=5)
    elements.append(CodeElement(
        id="class_1",
        type=ElementType.CLASS,
        name="Calculator",
        content="class Calculator:\n    def add(self, a, b):\n        return a + b",
        file_path="/test/calculator.py",
        location=location2,
        metadata=metadata2,
        embedding=[0.2, 0.3, 0.4, 0.5, 0.6]
    ))
    
    # Method element
    location3 = SourceLocation(line_start=20, line_end=25)
    metadata3 = ElementMetadata(language="python", complexity=2)
    elements.append(CodeElement(
        id="method_1",
        type=ElementType.METHOD,
        name="add",
        content="def add(self, a, b):\n    return a + b",
        file_path="/test/calculator.py",
        location=location3,
        metadata=metadata3,
        embedding=[0.3, 0.4, 0.5, 0.6, 0.7]
    ))
    
    return elements


class TestVectorStore:
    """Test VectorStore functionality."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test that VectorStore initializes correctly."""
        temp_dir = tempfile.mkdtemp()

        try:
            store = VectorStore(persist_directory=temp_dir)
            await store.initialize()

            # Check that client and collection are created
            assert store.client is not None
            assert store.collection is not None
            assert store.collection.name == "contextbrain_elements"

            await store.close()

            # Give ChromaDB time to release file handles
            await asyncio.sleep(0.1)

        finally:
            # Try to cleanup, but don't fail if it doesn't work on Windows
            if Path(temp_dir).exists():
                try:
                    shutil.rmtree(temp_dir)
                except PermissionError:
                    # On Windows, ChromaDB might still have file handles open
                    pass
    
    @pytest.mark.asyncio
    async def test_store_single_element(self, temp_vector_store, sample_element_with_embedding):
        """Test storing a single element with embedding."""
        await temp_vector_store.store_elements([sample_element_with_embedding])
        
        # Verify element was stored by checking collection count
        stats = await temp_vector_store.get_collection_stats()
        assert stats["count"] == 1
    
    @pytest.mark.asyncio
    async def test_store_multiple_elements(self, temp_vector_store, sample_elements_with_embeddings):
        """Test storing multiple elements with embeddings."""
        await temp_vector_store.store_elements(sample_elements_with_embeddings)
        
        # Verify all elements were stored
        stats = await temp_vector_store.get_collection_stats()
        assert stats["count"] == len(sample_elements_with_embeddings)
    
    @pytest.mark.asyncio
    async def test_store_element_without_embedding(self, temp_vector_store):
        """Test storing element without embedding (should be skipped)."""
        location = SourceLocation(line_start=1, line_end=10)
        metadata = ElementMetadata(language="python")
        
        element_without_embedding = CodeElement(
            id="no_embedding",
            type=ElementType.FUNCTION,
            name="test_function",
            content="def test_function(): pass",
            file_path="/test/file.py",
            location=location,
            metadata=metadata
            # No embedding provided
        )
        
        await temp_vector_store.store_elements([element_without_embedding])
        
        # Should not be stored
        stats = await temp_vector_store.get_collection_stats()
        assert stats["count"] == 0
    
    @pytest.mark.asyncio
    async def test_store_elements_batching(self, temp_vector_store):
        """Test that elements are stored in batches."""
        # Create many elements to test batching
        elements = []
        for i in range(5):  # Small number for testing
            location = SourceLocation(line_start=i, line_end=i+5)
            metadata = ElementMetadata(language="python")
            
            element = CodeElement(
                id=f"element_{i}",
                type=ElementType.FUNCTION,
                name=f"function_{i}",
                content=f"def function_{i}(): pass",
                file_path=f"/test/file_{i}.py",
                location=location,
                metadata=metadata,
                embedding=[0.1 * i, 0.2 * i, 0.3 * i, 0.4 * i, 0.5 * i]
            )
            elements.append(element)
        
        # Store with small batch size
        await temp_vector_store.store_elements(elements, batch_size=2)
        
        # Verify all elements were stored
        stats = await temp_vector_store.get_collection_stats()
        assert stats["count"] == len(elements)
    
    @pytest.mark.asyncio
    async def test_search_basic(self, temp_vector_store, sample_elements_with_embeddings):
        """Test basic search functionality."""
        await temp_vector_store.store_elements(sample_elements_with_embeddings)
        
        # Search for similar content
        results = await temp_vector_store.search("calculate sum function", threshold=0.0, limit=5)
        
        # Should return results
        assert len(results) > 0
        assert all(isinstance(result, SearchResult) for result in results)
        
        # Check that results have proper structure
        for result in results:
            assert hasattr(result, 'element')
            assert hasattr(result, 'score')
            assert hasattr(result, 'snippet')
            assert 0 <= result.score <= 1
    
    @pytest.mark.asyncio
    async def test_search_with_threshold(self, temp_vector_store, sample_elements_with_embeddings):
        """Test search with score threshold."""
        await temp_vector_store.store_elements(sample_elements_with_embeddings)
        
        # Search with high threshold (should return fewer results)
        high_threshold_results = await temp_vector_store.search(
            "calculate sum function", threshold=0.9, limit=5
        )
        
        # Search with low threshold (should return more results)
        low_threshold_results = await temp_vector_store.search(
            "calculate sum function", threshold=0.1, limit=5
        )
        
        # Low threshold should return same or more results
        assert len(low_threshold_results) >= len(high_threshold_results)
        
        # All results should meet threshold
        for result in high_threshold_results:
            assert result.score >= 0.9
        
        for result in low_threshold_results:
            assert result.score >= 0.1
    
    @pytest.mark.asyncio
    async def test_search_limit(self, temp_vector_store, sample_elements_with_embeddings):
        """Test search result limit."""
        await temp_vector_store.store_elements(sample_elements_with_embeddings)
        
        # Search with limit of 1
        results = await temp_vector_store.search("function", threshold=0.0, limit=1)
        assert len(results) <= 1
        
        # Search with limit of 2
        results = await temp_vector_store.search("function", threshold=0.0, limit=2)
        assert len(results) <= 2
    
    @pytest.mark.asyncio
    async def test_search_empty_collection(self, temp_vector_store):
        """Test search on empty collection."""
        results = await temp_vector_store.search("test query", threshold=0.0, limit=5)
        assert results == []
    
    @pytest.mark.asyncio
    async def test_search_without_collection(self):
        """Test search behavior when collection is not initialized."""
        store = VectorStore()
        # Don't initialize - collection should be None
        
        results = await store.search("test query", threshold=0.0, limit=5)
        assert results == []
    
    @pytest.mark.asyncio
    async def test_get_collection_stats(self, temp_vector_store, sample_elements_with_embeddings):
        """Test getting collection statistics."""
        # Test empty collection stats
        stats = await temp_vector_store.get_collection_stats()
        assert stats["count"] == 0
        assert stats["name"] == "contextbrain_elements"
        
        # Store elements and test stats
        await temp_vector_store.store_elements(sample_elements_with_embeddings)
        stats = await temp_vector_store.get_collection_stats()
        
        assert stats["count"] == len(sample_elements_with_embeddings)
        assert stats["name"] == "contextbrain_elements"
    
    @pytest.mark.asyncio
    async def test_get_collection_stats_without_collection(self):
        """Test stats behavior when collection is not initialized."""
        store = VectorStore()
        # Don't initialize - collection should be None
        
        stats = await store.get_collection_stats()
        assert stats == {"count": 0, "name": "none"}
    
    @pytest.mark.asyncio
    async def test_upsert_behavior(self, temp_vector_store, sample_element_with_embedding):
        """Test that storing the same element twice updates rather than duplicates."""
        # Store element first time
        await temp_vector_store.store_elements([sample_element_with_embedding])
        
        # Modify element and store again
        sample_element_with_embedding.content = "def test_function():\n    return 'updated'"
        sample_element_with_embedding.embedding = [0.2, 0.3, 0.4, 0.5, 0.6]  # Different embedding
        await temp_vector_store.store_elements([sample_element_with_embedding])
        
        # Verify only one element exists
        stats = await temp_vector_store.get_collection_stats()
        assert stats["count"] == 1
        
        # Verify content was updated by searching
        results = await temp_vector_store.search("updated", threshold=0.0, limit=1)
        assert len(results) == 1
        assert "updated" in results[0].element.content
    
    @pytest.mark.asyncio
    async def test_close(self, temp_vector_store):
        """Test closing the vector store."""
        assert temp_vector_store.client is not None
        assert temp_vector_store.collection is not None
        
        await temp_vector_store.close()
        
        assert temp_vector_store.client is None
        assert temp_vector_store.collection is None
    
    @pytest.mark.asyncio
    async def test_score_calculation(self, temp_vector_store, sample_elements_with_embeddings):
        """Test that similarity scores are calculated correctly."""
        await temp_vector_store.store_elements(sample_elements_with_embeddings)
        
        results = await temp_vector_store.search("function", threshold=0.0, limit=5)
        
        # All scores should be between 0 and 1
        for result in results:
            assert 0 <= result.score <= 1
        
        # Results should be ordered by score (highest first)
        scores = [result.score for result in results]
        assert scores == sorted(scores, reverse=True)
    
    @pytest.mark.asyncio
    async def test_snippet_generation(self, temp_vector_store, sample_elements_with_embeddings):
        """Test that snippets are generated correctly."""
        await temp_vector_store.store_elements(sample_elements_with_embeddings)
        
        results = await temp_vector_store.search("function", threshold=0.0, limit=5)
        
        for result in results:
            # Snippet should not be empty
            assert result.snippet != ""
            
            # Snippet should be truncated if content is long
            if len(result.element.content) > 200:
                assert result.snippet.endswith("...")
                assert len(result.snippet) <= 203  # 200 + "..."
            else:
                assert result.snippet == result.element.content
