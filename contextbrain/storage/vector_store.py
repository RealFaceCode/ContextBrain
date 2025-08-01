"""
Vector store implementation using ChromaDB for semantic search.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

from ..models import CodeElement, SearchResult, ElementType

logger = logging.getLogger(__name__)


class VectorStore:
    """Vector store for semantic search using ChromaDB."""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """Initialize the vector store."""
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self.collection_name = "contextbrain_elements"
    
    async def initialize(self):
        """Initialize the ChromaDB client and collection."""
        logger.info("Initializing vector store...")
        
        try:
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
                logger.info(f"Loaded existing collection: {self.collection_name}")
            except Exception:
                # Collection doesn't exist, create it with cosine distance
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "ContextBrain code elements", "hnsw:space": "cosine"}
                )
                logger.info(f"Created new collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    async def store_elements(self, elements: List[CodeElement], batch_size: int = 100):
        """
        Store code elements with their embeddings using batching to prevent timeouts.
        
        Args:
            elements: List of code elements to store
            batch_size: Number of elements to store per batch (default: 100)
        """
        if not elements:
            return
        
        logger.debug(f"Storing {len(elements)} elements in vector store using batches of {batch_size}")
        
        # Process elements in batches to prevent ChromaDB timeouts
        total_stored = 0
        
        for i in range(0, len(elements), batch_size):
            batch = elements[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(elements) + batch_size - 1) // batch_size
            
            logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} elements)")
            
            # Prepare data for this batch
            ids = []
            embeddings = []
            metadatas = []
            documents = []
            
            for element in batch:
                if not element.embedding:
                    logger.warning(f"Element {element.id} has no embedding, skipping")
                    continue
                
                ids.append(element.id)
                embeddings.append(element.embedding)
                documents.append(element.content)
                
                # Prepare metadata (ChromaDB requires flat dict)
                metadata = {
                    "type": element.type.value,
                    "name": element.name,
                    "file_path": element.file_path,
                    "language": element.metadata.language,
                    "line_start": element.location.line_start,
                    "line_end": element.location.line_end,
                }
                
                # Add optional metadata fields
                if element.metadata.complexity:
                    metadata["complexity"] = element.metadata.complexity
                if element.metadata.lines_of_code:
                    metadata["lines_of_code"] = element.metadata.lines_of_code
                if element.metadata.author:
                    metadata["author"] = element.metadata.author
                
                metadatas.append(metadata)
            
            if ids:
                # Store this batch in ChromaDB
                self.collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=documents,
                )
                total_stored += len(ids)
                logger.debug(f"Stored batch {batch_num}/{total_batches}: {len(ids)} elements")
                
                # Yield control to the event loop to prevent blocking
                await asyncio.sleep(0.01)  # Small delay to allow other operations
        
        logger.debug(f"Successfully stored {total_stored} elements in {total_batches} batches")
    
    async def search(self, query: str, threshold: float = 0.2, limit: int = 10) -> List[SearchResult]:
        """Search for similar code elements."""
        if not self.collection:
            return []
        
        try:
            # Query the collection
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                include=["documents", "metadatas", "distances"]
            )
            
            search_results = []
            
            if results["ids"] and results["ids"][0]:
                for i, element_id in enumerate(results["ids"][0]):
                    # Convert distance to similarity score
                    distance = results["distances"][0][i]

                    # ChromaDB with cosine distance: distance = 1 - cosine_similarity
                    # So: cosine_similarity = 1 - distance
                    # Distance range: [0, 2] where 0 = identical, 1 = orthogonal, 2 = opposite
                    score = max(0, 1 - distance)

                    # Ensure score is between 0 and 1
                    score = max(0, min(1, score))
                    
                    if score >= threshold:
                        metadata = results["metadatas"][0][i]
                        document = results["documents"][0][i]
                        
                        # Create CodeElement from stored data
                        from ..models import SourceLocation, ElementMetadata
                        
                        element = CodeElement(
                            id=element_id,
                            type=ElementType(metadata["type"]),
                            name=metadata["name"],
                            content=document,
                            file_path=metadata["file_path"],
                            location=SourceLocation(
                                line_start=metadata["line_start"],
                                line_end=metadata["line_end"],
                                column_start=0,
                                column_end=0
                            ),
                            metadata=ElementMetadata(
                                language=metadata["language"],
                                complexity=metadata.get("complexity"),
                                lines_of_code=metadata.get("lines_of_code"),
                                author=metadata.get("author")
                            )
                        )
                        
                        search_results.append(SearchResult(
                            element=element,
                            score=score,
                            snippet=document[:200] + "..." if len(document) > 200 else document
                        ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        if not self.collection:
            return {"count": 0, "name": "none"}
        
        try:
            count = self.collection.count()
            return {
                "count": count,
                "name": self.collection_name
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"count": 0, "name": self.collection_name, "error": str(e)}
    
    async def clear_collection(self):
        """Clear all elements from the collection without recreating it."""
        if not self.collection:
            logger.warning("No collection to clear")
            return 0

        try:
            # Get current count
            count = self.collection.count()
            if count == 0:
                logger.info("Collection is already empty")
                return 0

            # Get all document IDs
            result = self.collection.get(include=[])
            if result['ids']:
                # Delete all documents in batches to avoid memory issues
                batch_size = 1000
                ids = result['ids']
                total_deleted = 0

                for i in range(0, len(ids), batch_size):
                    batch_ids = ids[i:i + batch_size]
                    self.collection.delete(ids=batch_ids)
                    total_deleted += len(batch_ids)

                    # Small delay to prevent overwhelming ChromaDB
                    await asyncio.sleep(0.01)

                logger.info(f"Cleared {total_deleted} elements from collection")
                return total_deleted
            else:
                logger.info("No elements found to clear")
                return 0

        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
            raise

    async def close(self):
        """Close the vector store."""
        logger.info("Closing vector store")
        # ChromaDB client doesn't need explicit closing
        self.client = None
        self.collection = None
