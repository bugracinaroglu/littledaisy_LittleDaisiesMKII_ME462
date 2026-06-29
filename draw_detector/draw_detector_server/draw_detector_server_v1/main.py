"""
main.py — Entry point.

Run:
    python main.py

Then open on the tablet (same Wi-Fi):
    http://littledaisy.local:8000
or:
    http://<pi-ip>:8000
"""

import socket

import uvicorn

import config
from server import app


def _print_access_info():
    print("=" * 50)
    print("LittleDaisy Draw Server")
    print("=" * 50)
    print(f"Listening on:  {config.HOST}:{config.PORT}")

    try:
        hostname = socket.gethostname()
        print(f"Hostname:      http://{hostname}.local:{config.PORT}")
    except Exception:
        pass

    try:
        # This trick reveals the IP the OS would use to reach the internet,
        # without actually sending any packets.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        print(f"LAN IP:        http://{ip}:{config.PORT}")
    except Exception:
        pass

    print("=" * 50)


if __name__ == "__main__":
    _print_access_info()
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level="info",
    )
