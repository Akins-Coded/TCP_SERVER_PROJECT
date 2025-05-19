import socket
import ssl
import logging
from typing import Optional
from configparser import ConfigParser

# Load configuration
config = ConfigParser()
config.read('server/config.cfg')
HOST: str = config.get('DEFAULT', 'HOST', fallback='135.181.96.160')
PORT: int = config.getint('DEFAULT', 'PORT', fallback=44445)
SSL_ENABLED: bool = config.getboolean('DEFAULT', 'SSL_ENABLED', fallback=False)

# Configure the logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def send_query(query: str, host: str = HOST, port: int = PORT, ssl_enabled: Optional[bool] = SSL_ENABLED) -> str:
    """
    Sends a query to the server and returns the response.

    Args:
        query: The string to send to the server.
        host: The server hostname or IP address (default: from config).
        port: The server port number (default: from config).
        ssl_enabled: Whether to use SSL (default: from config).

    Returns:
        The server's response as a string, or "ERROR" if an error occurs.
    """
    client_socket: Optional[socket.socket] = None
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if ssl_enabled:
            context = ssl.create_default_context()
            client_socket = context.wrap_socket(client_socket, server_hostname=host)
        client_socket.connect((host, port))
        client_socket.send(query.encode())
        response: str = client_socket.recv(1024).decode().strip()
        logging.debug(f"Received response: {response}")
        return response
    except Exception as e:
        logging.error(f"Error sending query: {e}")
        return "ERROR"
    finally:
        if client_socket:
            client_socket.close()


if __name__ == "__main__":
    query: str = input("Enter the query string: ")
    response: str = send_query(query)
    print(f"Server response: {response}")