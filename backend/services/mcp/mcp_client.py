


"""
mcp_client.py
=============
Communicates with the JamesANZ Medical MCP server via stdio transport.
The MCP server is NOT an HTTP server — it uses stdin/stdout JSON-RPC.

Protocol:
    1. Start the Node.js process
    2. Send JSON-RPC request to stdin
    3. Read JSON response from stdout
    4. Kill process when done
"""

import json
import subprocess
import logging
import os

log = logging.getLogger("murphybot.mcp")

# Path to the built MCP server index.js
MCP_SERVER_PATH = os.path.expanduser(
    "~/Desktop/MurphyBot_AIChatbot/medical-mcp/build/index.js"
)
TIMEOUT = 30  # seconds


def call_tool(tool_name: str, arguments: dict) -> dict:
    """
    Call a single MCP tool via stdio JSON-RPC.

    Starts the MCP server process, sends the request, reads the response,
    then terminates the process.

    Args:
        tool_name:  e.g. "search-drugs", "search-medical-literature"
        arguments:  tool-specific arguments dict

    Returns:
        Parsed result dict from MCP server.
        Returns {"error": "..."} if anything fails — never raises.
    """
    if not os.path.exists(MCP_SERVER_PATH):
        log.warning(f"MCP server not found at {MCP_SERVER_PATH}")
        return {"error": f"MCP server not found at {MCP_SERVER_PATH}"}

    # JSON-RPC 2.0 request format
    request = {
        "jsonrpc": "2.0",
        "id":      1,
        "method":  "tools/call",
        "params":  {
            "name":      tool_name,
            "arguments": arguments
        }
    }

    try:
        proc = subprocess.Popen(
            ["node", MCP_SERVER_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Send initialize handshake first (required by MCP protocol)
        init_request = {
            "jsonrpc": "2.0",
            "id":      0,
            "method":  "initialize",
            "params":  {
                "protocolVersion": "2024-11-05",
                "capabilities":    {},
                "clientInfo":      {"name": "murphybot", "version": "1.0"}
            }
        }

        # Write both requests — initialize then tool call
        stdin_input = (
            json.dumps(init_request) + "\n" +
            json.dumps(request)      + "\n"
        )

        stdout, stderr = proc.communicate(
            input=stdin_input,
            timeout=TIMEOUT
        )

        if not stdout.strip():
            log.warning(f"MCP tool {tool_name} returned empty response")
            return {"error": "Empty response from MCP server"}

        # Parse response lines — find the one matching our tool call (id=1)
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                response = json.loads(line)
                if response.get("id") == 1:
                    if "error" in response:
                        return {"error": response["error"].get("message", "MCP error")}
                    result = response.get("result", {})
                    # MCP returns content as array of text blocks
                    content = result.get("content", [])
                    if content and isinstance(content, list):
                        text = content[0].get("text", "")
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            return {"raw": text}
                    return result
            except json.JSONDecodeError:
                continue

        return {"error": "No matching response found in MCP output"}

    except subprocess.TimeoutExpired:
        proc.kill()
        log.warning(f"MCP tool {tool_name} timed out after {TIMEOUT}s")
        return {"error": f"Tool {tool_name} timed out"}
    except Exception as e:
        log.warning(f"MCP tool {tool_name} failed: {e}")
        return {"error": str(e)}


def is_mcp_available() -> bool:
    """
    Check if the MCP server binary exists and is executable.
    Since it's stdio-based, we just verify the file exists.
    """
    return os.path.exists(MCP_SERVER_PATH)