# Secure TCP String Search Server

This project implements a secure, multithreaded TCP server in Python for performing exact string match lookups within a large text file. It includes support for SSL/TLS encryption, dynamic configuration, multithreaded client handling, unit testing, logging, and Linux daemonization.

---

## 🚀 Features

- ✅ SSL/TLS encryption with configurable certificates
- 🔄 Dynamic configuration reload on each query
- 🧵 Multithreaded handling of concurrent client connections
- ⚡ Fast exact line matching (tested with files up to 250,000 lines)
- 🧪 Unit tested using `unittest`
- 🐧 Ready for deployment as a Linux daemon
- ⚙️ Easily configurable via `server/config.cfg`

---

## 🔐 Generating SSL Certificate and Key Files

To enable SSL/TLS encryption, the server requires a certificate and a private key. You can generate self-signed credentials using OpenSSL.

### 📥 Prerequisites

Ensure OpenSSL is installed on your system.

### 🛠️ Steps to Generate SSL Files

1. Open a terminal.
2. Navigate to your project directory:

```bash
cd tcp_server_project

3. Run the following command to generate the certificate and key:
```bash
openssl req -new -x509 -days 365 -nodes \
  -out server/server-cert.pem \
  -keyout server/server-key.pem \
  -config openssl.cnf

This command will:

    Generate a new private key (server/server-key.pem)

    Create a self-signed X.509 certificate (server/server-cert.pem) valid for 365 days

    Use the values defined in openssl.cnf for the certificate's distinguished name and extensions


    
🧰 Installation & Setup
1. Install Dependencies

```bash
sudo apt update
sudo apt install python3-pip -y
pip install matplotlib


2. Start the Server
```bash
python3 server/server.py

3. Connect a Client
```bash
python3 client/client.py --host 135.181.96.160 --port 44445

4. Run Performance Benchmark
```bash
python3 report/benchmark.py

🛰️ Deploying as a Linux Daemon
Step 1: Create a systemd Service File

Create a new service file:
```bash
sudo nano /etc/systemd/system/tcp-server.service

Paste the following configuration:
ini
[Unit]
Description=Secure TCP String Search Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 tcp_server_project/server/server.py
WorkingDirectory=/tcp_server_project/
Restart=always
User=nobody

[Install]
WantedBy=multi-user.target

    

Step 2: Enable and Start the Service
```bash
sudo systemctl daemon-reexec
sudo systemctl enable tcp-server
sudo systemctl start tcp-server

You can verify the service status with:
```bash
sudo systemctl status tcp-server