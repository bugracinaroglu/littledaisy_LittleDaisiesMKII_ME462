#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

docker compose -f compose.ros2.yaml up -d --build
docker compose -f compose.ros2.yaml ps
