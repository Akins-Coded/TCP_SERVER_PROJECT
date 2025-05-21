import os
import tempfile
import threading
import socket
import time
import logging
import pytest
from unittest.mock import patch, mock_open

from server import server  # assuming server.py is importable as server.server in your project

HOST = "127.0.0.1"
PORT = 44555
TEST_QUERY_EXISTS = "present_line"
TEST_QUERY_NOT_FOUND = "absent_line"
TEST_FILE_CONTENT = "present_line\nanother_line\nyet_another_line\n"

@pytest.fixture(scope="module")
def temp_file_with_lines():
    lines = [
        "apple",
        "banana",
        "cherry",
        "date",
        "elderberry"
    ]
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        f.write("\n".join(lines) + "\n")
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


@pytest.fixture(scope="module")
def temp_config_file(temp_file_with_lines):
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        f.write(f"""
[DEFAULT]
linuxpath={temp_file_with_lines}
REREAD_ON_QUERY=True
SSL_ENABLED=False
HOST={HOST}
PORT={PORT}
LOG_LEVEL=DEBUG
""")
        config_path = f.name
    yield config_path
    os.unlink(config_path)


@pytest.fixture(scope="module")
def run_server_thread(temp_config_file):
    # Override config file path in the server module
    server.DEFAULT_CONFIG_FILE = temp_config_file
    # Start server thread
    t = threading.Thread(target=server.run_server, daemon=True)
    t.start()
    time.sleep(1)  # wait for server to be ready
    yield
    # No explicit stop, daemon thread ends with tests


# --- Unit Tests for search_in_file --- #

def test_search_found(temp_file_with_lines):
    server.CONFIGURED_FILE_PATH = temp_file_with_lines
    result = server.search_in_file("banana", reread=False)
    assert result == "STRING EXISTS"

def test_search_not_found(temp_file_with_lines):
    server.CONFIGURED_FILE_PATH = temp_file_with_lines
    result = server.search_in_file("fig", reread=False)
    assert result == "STRING NOT FOUND"

def test_search_reread_flag(temp_file_with_lines, temp_config_file):
    server.DEFAULT_CONFIG_FILE = temp_config_file

    # With reread True
    result = server.search_in_file("cherry", reread=True)
    assert result == "STRING EXISTS"

    # With reread False override
    result = server.search_in_file("date", reread=False)
    assert result == "STRING EXISTS"

def test_search_file_not_found():
    server.CONFIGURED_FILE_PATH = "/non/existent/file.txt"
    result = server.search_in_file("anything", reread=False)
    assert result == "ERROR"

def test_search_benchmark_log(caplog, temp_file_with_lines):
    server.CONFIGURED_FILE_PATH = temp_file_with_lines
    with caplog.at_level(logging.DEBUG):
        server.search_in_file("banana", reread=False)
        found_log = any("FOUND" in rec.message for rec in caplog.records)
        assert found_log

        caplog.clear()
        server.search_in_file("notthere", reread=False)
        not_found_log = any("NOT FOUND" in rec.message for rec in caplog.records)
        assert not_found_log


# --- Unit Tests with mocks for search_in_file --- #

@patch("builtins.open", new_callable=mock_open, read_data=TEST_FILE_CONTENT)
@patch("server.CONFIGURED_FILE_PATH", "/fake/path/to/file.txt")
def test_search_in_file_found_mock(mock_file):
    result = server.search_in_file(TEST_QUERY_EXISTS)
    assert result == "STRING EXISTS"

@patch("builtins.open", new_callable=mock_open, read_data=TEST_FILE_CONTENT)
@patch("server.CONFIGURED_FILE_PATH", "/fake/path/to/file.txt")
def test_search_in_file_not_found_mock(mock_file):
    result = server.search_in_file(TEST_QUERY_NOT_FOUND)
    assert result == "STRING NOT FOUND"

@patch("builtins.open", side_effect=FileNotFoundError)
@patch("server.CONFIGURED_FILE_PATH", "/invalid/path.txt")
def test_search_file_not_found_mock(mock_open_file):
    result = server.search_in_file("any_line")
    assert result == "ERROR"


# --- Integration tests for full server --- #

def send_request(message: str) -> str:
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall((message + "\n").encode("utf-8"))
        response = sock.recv(1024).decode("utf-8").strip()
        return response


@pytest.mark.usefixtures("run_server_thread")
def test_integration_string_exists():
    response = send_request("banana")
    assert response == "STRING EXISTS"

@pytest.mark.usefixtures("run_server_thread")
def test_integration_string_not_found():
    response = send_request("not_in_file")
    assert response == "STRING NOT FOUND"

@pytest.mark.usefixtures("run_server_thread")
def test_integration_empty_request():
    response = send_request("")
    assert response == "INVALID REQUEST"
