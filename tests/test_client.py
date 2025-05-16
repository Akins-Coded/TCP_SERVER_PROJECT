import socket
import ssl
import time
from configparser import ConfigParser

# Load config
config = ConfigParser()
config.read('server/config.cfg')

HOST = config.get('DEFAULT', 'HOST', fallback='135.181.96.160')
PORT = config.getint('DEFAULT', 'PORT', fallback=44445)
SSL_ENABLED = config.getboolean('DEFAULT', 'SSL_ENABLED', fallback=False)
CERT_PATH = 'server/server-cert.pem'
KEY_PATH = 'server/server-key.pem'

def send_query(query: str):
    try:
        if SSL_ENABLED:
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.load_cert_chain(certfile=CERT_PATH, keyfile=KEY_PATH)
            connection = context.wrap_socket(socket.socket(socket.AF_INET), server_hostname=HOST)
        else:
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        connection.connect((HOST, PORT))
        print(f"Connected to {HOST}:{PORT}")
        connection.send(query.encode())
        response = connection.recv(1024).decode().strip()
        print(f"Server response: {response}")
        connection.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    query = input("Enter the string to search for: ")
    start_time = time.time()
    send_query(query)
    end_time = time.time()
    print(f"Query executed in {end_time - start_time:.6f} seconds")
