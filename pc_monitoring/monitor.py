from abc import ABC, abstractmethod
from typing import Dict
from enum import Enum

class DeviceType(Enum):
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    MONITOR = "monitor"

class Monitor(ABC):
    def __init__(self):
        self._devices: Dict[str, dict] = {}
        self._is_running = False

    @abstractmethod
    def start_monitor(self):
        pass

    @abstractmethod
    def stop_monitor(self):
        pass

    @abstractmethod
    def _on_device_connected(self):
        pass

    @abstractmethod
    def _on_device_desconnected(self):
        pass

    @abstractmethod
    def get_connected_devices(self):
        pass

    @abstractmethod
    def _get_device_info(self, device):
        pass
