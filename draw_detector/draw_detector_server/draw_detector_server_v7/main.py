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
    print(
        "Startup output erase: "
        f"{'ON' if config.STARTUP_OUTPUT_ERASE_ENABLED else 'OFF'}"
    )
    print(f"Startup full erase: {'ON' if config.STARTUP_FULL_ERASE_ENABLED else 'OFF'}")
    print("Commands:")
    print("  send_data2robot_arm")
    print("  send_full_erase")
    print("  set_mode difference")
    print("  set_mode full_redraw")
    print("  show_state")
    print("  show_queue")
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
            elif command == "send_full_erase":
                robot_job_manager.send_full_erase(reason="manual")
            elif command.startswith("set_mode "):
                mode = command.split(maxsplit=1)[1].strip()
                selected = robot_job_manager.set_mode(mode)
                print(f"[robot] mode={selected}")
            elif command in ("show_state", "show_queue"):
                print(robot_job_manager.describe_state())
            elif command == "help":
                print(
                    "send_data2robot_arm | send_full_erase | "
                    "set_mode difference | set_mode full_redraw | show_state | show_queue"
                )
            else:
                print(f"Unknown command: {command}. Type 'help'.")
        except Exception as error:
            print(f"[command error] {error}")


def main() -> None:
    # Apply startup cleanup policy. output/ is cleared only when explicitly
    # enabled in config; comparison/job runtime JSON files follow their settings.
    robot_job_manager.reset_for_program_start()
    _print_access_info()

    # Start the FIFO worker before queuing startup work. Startup erase and any
    # later drawing requests are then processed in strict queue order.
    robot_job_manager.start_worker()

    # When enabled, enqueue one path-free erase_all action. The future robot
    # controller owns the physical cleaning trajectory.
    robot_job_manager.send_startup_full_erase_if_enabled()

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
        robot_job_manager.stop_worker()
        server.should_exit = True
        server_thread.join(timeout=3.0)
        cv2.destroyAllWindows()
        print("LittleDaisy stopped.")


if __name__ == "__main__":
    main()
