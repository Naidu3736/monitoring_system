import os

if os.name == 'posix':
    print('linux')
elif os.name == 'windows':
    print('windows')