"""
Entry point for running the MCP server.

Usage:
    python -m mycelium.mcp
"""

from mycelium.mcp.server import mcp

if __name__ == "__main__":
    mcp.run()
