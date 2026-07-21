"""独立 relay 进程：管理一个 stdio MCP 子进程，对外暴露 HTTP 接口。

用法：python tools/mcp/relay.py <params_json_file>
params_json_file 包含 MCP 启动参数、空闲超时、Owner 和进程树策略。
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcp.mcp_client import RelayServer, StdioMcpClient
from lib.caplib import OwnerWatcher, delete_session_if_pid


def main():
    if len(sys.argv) < 2:
        print("Usage: python relay.py <params_file>", file=sys.stderr)
        sys.exit(1)

    params_path = sys.argv[1]
    config_path = Path(params_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config_path.unlink(missing_ok=True)
    params = config.get("mcp", config)
    idle_timeout = float(config.get("idle_timeout", 0))
    owner = config.get("owner")
    owner_watcher = OwnerWatcher(owner["pid"]) if owner else None

    client = StdioMcpClient(params, kill_process_tree=config.get("kill_process_tree", True))
    relay = None
    try:
        client.__enter__()
        relay = RelayServer(client, shutdown_token=config.get("shutdown_token"))
        port = relay.start()
        print(f"RELAY_READY port={port}", flush=True)
        while True:
            if relay.shutdown_requested():
                break
            if owner_watcher and not owner_watcher.is_alive():
                break
            if relay.is_idle(idle_timeout):
                break
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        if relay:
            relay.stop()
        client.__exit__(None, None, None)
        if owner_watcher:
            owner_watcher.close()
        if config.get("mcp_id"):
            delete_session_if_pid(config["mcp_id"], os.getpid())


if __name__ == "__main__":
    main()
