import socket
import ssl
import threading
import logging
import time
import os
from configparser import ConfigParser, Error as ConfigError
from typing import Optional, Tuple

# Default config file path
DEFAULT_CONFIG_FILE = "server/config.cfg"

# Globals to be set after config load
LINUX_PATH: str = ""
REREAD_ON_QUERY: bool = True
SSL_ENABLED: bool = False
SSL_CERTFILE: Optional[str] = None
SSL_KEYFILE: Optional[str] = None

# Load configuration function
def load_config(config_file: str) -> ConfigParser:
    config = ConfigParser()
    try:
        read_files = config.read(config_file)
        if not read_files:
            raise FileNotFoundError(f"Config file not found: {config_file}")

        return config
    except ConfigError as ce:
        logging.error(f"Config parsing error: {ce}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error loading config: {e}")
        raise

def init_globals_from_config(config: ConfigParser) -> None:
    global LINUX_PATH, REREAD_ON_QUERY, SSL_ENABLED, SSL_CERTFILE, SSL_KEYFILE

    LINUX_PATH = config.get("DEFAULT", "linuxpath", fallback="")
    REREAD_ON_QUERY = config.getboolean("DEFAULT", "REREAD_ON_QUERY", fallback=True)
    SSL_ENABLED = config.getboolean("DEFAULT", "SSL_ENABLED", fallback=False)
    SSL_CERTFILE = os.getenv("SSL_CERTFILE", config.get("DEFAULT", "SSL_CERTFILE", fallback="server/server-cert.pem"))
    SSL_KEYFILE = os.getenv("SSL_KEYFILE", config.get("DEFAULT", "SSL_KEYFILE", fallback="server/server-key.pem"))

def setup_logging(level_str: str) -> None:
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

def search_in_file(query: str) -> str:
    """
    Search for an exact full-line match of `query` in the file specified by LINUX_PATH.

    Returns:
        - "STRING EXISTS" if found
        - "STRING NOT FOUND" if not found
        - "ERROR" if any error occurs
    """
    global LINUX_PATH, REREAD_ON_QUERY

    if REREAD_ON_QUERY:
        # Reload config on each query to allow dynamic changes (optional)
        try:
            config = load_config(DEFAULT_CONFIG_FILE)
            LINUX_PATH = config.get("DEFAULT", "linuxpath", fallback=LINUX_PATH)
        except Exception:
            logging.warning("Failed to reload config during search; using existing settings")

    try:
        start_time = time.perf_counter()
        with open(LINUX_PATH, 'r', encoding='utf-8') as file:
            found = any(line.rstrip('\n') == query for line in file)
        elapsed = time.perf_counter() - start_time
        result = "STRING EXISTS" if found else "STRING NOT FOUND"
        logging.debug(f"Search query: {query!r} Result: {result} Time: {elapsed:.4f}s")
        return result

    except FileNotFoundError:
        logging.error(f"Search file not found: {LINUX_PATH}")
        return "ERROR"
    except PermissionError:
        logging.error(f"Permission denied accessing file: {LINUX_PATH}")
        return "ERROR"
    except UnicodeDecodeError:
        logging.error("File encoding error: cannot decode with UTF-8")
        return "ERROR"
    except Exception as e:
        logging.exception(f"Unexpected error searching file: {e}")
        return "ERROR"

def handle_client(client_socket: socket.socket, client_address: Tuple[str, int]) -> None:
    """
    Handle communication with a client: receive query, search file, send response.
    """
    try:
        request = client_socket.recv(1024).decode('utf-8').strip()
        if not request:
            logging.warning(f"Empty request received from {client_address}")
            client_socket.sendall(b"INVALID REQUEST\n")
            return

        logging.debug(f"Request from {client_address}: {request}")
        result = search_in_file(request)
        client_socket.sendall(f"{result}\n".encode('utf-8'))

    except UnicodeDecodeError:
        logging.error(f"Unicode decode error from {client_address}")
        client_socket.sendall(b"DECODE ERROR\n")
    except socket.timeout:
        logging.warning(f"Timeout from {client_address}")
        client_socket.sendall(b"TIMEOUT ERROR\n")
    except ConnectionResetError:
        logging.warning(f"Connection reset by {client_address}")
    except Exception as e:
        logging.exception(f"Unexpected error handling client {client_address}: {e}")
        try:
            client_socket.sendall(b"ERROR\n")
        except Exception:
            pass
    finally:
        client_socket.close()

def run_server(
    host: Optional[str] = None,
    port: Optional[int] = None,
    config_file: Optional[str] = None
) -> None:
    """
    Start the TCP server with optional SSL.

    Args:
        host: Override host address to bind.
        port: Override port number to bind.
        config_file: Path to config file (defaults to DEFAULT_CONFIG_FILE).
    """
    global LINUX_PATH, REREAD_ON_QUERY, SSL_ENABLED, SSL_CERTFILE, SSL_KEYFILE

    config_path = config_file or os.environ.get("SERVER_CONFIG_PATH") or DEFAULT_CONFIG_FILE

    try:
        config = load_config(config_path)
        init_globals_from_config(config)
        setup_logging(config.get("DEFAULT", "LOG_LEVEL", fallback="INFO"))

        server_host = host or config.get("DEFAULT", "HOST", fallback="0.0.0.0")
        server_port = port or config.getint("DEFAULT", "PORT", fallback=9999)

        logging.info(f"Starting server on {server_host}:{server_port} SSL={'enabled' if SSL_ENABLED else 'disabled'}")

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if SSL_ENABLED:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=SSL_CERTFILE, keyfile=SSL_KEYFILE)
            server_socket = context.wrap_socket(server_socket, server_side=True)

        server_socket.bind((server_host, server_port))
        server_socket.listen(5)

        while True:
            client_sock, client_addr = server_socket.accept()
            logging.info(f"Accepted connection from {client_addr}")
            thread = threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True)
            thread.start()

    except KeyboardInterrupt:
        logging.info("Server shutdown requested by user.")
    except Exception as e:
        logging.exception(f"Fatal server error: {e}")
    finally:
        try:
            server_socket.close()
        except Exception:
            pass
        logging.info("Server socket closed.")


if __name__ == "__main__":
    run_server()
