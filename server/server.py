import socket
import ssl
import threading
import logging
import time
import os
from configparser import ConfigParser
from typing import Optional, Tuple
from dataclasses import dataclass

DEFAULT_CONFIG_FILE = "server/config.cfg"


@dataclass
class ServerSettings:
    file_path: str
    reread_on_query: bool
    ssl_enabled: bool
    certfile: Optional[str]
    keyfile: Optional[str]
    host: str
    port: int
    log_level: str


class TCPServer:
    def __init__(self, config_path: str = DEFAULT_CONFIG_FILE):
        self.config_path = config_path
        self.settings = self._load_and_parse_config()
        self._setup_logging()
        self.base_socket = None

        # For caching search file contents
        self._file_lock = threading.Lock()
        self._cached_lines = set()
        self._cached_file_mtime = 0

        # Initial load of the search file into cache
        self._load_search_file()

    def _load_and_parse_config(self) -> ServerSettings:
        config = ConfigParser()
        if not config.read(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        return ServerSettings(
            file_path=os.getenv(
                "SEARCH_FILE_PATH",
                config.get("DEFAULT", "SEARCH_FILE_PATH", fallback=""),
            ),
            reread_on_query=config.getboolean("DEFAULT", "REREAD_ON_QUERY", fallback=True),
            ssl_enabled=config.getboolean("DEFAULT", "SSL_ENABLED", fallback=False),
            certfile=os.getenv(
                "SSL_CERTFILE",
                config.get("DEFAULT", "SSL_CERTFILE", fallback="server/server-cert.pem"),
            ),
            keyfile=os.getenv(
                "SSL_KEYFILE",
                config.get("DEFAULT", "SSL_KEYFILE", fallback="server/server-key.pem"),
            ),
            host=config.get("DEFAULT", "HOST", fallback="0.0.0.0"),
            port=config.getint("DEFAULT", "PORT", fallback=9999),
            log_level=config.get("DEFAULT", "LOG_LEVEL", fallback="INFO"),
        )

    def _setup_logging(self):
        level = getattr(logging, self.settings.log_level.upper(), logging.INFO)
        logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")

    def _load_search_file(self):
        """Load the search file and cache its lines with thread-safe locking."""
        try:
            file_path = self.settings.file_path
            mtime = os.path.getmtime(file_path)

            if mtime == self._cached_file_mtime:
                # File unchanged; no reload needed
                return

            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()

            with self._file_lock:
                self._cached_lines = set(lines)
                self._cached_file_mtime = mtime

            logging.debug(f"Reloaded search file; {len(lines)} lines cached.")

        except FileNotFoundError:
            logging.error(f"Search file not found: {self.settings.file_path}")
            with self._file_lock:
                self._cached_lines = set()
                self._cached_file_mtime = 0
        except PermissionError:
            logging.error(f"Permission denied: {self.settings.file_path}")
            with self._file_lock:
                self._cached_lines = set()
                self._cached_file_mtime = 0
        except Exception as exc:
            logging.exception(f"Failed to load search file: {exc}")
            with self._file_lock:
                self._cached_lines = set()
                self._cached_file_mtime = 0

    def _search_in_file(self, query: str) -> str:
        """Search for the query string in the cached file lines."""
        start_time = time.perf_counter()

        # If configured to reread on each query, check if the file changed and reload
        if self.settings.reread_on_query:
            self._load_search_file()

        with self._file_lock:
            found = query in self._cached_lines

        elapsed = (time.perf_counter() - start_time) * 1000  # milliseconds
        if found:
            logging.debug(f"Query '{query}' FOUND in {elapsed:.2f} ms")
            return "STRING EXISTS"
        logging.debug(f"Query '{query}' NOT FOUND in {elapsed:.2f} ms")
        return "STRING NOT FOUND"

    def _handle_client(self, client_socket: socket.socket, client_address: Tuple[str, int]) -> None:
        """Handle a single client connection."""
        try:
            request = client_socket.recv(1024).decode("utf-8").strip()
            if not request:
                logging.warning(f"Empty request from {client_address}")
                client_socket.sendall(b"ERROR: Empty request\n")
                return

            logging.debug(f"Received request from {client_address}: {request}")
            result = self._search_in_file(request)
            client_socket.sendall(f"{result}\n".encode("utf-8"))

        except UnicodeDecodeError:
            logging.error(f"Failed to decode request from {client_address}")
            client_socket.sendall(b"ERROR: Unable to decode request. Ensure UTF-8 encoding.\n")
        except socket.timeout:
            logging.warning(f"Connection timed out from {client_address}")
            client_socket.sendall(b"ERROR: Connection timed out\n")
        except ConnectionResetError:
            logging.warning(f"Connection reset by {client_address}")
        except Exception as exc:
            logging.exception(f"Unhandled error from {client_address}: {exc}")
            try:
                client_socket.sendall(b"ERROR: Internal server error occurred\n")
            except Exception:
                pass
        finally:
            client_socket.close()

    def run(self):
        """Start the TCP server and listen for incoming client connections."""
        self.base_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.base_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if self.settings.ssl_enabled:
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(certfile=self.settings.certfile, keyfile=self.settings.keyfile)
                self.base_socket = context.wrap_socket(self.base_socket, server_side=True)
                logging.info("SSL context initialized successfully.")
            except Exception as exc:
                logging.critical(f"Failed to initialize SSL context: {exc}")
                return

        try:
            self.base_socket.bind((self.settings.host, self.settings.port))
            self.base_socket.listen(5)
            logging.info(
                f"Server listening on {self.settings.host}:{self.settings.port} | "
                f"SSL: {'ENABLED' if self.settings.ssl_enabled else 'DISABLED'}"
            )

            while True:
                try:
                    client_sock, client_addr = self.base_socket.accept()
                    logging.info(f"Connection established with {client_addr}")
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, client_addr),
                        daemon=True,
                        name=f"ClientThread-{client_addr[0]}:{client_addr[1]}",
                    ).start()
                except Exception as exc:
                    logging.error(f"Error accepting new connection: {exc}")

        except KeyboardInterrupt:
            logging.info("Server shutdown initiated by user.")
        except Exception as exc:
            logging.exception(f"Critical server error: {exc}")
        finally:
            try:
                self.base_socket.close()
            except Exception:
                pass
            logging.info("Server socket closed.")


if __name__ == "__main__":
    server = TCPServer()
    server.run()
