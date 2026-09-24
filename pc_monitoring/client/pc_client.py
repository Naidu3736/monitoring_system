import socket
import json
import platform
from threading import RLock
from typing import Any, Dict, Optional


class ClientPC:
    def __init__(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        pc_name: Optional[str] = None,
    ):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._pc_name = pc_name or platform.node()
        self._socket: Optional[socket.socket] = None
        self._socket_lock = RLock()

    def connect(self):
        with self._socket_lock:
            if self._socket is not None:
                return

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.settimeout(self._timeout)
                s.connect((self._host, self._port))
            except OSError as e:
                s.close()
                raise ConnectionError(f"No se pudo conectar: {e}")
            self._socket = s


    def send_report(self, report: Dict[str, Any]) -> None:
        message_data = {
            "pc_name": self._pc_name,
            **report,
        }
        message = (
            json.dumps(message_data, separators=(",", ":")) + "\n"
        ).encode("utf-8")

        with self._socket_lock:
            if self._socket is None:
                self.connect()

            if self._socket is None:
                raise ConnectionError('ClientPC no esta conectado')

            self._socket.sendall(message)

    def close(self):
        with self._socket_lock:
            if self._socket is not None:
                self._socket.close()
                self._socket = None