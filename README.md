# ContextBrain: MCP Server for Project Context Management

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

ContextBrain is a Model Context Protocol (MCP) server that eliminates context loss in AI-assisted development by providing intelligent, real-time project indexing and semantic context retrieval for any AI application.

## 🚀 Features

### Core Capabilities
- **Universal Context Access**: Any MCP-compatible AI application can access rich project context
- **Intelligent Indexing**: Advanced semantic chunking and embedding strategies maintain code relationships
- **Real-time Synchronization**: Automatic index updates as projects evolve
- **Multi-Language Support**: 20+ programming languages with syntax-aware parsing
- **Semantic Search**: Vector-based similarity search for code and documentation
- **Advanced Exclusion System**: Intelligent file/directory filtering with dependency analysis

### MCP Resources
- `project://files/{path}` - Access indexed file contents with metadata
- `project://structure` - Complete project structure and hierarchy
- `project://dependencies` - Package dependencies and relationships
- `project://git/history/{path}` - Git history and change patterns
- `project://documentation` - Aggregated documentation from various sources

### MCP Tools
- `index_project` - Initialize or re-index a project directory with advanced exclusion support
- `search_semantic` - Semantic search across project content
- `search_structural` - Search by code structure (classes, functions, modules)
- `get_context_for_file` - Get relevant context for a specific file
- `analyze_dependencies` - Analyze dependency relationships

### MCP Prompts
- `explain_architecture` - Generate architectural overview
- `code_review_context` - Provide context for code review
- `onboarding_guide` - Generate new developer onboarding information

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- Git (optional, for Git integration features)

### Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd context_mcp
```

2. **Create and activate virtual environment:**
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

## 🎯 Quick Start

### 1. Run the Demo
```bash
python demo.py
```

### 2. Test Basic Functionality
```bash
python simple_test.py
```

### 3. Start the MCP Server

**🚀 Einfacher Start (empfohlen):**
```bash
# Windows
start.bat

# Unix/Linux/macOS
./start.sh

# Plattformübergreifend
python start.py
```

**⚙️ Mit Parametern:**
```bash
# SSE Transport auf Port 8000
python start.py --transport sse

# HTTP Transport auf Port 8080
python start.py --transport http --port 8080

# Benutzerdefinierte Konfiguration
python start.py --transport sse --host 0.0.0.0 --port 9000
```

**🔧 Manueller Start (falls nötig):**
```bash
# Aktiviere venv manuell
venv\Scripts\activate  # Windows
source venv/bin/activate  # Unix/Linux/macOS

# Starte Server
python main.py serve --transport stdio
```

### 4. Index a Project
```bash
# Index current directory with default exclusions
python main.py index .

# Add custom exclusion patterns
python main.py index /path/to/project --exclude "*.log" --exclude "temp/**"

# Index only specific languages
python main.py index /path/to/project --languages python --languages javascript

# Advanced exclusion options
python main.py index /path/to/project --no-defaults --verbosity debug
python main.py index /path/to/project --no-dependency-scan --batch-size 64
```

#### 🚫 Advanced Exclusion System

ContextBrain features a comprehensive exclusion system for optimal indexing performance:

**Default Exclusions (Automatically Applied):**
- Virtual environments: `venv/`, `.venv/`, `env/`, `.env/`
- Package managers: `node_modules/`, `__pycache__/`, `.pytest_cache/`
- Version control: `.git/`, `.svn/`, `.hg/`
- Build artifacts: `dist/`, `build/`, `target/`, `bin/`, `obj/`
- IDE files: `.vscode/`, `.idea/`, `*.swp`, `*.tmp`
- Compiled files: `*.pyc`, `*.pyo`, `*.class`, `*.o`, `*.so`

**Key Features:**
- **Smart Filtering**: Excludes noise while preserving important code
- **Dependency Analysis**: Scans excluded directories for dependency files
- **Performance**: 83% faster indexing on typical projects
- **Customizable**: Add project-specific patterns as needed

### 5. Search Indexed Content
```bash
# Semantic search
python main.py search "function that calculates fibonacci"

# Search with custom parameters
python main.py search "database connection" --threshold 0.8 --limit 5
```

### 6. Watch for File Changes
```bash
python main.py watch /path/to/project
```

## 🏗️ Architecture

ContextBrain follows a modular architecture designed for scalability and extensibility:

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Applications                          │
│         (VS Code, Cursor, Aider, Custom Tools)             │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol
┌─────────────────────▼───────────────────────────────────────┐
│                ContextBrain MCP Server                     │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │ Resources   │ Tools       │ Prompts     │ Transport   │  │
│  │ Handler     │ Executor    │ Generator   │ Layer       │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 Core Services                               │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │ Indexing    │ Query       │ File        │ Git         │  │
│  │ Engine      │ Processor   │ Watcher     │ Integration │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                Storage Layer                                │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐  │
│  │ Vector      │ Structured  │ Cache       │ Metadata    │  │
│  │ Database    │ Index       │ Layer       │ Store       │  │
│  │ (ChromaDB)  │ (SQLite)    │             │             │  │
│  └─────────────┴─────────────┴─────────────┴─────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

1. **MCP Server Layer**: Handles protocol communication and request routing
2. **Indexing Engine**: Language-aware parsing and semantic analysis
3. **Storage Layer**: Vector database for semantic search, SQLite for structured queries
4. **File Monitoring**: Real-time change detection with debouncing
5. **Language Parsers**: Specialized parsers for different programming languages

## 🔧 Configuration

ContextBrain uses environment variables for configuration. Create a `.env` file or set environment variables:

```bash
# Database Configuration
CONTEXTBRAIN_DATABASE__VECTOR_DB_PATH=./chroma_db
CONTEXTBRAIN_DATABASE__STRUCTURED_DB_PATH=./contextbrain.db

