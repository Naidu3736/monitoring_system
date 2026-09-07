import pyudev
from monitor import Monitor, DeviceType
from typing import List, Dict, Set, Optional

class MonitorLinux(Monitor):
    LINUX_FILTERS = {
        DeviceType.KEYBOARD: {'subsystem': 'usb', 'device_type': 'usb_device'},
        DeviceType.MOUSE: {'subsystem': 'usb', 'device_type': 'usb_device'},
        DeviceType.MONITOR: {'subsystem': 'drm', 'device_type': 'drm_minor'},
    }

    def __init__(self):
        super().__init__()        
        self._context = pyudev.Context()
        self._monitor = pyudev.Monitor.from_netlink(context=self._context)
        self._observer: Optional[pyudev.MonitorObserver] = None

        self.__set_filters_by()


    def __set_filters_by(self):
        for device_type in DeviceType:
            filter_config = self.LINUX_FILTERS.get(device_type)
            subsystem = filter_config.get('subsystem')
            devtype = filter_config.get('device_type')

            if devtype:
                self._monitor.filter_by(subsystem=subsystem, device_type=devtype)
            else:
                self._monitor.filter_by(subsystem=subsystem)

    def __handle_event(self, device: pyudev.Device):
        if device.action not in ['add', 'remove', 'change']:
            return

        device_info = None
        
        if (device.action == 'change' and device.subsystem != 'drm'):
            return

        else:
            device_info = self._get_device_info(device)

        self._print_device_info(device_info)
        
    
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

    def _on_device_connected(self):
        pass

    def _on_device_desconnected(self):
        pass

    def get_connected_devices(self):
        pass

    def _print_device_info(self, device_info):
        print(f"Name: {device_info['name']}")
        print(f"Action: {device_info['action']}")
        print(f"Node: {device_info['node']}")
        print(f"Subsystem: {device_info['subsystem']}")
        print(f"Device type: {device_info['devtype']}")
        print(f"System name: {device_info['sys_name']}")
        print(f"-" * 50)

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
        

lm = MonitorLinux()

try:
    lm.start_monitor()
    while True:
        1 + 1

except KeyboardInterrupt:
    lm.stop_monitor()