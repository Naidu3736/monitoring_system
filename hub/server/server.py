import json
import os
import socket


HOST = os.getenv('MONITOR_SERVER_HOST', '0.0.0.0')
PORT = int(os.getenv('MONITOR_SERVER_PORT', '5000'))


def handle_client(connection: socket.socket, address):
    print(f'Cliente conectado: {address}')
    with connection, connection.makefile('r', encoding='utf-8') as messages:
        for message in messages:
            try:
                report = json.loads(message)
            except json.JSONDecodeError:
                print(f'Mensaje inválido: {message.rstrip()}')
                continue

            print(f'Reporte recibido: {report}')

    print(f'Cliente desconectado: {address}')


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()
        print(f'Receptor escuchando en {HOST}:{PORT}')

        try:
            while True:
                connection, address = server.accept()
                handle_client(connection, address)
        except KeyboardInterrupt:
            print('\nReceptor detenido')


if __name__ == '__main__':
    main()
