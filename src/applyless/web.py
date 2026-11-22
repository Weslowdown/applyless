from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__
from .extract import MAX_FILE_BYTES, ExtractionError, extract_resume_file
from .scoring import score_batch


MAX_SCORE_BODY_BYTES = 1_000_000


def _asset_bytes(name: str) -> bytes:
    return files("applyless").joinpath("static", name).read_bytes()


JsonValue = dict[str, object] | list[object] | str | int | float | bool | None


class ApplyLessHandler(BaseHTTPRequestHandler):
    server_version = f"ApplyLess/{__version__}"

    def log_message(self, format: str, *args: object) -> None:
        # Do not log resume or job-description content.
        return

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'",
        )

    def _send(
        self,
        body: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") else "no-cache")
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: JsonValue, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self._send(payload, "application/json; charset=utf-8", status)

    def _read_body(self, maximum: int) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json({"error": "Invalid content length."}, HTTPStatus.BAD_REQUEST)
            return None
        if length <= 0 or length > maximum:
            self._json(
                {"error": f"Request must be between 1 byte and {maximum // 1_000_000} MB."},
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
            return None
        return self.rfile.read(length)

    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path)
        if path == "/api/health":
            self._json({"ok": True, "version": __version__})
            return
        if path == "/api/sample":
            self._json(
                {
                    "resume": files("applyless").joinpath("data/sample_resume.txt").read_text(encoding="utf-8"),
                    "jobs": files("applyless").joinpath("data/sample_jobs.txt").read_text(encoding="utf-8"),
                }
            )
            return

        asset = "index.html" if path in {"", "/"} else path.lstrip("/")
        if asset not in {"index.html", "style.css", "app.js"}:
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(asset)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type += "; charset=utf-8"
        self._send(_asset_bytes(asset), content_type)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/extract":
            body = self._read_body(MAX_FILE_BYTES)
            if body is None:
                return
            filename = parse_qs(parsed.query).get("filename", [""])[0]
            try:
                text = extract_resume_file(filename, body)
            except ExtractionError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self._json(
                {
                    "filename": filename,
                    "text": text,
                    "characters": len(text),
                    "format": Path(filename).suffix.lower().lstrip("."),
                }
            )
            return

        if parsed.path != "/api/score":
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        body = self._read_body(MAX_SCORE_BODY_BYTES)
        if body is None:
            return
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object.")
            resume = payload.get("resume")
            jobs = payload.get("jobs")
            if not isinstance(resume, str) or not isinstance(jobs, str):
                raise ValueError("Both resume and jobs must be text.")
            result = score_batch(resume, jobs)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        self._json(result)


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = ThreadingHTTPServer((host, port), ApplyLessHandler)
    url = f"http://{host}:{port}"
    print(f"ApplyLess is running locally at {url}")
    print("No resume data leaves this machine. Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()

