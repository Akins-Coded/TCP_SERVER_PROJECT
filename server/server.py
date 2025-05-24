import socket
import ssl
import threading
import logging
import time
import os
import mmap
from configparser import ConfigParser, Error as ConfigError
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

    def _load_and_parse_config(self) -> ServerSettings:
        config = ConfigParser()
        if not config.read(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        return ServerSettings(
            file_path=os.getenv("SEARCH_FILE_PATH", config.get("DEFAULT", "SEARCH_FILE_PATH", fallback="")),
            reread_on_query=config.getboolean("DEFAULT", "REREAD_ON_QUERY", fallback=True),
            ssl_enabled=config.getboolean("DEFAULT", "SSL_ENABLED", fallback=False),
            certfile=os.getenv("SSL_CERTFILE", config.get("DEFAULT", "SSL_CERTFILE", fallback="server/server-cert.pem")),
            keyfile=os.getenv("SSL_KEYFILE", config.get("DEFAULT", "SSL_KEYFILE", fallback="server/server-key.pem")),
            host=config.get("DEFAULT", "HOST", fallback="0.0.0.0"),
            port=config.getint("DEFAULT", "PORT", fallback=9999),
            log_level=config.get("DEFAULT", "LOG_LEVEL", fallback="INFO")
        )

    def _setup_logging(self):
        level = getattr(logging, self.settings.log_level.upper(), logging.INFO)
        logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

    def _search_in_file(self, query: str) -> str:
        file_path = self.settings.file_path

        if self.settings.reread_on_query:
            try:
                config = ConfigParser()
                if config.read(self.config_path):
                    file_path = os.getenv("SEARCH_FILE_PATH", config.get("DEFAULT", "SEARCH_FILE_PATH", fallback=file_path))
            except Exception:
                logging.warning("Failed to reload config during query. Using existing file path.")

        try:
            start = time.perf_counter()
            encoded_query = (query + "\n").encode("utf-8")

            with open(file_path, "rb") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    if encoded_query in mm:
                        elapsed = time.perf_counter() - start
                        logging.debug(f"Query '{query}' FOUND in {elapsed:.4f} seconds")
                        return "STRING EXISTS"

            elapsed = time.perf_counter() - start
            logging.debug(f"Query '{query}' NOT FOUND in {elapsed:.4f} seconds")
            return "STRING NOT FOUND"

        except FileNotFoundError:
            logging.error(f"Search file not found: {file_path}")
            return "ERROR:FILE_NOT_FOUND"
        except PermissionError:
            logging.error(f"Permission denied: {file_path}")
            return "ERROR:PERMISSION_DENIED"
        except Exception as e:
            logging.exception("Unexpected error during file search.")
            return "ERROR:UNEXPECTED"

    def _handle_client(self, client_socket: socket.socket, client_address: Tuple[str, int]) -> None:
        try:
            request = client_socket.recv(1024).decode('utf-8').strip()
            if not request:
                logging.warning(f"Empty request from {client_address}")
                client_socket.sendall(b"INVALID REQUEST\n")
                return

            logging.debug(f"Received request from {client_address}: {request}")
            result = self._search_in_file(request)
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

    def run(self):
        self.base_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.base_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        if self.settings.ssl_enabled:
            try:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(certfile=self.settings.certfile, keyfile=self.settings.keyfile)
                self.base_socket = context.wrap_socket(self.base_socket, server_side=True)
                logging.info("SSL context initialized")
            except Exception as e:
                logging.critical(f"SSL setup failed: {e}")
                return

        try:
            self.base_socket.bind((self.settings.host, self.settings.port))
            self.base_socket.listen(5)
            logging.info(f"Server listening on {self.settings.host}:{self.settings.port} | SSL: {'ENABLED' if self.settings.ssl_enabled else 'DISABLED'}")

            while True:
                try:
                    client_sock, client_addr = self.base_socket.accept()
                    logging.info(f"Connection from {client_addr}")
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, client_addr),
                        daemon=True,
                        name=f"ClientThread-{client_addr[0]}:{client_addr[1]}"
                    ).start()
                except Exception as e:
                    logging.error(f"Error accepting connection: {e}")

        except KeyboardInterrupt:
            logging.info("Server stopped by user")
        except Exception as e:
            logging.exception(f"Server error: {e}")
        finally:
            try:
                self.base_socket.close()
            except Exception:
                pass
            logging.info("Server socket closed.")


if __name__ == "__main__":
    server = TCPServer()
    server.run()
