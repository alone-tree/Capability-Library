"""独立 relay 进程：管理一个 stdio MCP 子进程，对外暴露 HTTP 接口。

用法：python tools/mcp/relay.py <params_json_file>
params_json_file 内容：{command, args, env, cwd}
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp.mcp_client import RelayServer, StdioMcpClient


def main():
    if len(sys.argv) < 2:
        print("Usage: python relay.py <params_file>", file=sys.stderr)
        sys.exit(1)

    params_path = sys.argv[1]
    params = json.loads(Path(params_path).read_text(encoding="utf-8"))

    client = StdioMcpClient(params)
    client.__enter__()

    relay = RelayServer(client)
    port = relay.start()

    print(f"RELAY_READY port={port}", flush=True)

    try:
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        client.__exit__(None, None, None)


if __name__ == "__main__":
    main()
