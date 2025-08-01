"""
Tests for ContextBrain server.
"""

import pytest
import asyncio
import sys
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# Mock heavy dependencies before importing
with patch.dict('sys.modules', {
    'sentence_transformers': Mock(),
    'transformers': Mock(),
    'torch': Mock(),
    'tensorflow': Mock(),
}):
    from contextbrain.server import ContextBrainServer, AppContext
    from contextbrain.indexing import IndexingEngine
    from contextbrain.storage import VectorStore, StructuredIndex
    from contextbrain.monitoring import FileWatcher


class TestAppContext:
    """Test AppContext functionality."""
    
    def test_app_context_initialization(self):
        """Test AppContext initialization."""
        context = AppContext()
        
        assert context.indexing_engine is None
        assert context.vector_store is None
        assert context.structured_index is None
        assert context.file_watcher is None
        assert context._initialized is False
    
    @pytest.mark.asyncio
    @patch('contextbrain.server.VectorStore')
    @patch('contextbrain.server.StructuredIndex')
    @patch('contextbrain.server.IndexingEngine')
    @patch('contextbrain.server.FileWatcher')
    async def test_ensure_initialized(self, mock_file_watcher, mock_indexing_engine, 
                                    mock_structured_index, mock_vector_store):
        """Test lazy initialization of components."""
        # Setup mocks
        mock_vector_store_instance = Mock()
        mock_vector_store_instance.initialize = AsyncMock()
        mock_vector_store.return_value = mock_vector_store_instance
        
        mock_structured_index_instance = Mock()
        mock_structured_index_instance.initialize = AsyncMock()
        mock_structured_index.return_value = mock_structured_index_instance
        
        mock_indexing_engine_instance = Mock()
        mock_indexing_engine.return_value = mock_indexing_engine_instance
        
        mock_file_watcher_instance = Mock()
        mock_file_watcher.return_value = mock_file_watcher_instance
        
        # Test initialization
        context = AppContext()
        await context.ensure_initialized()
        
        # Verify components were created and initialized
        assert context._initialized is True
        assert context.vector_store == mock_vector_store_instance
        assert context.structured_index == mock_structured_index_instance
        assert context.indexing_engine == mock_indexing_engine_instance
        assert context.file_watcher == mock_file_watcher_instance
        
        # Verify initialization methods were called
        mock_vector_store_instance.initialize.assert_called_once()
        mock_structured_index_instance.initialize.assert_called_once()
        
        # Verify constructors were called with correct arguments
        mock_indexing_engine.assert_called_once_with(
            mock_vector_store_instance, mock_structured_index_instance
        )
        mock_file_watcher.assert_called_once_with(mock_indexing_engine_instance)
    
    @pytest.mark.asyncio
    async def test_ensure_initialized_idempotent(self):
        """Test that ensure_initialized can be called multiple times safely."""
        context = AppContext()
        
        with patch('contextbrain.server.VectorStore') as mock_vector_store:
            mock_vector_store_instance = Mock()
            mock_vector_store_instance.initialize = AsyncMock()
            mock_vector_store.return_value = mock_vector_store_instance
            
            with patch('contextbrain.server.StructuredIndex') as mock_structured_index:
                mock_structured_index_instance = Mock()
                mock_structured_index_instance.initialize = AsyncMock()
                mock_structured_index.return_value = mock_structured_index_instance
                
                with patch('contextbrain.server.IndexingEngine') as mock_indexing_engine:
                    mock_indexing_engine_instance = Mock()
                    mock_indexing_engine.return_value = mock_indexing_engine_instance
                    
                    with patch('contextbrain.server.FileWatcher') as mock_file_watcher:
                        mock_file_watcher_instance = Mock()
                        mock_file_watcher.return_value = mock_file_watcher_instance
                        
                        # Call ensure_initialized twice
                        await context.ensure_initialized()
                        await context.ensure_initialized()
                        
                        # Verify components were only created once
                        mock_vector_store.assert_called_once()
                        mock_structured_index.assert_called_once()
                        mock_indexing_engine.assert_called_once()
                        mock_file_watcher.assert_called_once()


