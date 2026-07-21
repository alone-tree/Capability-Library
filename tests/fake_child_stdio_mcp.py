import json
import os
import subprocess
import sys
from pathlib import Path


child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
Path(os.environ["CHILD_PID_FILE"]).write_text(str(child.pid), encoding="utf-8")

for line in sys.stdin:
    if not line.strip():
        continue
    message = json.loads(line)
    if "id" not in message:
        continue
    method = message.get("method")
    if method == "initialize":
        result = {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "serverInfo": {"name": "fake-child-stdio", "version": "0.1"},
        }
    elif method == "tools/list":
        result = {"tools": []}
    else:
        result = {}
    print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
