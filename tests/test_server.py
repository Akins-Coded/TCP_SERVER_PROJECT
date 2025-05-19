import tempfile
import os
import pytest
from unittest import mock
import server.server as server_module


@pytest.fixture
def temp_file_with_lines():
    content = [
        "TestLine1",
        "ExactMatch",
        " Another Line with leading space ",
        "",
        "TrailingSpace ",
        "CaseSensitive",
        "casesensitive"
    ]
    with tempfile.NamedTemporaryFile('w+', delete=False) as tmp:
        tmp.write("\n".join(content) + "\n")
        tmp_path = tmp.name
    yield tmp_path
    os.remove(tmp_path)


def test_exact_match(temp_file_with_lines):
    with mock.patch.object(server_module, "LINUX_PATH", temp_file_with_lines), \
         mock.patch.object(server_module, "REREAD_ON_QUERY", True):
        assert server_module.search_in_file("ExactMatch") == "STRING EXISTS"


def test_leading_trailing_spaces_not_found(temp_file_with_lines):
    with mock.patch.object(server_module, "LINUX_PATH", temp_file_with_lines), \
         mock.patch.object(server_module, "REREAD_ON_QUERY", True):
        # exact match includes spaces; query with stripped spaces should not match line with spaces
        assert server_module.search_in_file("Another Line with leading space") == "STRING NOT FOUND"
        # querying with exact spaces should match
        assert server_module.search_in_file(" Another Line with leading space ") == "STRING EXISTS"
        assert server_module.search_in_file("TrailingSpace ") == "STRING EXISTS"
        # query without trailing space does not match
        assert server_module.search_in_file("TrailingSpace") == "STRING NOT FOUND"


def test_empty_line_match(temp_file_with_lines):
    with mock.patch.object(server_module, "LINUX_PATH", temp_file_with_lines), \
         mock.patch.object(server_module, "REREAD_ON_QUERY", True):
        assert server_module.search_in_file("") == "STRING EXISTS"


def test_case_sensitivity(temp_file_with_lines):
    with mock.patch.object(server_module, "LINUX_PATH", temp_file_with_lines), \
         mock.patch.object(server_module, "REREAD_ON_QUERY", True):
        assert server_module.search_in_file("CaseSensitive") == "STRING EXISTS"
        assert server_module.search_in_file("casesensitive") == "STRING EXISTS"
        # Different casing that does not match exactly
        assert server_module.search_in_file("casesensitive ".strip()) == "STRING EXISTS"  # exact line is "casesensitive"
        assert server_module.search_in_file("CASESENSITIVE") == "STRING NOT FOUND"


def test_partial_match_not_found(temp_file_with_lines):
    with mock.patch.object(server_module, "LINUX_PATH", temp_file_with_lines), \
         mock.patch.object(server_module, "REREAD_ON_QUERY", True):
        assert server_module.search_in_file("Exact") == "STRING NOT FOUND"
        assert server_module.search_in_file("Test") == "STRING NOT FOUND"


def test_file_not_found_error():
    with mock.patch.object(server_module, "LINUX_PATH", "/nonexistent/path/to/file.txt"), \
         mock.patch.object(server_module, "REREAD_ON_QUERY", True):
        assert server_module.search_in_file("TestLine") == "ERROR"


def test_permission_error(monkeypatch):
    # Patch open to raise PermissionError
    def raise_permission_error(*args, **kwargs):
        raise PermissionError("Permission denied")

    with mock.patch.object(server_module, "LINUX_PATH", "dummy_path"), \
         mock.patch.object(server_module, "REREAD_ON_QUERY", True), \
         mock.patch("builtins.open", raise_permission_error):
        assert server_module.search_in_file("TestLine") == "ERROR"


def test_unicode_decode_error(monkeypatch):
    # Patch open to return a file-like object that raises UnicodeDecodeError on iteration
    class FakeFile:
        def __iter__(self):
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "reason")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def fake_open(*args, **kwargs):
        return FakeFile()

    with mock.patch.object(server_module, "LINUX_PATH", "dummy_path"), \
         mock.patch.object(server_module, "REREAD_ON_QUERY", True), \
         mock.patch("builtins.open", fake_open):
        assert server_module.search_in_file("TestLine") == "ERROR"
