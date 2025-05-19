import pytest
import threading
import time
from client import send_query
from server import run_server
from configparser import ConfigParser
from pathlib import Path


@pytest.fixture(scope="module", autouse=True)
def start_main_server():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1)  # Wait for server to start
    yield


def test_query_found():
    response = send_query("ExactMatch")
    assert response == "STRING EXISTS"


def test_query_not_found():
    response = send_query("DefinitelyNotInFile")
    assert response == "STRING NOT FOUND"


def test_empty_query():
    response = send_query("")
    assert response == "STRING NOT FOUND"


def test_partial_match():
    response = send_query("Exact")
    assert response == "STRING NOT FOUND"


def test_case_sensitive_match():
    response = send_query("exactmatch")
    assert response == "STRING NOT FOUND"


@pytest.mark.parametrize("reread_value", [True, False])
def test_reread_on_query_behavior(reread_value, tmp_path: Path):
    """
    Test how server reacts to file changes under REREAD_ON_QUERY = True/False
    """
    # Setup test file and config
    search_file = tmp_path / "test_data.txt"
    config_file = tmp_path / "server_test.cfg"

    search_file.write_text("InitialLine\n")

    config = ConfigParser()
    config["DEFAULT"] = {
        "LINUXPATH": str(search_file),
        "REREAD_ON_QUERY": str(reread_value),
        "SSL_ENABLED": "False",
        "HOST": "127.0.0.1",
        "PORT": "45454",
        "LOG_LEVEL": "DEBUG"
    }
    with open(config_file, "w") as f:
        config.write(f)

    # Start isolated server on port 45454
    thread = threading.Thread(target=run_server, kwargs={"config_file": str(config_file)}, daemon=True)
    thread.start()
    time.sleep(1)

    # Query existing line
    resp1 = send_query("InitialLine", host="127.0.0.1", port=45454, ssl_enabled=False)
    assert resp1 == "STRING EXISTS"

    # Change file content
    search_file.write_text("DifferentLine\n")
    time.sleep(0.2)

    # Query same line again
    resp2 = send_query("InitialLine", host="127.0.0.1", port=45454, ssl_enabled=False)
    if reread_value:
        assert resp2 == "STRING NOT FOUND"
    else:
        assert resp2 == "STRING EXISTS"