# Indexing Configuration
CONTEXTBRAIN_INDEXING__EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CONTEXTBRAIN_INDEXING__MAX_FILE_SIZE_MB=10.0
CONTEXTBRAIN_INDEXING__BATCH_SIZE=50

# Server Configuration
CONTEXTBRAIN_SERVER__NAME=ContextBrain
CONTEXTBRAIN_SERVER__MAX_CONCURRENT_REQUESTS=100

# Logging Configuration
CONTEXTBRAIN_LOGGING__LEVEL=INFO
CONTEXTBRAIN_LOGGING__FILE_PATH=contextbrain.log

# Performance Configuration
CONTEXTBRAIN_PERFORMANCE__CACHE_ENABLED=true
CONTEXTBRAIN_PERFORMANCE__WORKER_THREADS=4
```

## 🌐 Supported Languages

ContextBrain supports syntax-aware parsing for 20+ programming languages:

- **Web**: JavaScript, TypeScript, HTML, CSS
- **Backend**: Python, Java, C#, Go, Rust, PHP, Ruby
- **Systems**: C, C++, Swift, Kotlin, Scala
- **Scripting**: Bash, SQL
- **Data**: JSON, YAML, XML
- **Documentation**: Markdown, reStructuredText

## 🔌 MCP Client Integration

### VS Code MCP Extension (Recommended)

Add to your VS Code settings.json:

```json
{
  "mcpServers": {
    "contextbrain": {
      "command": "python",
      "args": ["./start_mcp.py"],
      "cwd": "C:/dev/context_mcp"
    }
  }
}
```

### Claude Desktop Integration

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "contextbrain": {
      "command": "python",
      "args": ["/path/to/context_mcp/main.py", "serve"],
      "env": {
        "CONTEXTBRAIN_LOGGING__LEVEL": "INFO"
      }
    }
  }
}
```

### Custom Client Integration

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def use_contextbrain():
    server_params = StdioServerParameters(
        command="python",
        args=["main.py", "serve"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")
            
            # Use a tool
            result = await session.call_tool("search_semantic", {
                "query": "database connection",
                "max_results": 5
            })
            print(f"Search results: {result}")

asyncio.run(use_contextbrain())
```

## 📊 Performance

ContextBrain is designed for performance and scalability:

- **Indexing Speed**: 1000+ files/minute for initial indexing
- **Query Response**: <200ms for semantic search queries
- **Memory Usage**: Efficient vector storage with configurable cache
- **Concurrent Users**: Supports 100+ simultaneous connections
- **Real-time Updates**: <5 seconds for incremental file changes

## 🧪 Testing

Run the test suite:

```bash
# Run simple functionality tests
python simple_test.py

# Run comprehensive tests (requires pytest)
pytest test_contextbrain.py -v

# Run demo to see all features
python demo.py
```

## 🔧 Troubleshooting

### Common Issues

**1. Server fails to start with "unexpected keyword argument" error:**
- **Fixed in latest version!** The FastMCP API issue has been resolved.
- Make sure you're using the updated server code.

**2. Unicode encoding errors in VS Code:**
- **Fixed in latest version!** Unicode characters replaced with ASCII alternatives.
- The server now works reliably with VS Code's MCP extension.

**3. MCP protocol communication errors:**
- **Fixed in latest version!** Clean JSON-RPC communication implemented.
- Use `start_mcp.py` for seamless VS Code MCP extension integration.

**4. Slow indexing with verbose output:**
- **Fixed in latest version!** Optimized batch embedding generation eliminates progress bar spam.
- Indexing is now significantly faster with clean, minimal output.

**4. Dependency conflicts (numpy/pandas):**
```bash
pip install --upgrade numpy pandas scikit-learn
```

**5. ChromaDB permission issues:**
- Ensure the data directory is writable
- Try running with elevated permissions if needed

**4. Port already in use:**
```bash
# Use a different port
python main.py serve --transport http --port 8001
```

### Testing Your Installation

```bash
# Test basic functionality
python test_fastmcp_only.py

# Test server startup
python test_stdio_server.py

# Run the demo
python demo.py
```

## 📚 Documentation

- [Server Starter Guide](START_GUIDE.md) - Einfaches Starten ohne venv-Aktivierung
- [Exclusion System Guide](EXCLUSION_SYSTEM_GUIDE.md) - Comprehensive file and directory exclusion
- [MCP Protocol Fix](MCP_PROTOCOL_FIX_SUMMARY.md) - VS Code MCP extension compatibility
- [Indexing Optimization](INDEXING_OPTIMIZATION_SUMMARY.md) - Performance improvements and verbose output fix
- [Unicode Fix Summary](UNICODE_FIX_SUMMARY.md) - Windows encoding compatibility
- [MCP Server Fix Details](MCP_SERVER_FIX.md)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) for the standardized AI context protocol
- [ChromaDB](https://www.trychroma.com/) for vector database capabilities
- [Sentence Transformers](https://www.sbert.net/) for semantic embeddings
- [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) for syntax-aware parsing

---

**ContextBrain** - Intelligent project context management for the AI era.
