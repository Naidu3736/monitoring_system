from abc import ABC, abstractmethod

class Alert(ABC):
    @abstractmethod
    def send_alert(self, messege: str, device: str):
        pass