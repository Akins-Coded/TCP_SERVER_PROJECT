import socket
import ssl
import logging
import threading
import time
from configparser import ConfigParser

# Load configuration
config = ConfigParser()
config.read('server/config.cfg')

HOST = config.get('DEFAULT', 'HOST', fallback='0.0.0.0')
PORT = config.getint('DEFAULT', 'PORT', fallback=9999)
LINUX_PATH = config.get('DEFAULT', 'linuxpath')
REREAD_ON_QUERY = config.getboolean('DEFAULT', 'REREAD_ON_QUERY')
SSL_ENABLED = config.getboolean('DEFAULT', 'SSL_ENABLED')
LOG_LEVEL = getattr(logging, config.get('DEFAULT', 'LOG_LEVEL').upper(), logging.INFO)

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

def search_in_file(query: str) -> str:
    try:
        start_time = time.time()
        with open(LINUX_PATH, 'r') as f:
            if REREAD_ON_QUERY:
                f.seek(0)
            found = any(line.strip() == query for line in f)
        exec_time = time.time() - start_time
        result = "STRING EXISTS" if found else "STRING NOT FOUND"
        logging.debug(f"Search query: {query}, Result: {result}, Time: {exec_time:.4f} seconds")
        return result
    except Exception as e:
        logging.error(f"Error while searching in file: {e}")
        return "ERROR"

def handle_client(client_socket: socket.socket, client_address):
    try:
        request = client_socket.recv(1024).strip().decode()
        logging.debug(f"Received request from {client_address}: {request}")
        result = search_in_file(request)
        client_socket.sendall(f"{result}\n".encode())
    except Exception as e:
        logging.error(f"Error handling client {client_address}: {e}")
        client_socket.sendall(b"ERROR\n")
    finally:
        client_socket.close()

def run_server(host: str = HOST, port: int = PORT):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if SSL_ENABLED:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile="server/server-cert.pem", keyfile="server/server-key.pem")
            server_socket = context.wrap_socket(server_socket, server_side=True)

        server_socket.bind((host, port))
        server_socket.listen(5)
        logging.info(f"Server listening on {host}:{port} with SSL={'enabled' if SSL_ENABLED else 'disabled'}")

        while True:
            client_socket, addr = server_socket.accept()
            logging.debug(f"Connection established with {addr}")
            client_handler = threading.Thread(target=handle_client, args=(client_socket, addr))
            client_handler.start()
    except Exception as e:
        logging.error(f"Server encountered an error: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":
    run_server()
