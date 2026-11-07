import smtplib
from email.message import EmailMessage

from .alert import Alert


class EmailAlert(Alert):

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        sender: str,
        recipient: str,
        use_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        required_values = {
            "smtp_host": smtp_host,
            "username": username,
            "password": password,
            "sender": sender,
            "recipient": recipient,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise ValueError(f"Valores SMTP faltantes: {', '.join(missing)}")
        if smtp_port <= 0:
            raise ValueError("smtp_port debe ser mayor que cero")
        if timeout <= 0:
            raise ValueError("timeout debe ser mayor que cero")

        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._username = username
        self._password = password
        self._sender = sender
        self._recipient = recipient
        self._use_tls = use_tls
        self._timeout = timeout

    def send_alert(self, message: str, device: str) -> None:
        email = EmailMessage()
        email["From"] = self._sender
        email["To"] = self._recipient
        email["Subject"] = f"Alerta de monitoreo: {device}"
        email.set_content(f"Dispositivo: {device}\n\n{message}")

        with smtplib.SMTP(
            self._smtp_host,
            self._smtp_port,
            timeout=self._timeout,
        ) as smtp:
            smtp.ehlo()
            if self._use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(self._username, self._password)
            smtp.send_message(email)