import json
from http.server import BaseHTTPRequestHandler, HTTPServer


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


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        message = json.loads(self.rfile.read(length).decode("utf-8"))
        method = message.get("method")
        if method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        if method == "initialize":
            result = {"protocolVersion": "2025-03-26", "capabilities": {}, "serverInfo": {"name": "fake-http", "version": "0.1"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = {"content": [{"type": "text", "text": json.dumps(message.get("params", {}).get("arguments", {}), ensure_ascii=False)}]}
        else:
            self.write_json({"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": -32601, "message": f"unknown method: {method}"}})
            return
        self.write_json({"jsonrpc": "2.0", "id": message.get("id"), "result": result})

    def log_message(self, fmt, *args):
        return

    def write_json(self, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
