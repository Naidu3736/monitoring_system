import logging
import os

from dotenv import load_dotenv

from hub.alerts.alert import Alert
from hub.alerts.alert_manager import AlertManager
from hub.alerts.email_alert import EmailAlert
from hub.alerts.telegram_alert import TelegramAlert
from hub.server.server import Server


def _build_alerts() -> list[Alert]:
    alerts: list[Alert] = []

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if telegram_token or telegram_chat_id:
        if not telegram_token or not telegram_chat_id:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID deben configurarse juntos"
            )
        alerts.append(TelegramAlert(telegram_token, telegram_chat_id))

    smtp_values = {
        "SMTP_HOST": os.getenv("SMTP_HOST"),
        "SMTP_PORT": os.getenv("SMTP_PORT"),
        "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
        "SMTP_SENDER": os.getenv("SMTP_SENDER"),
        "SMTP_RECIPIENT": os.getenv("SMTP_RECIPIENT"),
    }
    configured_smtp = any(smtp_values.values())
    if configured_smtp:
        missing = [name for name, value in smtp_values.items() if not value]
        if missing:
            raise RuntimeError(
                f"Configuración SMTP incompleta; faltan: {', '.join(missing)}"
            )
        try:
            smtp_port = int(smtp_values["SMTP_PORT"])
        except ValueError as error:
            raise RuntimeError("SMTP_PORT debe ser un número entero") from error

        alerts.append(
            EmailAlert(
                smtp_host=smtp_values["SMTP_HOST"],
                smtp_port=smtp_port,
                username=smtp_values["SMTP_USERNAME"],
                password=smtp_values["SMTP_PASSWORD"],
                sender=smtp_values["SMTP_SENDER"],
                recipient=smtp_values["SMTP_RECIPIENT"],
                use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            )
        )

    return alerts


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    alert_manager = AlertManager(
        alerts=_build_alerts(),
        log_file=os.getenv("ALERT_LOG_FILE", "logs/alerts.log"),
    )
    server = Server(
        host=os.getenv("HUB_HOST", "0.0.0.0"),
        port=int(os.getenv("HUB_PORT", "5000")),
        alert_manager=alert_manager,
    )

    try:
        server.start()
        logging.getLogger(__name__).info(
            "Hub escuchando en %s:%s", os.getenv("HUB_HOST", "0.0.0.0"),
            os.getenv("HUB_PORT", "5000"),
        )
        server.serve_forever()
    finally:
        alert_manager.close()


if __name__ == "__main__":
    main()
