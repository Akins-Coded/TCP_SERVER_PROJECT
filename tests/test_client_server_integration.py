import unittest
import threading
import time
from client import send_query
from server import run_server
from configparser import ConfigParser
from pathlib import Path


class TestClientServerIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_thread = threading.Thread(target=run_server, daemon=True)
        cls.server_thread.start()
        time.sleep(1)

    def test_query_found(self):
        self.assertEqual(send_query("ExactMatch"), "STRING EXISTS")

    def test_query_not_found(self):
        self.assertEqual(send_query("DefinitelyNotInFile"), "STRING NOT FOUND")

    def test_empty_query(self):
        self.assertEqual(send_query(""), "STRING NOT FOUND")

    def test_partial_match(self):
        self.assertEqual(send_query("Exact"), "STRING NOT FOUND")

    def test_case_sensitive_match(self):
        self.assertEqual(send_query("exactmatch"), "STRING NOT FOUND")


class TestRereadOnQueryBehavior(unittest.TestCase):
    def test_reread_on_query_toggle(self):
        for reread_value in [True, False]:
            with self.subTest(reread_value=reread_value):
                tmp_path = Path("tests/tmp")
                tmp_path.mkdir(parents=True, exist_ok=True)

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

                thread = threading.Thread(
                    target=run_server,
                    kwargs={"config_file": str(config_file)},
                    daemon=True
                )
                thread.start()
                time.sleep(1)

                response_before = send_query("InitialLine", host="127.0.0.1", port=45454, ssl_enabled=False)
                self.assertEqual(response_before, "STRING EXISTS")

                search_file.write_text("DifferentLine\n")
                time.sleep(0.2)

                response_after = send_query("InitialLine", host="127.0.0.1", port=45454, ssl_enabled=False)
                if reread_value:
                    self.assertEqual(response_after, "STRING NOT FOUND")
                else:
                    self.assertEqual(response_after, "STRING EXISTS")


if __name__ == "__main__":
    unittest.main()
