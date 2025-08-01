#!/usr/bin/env python3
"""
ContextBrain MCP Server - Main Entry Point

Starts the ContextBrain MCP server with the specified transport and configuration.
Supports stdio, SSE, and HTTP transports for different deployment scenarios.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from contextbrain.server import ContextBrainServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler('contextbrain.log')
    ]
)

logger = logging.getLogger(__name__)


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
def cli(debug: bool):
    """ContextBrain MCP Server - Intelligent project context management."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")


@cli.command()
@click.option('--transport', '-t',
              type=click.Choice(['stdio', 'sse', 'http']),
              default='stdio',
              help='Transport protocol to use')
@click.option('--host', '-h', default='127.0.0.1', help='Host to bind to (for HTTP/SSE)')
@click.option('--port', '-p', default=8000, type=int, help='Port to bind to (for HTTP/SSE)')
@click.option('--mount-path', default='/mcp', help='Mount path for HTTP transport')
def serve(transport: str, host: str, port: int, mount_path: str):
    """Start the ContextBrain MCP server."""
    # For stdio transport, reduce logging to avoid potential interference
    if transport == 'stdio':
        # Set logging to WARNING level for stdio to minimize output
        logging.getLogger().setLevel(logging.WARNING)
        # Only log to file for stdio transport
        for handler in logging.getLogger().handlers[:]:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stderr:
                logging.getLogger().removeHandler(handler)

    logger.info(f"Starting ContextBrain server with {transport} transport")

    try:
        # Create server with host and port configuration
        server = ContextBrainServer("ContextBrain", host=host, port=port)

        # Run server with appropriate transport
        if transport == 'stdio':
            server.run(transport='stdio')
        elif transport == 'sse':
            server.run(transport='sse', mount_path=mount_path)
        elif transport == 'http':
            server.run(transport='streamable-http', mount_path=mount_path)

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


@cli.command()
@click.argument('project_path', type=click.Path(exists=True, path_type=Path))
@click.option('--exclude', multiple=True, help='Additional patterns to exclude from indexing')
@click.option('--languages', multiple=True, help='Languages to include (default: all supported)')
@click.option('--no-defaults', is_flag=True, help='Disable default exclusion rules')
@click.option('--dependency-scan/--no-dependency-scan', default=True, help='Enable/disable dependency scanning in excluded dirs')
@click.option('--verbosity', type=click.Choice(['debug', 'info', 'warning']), default='info', help='Exclusion logging verbosity')
@click.option('--batch-size', default=32, help='Embedding generation batch size')
def index(project_path: Path, exclude: tuple, languages: tuple, no_defaults: bool, dependency_scan: bool, verbosity: str, batch_size: int):
    """Index a project directory."""
    logger.info(f"Indexing project: {project_path}")
    
    async def run_indexing():
        from contextbrain.indexing import IndexingEngine
        from contextbrain.storage import VectorStore, StructuredIndex
        
        # Initialize components
        vector_store = VectorStore()
        structured_index = StructuredIndex()
        indexing_engine = IndexingEngine(vector_store, structured_index)
        
        await vector_store.initialize()
        await structured_index.initialize()
        await indexing_engine.initialize()
        
        try:
            # Create configuration
            from contextbrain.models import IndexConfiguration
            config = IndexConfiguration(
                exclude_patterns=list(exclude),
                include_languages=list(languages) if languages else [],
                use_default_exclusions=not no_defaults,
                enable_dependency_scanning=dependency_scan,
                exclusion_verbosity=verbosity,
                embedding_batch_size=batch_size,
                show_progress_bars=False,
                verbose_output=verbosity == 'debug'
            )

            # Index the project
            result = await indexing_engine.index_project(
                project_path=project_path,
                config=config
            )
            
            logger.info("Indexing completed:")
            logger.info(f"  - Files indexed: {result.statistics.total_files}")
            logger.info(f"  - Elements extracted: {result.statistics.total_elements}")
            logger.info(f"  - Languages: {', '.join(result.languages)}")
            logger.info(f"  - Processing time: {result.statistics.processing_time_seconds:.2f}s")
            
        finally:
            await vector_store.close()
            await structured_index.close()
    
    try:
        asyncio.run(run_indexing())
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument('query')
@click.option('--threshold', default=0.7, type=float, help='Similarity threshold')
@click.option('--limit', default=10, type=int, help='Maximum results')
def search(query: str, threshold: float, limit: int):
    """Search the indexed project."""
    logger.info(f"Searching for: {query}")
    
    async def run_search():
        from contextbrain.storage import VectorStore
        
        vector_store = VectorStore()
        await vector_store.initialize()
        
        try:
            results = await vector_store.search(
                query=query,
                threshold=threshold,
                limit=limit
            )
            
            if results:
                logger.info(f"Found {len(results)} results:")
                for i, result in enumerate(results, 1):
                    logger.info(f"{i}. {result.element.name} ({result.element.type.value})")
                    logger.info(f"   File: {result.element.file_path}")
                    logger.info(f"   Score: {result.score:.3f}")
                    logger.info(f"   Snippet: {result.snippet}")
                    logger.info("")
            else:
                logger.info("No results found")
                
        finally:
            await vector_store.close()
    
    try:
        asyncio.run(run_search())
    except Exception as e:
        logger.error(f"Search failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument('project_path', type=click.Path(exists=True, path_type=Path))
def watch(project_path: Path):
    """Watch a project directory for changes."""
    logger.info(f"Starting file watcher for: {project_path}")
    
    async def run_watcher():
        from contextbrain.indexing import IndexingEngine
        from contextbrain.storage import VectorStore, StructuredIndex
        from contextbrain.monitoring import FileWatcher
        
        # Initialize components
        vector_store = VectorStore()
        structured_index = StructuredIndex()
        indexing_engine = IndexingEngine(vector_store, structured_index)
        file_watcher = FileWatcher(indexing_engine)
        
        await vector_store.initialize()
        await structured_index.initialize()
        await indexing_engine.initialize()
        
        try:
            # Start watching
            await file_watcher.start_watching(project_path)
            
            logger.info("File watcher started. Press Ctrl+C to stop.")
            
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Stopping file watcher...")
        finally:
            await file_watcher.stop()
            await vector_store.close()
            await structured_index.close()
    
    try:
        asyncio.run(run_watcher())
    except Exception as e:
        logger.error(f"File watcher failed: {e}")
        sys.exit(1)


@cli.command()
def status():
    """Show server status and statistics."""
    logger.info("ContextBrain Server Status")
    
    async def show_status():
        from contextbrain.storage import VectorStore, StructuredIndex
        
        vector_store = VectorStore()
        structured_index = StructuredIndex()
        
        try:
            await vector_store.initialize()
            await structured_index.initialize()
            
            # Get statistics
            vector_stats = await vector_store.get_collection_stats()
            
            logger.info("=== Storage Statistics ===")
            logger.info(f"Vector Store Elements: {vector_stats['total_elements']}")
            logger.info(f"Collection: {vector_stats['collection_name']}")
            
        except Exception as e:
            logger.error(f"Could not retrieve status: {e}")
        finally:
            await vector_store.close()
            await structured_index.close()
    
    try:
        asyncio.run(show_status())
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
