import os
import socket
import tempfile
import threading
import time
import logging
from configparser import ConfigParser
from unittest.mock import patch, mock_open

import pytest

from server import TCPServer  # Your server implementation

HOST = "127.0.0.1"
PORT = 44555
TEST_QUERY_EXISTS = "present_line"
TEST_QUERY_NOT_FOUND = "absent_line"
TEST_FILE_CONTENT = "present_line\nanother_line\nyet_another_line\n"


@pytest.fixture(scope="module")
def temp_file_with_lines():
    """Creates a temporary file with sample lines for testing."""
    lines = ["apple", "banana", "cherry", "date", "elderberry"]
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        f.write("\n".join(lines) + "\n")
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


@pytest.fixture(scope="module")
def temp_config_file(temp_file_with_lines):
    """Creates a temporary config file with the appropriate settings."""
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        f.write(f"""
[DEFAULT]
SEARCH_FILE_PATH={temp_file_with_lines}
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
    """
    Starts the server in a daemon thread for integration tests.
    Server will stop automatically when tests complete.
    """
    srv = TCPServer(config_path=temp_config_file)
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    time.sleep(1)  # Give the server time to start
    yield
    # No explicit server shutdown needed since thread is daemon


# --- Unit Tests for _search_in_file --- #

def test_search_found(temp_file_with_lines, temp_config_file):
    """Tests if a known string is found in the file."""
    srv = TCPServer(config_path=temp_config_file)
    srv.settings.file_path = temp_file_with_lines
    srv._load_search_file()
    result = srv._search_in_file("banana")
    assert result == "STRING EXISTS"


def test_search_not_found(temp_file_with_lines, temp_config_file):
    """Tests if an unknown string returns 'STRING NOT FOUND'."""
    srv = TCPServer(config_path=temp_config_file)
    srv.settings.file_path = temp_file_with_lines
    srv._load_search_file()
    result = srv._search_in_file("fig")
    assert result == "STRING NOT FOUND"


def test_search_reread_flag(temp_config_file):
    """
    Tests the behavior with reread_on_query flag both True and False.
    Ensures cached and reloaded results behave correctly.
    """
    srv = TCPServer(config_path=temp_config_file)

    srv.settings.reread_on_query = True
    srv._load_search_file()
    result = srv._search_in_file("cherry")
    assert result == "STRING EXISTS"

    srv.settings.reread_on_query = False
    result = srv._search_in_file("date")
    assert result == "STRING EXISTS"


def test_search_file_not_found(temp_config_file):
    """
    Tests the behavior when the search file does not exist.
    Should return 'STRING NOT FOUND' or 'ERROR' depending on implementation.
    """
    srv = TCPServer(config_path=temp_config_file)
    srv.settings.file_path = "/non/existent/file.txt"
    srv._load_search_file()
    result = srv._search_in_file("anything")
    assert result == "STRING NOT FOUND" or result == "ERROR"


def test_missing_config_key(tmp_path):
    """
    Tests that missing SEARCH_FILE_PATH in the config raises an exception.
    """
    config_file = tmp_path / "broken.cfg"
    config = ConfigParser()
    config["DEFAULT"] = {
        "REREAD_ON_QUERY": "True",
        "HOST": HOST,
        "PORT": str(PORT),
        "LOG_LEVEL": "DEBUG"
    }
    with open(config_file, "w") as f:
        config.write(f)

    with pytest.raises(Exception):
        TCPServer(config_path=str(config_file)).run()


def test_search_benchmark_log(caplog, temp_file_with_lines, temp_config_file):
    """
    Tests that logs are generated correctly for found and not found strings.
    """
    srv = TCPServer(config_path=temp_config_file)
    srv.settings.file_path = temp_file_with_lines
    srv._load_search_file()

    with caplog.at_level(logging.DEBUG):
        srv._search_in_file("banana")
        assert any("FOUND" in rec.message for rec in caplog.records)

        caplog.clear()
        srv._search_in_file("notthere")
        assert any("NOT FOUND" in rec.message for rec in caplog.records)


# --- Unit Tests with mocks for _search_in_file --- #

@patch("builtins.open", new_callable=mock_open, read_data=TEST_FILE_CONTENT)
def test_search_in_file_found_mock(mock_file, temp_config_file):
    """Tests that mock file returns 'STRING EXISTS' for known string."""
    srv = TCPServer(config_path=temp_config_file)
    srv.settings.file_path = "/fake/path/to/file.txt"
    result = srv._search_in_file(TEST_QUERY_EXISTS)
    assert result == "STRING EXISTS"


@patch("builtins.open", new_callable=mock_open, read_data=TEST_FILE_CONTENT)
def test_search_in_file_not_found_mock(mock_file, temp_config_file):
    """Tests that mock file returns 'STRING NOT FOUND' for unknown string."""
    srv = TCPServer(config_path=temp_config_file)
    srv.settings.file_path = "/fake/path/to/file.txt"
    result = srv._search_in_file(TEST_QUERY_NOT_FOUND)
    assert result == "STRING NOT FOUND"


@patch("builtins.open", side_effect=FileNotFoundError)
def test_search_file_not_found_mock(mock_open_file, temp_config_file):
    """Tests mocked FileNotFoundError returns 'STRING NOT FOUND'."""
    srv = TCPServer(config_path=temp_config_file)
    srv.settings.file_path = "/invalid/path.txt"
    result = srv._search_in_file("any_line")
    assert result == "STRING NOT FOUND"


# --- Integration Tests for Full Server --- #

def send_request(message: str) -> str:
    """Helper function to send a TCP request and receive a response."""
    with socket.create_connection((HOST, PORT), timeout=5) as sock:
        sock.sendall((message + "\n").encode("utf-8"))
        return sock.recv(1024).decode("utf-8").strip()


@pytest.mark.usefixtures("run_server_thread")
def test_integration_string_exists():
    """Integration test for string that exists in the file."""
    response = send_request("banana")
    assert response == "STRING EXISTS"


@pytest.mark.usefixtures("run_server_thread")
def test_integration_string_not_found():
    """Integration test for string not found in the file."""
    response = send_request("not_in_file")
    assert response == "STRING NOT FOUND"


@pytest.mark.usefixtures("run_server_thread")
def test_integration_empty_request():
    """Integration test for an empty TCP request."""
    response = send_request("")
    assert response.startswith("ERROR")  # e.g., "ERROR: Empty request"
