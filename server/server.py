import socket
import ssl
import threading
import logging
import time
import os
import mmap
from configparser import ConfigParser, Error as ConfigError
from typing import Optional, Tuple

DEFAULT_CONFIG_FILE = "server/config.cfg"

CONFIGURED_FILE_PATH: str = ""
REREAD_CONFIG_ON_QUERY: bool = True
SSL_ENABLED: bool = False
SSL_CERTFILE: Optional[str] = None
SSL_KEYFILE: Optional[str] = None


def load_config(config_file: str) -> ConfigParser:
    config = ConfigParser()
    try:
        if not config.read(config_file):
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        return config
    except ConfigError as ce:
        logging.error(f"Configuration parsing error: {ce}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error while loading configuration: {e}")
        raise


def init_globals_from_config(config: ConfigParser) -> None:
    global CONFIGURED_FILE_PATH, REREAD_CONFIG_ON_QUERY, SSL_ENABLED, SSL_CERTFILE, SSL_KEYFILE
    CONFIGURED_FILE_PATH = config.get("DEFAULT", "linuxpath", fallback="")
    REREAD_CONFIG_ON_QUERY = config.getboolean("DEFAULT", "REREAD_ON_QUERY", fallback=True)
    SSL_ENABLED = config.getboolean("DEFAULT", "SSL_ENABLED", fallback=False)
    SSL_CERTFILE = os.getenv("SSL_CERTFILE", config.get("DEFAULT", "SSL_CERTFILE", fallback="server/server-cert.pem"))
    SSL_KEYFILE = os.getenv("SSL_KEYFILE", config.get("DEFAULT", "SSL_KEYFILE", fallback="server/server-key.pem"))


def setup_logging(level_str: str) -> None:
    level = getattr(logging, level_str.upper(), logging.INFO)
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')


def search_in_file(query: str, reread: Optional[bool] = None) -> str:
    """
    Search for exact query line in file.

    Args:
        query: The string to search.
        reread: Override global reread config (optional).

    Returns:
        "STRING EXISTS", "STRING NOT FOUND", or "ERROR".
    """
    global CONFIGURED_FILE_PATH, REREAD_CONFIG_ON_QUERY

    reread_config = reread if reread is not None else REREAD_CONFIG_ON_QUERY
    file_path = CONFIGURED_FILE_PATH

    if reread_config:
        try:
            config = load_config(DEFAULT_CONFIG_FILE)
            file_path = config.get("DEFAULT", "linuxpath", fallback=file_path)
        except Exception:
            logging.warning("Failed to reload config during query. Continuing with current path.")

    try:
        start = time.perf_counter()
        encoded_query = (query + "\n").encode("utf-8")

        with open(file_path, "rb") as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                if encoded_query in mm:
                    elapsed = time.perf_counter() - start
                    logging.debug(f"Query '{query}' FOUND in {elapsed:.4f} seconds with reread={reread_config}")
                    return "STRING EXISTS"

        elapsed = time.perf_counter() - start
        logging.debug(f"Query '{query}' NOT FOUND in {elapsed:.4f} seconds with reread={reread_config}")
        return "STRING NOT FOUND"

    except FileNotFoundError:
        logging.error(f"Search file not found: {file_path}")
        return "ERROR"
    except PermissionError:
        logging.error(f"Permission denied: {file_path}")
        return "ERROR"
    except UnicodeDecodeError:
        logging.error("Encoding error during search")
        return "ERROR"
    except Exception as e:
        logging.exception("Unexpected error during file search.")
        return "ERROR"


def handle_client(client_socket: socket.socket, client_address: Tuple[str, int]) -> None:
    try:
        request = client_socket.recv(1024).decode('utf-8').strip()
        if not request:
            logging.warning(f"Empty request from {client_address}")
            client_socket.sendall(b"INVALID REQUEST\n")
            return

        logging.debug(f"Received request from {client_address}: {request}")
        result = search_in_file(request)
        client_socket.sendall(f"{result}\n".encode('utf-8'))

    except UnicodeDecodeError:
        logging.error(f"Failed to decode request from {client_address}")
        client_socket.sendall(b"DECODE ERROR\n")
    except socket.timeout:
        logging.warning(f"Timeout from {client_address}")
        client_socket.sendall(b"TIMEOUT ERROR\n")
    except ConnectionResetError:
        logging.warning(f"Connection reset by {client_address}")
    except Exception as e:
        logging.exception(f"Unhandled error from {client_address}: {e}")
        try:
            client_socket.sendall(b"ERROR\n")
        except Exception:
            pass
    finally:
        client_socket.close()


def run_server(host: Optional[str] = None, port: Optional[int] = None, config_file: Optional[str] = None) -> None:
    global SSL_ENABLED, SSL_CERTFILE, SSL_KEYFILE

    config_path = config_file or os.environ.get("SERVER_CONFIG_PATH") or DEFAULT_CONFIG_FILE

    try:
        config = load_config(config_path)
        init_globals_from_config(config)
        setup_logging(config.get("DEFAULT", "LOG_LEVEL", fallback="INFO"))

        server_host = host or config.get("DEFAULT", "HOST", fallback="0.0.0.0")
        server_port = port or config.getint("DEFAULT", "PORT", fallback=9999)

        logging.info(f"Starting server on {server_host}:{server_port} | SSL: {'ENABLED' if SSL_ENABLED else 'DISABLED'}")

        base_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        base_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if SSL_ENABLED:
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(certfile=SSL_CERTFILE, keyfile=SSL_KEYFILE)
                base_socket = context.wrap_socket(base_socket, server_side=True)
                logging.info("SSL context initialized")
            except ssl.SSLError as ssl_error:
                logging.critical(f"SSL setup error: {ssl_error}")
                return
            except FileNotFoundError as fe:
                logging.critical(f"SSL cert/key file not found: {fe}")
                return
            except Exception as e:
                logging.critical(f"Unexpected SSL error: {e}")
                return

        base_socket.bind((server_host, server_port))
        base_socket.listen(5)
        logging.info("Server listening for connections...")

        while True:
            try:
                client_sock, client_addr = base_socket.accept()
                logging.info(f"Connection from {client_addr}")
                threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True).start()
            except Exception as e:
                logging.error(f"Accept error: {e}")

    except KeyboardInterrupt:
        logging.info("Server stopped by user")
    except Exception as e:
        logging.exception(f"Fatal server error: {e}")
    finally:
        try:
            base_socket.close()
        except Exception:
            pass
        logging.info("Server socket closed.")


if __name__ == "__main__":
    run_server()
