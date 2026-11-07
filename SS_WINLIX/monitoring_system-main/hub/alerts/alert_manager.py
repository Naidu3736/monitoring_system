import logging
from collections.abc import Iterable
from pathlib import Path

from .alert import Alert


class AlertManager:
    def __init__(
        self,
        alerts: Iterable[Alert] = (),
        log_file: str | Path = "alerts.log",
    ) -> None:
        self._alerts = tuple(alerts)
        self._logger = logging.getLogger("monitoring.alerts")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._handler = logging.FileHandler(log_path, encoding="utf-8")
        self._handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        self._logger.addHandler(self._handler)

    def process(self, message: str, device: str) -> bool:
        if not message:
            raise ValueError("message no puede estar vacío")
        if not device:
            raise ValueError("device no puede estar vacío")

        self._logger.info("Alerta recibida device=%s message=%s", device, message)
        delivered = True

        for alert in self._alerts:
            channel = type(alert).__name__
            try:
                alert.send_alert(message, device)
            except Exception:
                delivered = False
                self._logger.exception(
                    "No se pudo enviar la alerta channel=%s device=%s",
                    channel,
                    device,
                )
            else:
                self._logger.info(
                    "Alerta enviada channel=%s device=%s",
                    channel,
                    device,
                )

        if not self._alerts:
            self._logger.warning(
                "Alerta registrada sin canales de envío device=%s",
                device,
            )

        return delivered

    def close(self) -> None:
        self._handler.flush()
        self._logger.removeHandler(self._handler)
        self._handler.close()