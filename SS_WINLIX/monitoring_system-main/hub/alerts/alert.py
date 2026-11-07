from abc import ABC, abstractmethod


class Alert(ABC):
    @abstractmethod
    def send_alert(self, message: str, device: str) -> None:
        pass