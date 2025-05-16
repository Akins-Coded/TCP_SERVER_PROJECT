# 🔐 TCP Client-Server Search Application

A multithreaded TCP server and client built with Python that supports optional SSL encryption. The server searches a configured text file for exact matches of client queries and responds accordingly.

---

## 📦 Features

- 🔍 File-based string search
- 🧵 Multi-threaded server (handles multiple clients concurrently)
- 🔐 Optional SSL encryption
- ⚙️ Dynamic configuration via `config.cfg`
- 📄 Detailed logging with configurable log levels
- ✅ Automated testing with `pytest`

---

## 🚀 Installation

### ✅ Prerequisites

- Python 3.13
- `pip` (Python package manager)
- OpenSSL (for generating SSL certs if needed)
