"""
Configuration settings for ContextBrain MCP Server

Centralized configuration management with environment variable support
and validation for all server components.
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """Database configuration settings."""
    vector_db_path: str = Field(default="./chroma_db", description="ChromaDB persistence directory")
    structured_db_path: str = Field(default="./contextbrain.db", description="SQLite database path")
    backup_enabled: bool = Field(default=True, description="Enable database backups")
    backup_interval_hours: int = Field(default=24, description="Backup interval in hours")


class IndexingConfig(BaseModel):
    """Indexing configuration settings."""
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Sentence transformer model for embeddings"
    )
    max_file_size_mb: float = Field(default=10.0, description="Maximum file size to index (MB)")
    batch_size: int = Field(default=50, description="Batch size for file processing")
    exclude_patterns: List[str] = Field(
        default_factory=lambda: [
            "*.pyc", "__pycache__", ".git", ".svn", ".hg",
            "node_modules", ".vscode", ".idea", "*.log",
            "*.tmp", "*.swp", "*.bak", "dist", "build",
            ".pytest_cache", "coverage", "*.egg-info"
        ],
        description="Default patterns to exclude from indexing"
    )
    supported_extensions: Dict[str, str] = Field(
        default_factory=lambda: {
            '.py': 'python',
            '.js': 'javascript', 
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sh': 'bash',
            '.sql': 'sql',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.md': 'markdown',
            '.rst': 'rst',
        },
        description="Supported file extensions and their languages"
    )


class MonitoringConfig(BaseModel):
    """File monitoring configuration settings."""
    debounce_delay: float = Field(default=2.0, description="Debounce delay for file changes (seconds)")
    enable_git_integration: bool = Field(default=True, description="Enable Git integration")
    watch_recursive: bool = Field(default=True, description="Watch directories recursively")
    ignore_hidden_files: bool = Field(default=True, description="Ignore hidden files and directories")


class ServerConfig(BaseModel):
    """MCP server configuration settings."""
    name: str = Field(default="ContextBrain", description="Server name")
    version: str = Field(default="1.0.0", description="Server version")
    description: str = Field(
        default="Intelligent project context management for AI applications",
        description="Server description"
    )
    max_concurrent_requests: int = Field(default=100, description="Maximum concurrent requests")
    request_timeout_seconds: int = Field(default=30, description="Request timeout in seconds")
    enable_cors: bool = Field(default=True, description="Enable CORS for HTTP transport")
    cors_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins"
    )


class LoggingConfig(BaseModel):
    """Logging configuration settings."""
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format"
    )
    file_path: Optional[str] = Field(default="contextbrain.log", description="Log file path")
    max_file_size_mb: int = Field(default=10, description="Maximum log file size (MB)")
    backup_count: int = Field(default=5, description="Number of log file backups")
    enable_structured_logging: bool = Field(default=False, description="Enable structured JSON logging")

    @validator('level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of: {valid_levels}')
        return v.upper()


class SecurityConfig(BaseModel):
    """Security configuration settings."""
    enable_authentication: bool = Field(default=False, description="Enable authentication")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    rate_limit_requests_per_minute: int = Field(default=60, description="Rate limit per minute")
    enable_request_validation: bool = Field(default=True, description="Enable request validation")
    max_query_length: int = Field(default=1000, description="Maximum query length")
    allowed_file_types: List[str] = Field(
        default_factory=lambda: [
            'text', 'application/json', 'application/xml',
            'application/javascript', 'text/html', 'text/css'
        ],
        description="Allowed MIME types for file processing"
    )


class PerformanceConfig(BaseModel):
    """Performance optimization settings."""
    cache_enabled: bool = Field(default=True, description="Enable caching")
    cache_size_mb: int = Field(default=100, description="Cache size in MB")
    cache_ttl_seconds: int = Field(default=3600, description="Cache TTL in seconds")
    enable_compression: bool = Field(default=True, description="Enable response compression")
    worker_threads: int = Field(default=4, description="Number of worker threads")
    connection_pool_size: int = Field(default=10, description="Database connection pool size")


class ContextBrainSettings(BaseSettings):
    """
    Main configuration class for ContextBrain MCP Server.
    
    Loads settings from environment variables with CONTEXTBRAIN_ prefix.
    """
    
    # Component configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    
    # Global settings
    data_directory: str = Field(default="./data", description="Data directory path")
    temp_directory: str = Field(default="./temp", description="Temporary files directory")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    debug_mode: bool = Field(default=False, description="Enable debug mode")
    
    class Config:
        env_prefix = "CONTEXTBRAIN_"
        env_nested_delimiter = "__"
        case_sensitive = False
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure required directories exist."""
        directories = [
            self.data_directory,
            self.temp_directory,
            Path(self.database.vector_db_path).parent,
            Path(self.database.structured_db_path).parent,
        ]
        
        if self.logging.file_path:
            directories.append(Path(self.logging.file_path).parent)
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_database_url(self) -> str:
        """Get the database URL for SQLite."""
        return f"sqlite:///{self.database.structured_db_path}"
    
    def get_log_config(self) -> Dict[str, Any]:
        """Get logging configuration dictionary."""
        config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': self.logging.format
                },
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': self.logging.level,
                    'formatter': 'standard',
                    'stream': 'ext://sys.stderr'
                },
            },
            'loggers': {
                'contextbrain': {
                    'level': self.logging.level,
                    'handlers': ['console'],
                    'propagate': False
                },
                'root': {
                    'level': self.logging.level,
                    'handlers': ['console']
                }
            }
        }
        
        # Add file handler if specified
        if self.logging.file_path:
            config['handlers']['file'] = {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': self.logging.level,
                'formatter': 'standard',
                'filename': self.logging.file_path,
                'maxBytes': self.logging.max_file_size_mb * 1024 * 1024,
                'backupCount': self.logging.backup_count
            }
            config['loggers']['contextbrain']['handlers'].append('file')
            config['loggers']['root']['handlers'].append('file')
        
        return config
    
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.debug_mode or os.getenv('ENVIRONMENT', '').lower() in ['dev', 'development']
    
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return os.getenv('ENVIRONMENT', '').lower() in ['prod', 'production']


# Global settings instance
settings = ContextBrainSettings()


def get_settings() -> ContextBrainSettings:
    """Get the global settings instance."""
    return settings


def reload_settings() -> ContextBrainSettings:
    """Reload settings from environment variables."""
    global settings
    settings = ContextBrainSettings()
    return settings
