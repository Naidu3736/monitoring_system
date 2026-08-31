from windows_monitoring import MonitorWindows

import os

def select_os():
    if os.name == 'poxis':
        print('linux')
        # return 
    elif os.name == 'nt':
        print('windows')
        # return MonitorWindows

def main():
    pass

if __name__ == "main":
    main()