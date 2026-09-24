import requests
from .alert import Alert


class TelegramAlert(Alert):

    def __init__(
        self,
        bot_token: str,
        chat_id: str | int,
        timeout: float = 10.0,
    ) -> None:
        if not bot_token:
            raise ValueError("bot_token no puede estar vacío")
        if not str(chat_id):
            raise ValueError("chat_id no puede estar vacío")
        if timeout <= 0:
            raise ValueError("timeout debe ser mayor que cero")

        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._chat_id = str(chat_id)
        self._timeout = timeout

    def send_alert(self, message: str, device: str) -> None:
        text = f"[{device}]\n{message}"
        response = requests.post(
            self._url,
            data={"chat_id": self._chat_id, "text": text},
            timeout=self._timeout,
        )
        response.raise_for_status()

        payload = response.json()
        if not payload.get("ok", False):
            description = payload.get("description", "Error desconocido")
            raise RuntimeError(f"Telegram rechazó la alerta: {description}")