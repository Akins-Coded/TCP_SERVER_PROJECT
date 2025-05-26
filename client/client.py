import socket
import ssl
import logging
import argparse
from typing import Optional
from configparser import ConfigParser
import os

# Load client configuration
config = ConfigParser()
config.read("server/config.cfg")

HOST: str = config.get("DEFAULT", "HOST", fallback="127.0.0.1")
PORT: int = config.getint("DEFAULT", "PORT", fallback=44445)
SSL_ENABLED: bool = config.getboolean("DEFAULT", "SSL_ENABLED", fallback=False)
CA_CERT_PATH: str = config.get("DEFAULT", "CA_CERT_PATH", fallback="server/ca-cert.pem")

# Configure default logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def send_query(query: str, host: str = HOST, port: int = PORT, ssl_enabled: bool = SSL_ENABLED) -> str:
    """
    Sends a query string to the TCP server and returns the response.

    Args:
        query (str): The query to send to the server.
        host (str): Server hostname or IP address.
        port (int): Server port number.
        ssl_enabled (bool): Whether SSL is enabled.

    Returns:
        str: Server response or "ERROR" in case of failure.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            if ssl_enabled:
                context = ssl.create_default_context()
                if os.path.exists(CA_CERT_PATH):
                    context.load_verify_locations(cafile=CA_CERT_PATH)
                else:
                    logging.warning(f"CA certificate not found at {CA_CERT_PATH}")
                client_socket = context.wrap_socket(client_socket, server_hostname=host)
            client_socket.connect((host, port))
            client_socket.sendall(query.encode())
            response: str = client_socket.recv(1024).decode().strip()
            logging.debug(f"Received response: {response}")
            return response
    except (socket.error, ssl.SSLError) as exc:
        logging.error(f"Error sending query: {exc}")
        return "ERROR"


def setup_logging(level_str: str) -> None:
    """
    Sets up the logging level.

    Args:
        level_str (str): Logging level (e.g., 'DEBUG', 'INFO').
    """
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.getLogger().setLevel(level)


def create_ssl_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    """
    Creates an SSL context for secure client connections.

    Args:
        certfile (str): Path to SSL certificate.
        keyfile (str): Path to SSL private key.

    Returns:
        ssl.SSLContext: Configured SSL context.
    """
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    context.load_verify_locations(cafile=CA_CERT_PATH)
    return context


def main():
    parser = argparse.ArgumentParser(description="Secure TCP Client")
    parser.add_argument("--host", default=HOST, help="Server hostname or IP address")
    parser.add_argument("--port", type=int, default=PORT, help="Server port number")
    parser.add_argument("--ssl", action="store_true", help="Enable SSL for secure connection")
    parser.add_argument("--certfile", default="client-cert.pem", help="Path to client SSL certificate")
    parser.add_argument("--keyfile", default="client-key.pem", help="Path to client SSL private key")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
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
            if query.lower() == "exit":
                break
            sock.sendall(query.encode("utf-8"))
            response = sock.recv(1024).decode("utf-8")
            print(f"Response: {response}")
    except (socket.error, ssl.SSLError, Exception) as exc:
        logging.error(f"An error occurred: {exc}")
    finally:
        sock.close()
        logging.info("Connection closed.")


if __name__ == "__main__":
    main()
