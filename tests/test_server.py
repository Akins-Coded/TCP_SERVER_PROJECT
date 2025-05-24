import os
import tempfile
import threading
import socket
import time
import logging
import pytest
from unittest.mock import patch, mock_open

from server import TCPServer

HOST = "127.0.0.1"
PORT = 44555
TEST_QUERY_EXISTS = "present_line"
TEST_QUERY_NOT_FOUND = "absent_line"
TEST_FILE_CONTENT = "present_line\nanother_line\nyet_another_line\n"

@pytest.fixture(scope="module")
def temp_file_with_lines():
    lines = ["apple", "banana", "cherry", "date", "elderberry"]
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
    srv = TCPServer(config_file=temp_config_file)
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    time.sleep(1)  # Wait for server to be ready
    yield
    # No teardown needed as thread is daemon


# --- Unit Tests for search_in_file --- #

def test_search_found(temp_file_with_lines, temp_config_file):
    srv = TCPServer(config_file=temp_config_file)
    srv.CONFIGURED_FILE_PATH = temp_file_with_lines
    result = srv.search_in_file("banana", reread=False)
    assert result == "STRING EXISTS"

def test_search_not_found(temp_file_with_lines, temp_config_file):
    srv = TCPServer(config_file=temp_config_file)
    srv.CONFIGURED_FILE_PATH = temp_file_with_lines
    result = srv.search_in_file("fig", reread=False)
    assert result == "STRING NOT FOUND"

def test_search_reread_flag(temp_config_file):
    srv = TCPServer(config_file=temp_config_file)
    result = srv.search_in_file("cherry", reread=True)
    assert result == "STRING EXISTS"

    result = srv.search_in_file("date", reread=False)
    assert result == "STRING EXISTS"

def test_search_file_not_found(temp_config_file):
    srv = TCPServer(config_file=temp_config_file)
    srv.CONFIGURED_FILE_PATH = "/non/existent/file.txt"
    result = srv.search_in_file("anything", reread=False)
    assert result == "ERROR"

def test_search_benchmark_log(caplog, temp_file_with_lines, temp_config_file):
    srv = TCPServer(config_file=temp_config_file)
    srv.CONFIGURED_FILE_PATH = temp_file_with_lines
    with caplog.at_level(logging.DEBUG):
        srv.search_in_file("banana", reread=False)
        assert any("FOUND" in rec.message for rec in caplog.records)

        caplog.clear()
        srv.search_in_file("notthere", reread=False)
        assert any("NOT FOUND" in rec.message for rec in caplog.records)


# --- Unit Tests with mocks for search_in_file --- #

@patch("builtins.open", new_callable=mock_open, read_data=TEST_FILE_CONTENT)
def test_search_in_file_found_mock(mock_file, temp_config_file):
    srv = TCPServer(config_file=temp_config_file)
    srv.CONFIGURED_FILE_PATH = "/fake/path/to/file.txt"
    result = srv.search_in_file(TEST_QUERY_EXISTS)
    assert result == "STRING EXISTS"

@patch("builtins.open", new_callable=mock_open, read_data=TEST_FILE_CONTENT)
def test_search_in_file_not_found_mock(mock_file, temp_config_file):
    srv = TCPServer(config_file=temp_config_file)
    srv.CONFIGURED_FILE_PATH = "/fake/path/to/file.txt"
    result = srv.search_in_file(TEST_QUERY_NOT_FOUND)
    assert result == "STRING NOT FOUND"

@patch("builtins.open", side_effect=FileNotFoundError)
def test_search_file_not_found_mock(mock_open_file, temp_config_file):
    srv = TCPServer(config_file=temp_config_file)
    srv.CONFIGURED_FILE_PATH = "/invalid/path.txt"
    result = srv.search_in_file("any_line")
    assert result == "ERROR"


# --- Integration tests for full server --- #

def send_request(message: str) -> str:
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall((message + "\n").encode("utf-8"))
        return sock.recv(1024).decode("utf-8").strip()


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
