# ContextBrain Test Suite

This directory contains comprehensive unit tests for the ContextBrain project, covering all major components and functionality.

## Test Structure

### Core Components Tested

1. **`test_models.py`** - Data Models and Validation
   - Tests all Pydantic models used throughout the system
   - Validates data structures, default values, and field validation
   - Covers: `CodeElement`, `SearchResult`, `QueryResult`, `ProjectIndex`, etc.

2. **`test_structured_index.py`** - SQLite-based Structured Index
   - Tests relational database operations for code elements
   - Validates search functionality, data storage, and retrieval
   - Covers: element storage, structural search, statistics, upsert behavior

3. **`test_vector_store.py`** - ChromaDB-based Vector Store
   - Tests semantic search capabilities using embeddings
   - Validates vector storage, similarity search, and collection management
   - Covers: element storage with embeddings, search with thresholds, batching

4. **`test_indexing.py`** - Code Indexing Engine
   - Tests code parsing, analysis, and embedding generation
   - Uses mocked ML dependencies to avoid heavy library imports
   - Covers: initialization, file parsing, embedding generation, element storage

5. **`test_server.py`** - MCP Server and Application Context
   - Tests server initialization and lifecycle management
   - Validates lazy initialization and component coordination
   - Covers: server setup, context management, cleanup procedures

## Running Tests

### Quick Test Run
```bash
python -m pytest tests/ -v
```

### Run Specific Test Module
```bash
python -m pytest tests/test_models.py -v
```

### Run with Coverage (if installed)
```bash
python -m pytest tests/ --cov=contextbrain --cov-report=html
```

### Use the Test Runner Script
```bash
python run_tests.py
```

## Test Configuration

- **pytest.ini**: Configuration file with test discovery settings
- **Async Testing**: Uses `pytest-asyncio` for async fixture and test support
- **Mocking**: Heavy ML dependencies (sentence-transformers, torch, tensorflow) are mocked to avoid import issues

## Key Testing Patterns

### Async Fixtures
```python
@pytest_asyncio.fixture
async def temp_db():
    # Setup async resource
    yield resource
    # Cleanup
```

### Mocking Heavy Dependencies
```python
with patch.dict('sys.modules', {
    'sentence_transformers': Mock(),
    'transformers': Mock(),
    'torch': Mock(),
}):
    from contextbrain.indexing import IndexingEngine
```

### Temporary Resources
- Database files are created in temporary locations
- ChromaDB collections use temporary directories
- Proper cleanup ensures no test pollution

## Test Coverage

The test suite covers:

- ✅ **Data Models**: All Pydantic models and validation logic
- ✅ **Database Operations**: SQLite storage, queries, and indexing
- ✅ **Vector Operations**: ChromaDB storage and semantic search
- ✅ **Code Analysis**: File parsing and element extraction (mocked)
- ✅ **Server Lifecycle**: Initialization, context management, cleanup
- ✅ **Error Handling**: Edge cases and failure scenarios
- ✅ **Async Operations**: Proper async/await patterns

## Dependencies

The tests require:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `chromadb` - Vector database (for integration tests)
- Standard library modules for mocking and temporary files

## Notes

- **ML Dependencies**: Heavy ML libraries are mocked to prevent import issues and speed up tests
- **Windows Compatibility**: Special handling for file cleanup on Windows due to ChromaDB file locking
- **Isolation**: Each test uses isolated temporary resources to prevent interference
- **Performance**: Tests are designed to run quickly while maintaining comprehensive coverage

## Troubleshooting

### Common Issues

1. **ChromaDB File Locking on Windows**
   - Tests include retry logic and graceful cleanup handling
   - Temporary directories may not be fully cleaned up immediately

2. **ML Library Import Errors**
   - Heavy dependencies are mocked at the module level
   - If you see import errors, ensure mocking is applied before imports

3. **Async Fixture Issues**
   - Use `pytest_asyncio.fixture` for async fixtures
   - Ensure proper async/await patterns in test functions

### Running Individual Tests

To debug specific functionality:
```bash
# Test just the models
python -m pytest tests/test_models.py::TestCodeElement::test_code_element_creation -v

# Test database operations
python -m pytest tests/test_structured_index.py::TestStructuredIndex::test_store_single_element -v

# Test vector operations
python -m pytest tests/test_vector_store.py::TestVectorStore::test_store_single_element -v
```
