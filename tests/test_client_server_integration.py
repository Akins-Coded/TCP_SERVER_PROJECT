import unittest
import threading
import time
import socket
import tempfile

from pathlib import Path
from configparser import ConfigParser

from client import send_query
from server import TCPServer  # Assuming this class exists


def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class ServerThread(threading.Thread):
    def __init__(self, config_file: str):
        super().__init__(daemon=True)
        self.config_file = config_file
        self.server = None

    def run(self):
        self.server = TCPServer(config_file=self.config_file)
        self.server.run()

    def stop(self):
        # Implement a graceful stop if your TCPServer supports it
        # For now, daemon thread will just exit when main exits
        pass


class TestClientServerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Prepare temp files and config
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_dir = Path(cls.temp_dir.name)

        # Create test data file
        cls.search_file = cls.test_dir / "test_data.txt"
        cls.search_file.write_text("ExactMatch\nAnotherLine\nThirdLine\n")

        # Create config file for the server
        cls.config_file = cls.test_dir / "server_test.cfg"

        cls.port = find_free_port()

        config = ConfigParser()
        config["DEFAULT"] = {
            "LINUXPATH": str(cls.search_file),
            "REREAD_ON_QUERY": "False",
            "SSL_ENABLED": "False",
            "HOST": "127.0.0.1",
            "PORT": str(cls.port),
            "LOG_LEVEL": "DEBUG"
        }
        with open(cls.config_file, "w") as f:
            config.write(f)

        # Start server thread
        cls.server_thread = ServerThread(config_file=str(cls.config_file))
        cls.server_thread.start()

        # Wait for server to be ready: retry connection a few times
        for _ in range(10):
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.5):
                    break
            except (ConnectionRefusedError, socket.timeout):
                time.sleep(0.3)
        else:
            raise RuntimeError("Server did not start in time")

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()
        # Ideally, stop server thread if implemented graceful stop

    def test_query_found(self):
        response = send_query("ExactMatch", host="127.0.0.1", port=self.port, ssl_enabled=False)
        self.assertEqual(response, "STRING EXISTS")

    def test_query_not_found(self):
        response = send_query("DefinitelyNotInFile", host="127.0.0.1", port=self.port, ssl_enabled=False)
        self.assertEqual(response, "STRING NOT FOUND")

    def test_empty_query(self):
        response = send_query("", host="127.0.0.1", port=self.port, ssl_enabled=False)
        # Adjust expectation to match your server's response for empty input
        self.assertEqual(response, "INVALID REQUEST")

    def test_partial_match(self):
        response = send_query("Exact", host="127.0.0.1", port=self.port, ssl_enabled=False)
        self.assertEqual(response, "STRING NOT FOUND")

    def test_case_sensitive_match(self):
        response = send_query("exactmatch", host="127.0.0.1", port=self.port, ssl_enabled=False)
        self.assertEqual(response, "STRING NOT FOUND")


class TestRereadOnQueryBehavior(unittest.TestCase):
    def test_reread_on_query_toggle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            search_file = tmp_path / "test_data.txt"
            search_file.write_text("InitialLine\n")

            config_file = tmp_path / "server_test.cfg"

            for reread_value in [True, False]:
                config = ConfigParser()
                config["DEFAULT"] = {
                    "LINUXPATH": str(search_file),
                    "REREAD_ON_QUERY": str(reread_value),
                    "SSL_ENABLED": "False",
                    "HOST": "127.0.0.1",
                    "PORT": "0",  # Let OS assign port dynamically
                    "LOG_LEVEL": "DEBUG"
                }
                with open(config_file, "w") as f:
                    config.write(f)

                port = find_free_port()
                # Override port in config file dynamically
                config.set("DEFAULT", "PORT", str(port))
                with open(config_file, "w") as f:
                    config.write(f)

                server_thread = ServerThread(config_file=str(config_file))
                server_thread.start()

                # Wait for server ready
                for _ in range(10):
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                            break
                    except (ConnectionRefusedError, socket.timeout):
                        time.sleep(0.3)
                else:
                    self.fail("Server did not start in time")

                try:
                    response_before = send_query("InitialLine", host="127.0.0.1", port=port, ssl_enabled=False)
                    self.assertEqual(response_before, "STRING EXISTS")

                    # Change file content
                    search_file.write_text("DifferentLine\n")
                    time.sleep(0.2)

                    response_after = send_query("InitialLine", host="127.0.0.1", port=port, ssl_enabled=False)
                    if reread_value:
                        self.assertEqual(response_after, "STRING NOT FOUND")
                    else:
                        self.assertEqual(response_after, "STRING EXISTS")
                finally:
                    # Server thread is daemon, will exit after test ends
                    pass


if __name__ == "__main__":
    unittest.main()
