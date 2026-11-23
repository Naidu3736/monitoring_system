import json
import os
import selectors
import sys
import socket
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from PyQt6.QtCore import QThread, pyqtSignal


BASE_DIR = Path(__file__).resolve().parent.parent
COLAB_DIR = BASE_DIR / "monitoring_system-main"

if str(COLAB_DIR) not in sys.path:
    sys.path.insert(0, str(COLAB_DIR))

# 2. Importamos las clases de monitoring_system-main directamente desde su carpeta
from hub.alerts.alert import Alert
from hub.alerts.alert_manager import AlertManager
from hub.alerts.email_alert import EmailAlert
from hub.alerts.telegram_alert import TelegramAlert
from hub.server.server import Server

DEFAULT_LOG_PATH = COLAB_DIR / "logs" / "alerts.log"
ENV_FILE_PATH = BASE_DIR / ".env"

ENV_KEYS_CONFIG = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_SENDER",
    "SMTP_RECIPIENT",
    "SMTP_USE_TLS",
    "HUB_HOST",
    "HUB_PORT",
)


def leer_config_env() -> dict[str, str]:
    """Lee las variables de configuración actuales desde .env y entorno."""
    load_dotenv(COLAB_DIR / ".env", override=False)
    load_dotenv(ENV_FILE_PATH, override=True)
    return {clave: os.getenv(clave, "").strip() for clave in ENV_KEYS_CONFIG}


def guardar_config_env(valores: dict[str, str]) -> Path:
    """Guarda los valores de configuración en BASE_DIR/.env preservando otras líneas."""
    lineas_existentes: list[str] = []
    if ENV_FILE_PATH.exists():
        lineas_existentes = ENV_FILE_PATH.read_text(encoding="utf-8").splitlines()

    pendientes = dict(valores)
    nuevas_lineas: list[str] = []

    for linea in lineas_existentes:
        stripped = linea.strip()
        if not stripped or stripped.startswith("#") or "=" not in linea:
            nuevas_lineas.append(linea)
            continue
        clave = linea.split("=", 1)[0].strip()
        if clave in pendientes:
            val = pendientes.pop(clave).replace("\n", "").replace("\r", "")
            nuevas_lineas.append(f"{clave}={val}")
            os.environ[clave] = val
        else:
            nuevas_lineas.append(linea)

    for clave, val in pendientes.items():
        limpio = val.replace("\n", "").replace("\r", "")
        nuevas_lineas.append(f"{clave}={limpio}")
        os.environ[clave] = limpio

    ENV_FILE_PATH.write_text("\n".join(nuevas_lineas) + "\n", encoding="utf-8")
    return ENV_FILE_PATH


def construir_alertas_desde_env(override: bool = False) -> tuple[list[Alert], bool, bool]:
    """Busca variables .env en SS_WIN (prioritario) o en monitoring_system-main."""
    if override:
        load_dotenv(COLAB_DIR / ".env", override=True)
        load_dotenv(ENV_FILE_PATH, override=True)
    else:
        load_dotenv(ENV_FILE_PATH, override=False)
        load_dotenv(COLAB_DIR / ".env", override=False)

    alerts: list[Alert] = []
    tiene_tg = False
    tiene_smtp = False

    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if tg_token and tg_chat:
        try:
            alerts.append(TelegramAlert(tg_token, tg_chat))
            tiene_tg = True
        except Exception:
            pass

    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port_str = os.getenv("SMTP_PORT", "").strip()
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_sender = os.getenv("SMTP_SENDER", "").strip()
    smtp_recipient = os.getenv("SMTP_RECIPIENT", "").strip()

    if all([smtp_host, smtp_port_str, smtp_user, smtp_pass, smtp_sender, smtp_recipient]):
        try:
            alerts.append(
                EmailAlert(
                    smtp_host=smtp_host,
                    smtp_port=int(smtp_port_str),
                    username=smtp_user,
                    password=smtp_pass,
                    sender=smtp_sender,
                    recipient=smtp_recipient,
                    use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
                )
            )
            tiene_smtp = True
        except Exception:
            pass

    return alerts, tiene_tg, tiene_smtp


