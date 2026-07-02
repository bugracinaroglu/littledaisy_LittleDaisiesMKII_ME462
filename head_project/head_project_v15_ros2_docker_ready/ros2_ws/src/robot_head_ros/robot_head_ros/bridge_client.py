import json
import socket
import threading
import uuid


class BridgeConnectionError(RuntimeError):
    pass


class RobotHeadBridgeClient:
    """Persistent JSON-lines client for the Pi host command server."""

    def __init__(self, host="127.0.0.1", port=8765, timeout_sec=1.0):
        self.host = str(host)
        self.port = int(port)
        self.timeout_sec = float(timeout_sec)
        self._socket = None
        self._reader = None
        self._lock = threading.RLock()

    def close(self):
        with self._lock:
            if self._reader is not None:
                try:
                    self._reader.close()
                except Exception:
                    pass
                self._reader = None
            if self._socket is not None:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

    def _connect(self):
        self.close()
        sock = socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout_sec,
        )
        sock.settimeout(self.timeout_sec)
        self._socket = sock
        self._reader = sock.makefile("rb")

    def request(self, command, args=None, retry=True):
        request_id = uuid.uuid4().hex
        payload = {
            "id": request_id,
            "command": str(command),
            "args": args or {},
        }

        with self._lock:
            try:
                if self._socket is None:
                    self._connect()

                wire = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
                self._socket.sendall(wire)
                raw = self._reader.readline()
                if not raw:
                    raise BridgeConnectionError("host bridge closed the connection")

                response = json.loads(raw.decode("utf-8"))
                if response.get("id") != request_id:
                    raise BridgeConnectionError("host bridge response id mismatch")
                return response
            except Exception as exc:
                self.close()
                if retry:
                    return self.request(command, args=args, retry=False)
                raise BridgeConnectionError(str(exc)) from exc

    def ping(self):
        return self.request("ping")

    def status(self):
        return self.request("get_status")
