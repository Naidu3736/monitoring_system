import os
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


def construir_alertas_desde_env() -> tuple[list[Alert], bool, bool]:
    """Busca variables .env en SS_WIN o en monitoring_system-main."""
    load_dotenv(BASE_DIR / ".env")
    load_dotenv(COLAB_DIR / ".env")

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
        super()._accept(sock)
        self._bridge.log_signal.emit("Nuevo agente conectado al socket del Hub.")

    def _on_message(self, sock: socket.socket, report: dict[str, Any]) -> None:
        required_fields = {"pc_name", "device_name", "action", "sys_name"}
        missing_fields = required_fields - report.keys()
        if missing_fields:
            self._bridge.log_signal.emit(
                f"Reporte inválido recibido; faltan: {', '.join(sorted(missing_fields))}"
            )
            return

        # Mandar el evento a las tarjetas y tabla de la interfaz 
        self._bridge.reporte_recibido.emit(dict(report))

        # Mandar el evento al AlertManager **
        pc_name = str(report["pc_name"])
        mensaje = (
            f"Acción '{report['action']}' en el dispositivo "
            f"'{report['device_name']}/{report['sys_name']}'"
        )
        entregado = self._alert_manager.process(message=mensaje, device=pc_name)
        self._bridge.alerta_procesada.emit(pc_name, entregado)


class HubServerThread(QThread):
    reporte_recibido = pyqtSignal(dict)
    alerta_procesada = pyqtSignal(str, bool)
    log_signal = pyqtSignal(str)
    canales_configurados = pyqtSignal(bool, bool)

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
            self.log_signal.emit(
                f"Hub escuchando agentes en <b>{host}:{port}</b> "
                f"(Log: <i>monitoring_system-main/logs/{self.log_file_path.name}</i>)"
            )
            self._server.serve_loop()
        except Exception as exc:
            self.log_signal.emit(
                f"<span style='color:#f43f5e;'>No se pudo abrir el puerto {port}: {exc}</span>"
            )
        finally:
            if self._alert_manager is not None:
                self._alert_manager.close()

    def simular_evento_local(
        self, pc_name: str, device_name: str, action: str, sys_name: str
    ) -> None:
        report = {
            "pc_name": pc_name,
            "device_name": device_name,
            "action": action,
            "sys_name": sys_name,
        }
        self.reporte_recibido.emit(report)
        if self._alert_manager is not None:
            mensaje = f"Acción '{action}' en el dispositivo '{device_name}/{sys_name}'"
            entregado = self._alert_manager.process(message=mensaje, device=pc_name)
            self.alerta_procesada.emit(pc_name, entregado)

    def detener(self) -> None:
        if self._server is not None:
            self._server.stop_loop()
        self.wait(1500)