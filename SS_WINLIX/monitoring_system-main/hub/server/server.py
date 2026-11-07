import json
import socket
import selectors
from typing import Dict, Optional

from hub.alerts.alert_manager import AlertManager

class Server:
    def __init__(
        self,
        host: str,
        port: int,
        alert_manager: AlertManager,
        timeout: Optional[float] = None,
    ):
        self._host = host
        self._port = port
        self._alert_manager = alert_manager
        self._timeout = timeout
        self._socket: Optional[socket.socket] = None
        self._sel = selectors.DefaultSelector()
        self._buffers: Dict[int, bytearray] = {}  

    def start(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self._host, self._port))
        self._socket.listen()
        self._socket.setblocking(False)
        self._sel.register(self._socket, selectors.EVENT_READ, self._accept)

    def serve_forever(self) -> None:
        try:
            while True:
                events = self._sel.select(timeout=self._timeout)
                for key, mask in events:
                    callback = key.data        
                    callback(key.fileobj)      
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def _accept(self, sock: socket.socket) -> None:
        """El listener tiene una conexión pendiente."""
        client, addr = sock.accept()
        client.setblocking(False)
        self._buffers[client.fileno()] = bytearray()
        self._sel.register(client, selectors.EVENT_READ, self._read)
        print(f"[+] {addr}")

    def _read(self, sock: socket.socket) -> None:
        fd = sock.fileno()
        data = sock.recv(4096)
        if not data:
            self._disconnect(sock)
            return

        buf = self._buffers[fd]
        buf.extend(data)

        while b"\n" in buf:
            line, _, rest = buf.partition(b"\n")
            buf.clear()
            buf.extend(rest)
            if line:
                self._on_message(sock, json.loads(line))

    def _on_message(self, sock: socket.socket, report: dict) -> None:
        required_fields = {"pc_name", "device_name", "action", "sys_name"}
        missing_fields = required_fields - report.keys()
        if missing_fields:
            print(
                f"[!] Reporte inválido de {sock.getpeername()}: "
                f"faltan {', '.join(sorted(missing_fields))}"
            )
            return

        print(f"[<] {sock.getpeername()}: {report}")
        self._alert_manager.process(
            message=(
                f"Acción '{report['action']}' en el dispositivo "
                f"'{report['device_name']}/{report['sys_name']}'"
            ),
            device=f"{report['pc_name']}",
        )

    def _disconnect(self, sock: socket.socket) -> None:
        self._buffers.pop(sock.fileno(), None)
        self._sel.unregister(sock)
        sock.close()

    def close(self) -> None:
        for key in list(self._sel.get_map().values()):
            try:
                self._sel.unregister(key.fileobj)
                key.fileobj.close()
            except Exception:
                pass
        self._sel.close()
        if self._socket is not None:
            self._socket.close()