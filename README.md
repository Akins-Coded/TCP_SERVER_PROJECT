# 🔐 TCP Client-Server Search Application
A multithreaded TCP server and client built with Python that supports optional SSL encryption. The server searches a configured text file for exact matches of client queries and responds accordingly.

📦 Features
🔍 File-based string search (exact full-line matching)
🧵 Multi-threaded server (handles multiple clients concurrently)
🔐 Optional SSL encryption
⚙️ Dynamic configuration via `server/config.cfg`


✨ Static typing with mypy


🚀 Installation

### Generating SSL Certificate and Key Files for Authentication

To enable SSL encryption, the server requires a valid certificate and private key. Follow these steps:

#### Using OpenSSL (Linux/macOS/Windows with OpenSSL installed):

1. Open a terminal or command prompt.

2. Navigate to the project directory:
   ```bash
   cd tcp_server_project


3.  Generate the SSL certificate and private key using the `openssl.cnf` configuration file provided:
    ```bash
    openssl req -new -x509 -days 365 -nodes -out server/server-cert.pem -keyout server/server-key.pem -config openssl.cnf
    ```
    This command will:
    * Generate a new private key (`server/server-key.pem`).
    * Create a self-signed X.509 certificate (`server/server-cert.pem`) valid for 365 days.
    * Use the settings defined in `openssl.cnf` for the certificate's distinguished name and extensions.

✅ Prerequisites
* Python 3.13
* pip (Python package manager)
* OpenSSL (for generating SSL certificates if needed)