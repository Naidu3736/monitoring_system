from threading import Event, Lock, Thread
from typing import Any, Dict, List, Optional

import wmi

from pc_monitoring.client.pc_client import ClientPC
from pc_monitoring.monitor import DeviceType, Monitor


class MonitorWindows(Monitor):
    WINDOWS_CLASSES = {
        DeviceType.KEYBOARD: 'Win32_Keyboard',
        DeviceType.MOUSE: 'Win32_PointingDevice',
        DeviceType.MONITOR: 'Win32_DesktopMonitor',
    }

    def __init__(self, client: Optional[ClientPC] = None,):
        super().__init__()
        self._device_types = list(DeviceType)
        self._client = client
        self._devices_lock = Lock()
        self._stop_event = Event()
        self._workers: List[Thread] = []
        self._is_running = False
        self._wmi = wmi.WMI()

        self.__load_connected_devices()

    def __load_connected_devices(self):
        for device_type in self._device_types:
            class_name = self.WINDOWS_CLASSES[device_type]
            for device in getattr(self._wmi, class_name)():
                device_info = self._get_device_info(device, device_type)
                device_info['action'] = 'add'
                self._on_device_connected(device_info)

    def start_monitor(self):
        if self._is_running:
            return

        self._stop_event.clear()
        self._workers = []

        for device_type in self._device_types:
            for action in ('Creation', 'Deletion', 'Modification'):
                worker = Thread(
                    target=self.__consume_watcher,
                    args=(device_type, action),
                    name=f'MonitorWindows-{device_type.value}-{action}',
                    daemon=True,
                )
                worker.start()
                self._workers.append(worker)

        self._is_running = True

    def stop_monitor(self):
        if not self._is_running:
            return

        self._stop_event.set()
        for worker in self._workers:
            worker.join(timeout=2)

        self._workers = []
        self._is_running = False

    def __consume_watcher(self, device_type: DeviceType, action: str):
        connection = wmi.WMI()
        watcher = connection.watch_for(
            notification_type=action,
            wmi_class=self.WINDOWS_CLASSES[device_type],
        )

        while not self._stop_event.is_set():
            try:
                device = watcher(timeout_ms=1000)
            except wmi.x_wmi_timed_out:
                continue

            device_info = self._get_device_info(device, device_type)
            device_info['action'] = {
                'Creation': 'add',
                'Deletion': 'remove',
                'Modification': 'change',
            }[action]
            if action == 'Deletion':
                self._on_device_disconnected(device_info['sys_name'])
            else:
                self._on_device_connected(device_info)

            self.__send_report(device_info)

    def _on_device_connected(self, device_info: dict):
        device_id = device_info['sys_name']
        with self._devices_lock:
            self._devices[device_id] = dict(device_info)

    def _on_device_disconnected(self, device_id: str):
        with self._devices_lock:
            self._devices.pop(device_id, None)

    def _on_device_desconnected(self, device_id: str):
        self._on_device_disconnected(device_id)

    def get_connected_devices(self) -> List[dict]:
        with self._devices_lock:
            return [dict(device) for device in self._devices.values()]

    def _get_device_info(self, device: Any, device_type: DeviceType) -> Dict[str, Any]:
        device_id = self.__get_device_id(device)
        return {
            'device_name': self.__get_property(device, 'Name') or device_id,
            'action': 'change',
            'sys_name': device_id,
        }

    @staticmethod
    def __get_device_id(device: Any) -> str:
        return (
            MonitorWindows.__get_property(device, 'PNPDeviceID')
            or MonitorWindows.__get_property(device, 'DeviceID')
            or MonitorWindows.__get_property(device, 'Name')
        )

    @staticmethod
    def __get_property(device: Any, name: str) -> Optional[str]:
        value = getattr(device, name, None)
        return str(value) if value is not None else None

    def __send_report(self, device_info: dict):
        if self._client is not None:
            self._client.send_report(device_info)
