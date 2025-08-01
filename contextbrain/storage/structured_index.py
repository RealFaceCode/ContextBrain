"""
Structured index implementation using SQLite for relational queries.
"""

import asyncio
import logging
import sqlite3
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..models import CodeElement, ElementType

logger = logging.getLogger(__name__)


class StructuredIndex:
    """Structured index for relational queries using SQLite."""
    
    def __init__(self, db_path: str = "./contextbrain.db"):
        """Initialize the structured index."""
        self.db_path = db_path
        self.connection = None
    
    async def initialize(self):
        """Initialize the SQLite database and create tables."""
        logger.info("Initializing structured index...")
        
        try:
            # Create database connection
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
            
            # Create tables
            await self._create_tables()
            
            logger.info("Structured index initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize structured index: {e}")
            raise
    
    async def _create_tables(self):
        """Create the necessary database tables."""
        cursor = self.connection.cursor()
        
        # Elements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS elements (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT,
                file_path TEXT NOT NULL,
                line_start INTEGER,
                line_end INTEGER,
                language TEXT,
                complexity INTEGER,
                lines_of_code INTEGER,
                author TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Dependencies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dependencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_element_id TEXT,
                target_element_id TEXT,
                dependency_type TEXT,
                FOREIGN KEY (source_element_id) REFERENCES elements (id),
                FOREIGN KEY (target_element_id) REFERENCES elements (id)
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_elements_type ON elements (type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_elements_name ON elements (name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_elements_file_path ON elements (file_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_elements_language ON elements (language)")
        
        self.connection.commit()
    
    async def store_elements(self, elements: List[CodeElement]):
        """Store code elements in the structured index."""
        if not elements:
            return
        
        logger.debug(f"Storing {len(elements)} elements in structured index")
        
        cursor = self.connection.cursor()
        
        for element in elements:
            # Insert or update element
            cursor.execute("""
                INSERT OR REPLACE INTO elements (
                    id, type, name, content, file_path, line_start, line_end,
                    language, complexity, lines_of_code, author, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                element.id,
                element.type.value,
                element.name,
                element.content,
                element.file_path,
                element.location.line_start,
                element.location.line_end,
                element.metadata.language,
                element.metadata.complexity,
                element.metadata.lines_of_code,
                element.metadata.author
            ))
            
            # Store dependencies
            for dep in element.dependencies:
                cursor.execute("""
                    INSERT OR REPLACE INTO dependencies (source_element_id, target_element_id, dependency_type)
                    VALUES (?, ?, ?)
                """, (element.id, dep, "import"))
        
        self.connection.commit()
        logger.debug(f"Stored {len(elements)} elements successfully")
    
    async def search_structural(self, element_type: str, name_pattern: str, scope: Optional[str] = None) -> List[CodeElement]:
        """Search for elements by structure."""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            
            # Build query with proper wildcard handling
            # Convert shell-style wildcards to SQL LIKE patterns
            sql_pattern = name_pattern.replace('*', '%').replace('?', '_')

            # If pattern doesn't contain wildcards, add % for partial matching
            if '*' not in name_pattern and '?' not in name_pattern:
                sql_pattern = f"%{sql_pattern}%"

            query = "SELECT * FROM elements WHERE type = ? AND name LIKE ?"
            params = [element_type, sql_pattern]
            
            if scope:
                query += " AND file_path LIKE ?"
                params.append(f"%{scope}%")
            
            # Order by file path length (longer paths first) to prefer complete paths, then by name
            query += " ORDER BY LENGTH(file_path) DESC, name LIMIT 50"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert rows to CodeElement objects and deduplicate by name + type
            elements = []
            seen_elements = set()

            for row in rows:
                from ..models import SourceLocation, ElementMetadata

                # Create a key for deduplication (name + type + content hash)
                element_key = (row["name"], row["type"], hash(row["content"] or ""))

                # Skip if we've already seen this element (prefer the first one due to ordering)
                if element_key in seen_elements:
                    continue

                seen_elements.add(element_key)

                element = CodeElement(
                    id=row["id"],
                    type=ElementType(row["type"]),
                    name=row["name"],
                    content=row["content"] or "",
                    file_path=row["file_path"],
                    location=SourceLocation(
                        line_start=row["line_start"] or 0,
                        line_end=row["line_end"] or 0,
                        column_start=0,
                        column_end=0
                    ),
                    metadata=ElementMetadata(
                        language=row["language"] or "unknown",
                        complexity=row["complexity"],
                        lines_of_code=row["lines_of_code"],
                        author=row["author"]
                    )
                )
                elements.append(element)

            return elements
            
        except Exception as e:
            logger.error(f"Structural search failed: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the structured index."""
        if not self.connection:
            return {"total_elements": 0}
        
        try:
            cursor = self.connection.cursor()
            
            # Get total count
            cursor.execute("SELECT COUNT(*) as count FROM elements")
            total = cursor.fetchone()["count"]
            
            # Get count by type
            cursor.execute("SELECT type, COUNT(*) as count FROM elements GROUP BY type")
            by_type = {row["type"]: row["count"] for row in cursor.fetchall()}
            
            # Get count by language
            cursor.execute("SELECT language, COUNT(*) as count FROM elements GROUP BY language")
            by_language = {row["language"]: row["count"] for row in cursor.fetchall()}
            
            return {
                "total_elements": total,
                "by_type": by_type,
                "by_language": by_language
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total_elements": 0, "error": str(e)}
    
    async def close(self):
        """Close the structured index."""
        logger.info("Closed structured index")
        if self.connection:
            self.connection.close()
            self.connection = None
