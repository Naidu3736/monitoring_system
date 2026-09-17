import os
import signal
from threading import Event

from client.pc_client import ClientPC


SERVER_HOST = os.getenv('MONITOR_SERVER_HOST', '127.0.0.1')
SERVER_PORT = int(os.getenv('MONITOR_SERVER_PORT', '5000'))
SERVER_TIMEOUT = float(os.getenv('MONITOR_SERVER_TIMEOUT', '10'))


def create_monitor(client: ClientPC):
    if os.name == 'posix':
        from linux_monitoring import MonitorLinux

        return MonitorLinux(client=client)

    if os.name == 'nt':
        from windows_monitoring import MonitorWindows

        return MonitorWindows(client=client)

    raise OSError(f'Unsupported operating system: {os.name}')


def main():
    stop_event = Event()

    def stop_monitor(*_):
        stop_event.set()

    signal.signal(signal.SIGINT, stop_monitor)
    signal.signal(signal.SIGTERM, stop_monitor)

    client = ClientPC(
        host=SERVER_HOST,
        port=SERVER_PORT,
        timeout=SERVER_TIMEOUT,
    )
    monitor = create_monitor(client)

    try:
        client.connect()
        monitor.start_monitor()
        stop_event.wait()
    finally:
        monitor.stop_monitor()
        client.close()


if __name__ == '__main__':
    main()
