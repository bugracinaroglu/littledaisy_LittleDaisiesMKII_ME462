#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."

printf '%s\n' '=== Pi host bridge ==='
python3 - <<'PY'
import json
import socket
import uuid

payload = {"id": uuid.uuid4().hex, "command": "ping", "args": {}}
try:
    with socket.create_connection(("127.0.0.1", 8765), timeout=1.0) as sock:
        sock.sendall((json.dumps(payload) + "\n").encode())
        response = sock.makefile("rb").readline().decode().strip()
        print(response)
except Exception as exc:
    print("UNAVAILABLE:", exc)
PY

printf '\n%s\n' '=== Docker container ==='
docker compose -f compose.ros2.yaml ps 2>/dev/null || true

printf '\n%s\n' '=== ROS bridge logs ==='
docker compose -f compose.ros2.yaml logs --tail=25 robot_head_ros 2>/dev/null || true
