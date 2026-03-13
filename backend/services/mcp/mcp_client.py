"""
mcp_client.py
=============
Stub — kept for import compatibility.
All tools now call FDA, PubMed, and NIH APIs directly.
No subprocess, no HTTP server needed.
"""

import os

MCP_SERVER_PATH = os.path.expanduser(
    "~/Desktop/MurphyBot_AIChatbot/medical-mcp/build/index.js"
)


def is_mcp_available() -> bool:
    """Always true — we call APIs directly now, no server needed."""
    return True


def call_tool(tool_name: str, arguments: dict) -> dict:
    """Deprecated — use direct API functions in drug_enrichment, literature, guidelines."""
    return {"error": "call_tool deprecated — use direct API functions"}