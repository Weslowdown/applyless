from __future__ import annotations

import json
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from applyless.web import ApplyLessHandler


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ApplyLessHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        host, port = cls.server.server_address
        cls.base_url = f"http://{host}:{port}"
        cls.resume = (ROOT / "samples/resume.txt").read_text(encoding="utf-8")
        cls.jobs = (ROOT / "samples/jobs.txt").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_home_page_has_security_headers(self) -> None:
        with urlopen(f"{self.base_url}/", timeout=3) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Find the roles", body)
            self.assertIn("Your shortlist", body)
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_score_endpoint_returns_ranked_jobs(self) -> None:
        payload = json.dumps({"resume": self.resume, "jobs": self.jobs}).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/score",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            result = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual(len(result["jobs"]), 3)
        self.assertEqual(result["jobs"][0]["company"], "Northstar Labs")
        self.assertEqual(result["jobs"][0]["score"], 85)

    def test_score_endpoint_rejects_short_resume(self) -> None:
        payload = json.dumps({"resume": "short", "jobs": self.jobs}).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/score",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as context:
            urlopen(request, timeout=3)
        self.assertEqual(context.exception.code, 400)

    def test_unknown_asset_is_not_served(self) -> None:
        with self.assertRaises(HTTPError) as context:
            urlopen(f"{self.base_url}/../pyproject.toml", timeout=3)
        self.assertEqual(context.exception.code, 404)

    def test_docx_import_endpoint(self) -> None:
        document = """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
        <w:body><w:p><w:r><w:t>Python and SQL product analytics experience</w:t></w:r></w:p></w:body>
        </w:document>"""
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", document)
        request = Request(
            f"{self.base_url}/api/extract?filename=resume.docx",
            data=buffer.getvalue(),
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            result = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual(result["filename"], "resume.docx")
        self.assertIn("Python and SQL", result["text"])


if __name__ == "__main__":
    unittest.main()

