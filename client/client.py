import socket
import ssl
import logging
from typing import Optional
from configparser import ConfigParser

# Load configuration
config = ConfigParser()
config.read('server/config.cfg')

HOST = config.get('DEFAULT', 'HOST', fallback='135.181.96.160')
PORT = config.getint('DEFAULT', 'PORT', fallback=44445)
SSL_ENABLED = config.getboolean('DEFAULT', 'SSL_ENABLED', fallback=False)

# Configure the logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def send_query(query: str, host: str = HOST, port: int = PORT, ssl_enabled: Optional[bool] = SSL_ENABLED) -> str:
    client_socket = None
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if ssl_enabled:
            context = ssl.create_default_context()
            client_socket = context.wrap_socket(client_socket, server_hostname=host)

        client_socket.connect((host, port))
        client_socket.send(query.encode())

        response = client_socket.recv(1024).decode().strip()
        logging.debug(f"Received response: {response}")
        return response

    except Exception as e:
        logging.error(f"Error sending query: {e}")
        return "ERROR"

    finally:
        if client_socket:
            client_socket.close()

if __name__ == "__main__":
    query = input("Enter the query string: ")
    response = send_query(query)
    print(f"Server response: {response}")
