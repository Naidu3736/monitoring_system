import pyudev

def event(device: pyudev.Device):
    nombre = (
        device.get('ID_MODEL') or
        device.get('ID_MODEL_ENC') or  
        device.get('ID_SERIAL') or
        device.get('DEVNAME') or
        device.sys_name
    )
    
    print(f"Dispositivo: {device.device_node}")
    print(f"  Nombre: {nombre}")
    print(f"  Tipo: {device.device_type or 'No especificado'}")
    print(f"  Subsistema: {device.subsystem}")
    print(f"  Action: {device.action}")
    print("-" * 50)

def main():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context=context)
    monitor.filter_by(subsystem='usb', device_type='usb_device')

    observer = pyudev.MonitorObserver(
        monitor=monitor,
        callback=event
    )

    observer.start()


if __name__ == '__main__':
    main()