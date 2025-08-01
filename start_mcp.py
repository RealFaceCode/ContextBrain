#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ContextBrain MCP Server Starter - MCP Compatible Version

This script is specifically designed for MCP clients like VS Code's MCP extension.
It ensures clean JSON-RPC communication by suppressing all informational output
and directly launching the MCP server without intermediate messages.
"""

import os
import sys
import subprocess
from pathlib import Path


def find_python_executable():
    """Find Python interpreter in virtual environment, silently."""
    script_dir = Path(__file__).parent
    
    # Windows venv paths
    venv_paths = [
        script_dir / "venv" / "Scripts" / "python.exe",
        script_dir / "venv" / "Scripts" / "python3.exe",
        script_dir / ".venv" / "Scripts" / "python.exe",
        script_dir / ".venv" / "Scripts" / "python3.exe",
    ]
    
    # Unix/Linux/macOS venv paths
    venv_paths.extend([
        script_dir / "venv" / "bin" / "python",
        script_dir / "venv" / "bin" / "python3",
        script_dir / ".venv" / "bin" / "python",
        script_dir / ".venv" / "bin" / "python3",
    ])
    
    # Check for venv Python
    for python_path in venv_paths:
        if python_path.exists():
            return str(python_path)
    
    # Fallback to system Python
    return sys.executable


def start_mcp_server():
    """Start the ContextBrain MCP server in clean MCP mode."""
    script_dir = Path(__file__).parent
    main_script = script_dir / "main.py"
    
    if not main_script.exists():
        # Write error to stderr, not stdout (to avoid interfering with MCP)
        print(f"[ERROR] main.py not found in {script_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Find Python executable
    python_exe = find_python_executable()
    
    # Build command for stdio transport
    cmd = [
        python_exe,
        str(main_script),
        "serve",
        "--transport", "stdio"
    ]
    
    try:
        # Start the server with clean stdio
        # This will pass through stdin/stdout directly to the MCP server
        # without any intermediate output that could interfere with JSON-RPC
        process = subprocess.Popen(
            cmd,
            cwd=script_dir,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            # Ensure clean environment
            env=os.environ.copy()
        )
        
        # Wait for the process to complete
        return_code = process.wait()
        sys.exit(return_code)
        
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        sys.exit(0)
        
    except Exception as e:
        print(f"[ERROR] Failed to start MCP server: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for MCP-compatible server startup."""
    # No argument parsing, no output - just start the server
    # This ensures the cleanest possible MCP communication
    start_mcp_server()


if __name__ == "__main__":
    main()
