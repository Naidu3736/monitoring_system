import wmi
from pc_monitoring.monitor import Monitor, DeviceType
from typing import List, Set, Dict

class MonitorWindows(Monitor):
    WINDOWS_CLASSES = {
        DeviceType.KEYBOARD: 'Win32_Keyboard',
        DeviceType.MOUSE: 'Win32_PointingDevice',
        DeviceType.MONITOR: 'Win32_DesktopMonitor',
        DeviceType.DISK: 'Win32_DiskDrive',
        DeviceType.USB_DEVICE: 'Win32_UsbHub',
        DeviceType.USB_STORAGE: 'Win32_DiskDrive',
        DeviceType.NETWORK: 'Win32_NetworkAdapter',
        DeviceType.SOUND: 'Win32_SoundDevice',
        DeviceType.BLUETOOTH: 'Win32_BluetoothDevice',
    }

    def __init__(self, device_types: List[DeviceType] = None):
        super.__init__()
        if device_types:
            self.set_device_types(device_types)

        self.wmi = wmi.WMI()

    def start_monitor(self):
        pass

    def stop_monitor(self):
        pass

    def on_device_connected(self, device_id):
        pass

    def on_device_disconnected(self, device_id):
        pass

    def get_connected_devices(self):
        pass