class GuiInterceptServer(Server):
    """Subclase de Server (hub/server/server.py) que conecta los sockets con PyQt6."""
    def __init__(
        self,
        host: str,
        port: int,
        alert_manager: AlertManager,
        bridge_thread: "HubServerThread",
    ) -> None:
        super().__init__(host=host, port=port, alert_manager=alert_manager, timeout=0.5)
        self._bridge = bridge_thread
        self._running = False
        self._peer_addrs: dict[int, str] = {}
        self._fd_pc_names: dict[int, str] = {}

    def serve_loop(self) -> None:
        self._running = True
        try:
            while self._running:
                events = self._sel.select(timeout=self._timeout)
                for key, _ in events:
                    callback = key.data
                    callback(key.fileobj)
        except Exception as exc:
            if self._running:
                self._bridge.log_signal.emit(f"[ERROR SOCKET HUB] {exc}")
        finally:
            self.close()

    def stop_loop(self) -> None:
        self._running = False

    def _accept(self, sock: socket.socket) -> None:
        client, addr = sock.accept()
        client.setblocking(False)
        fd = client.fileno()
        peer = f"{addr[0]}:{addr[1]}"
        self._buffers[fd] = bytearray()
        self._peer_addrs[fd] = peer
        self._sel.register(client, selectors.EVENT_READ, self._read)
        self._bridge.agente_conectado.emit(peer)
        self._bridge.log_signal.emit(f"Nuevo agente conectado al Hub desde <b>{peer}</b>.")

    def _read(self, sock: socket.socket) -> None:
        fd = sock.fileno()
        try:
            data = sock.recv(4096)
        except (ConnectionResetError, BrokenPipeError, OSError):
            self._disconnect(sock)
            return

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
                try:
                    report = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    peer = self._peer_addrs.get(fd, "desconocido")
                    self._bridge.log_signal.emit(
                        f"<span style='color:#f59e0b;'>Mensaje JSON inválido desde {peer}: {exc}</span>"
                    )
                    continue
                if isinstance(report, dict):
                    self._on_message(sock, report)

    def _on_message(self, sock: socket.socket, report: dict[str, Any]) -> None:
        required_fields = {"pc_name", "device_name", "action", "sys_name"}
        missing_fields = required_fields - report.keys()
        if missing_fields:
            self._bridge.log_signal.emit(
                f"Reporte inválido recibido; faltan: {', '.join(sorted(missing_fields))}"
            )
            return

        fd = sock.fileno()
        pc_name = str(report["pc_name"]).strip().upper()
        peer = self._peer_addrs.get(fd, "desconocido")
        self._fd_pc_names[fd] = pc_name

        payload = dict(report)
        payload["peer"] = peer

        # Mandar el evento a las tarjetas y tabla de la interfaz
        self._bridge.reporte_recibido.emit(payload)

        # Mandar el evento al AlertManager (Telegram / SMTP / alerts.log)
        mensaje = (
            f"Acción '{report['action']}' en el dispositivo "
            f"'{report['device_name']}/{report['sys_name']}'"
        )
        entregado = self._alert_manager.process(message=mensaje, device=pc_name)
        self._bridge.alerta_procesada.emit(pc_name, entregado)

    def _disconnect(self, sock: socket.socket) -> None:
        fd = sock.fileno()
        peer = self._peer_addrs.pop(fd, "desconocido")
        pc_name = self._fd_pc_names.pop(fd, "")
        super()._disconnect(sock)
        self._bridge.agente_desconectado.emit(pc_name, peer)
        if pc_name:
            self._bridge.log_signal.emit(
                f"<span style='color:#f59e0b;'>Agente <b>{pc_name}</b> ({peer}) desconectado del Hub.</span>"
            )
        else:
            self._bridge.log_signal.emit(
                f"<span style='color:#94a3b8;'>Conexión de agente ({peer}) cerrada.</span>"
            )


class HubServerThread(QThread):
    reporte_recibido = pyqtSignal(dict)
    alerta_procesada = pyqtSignal(str, bool)
    log_signal = pyqtSignal(str)
    canales_configurados = pyqtSignal(bool, bool)
    hub_estado_cambiado = pyqtSignal(bool, str)
    agente_conectado = pyqtSignal(str)
    agente_desconectado = pyqtSignal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self._server: GuiInterceptServer | None = None
        self._alert_manager: AlertManager | None = None
        self.log_file_path = DEFAULT_LOG_PATH

    def run(self) -> None:
        alerts, tiene_tg, tiene_smtp = construir_alertas_desde_env()
        self.canales_configurados.emit(tiene_tg, tiene_smtp)

        log_env = os.getenv("ALERT_LOG_FILE")
        self.log_file_path = Path(log_env) if log_env else DEFAULT_LOG_PATH
        self._alert_manager = AlertManager(alerts=alerts, log_file=self.log_file_path)

        host = os.getenv("HUB_HOST", "0.0.0.0")
        port = int(os.getenv("HUB_PORT", "5000"))

        self._server = GuiInterceptServer(
            host=host,
            port=port,
            alert_manager=self._alert_manager,
            bridge_thread=self,
        )

        try:
            self._server.start()
            self.hub_estado_cambiado.emit(True, f"{host}:{port}")
            self.log_signal.emit(
                f"Hub escuchando agentes en <b>{host}:{port}</b> "
                f"(Log: <i>monitoring_system-main/logs/{self.log_file_path.name}</i>)"
            )
            self._server.serve_loop()
        except Exception as exc:
            self.hub_estado_cambiado.emit(False, f"Error puerto {port}")
            self.log_signal.emit(
                f"<span style='color:#f43f5e;'>No se pudo abrir el puerto {port}: {exc}</span>"
            )
        finally:
            if self._alert_manager is not None:
                self._alert_manager.close()

    def recargar_canales(self) -> tuple[bool, bool]:
        """Recarga Telegram/SMTP desde .env y actualiza el AlertManager en caliente."""
        alerts, tiene_tg, tiene_smtp = construir_alertas_desde_env(override=True)
        if self._alert_manager is not None:
            self._alert_manager._alerts = tuple(alerts)
        self.canales_configurados.emit(tiene_tg, tiene_smtp)
        self.log_signal.emit(
            "Canales de alerta recargados desde .env "
            f"(Telegram: {'activo' if tiene_tg else 'sin configurar'}, "
            f"SMTP: {'activo' if tiene_smtp else 'sin configurar'})."
        )
        return tiene_tg, tiene_smtp

    def detener(self) -> None:
        if self._server is not None:
            self._server.stop_loop()
        self.wait(1500)