class TestContextBrainServer:
    """Test ContextBrainServer functionality."""
    
    @patch('contextbrain.server.FastMCP')
    def test_server_initialization(self, mock_fastmcp):
        """Test ContextBrainServer initialization."""
        mock_mcp_instance = Mock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        server = ContextBrainServer(name="TestServer", host="localhost", port=9000)
        
        assert server.name == "TestServer"
        assert server.mcp == mock_mcp_instance
        
        # Verify FastMCP was called with correct parameters
        mock_fastmcp.assert_called_once_with(
            "TestServer", 
            lifespan=server._app_lifespan,
            host="localhost",
            port=9000
        )
    
    @patch('contextbrain.server.FastMCP')
    def test_server_default_parameters(self, mock_fastmcp):
        """Test ContextBrainServer with default parameters."""
        mock_mcp_instance = Mock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        server = ContextBrainServer()
        
        assert server.name == "ContextBrain"
        
        # Verify FastMCP was called with defaults
        mock_fastmcp.assert_called_once_with(
            "ContextBrain",
            lifespan=server._app_lifespan,
            host="127.0.0.1",
            port=8000
        )
    
    @pytest.mark.asyncio
    @patch('contextbrain.server.FastMCP')
    async def test_app_lifespan_startup_and_shutdown(self, mock_fastmcp):
        """Test application lifespan management."""
        mock_mcp_instance = Mock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        server = ContextBrainServer()
        
        # Mock the components that would be created during initialization
        mock_file_watcher = Mock()
        mock_file_watcher.stop = AsyncMock()
        
        mock_vector_store = Mock()
        mock_vector_store.close = AsyncMock()
        
        mock_structured_index = Mock()
        mock_structured_index.close = AsyncMock()
        
        # Test the lifespan context manager
        async with server._app_lifespan(mock_mcp_instance) as context:
            # Context should be created but not initialized
            assert isinstance(context, AppContext)
            assert context._initialized is False
            
            # Simulate components being initialized
            context.file_watcher = mock_file_watcher
            context.vector_store = mock_vector_store
            context.structured_index = mock_structured_index
        
        # Verify cleanup was called
        mock_file_watcher.stop.assert_called_once()
        mock_vector_store.close.assert_called_once()
        mock_structured_index.close.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('contextbrain.server.FastMCP')
    async def test_app_lifespan_partial_cleanup(self, mock_fastmcp):
        """Test cleanup when only some components are initialized."""
        mock_mcp_instance = Mock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        server = ContextBrainServer()
        
        # Mock only some components
        mock_vector_store = Mock()
        mock_vector_store.close = AsyncMock()
        
        async with server._app_lifespan(mock_mcp_instance) as context:
            # Only set vector_store, leave others as None
            context.vector_store = mock_vector_store
        
        # Should only call close on the initialized component
        mock_vector_store.close.assert_called_once()
    
    @patch('contextbrain.server.FastMCP')
    def test_setup_methods_called(self, mock_fastmcp):
        """Test that setup methods are called during initialization."""
        mock_mcp_instance = Mock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        with patch.object(ContextBrainServer, '_setup_resources') as mock_setup_resources, \
             patch.object(ContextBrainServer, '_setup_tools') as mock_setup_tools, \
             patch.object(ContextBrainServer, '_setup_prompts') as mock_setup_prompts:
            
            server = ContextBrainServer()
            
            # Verify setup methods were called
            mock_setup_resources.assert_called_once()
            mock_setup_tools.assert_called_once()
            mock_setup_prompts.assert_called_once()
    
    @patch('contextbrain.server.FastMCP')
    def test_server_run_method_exists(self, mock_fastmcp):
        """Test that server has a run method."""
        mock_mcp_instance = Mock()
        mock_mcp_instance.run = Mock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        server = ContextBrainServer()
        
        # Should have access to run method through mcp
        assert hasattr(server.mcp, 'run')
    
    @pytest.mark.asyncio
    @patch('contextbrain.server.FastMCP')
    async def test_lifespan_exception_handling(self, mock_fastmcp):
        """Test that lifespan handles exceptions gracefully."""
        mock_mcp_instance = Mock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        server = ContextBrainServer()
        
        # Mock components with failing close methods
        mock_file_watcher = Mock()
        mock_file_watcher.stop = AsyncMock(side_effect=Exception("Stop failed"))
        
        mock_vector_store = Mock()
        mock_vector_store.close = AsyncMock(side_effect=Exception("Close failed"))
        
        try:
            async with server._app_lifespan(mock_mcp_instance) as context:
                context.file_watcher = mock_file_watcher
                context.vector_store = mock_vector_store
                # Simulate an exception during operation
                raise Exception("Test exception")
        except Exception as e:
            # The original exception should be raised
            assert str(e) == "Test exception"
        
        # Cleanup should still be attempted despite exceptions
        mock_file_watcher.stop.assert_called_once()
        mock_vector_store.close.assert_called_once()
    
    @patch('contextbrain.server.FastMCP')
    def test_server_attributes(self, mock_fastmcp):
        """Test server attributes are set correctly."""
        mock_mcp_instance = Mock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        server = ContextBrainServer(name="CustomServer", host="0.0.0.0", port=8080)
        
        assert server.name == "CustomServer"
        assert server.mcp == mock_mcp_instance
        
        # Verify the mcp instance was configured correctly
        mock_fastmcp.assert_called_once_with(
            "CustomServer",
            lifespan=server._app_lifespan,
            host="0.0.0.0",
            port=8080
        )
