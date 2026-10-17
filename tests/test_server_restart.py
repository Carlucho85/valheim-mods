import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import server_restart


class RestartCurlTests(unittest.TestCase):
    def test_reads_cookie_header_from_browser_curl(self) -> None:
        request = (
            "curl 'https://dashboard.indifferentbroccoli.com/restart' "
            "-H 'accept: application/json' "
            "-H 'Cookie: session=test-session; XSRF-TOKEN=test-token' "
            "--data-raw 'action=restart'"
        )
        with tempfile.TemporaryDirectory() as temporary:
            curl_file = Path(temporary) / "restart.curl.txt"
            curl_file.write_text(request, encoding="utf-8")
            with patch.object(server_restart, "CURL_FILE", curl_file):
                url, data, headers = server_restart.load()

        self.assertEqual(url, "https://dashboard.indifferentbroccoli.com/restart")
        self.assertEqual(data, "action=restart")
        self.assertEqual(
            headers["Cookie"],
            "session=test-session; XSRF-TOKEN=test-token",
        )
        self.assertEqual(headers["accept"], "application/json")

    def test_reads_windows_command_curl_line_continuations(self) -> None:
        request = (
            'curl.exe "https://dashboard.indifferentbroccoli.com/restart" ^\r\n'
            '  -H "accept: application/json" ^\r\n'
            '  -H "Cookie: session=test-session" ^\r\n'
            '  --data-raw "action=restart"'
        )
        with tempfile.TemporaryDirectory() as temporary:
            curl_file = Path(temporary) / "restart.curl.txt"
            curl_file.write_text(request, encoding="utf-8")
            with patch.object(server_restart, "CURL_FILE", curl_file):
                url, data, headers = server_restart.load()

        self.assertEqual(url, "https://dashboard.indifferentbroccoli.com/restart")
        self.assertEqual(data, "action=restart")
        self.assertEqual(headers["Cookie"], "session=test-session")
        self.assertEqual(headers["accept"], "application/json")
