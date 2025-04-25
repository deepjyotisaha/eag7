import os
from pathlib import Path

# Get the root directory of the project
ROOT_DIR = Path(__file__).parent.parent

# MCP Server configurations
MCP_SERVER_CONFIG = {
    "math_server": {
        "command": "uv",
        "script_path": str(ROOT_DIR / "mcp_server" / "math" / "mcp_math_server.py"),
        "args": ["run"]
    },
    "rag_server": {
        "command": "uv",
        "script_path": str(ROOT_DIR / "mcp_server" / "rag" / "mcp_rag_server.py"),
        "args": ["run"]
    },
    "gmail_server": {
        "command": "uv",
        "script_path": str(ROOT_DIR / "mcp_server" / "gmail" / "src" / "gmail" / "gmail_mcp_server.py"),
        "args": ["run"],
        "creds_file_path": str(ROOT_DIR / ".google" / "client_creds.json"),
        "token_path": str(ROOT_DIR / ".google" / "app_tokens.json")
    }
}