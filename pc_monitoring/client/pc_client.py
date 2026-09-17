import socket
import json
from threading import RLock
from typing import Any, Dict, Optional


class ClientPC:
    def __init__(self, host: str, port: int, timeout: Optional[float] = None):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._socket: Optional[socket.socket] = None
        self._socket_lock = RLock()

    def connect(self):
        with self._socket_lock:
            if self._socket is not None:
                return

            connection = socket.create_connection(
                (self._host, self._port),
                timeout=self._timeout,
            )
            if self._timeout is not None:
                connection.settimeout(self._timeout)
            self._socket = connection

    def send_report(self, report: Dict[str, Any]):
        message = (json.dumps(report, separators=(',', ':')) + '\n').encode('utf-8')

        with self._socket_lock:
            if self._socket is None:
                self.connect()

            if self._socket is None:
                raise ConnectionError('ClientPC is not connected')

            self._socket.sendall(message)

    def close(self):
        with self._socket_lock:
            if self._socket is not None:
                self._socket.close()
                self._socket = None