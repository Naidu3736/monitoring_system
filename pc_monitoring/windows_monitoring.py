import wmi

class MonitorWindows:
    def __init__(self, logger = None):
        self.wmi = wmi.WMI()
        self.logger = logger
        self.connected_devices = {}
        self.devices_classes = [
            'Win32_UsbHub',             # Hub's usb
            'Win32_PnPEntity',          # Dispositivos plug and play
            'Win32_DiskDrive',          # Discos y usb's
            'Win32_Keyboard',           # Teclados
            'Win32_PointingDevice',     # Ratones y dispositivos apuntadores
            'Win32_NetworkAdapter',     # Adaptadores de red 
            'Win32_SoundDevice',        # Dispositivos de audio
            'Win32_BluetoothDevice',    # Dispositivos Bluetooth
            'Win32_DesktopMonitor',     # Pantallas
        ]

    def _scan_devices(self):
        self.connected_devices = {}

        for device_class in self.devices_classes:
            try:
                # print(f"\n--- {device_class} ---")
                wql = f"SELECT * FROM {device_class}"
                items = self.wmi.query(wql)
                for item in items:
                    try:
                        device_id = (
                            getattr(item, "PNPDeviceID", None)
                            or getattr(item, "DeviceID", None)
                            or getattr(item, "Name", None)
                        )
                        device_name = (
                            getattr(item, "Name", None)
                            or getattr(item, "Caption", None)
                            or "Unknown"
                        )
                        if device_id:
                            self.connected_devices[device_id] = device_name
                    except Exception:
                        continue
            except Exception:
                continue

    def get_connected_devices(self):
        self._scan_devices()

        for _, device_name in self.connected_devices.items():
            print(device_name)

monitor = MonitorWindows()
monitor.get_connected_devices()