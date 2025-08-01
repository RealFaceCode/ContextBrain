"""
Tests for StructuredIndex.
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import os
from pathlib import Path

from contextbrain.storage.structured_index import StructuredIndex
from contextbrain.models import (
    CodeElement, ElementType, SourceLocation, ElementMetadata
)


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest_asyncio.fixture
async def temp_db(temp_db_path):
    """Create a temporary database for testing."""
    # Create and initialize the index
    index = StructuredIndex(temp_db_path)
    await index.initialize()

    yield index

    # Cleanup
    await index.close()


@pytest.fixture
def sample_element():
    """Create a sample CodeElement for testing."""
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
        dependencies=["import_module"]
    )


@pytest.fixture
def sample_elements():
    """Create multiple sample CodeElements for testing."""
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
        metadata=metadata1
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
        metadata=metadata2
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
        metadata=metadata3
    ))
    
    return elements


class TestStructuredIndex:
    """Test StructuredIndex functionality."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test that StructuredIndex initializes correctly."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            index = StructuredIndex(db_path)
            await index.initialize()
            
            # Check that connection is established
            assert index.connection is not None
            
            # Check that tables exist
            cursor = index.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            assert "elements" in tables
            assert "dependencies" in tables
            
            await index.close()
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_store_single_element(self, temp_db, sample_element):
        """Test storing a single element."""
        await temp_db.store_elements([sample_element])
        
        # Verify element was stored
        cursor = temp_db.connection.cursor()
        cursor.execute("SELECT * FROM elements WHERE id = ?", (sample_element.id,))
        row = cursor.fetchone()
        
        assert row is not None
        assert row["id"] == sample_element.id
        assert row["type"] == sample_element.type.value
        assert row["name"] == sample_element.name
        assert row["content"] == sample_element.content
        assert row["file_path"] == sample_element.file_path
        assert row["language"] == sample_element.metadata.language
    
    @pytest.mark.asyncio
    async def test_store_multiple_elements(self, temp_db, sample_elements):
        """Test storing multiple elements."""
        await temp_db.store_elements(sample_elements)
        
        # Verify all elements were stored
        cursor = temp_db.connection.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM elements")
        count = cursor.fetchone()["count"]
        
        assert count == len(sample_elements)
        
        # Verify specific elements
        for element in sample_elements:
            cursor.execute("SELECT * FROM elements WHERE id = ?", (element.id,))
            row = cursor.fetchone()
            assert row is not None
            assert row["name"] == element.name
    
    @pytest.mark.asyncio
    async def test_store_dependencies(self, temp_db, sample_element):
        """Test storing element dependencies."""
        await temp_db.store_elements([sample_element])
        
        # Verify dependencies were stored
        cursor = temp_db.connection.cursor()
        cursor.execute("SELECT * FROM dependencies WHERE source_element_id = ?", (sample_element.id,))
        rows = cursor.fetchall()
        
        assert len(rows) == len(sample_element.dependencies)
        assert rows[0]["target_element_id"] == sample_element.dependencies[0]
        assert rows[0]["dependency_type"] == "import"
    
    @pytest.mark.asyncio
    async def test_search_structural_by_type(self, temp_db, sample_elements):
        """Test structural search by element type."""
        await temp_db.store_elements(sample_elements)
        
        # Search for functions
        results = await temp_db.search_structural("function", "*")
        function_results = [r for r in results if r.type == ElementType.FUNCTION]
        assert len(function_results) == 1
        assert function_results[0].name == "calculate_sum"
        
        # Search for classes
        results = await temp_db.search_structural("class", "*")
        class_results = [r for r in results if r.type == ElementType.CLASS]
        assert len(class_results) == 1
        assert class_results[0].name == "Calculator"
    
    @pytest.mark.asyncio
    async def test_search_structural_by_name_pattern(self, temp_db, sample_elements):
        """Test structural search by name pattern."""
        await temp_db.store_elements(sample_elements)
        
        # Search with exact name
        results = await temp_db.search_structural("function", "calculate_sum")
        assert len(results) == 1
        assert results[0].name == "calculate_sum"
        
        # Search with wildcard
        results = await temp_db.search_structural("function", "calc*")
        assert len(results) == 1
        assert results[0].name == "calculate_sum"
        
        # Search with partial match (should add % automatically)
        results = await temp_db.search_structural("function", "calc")
        assert len(results) == 1
        assert results[0].name == "calculate_sum"
    
    @pytest.mark.asyncio
    async def test_search_structural_with_scope(self, temp_db, sample_elements):
        """Test structural search with file scope."""
        await temp_db.store_elements(sample_elements)
        
        # Search in specific file
        results = await temp_db.search_structural("method", "*", scope="calculator.py")
        assert len(results) == 1
        assert results[0].name == "add"
        assert "calculator.py" in results[0].file_path
        
        # Search in non-existent file
        results = await temp_db.search_structural("method", "*", scope="nonexistent.py")
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_search_structural_empty_results(self, temp_db, sample_elements):
        """Test structural search with no matching results."""
        await temp_db.store_elements(sample_elements)
        
        # Search for non-existent type
        results = await temp_db.search_structural("variable", "*")
        assert len(results) == 0
        
        # Search for non-existent name
        results = await temp_db.search_structural("function", "nonexistent_function")
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_get_stats(self, temp_db, sample_elements):
        """Test getting index statistics."""
        # Test empty stats
        stats = await temp_db.get_stats()
        assert stats["total_elements"] == 0
        
        # Store elements and test stats
        await temp_db.store_elements(sample_elements)
        stats = await temp_db.get_stats()
        
        assert stats["total_elements"] == len(sample_elements)
        assert "by_type" in stats
        assert "by_language" in stats
        
        # Check type counts
        assert stats["by_type"]["function"] == 1
        assert stats["by_type"]["class"] == 1
        assert stats["by_type"]["method"] == 1
        
        # Check language counts
        assert stats["by_language"]["python"] == len(sample_elements)
    
    @pytest.mark.asyncio
    async def test_upsert_behavior(self, temp_db, sample_element):
        """Test that storing the same element twice updates rather than duplicates."""
        # Store element first time
        await temp_db.store_elements([sample_element])
        
        # Modify element and store again
        sample_element.content = "def test_function():\n    return 'updated'"
        await temp_db.store_elements([sample_element])
        
        # Verify only one element exists with updated content
        cursor = temp_db.connection.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM elements WHERE id = ?", (sample_element.id,))
        count = cursor.fetchone()["count"]
        assert count == 1
        
        cursor.execute("SELECT content FROM elements WHERE id = ?", (sample_element.id,))
        content = cursor.fetchone()["content"]
        assert "updated" in content
    
    @pytest.mark.asyncio
    async def test_close(self, temp_db):
        """Test closing the index."""
        assert temp_db.connection is not None
        await temp_db.close()
        assert temp_db.connection is None
    
    @pytest.mark.asyncio
    async def test_search_without_connection(self):
        """Test search behavior when connection is not established."""
        index = StructuredIndex(":memory:")
        # Don't initialize - connection should be None
        
        results = await index.search_structural("function", "*")
        assert results == []
    
    @pytest.mark.asyncio
    async def test_stats_without_connection(self):
        """Test stats behavior when connection is not established."""
        index = StructuredIndex(":memory:")
        # Don't initialize - connection should be None
        
        stats = await index.get_stats()
        assert stats == {"total_elements": 0}
