import pyudev
from threading import Lock
from typing import List, Optional

from pc_monitoring.client.pc_client import ClientPC
from pc_monitoring.monitor import DeviceType, Monitor

class MonitorLinux(Monitor):
    LINUX_FILTERS = {
        DeviceType.KEYBOARD: {'subsystem': 'usb', 'device_type': 'usb_device'},
        DeviceType.MOUSE: {'subsystem': 'usb', 'device_type': 'usb_device'},
        DeviceType.MONITOR: {'subsystem': 'drm', 'device_type': 'drm_minor'},
    }

    def __init__(self, client: Optional[ClientPC] = None):
        super().__init__()        
        self._context = pyudev.Context()
        self._monitor = pyudev.Monitor.from_netlink(context=self._context)
        self._observer: Optional[pyudev.MonitorObserver] = None
        self._devices_lock = Lock()
        self._client = client

        self.__set_filters_by()
        self.__load_connected_devices()


    def __set_filters_by(self):
        for device_type in DeviceType:
            filter_config = self.LINUX_FILTERS.get(device_type)
            subsystem = filter_config.get('subsystem')
            devtype = filter_config.get('device_type')

            if devtype:
                self._monitor.filter_by(subsystem=subsystem, device_type=devtype)
            else:
                self._monitor.filter_by(subsystem=subsystem)

    def __load_connected_devices(self):
        seen_devices = set()

        for filter_config in self.LINUX_FILTERS.values():
            devices = self._context.list_devices(
                subsystem=filter_config['subsystem'],
                DEVTYPE=filter_config.get('device_type'),
            )

            for device in devices:
                device_id = self.__get_device_id(device)
                if device_id in seen_devices:
                    continue

                seen_devices.add(device_id)
                device_info = self._get_device_info(device)
                self._on_device_connected(device_info)

    def __handle_event(self, device: pyudev.Device):
        if device.action not in ['add', 'remove', 'change']:
            return

        if device.action == 'change' and device.subsystem != 'drm':
            return

        device_id = self.__get_device_id(device)
        if device.action == 'remove':
            with self._devices_lock:
                device_info = dict(self._devices.get(device_id, {}))

            if not device_info:
                device_info = self._get_device_info(device)
        else:
            device_info = self._get_device_info(device)

        if device.action == 'remove':
            device_info['action'] = 'remove'
            self._on_device_desconnected(device_id)
        else:
            self._on_device_connected(device_info)

        # self._print_device_info(device_info)
        if self._client is not None:
            self._client.send_report(device_info)
        
    def start_monitor(self):
        if self._is_running:
            return

        self._observer = pyudev.MonitorObserver(
            monitor=self._monitor,
            callback=self.__handle_event,
            name="MonitorLinux"
        )

        self._observer.start()
        self._is_running = True

    def stop_monitor(self):
        if not self._is_running:
            return

        if not self._observer:
            return

        self._observer.stop()
        self._observer = None

        self._is_running = False

    def _on_device_connected(self, device_info: dict):
        device_id = self.__get_device_id(device_info)
        with self._devices_lock:
            self._devices[device_id] = dict(device_info)

    def _on_device_desconnected(self, device_id: str):
        with self._devices_lock:
            self._devices.pop(device_id, None)

    def get_connected_devices(self) -> List[dict]:
        with self._devices_lock:
            return [dict(device) for device in self._devices.values()]

    def _print_device_info(self, device_info):
        print(f"Name: {device_info['device_name']}")
        print(f"Action: {device_info['action']}")
        print(f"Node: {device_info['node']}")
        print(f"Subsystem: {device_info['subsystem']}")
        print(f"Device type: {device_info['devtype']}")
        print(f"System name: {device_info['sys_name']}")
        print(f"-" * 50)

    @staticmethod
    def __get_device_id(device) -> str:
        if isinstance(device, dict):
            return device['sys_name']
        return device.sys_name

    def _get_device_info(self, device: pyudev.Device) -> dict:
        name = (
            device.get('ID_MODEL') or
            device.get('ID_MODEL_ENC') or
            device.get('ID_SERIAL') or
            device.get('DEVNAME') or
            device.sys_name
        )

        return {
            'device_name': name,
            'action': device.action,
            'sys_name': device.sys_name
        }