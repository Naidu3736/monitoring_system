import pyudev
from monitor import Monitor, DeviceType
from typing import List, Dict, Set, Optional

class MonitorLinux(Monitor):
    LINUX_FILTERS = {
        DeviceType.KEYBOARD: 'usb',
        DeviceType.MOUSE: 'usb' ,
        DeviceType.MONITOR: 'drm',
        DeviceType.DISK: 'block',
        DeviceType.USB_DEVICE: 'usb',
        DeviceType.USB_STORAGE: 'block',
        DeviceType.NETWORK: 'net',
        DeviceType.SOUND: 'sound',
        DeviceType.BLUETOOTH: 'bluetooth',
    }

    def __init__(self, device_types: List[DeviceType]):
        super().__init__()
        if device_types:
            self.set_device_types(device_types)
        
        self._context = pyudev.Context()
        self._monitor = pyudev.Monitor.from_netlink(context=self._context)
        self._observer: Optional[pyudev.MonitorObserver] = None

        self.__set_filters_by()


    def __set_filters_by(self):
        if not self._device_types:
            return

        for device_type in self._device_types:
            subsystem = self.LINUX_FILTERS[device_type]
            print(device_type)
            self._monitor.filter_by(subsystem=subsystem)

    def __handle_event(self, device: pyudev.Device):
        if device.action not in ['add', 'remove']:
            return

        if device.action == 'add':
            self.on_device_connected(device)

        elif device.action == 'remove':
            self.on_device_disconnected(device)
        
    
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

    def on_device_connected(self, device: pyudev.Device):
        device_info = self._get_device_info(device)

        print(f"Name: {device_info['name']}")
        print(f"Action: {device_info['action']}")
        print(f"Node: {device_info['node']}")
        print(f"Subsystem: {device_info['subsystem']}")
        print(f"Device type: {device_info['devtype']}")
        print(f"System name: {device_info['sys_name']}")

    def on_device_disconnected(self, device: pyudev.Device):
        device_info = self._get_device_info(device)

        print(f"Name: {device_info['name']}")
        print(f"Action: {device_info['action']}")
        print(f"Node: {device_info['node']}")
        print(f"Subsystem: {device_info['subsystem']}")
        print(f"Device type: {device_info['devtype']}")
        print(f"System name: {device_info['sys_name']}")

    def get_connected_devices(self):
        pass

    def _get_device_info(self, device: pyudev.Device) -> dict:
        name = (
            device.get('ID_MODEL') or
            device.get('ID_MODEL_ENC') or
            device.get('ID_SERIAL') or
            device.get('DEVNAME') or
            device.sys_name
        )

        return {
            'name': name,
            'action': device.action,
            'node': device.device_node or 'N/A',
            'subsystem': device.subsystem,
            'devtype': device.device_type or "unknow",
            'sys_name': device.sys_name
        }
        

lm = MonitorLinux([
    DeviceType.MOUSE,
    DeviceType.KEYBOARD,
    DeviceType.DISK
])

try:
    lm.start_monitor()
    while True:
        1 + 1

except KeyboardInterrupt:
    lm.stop_monitor()