from abc import ABC, abstractmethod
from typing import Dict, Set, List, Any
from enum import Enum

class DeviceType(Enum):
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    MONITOR = "monitor"
    DISK = "disk"
    USB_DEVICE = "usb_device"
    USB_STORAGE = "usb_storage"
    NETWORK = "network"
    SOUND = "sound"
    BLUETOOTH = "bluetooth"

class Monitor(ABC):
    def __init__(self):
        self._device_types: List[DeviceType] = list()
        self._devices: Set[str] = set()
        self._is_running = False

    def set_device_types(self, device_types: List[DeviceType]):
        self._device_types = device_types

    def get_device_types(self) -> List[DeviceType]:
        return self._device_types.copy()

    def add_device_type(self, device_type: DeviceType):
        if device_type not in self._device_types:
            self._device_types.append(device_type)

        self._device_types.append(DeviceType)

    @abstractmethod
    def start_monitor(self):
        pass

    @abstractmethod
    def stop_monitor(self):
        pass

    @abstractmethod
    def on_device_connected(self, device):
        pass

    @abstractmethod
    def on_device_disconnected(self, device):
        pass

    @abstractmethod
    def get_connected_devices(self):
        pass

    @abstractmethod
    def _get_device_info(self, device):
        pass
