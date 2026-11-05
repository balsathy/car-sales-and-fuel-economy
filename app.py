"""Small local web app for downloading vehicle data and asking numeric questions."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

from chatbot import answer


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SALES_FILE = DATA_DIR / "sales.json"
EPA_FILE = DATA_DIR / "mileage.json"


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, value: dict) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/status":
            sales = _load(SALES_FILE)
            mileage = _load(EPA_FILE)
            self._json(200, {
                "sales_years": sorted({r["year"] for r in sales.get("records", [])}),
                "sales_records": len(sales.get("records", [])),
                "sales_source": sales.get("source_url"),
                "mileage_years": sorted({r["year"] for r in mileage.get("records", [])}),
                "mileage_records": len(mileage.get("records", [])),
                "mileage_source": mileage.get("source_url"),
            })
            return
        if path in ("/", "/index.html"):
            file_path = ROOT / "public" / "index.html"
            payload = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16_384:
                self._json(413, {"error": "Request too large"})
                return
            body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/chat":
                self._json(200, {"answer": answer(
                    str(body.get("message", "")), _load(SALES_FILE), _load(EPA_FILE)
                )})
            else:
                self._json(404, {"error": "Not found"})
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            self._json(502, {"error": f"Data source request failed: {exc}"})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", file=sys.stderr)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Vehicle data chatbot: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
