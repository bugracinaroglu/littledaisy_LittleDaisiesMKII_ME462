"""Start the tablet server, terminal command listener and native Pi preview."""

from __future__ import annotations

import socket
import threading
import time

import cv2
import uvicorn

import config
from native_preview import run_native_preview
from robot_jobs import robot_job_manager
from server import app


def _local_ip() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return None
    finally:
        sock.close()


def _print_access_info() -> None:
    hostname = socket.gethostname()
    print("=" * 76)
    print("LittleDaisy Draw Server + Detect Snapshot + Robot Job Planner")
    print("=" * 76)
    print(f"Tablet page:  http://{hostname}.local:{config.PORT}")
    ip = _local_ip()
    if ip:
        print(f"IP fallback:  http://{ip}:{config.PORT}")
    print("Pi preview:   opens automatically as a three-panel OpenCV window")
    print("Commands:")
    print("  send_data2robot_arm")
    print("  set_mode difference")
    print("  set_mode full_redraw")
    print("  show_state")
    print("  help")
    print("=" * 76)


def _command_loop() -> None:
    while True:
        try:
            command = input("little-daisy> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not command:
            continue
        try:
            if command == "send_data2robot_arm":
                robot_job_manager.send_latest_to_robot()
            elif command.startswith("set_mode "):
                mode = command.split(maxsplit=1)[1].strip()
                selected = robot_job_manager.set_mode(mode)
                print(f"[robot] mode={selected}")
            elif command == "show_state":
                print(robot_job_manager.describe_state())
            elif command == "help":
                print("send_data2robot_arm | set_mode difference | set_mode full_redraw | show_state")
            else:
                print(f"Unknown command: {command}. Type 'help'.")
        except Exception as error:
            print(f"[command error] {error}")


def main() -> None:
    _print_access_info()
    uvicorn_config = uvicorn.Config(app, host=config.HOST, port=config.PORT, log_level="info")
    server = uvicorn.Server(uvicorn_config)
    server_thread = threading.Thread(
        target=server.run, name="little-daisy-web-server", daemon=True
    )
    server_thread.start()

    command_thread = threading.Thread(
        target=_command_loop, name="little-daisy-command-console", daemon=True
    )
    command_thread.start()
    time.sleep(0.35)

    try:
        run_native_preview()
    except cv2.error as error:
        print(f"[preview] OpenCV window could not be opened: {error}")
        print("[preview] The web server and terminal commands remain active. Ctrl+C stops.")
        try:
            while server_thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
    except KeyboardInterrupt:
        pass
    finally:
        server.should_exit = True
        server_thread.join(timeout=3.0)
        cv2.destroyAllWindows()
        print("LittleDaisy stopped.")


if __name__ == "__main__":
    main()
