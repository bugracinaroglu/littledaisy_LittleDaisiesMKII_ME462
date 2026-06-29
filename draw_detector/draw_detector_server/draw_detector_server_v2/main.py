"""Start the tablet server and native Raspberry Pi preview window."""

from __future__ import annotations

import socket
import threading
import time

import cv2
import uvicorn

import config
from native_preview import run_native_preview
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
    print("=" * 62)
    print("LittleDaisy Draw Server + Native Preview")
    print("=" * 62)
    print(f"Tablet page:  http://{hostname}.local:{config.PORT}")
    ip = _local_ip()
    if ip:
        print(f"IP fallback:  http://{ip}:{config.PORT}")
    print("Pi preview:   opens automatically as an OpenCV window")
    print("Close:        press Q or ESC in the preview window")
    print("=" * 62)


def main() -> None:
    _print_access_info()

    uvicorn_config = uvicorn.Config(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)
    server_thread = threading.Thread(
        target=server.run,
        name="little-daisy-web-server",
        daemon=True,
    )
    server_thread.start()

    # Give Uvicorn a brief chance to bind before opening the UI.
    time.sleep(0.35)

    try:
        run_native_preview()
    except cv2.error as error:
        print(f"[preview] OpenCV window could not be opened: {error}")
        print("[preview] The web server is still running. Press Ctrl+C to stop.")
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
