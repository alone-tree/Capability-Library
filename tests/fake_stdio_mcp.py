import json
import sys


TOOLS = [
    {
        "name": "echo",
        "description": "返回输入参数。",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    }
]


def respond(request, result=None, error=None):
    payload = {"jsonrpc": "2.0", "id": request.get("id")}
    if error:
        payload["error"] = error
    else:
        payload["result"] = result
    print(json.dumps(payload, ensure_ascii=False), flush=True)


for line in sys.stdin:
    if not line.strip():
        continue
    message = json.loads(line)
    method = message.get("method")
    if "id" not in message:
        continue
    if method == "initialize":
        respond(message, {"protocolVersion": "2025-03-26", "capabilities": {}, "serverInfo": {"name": "fake-stdio", "version": "0.1"}})
    elif method == "tools/list":
        respond(message, {"tools": TOOLS})
    elif method == "tools/call":
        params = message.get("params", {})
        respond(message, {"content": [{"type": "text", "text": json.dumps(params.get("arguments", {}), ensure_ascii=False)}]})
    else:
        respond(message, error={"code": -32601, "message": f"unknown method: {method}"})
