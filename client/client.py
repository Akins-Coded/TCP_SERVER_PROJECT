import socket
import ssl
import logging
import argparse
from typing import Optional
from configparser import ConfigParser

# Load configuration
config = ConfigParser()
config.read('server/config.cfg')

HOST: str = config.get('DEFAULT', 'HOST', fallback='127.0.0.1')
PORT: int = config.getint('DEFAULT', 'PORT', fallback=44445)
SSL_ENABLED: bool = config.getboolean('DEFAULT', 'SSL_ENABLED', fallback=False)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_query(query: str, host: str = HOST, port: int = PORT, ssl_enabled: bool = SSL_ENABLED) -> str:
    """
    Sends a query to the TCP server and returns the response.

    Args:
        query (str): The query string to send.
        host (str): The server hostname or IP address.
        port (int): The server port.
        ssl_enabled (bool): Whether to use SSL.

    Returns:
        str: The server's response, or "ERROR" if an error occurs.
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

def setup_logging(level_str: str) -> None:
    """
    Configures the logging level and format.

    Args:
        level_str (str): Logging level as a string (e.g., INFO, DEBUG).
    """
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

def create_ssl_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    """
    Creates and returns an SSL context using the given certificate and key files.

    Args:
        certfile (str): Path to the certificate file.
        keyfile (str): Path to the key file.

    Returns:
        ssl.SSLContext: Configured SSL context.
    """
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context

def main():
    parser = argparse.ArgumentParser(description="Secure TCP Client")
    parser.add_argument('--host', default='127.0.0.1', help='Server hostname or IP address')
    parser.add_argument('--port', type=int, default=PORT, help='Server port')
    parser.add_argument('--ssl', action='store_true', help='Enable SSL')
    parser.add_argument('--certfile', default='client-cert.pem', help='Path to SSL certificate')
    parser.add_argument('--keyfile', default='client-key.pem', help='Path to SSL key')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    args = parser.parse_args()

    setup_logging(args.log_level)

    try:
        sock = socket.create_connection((args.host, args.port))
        if args.ssl:
            context = create_ssl_context(args.certfile, args.keyfile)
            sock = context.wrap_socket(sock, server_hostname=args.host)
        logging.info(f"Connected to {args.host}:{args.port}")
        while True:
            query = input("Enter query (or 'exit' to quit): ").strip()
            if query.lower() == 'exit':
                break
            sock.sendall(query.encode('utf-8'))
            response = sock.recv(1024).decode('utf-8')
            print(f"Response: {response}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        sock.close()
        logging.info("Connection closed.")

if __name__ == "__main__":
    main()
