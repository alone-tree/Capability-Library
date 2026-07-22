"""本地回声 MCP，用于验证能力库的 load/use 基础链路。"""

import json
import sys


def _initialize(_params):
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "本地回声 MCP", "version": "1.0.0"},
    }


def _list_tools(_params):
    return {
        "tools": [
            {
                "name": "echo",
                "description": "把 text 参数原样返回，用于验证 MCP 链路。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "要返回的文本"}
                    },
                    "required": ["text"],
                },
            }
        ]
    }


def _call_tool(params):
    name = params.get("name", "")
    arguments = params.get("arguments", {})
    if name == "echo":
        return {"content": [{"type": "text", "text": arguments.get("text", "")}]}
    return {
        "content": [{"type": "text", "text": f"未知工具: {name}"}],
        "isError": True,
    }


HANDLERS = {
    "initialize": _initialize,
    "tools/list": _list_tools,
    "tools/call": _call_tool,
}


def main():
    sys.stderr.write("[echo_mcp] 本地回声 MCP 已启动\n")
    sys.stderr.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        request_id = request.get("id")
        method = request.get("method", "")
        handler = HANDLERS.get(method)
        if handler:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": handler(request.get("params", {})),
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
