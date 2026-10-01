"""Dependency-free preview server. No shared project state or browser-side secrets."""

import argparse
import json
import logging
import mimetypes
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from engine import ROOT, analyze, load_policy
from exports import export_csv, export_proposal
from learning import apply_proposals
from market import ResearchError, ResearchUnavailable, research_enabled, search_market
from validation import ValidationError, obj, validate_project

MAX_BODY = 1_048_576
STATIC = {"/": "index.html", "/index.html": "index.html", "/styles.css": "styles.css", "/app.js": "app.js"}
RESEARCH_SLOTS = threading.BoundedSemaphore(2)
LOGGER = logging.getLogger("eo-agent")


class Handler(BaseHTTPRequestHandler):
    server_version = "EOAgent/1.0"

    def log_message(self, fmt, *args):
        LOGGER.info(fmt, *args)

    def send(self, status, body, content_type="application/json; charset=utf-8", filename=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        # Deliberately no X-Frame-Options: Arena embeds the same-origin preview.
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, status, payload):
        self.send(status, json.dumps(payload, ensure_ascii=False, allow_nan=False))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in STATIC:
            file = ROOT / "web" / STATIC[path]
            content_type = mimetypes.guess_type(str(file))[0] or "application/octet-stream"
            self.send(200, file.read_bytes(), content_type + "; charset=utf-8")
        elif path == "/api/health":
            self.send_json(200, {"ok": True, "version": "1.0.0"})
        elif path == "/api/bootstrap":
            data = json.loads((ROOT / "data" / "templates.json").read_text(encoding="utf-8"))
            self.send_json(200, {**data, "policy": load_policy(), "today": date.today().isoformat(),
                                 "researchEnabled": research_enabled(), "engineMode": "parallel-rules"})
        else:
            self.send_json(404, {"error": "Halaman atau endpoint tidak ditemukan."})

    def same_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True  # CLI clients do not send Origin.
        try:
            parsed = urlsplit(origin)
            hosts = {self.headers.get("Host", "").lower(), self.headers.get("X-Forwarded-Host", "").split(",")[0].strip().lower()}
            return parsed.scheme in {"http", "https"} and not parsed.username and not parsed.password and parsed.netloc.lower() in hosts
        except ValueError:
            return False

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_BODY:
            self.close_connection = True
            self.send_json(413 if length > MAX_BODY else 400, {"error": "Body JSON wajib diisi, maksimal 1 MB."})
            return None
        if self.headers.get_content_type() != "application/json":
            self.close_connection = True
            self.send_json(415, {"error": "Gunakan Content-Type: application/json."})
            return None
        try:
            raw = self.rfile.read(length)
            def reject_constant(value):
                raise ValueError("Non-finite JSON number")
            return obj(json.loads(raw.decode("utf-8"), parse_constant=reject_constant), "body")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            self.send_json(400, {"error": "JSON tidak valid. Gunakan objek dan angka finite."})
            return None

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in {"/api/analyze", "/api/learning/apply", "/api/export", "/api/market/search"}:
            self.close_connection = True
            self.send_json(404, {"error": "Endpoint tidak ditemukan."})
            return
        if not self.same_origin():
            self.close_connection = True
            self.send_json(403, {"error": "Permintaan lintas origin tidak diizinkan."})
            return
        payload = self.read_json()
        if payload is None:
            return
        try:
            if path == "/api/analyze":
                project = validate_project(payload)
                self.send_json(200, {"project": project, "report": analyze(project)})
            elif path == "/api/learning/apply":
                project = apply_proposals(payload.get("project"), payload.get("proposalIds"), load_policy())
                self.send_json(200, {"project": project, "report": analyze(project)})
            elif path == "/api/export":
                project = validate_project(payload.get("project"))
                report = analyze(project)
                format_name = payload.get("format")
                if format_name == "csv":
                    self.send(200, export_csv(project, report), "text/csv; charset=utf-8", "rab-internal.csv")
                elif format_name == "proposal":
                    self.send(200, export_proposal(project, report), "text/html; charset=utf-8", "draft-penawaran.html")
                else:
                    raise ValidationError("Format export harus csv atau proposal.", "format")
            else:
                if not RESEARCH_SLOTS.acquire(blocking=False):
                    self.send_json(429, {"error": "Riset lain masih berlangsung. Coba lagi nanti."})
                    return
                try:
                    self.send_json(200, search_market(payload.get("query"), payload.get("city")))
                finally:
                    RESEARCH_SLOTS.release()
        except ValidationError as error:
            self.send_json(422, {"error": str(error), "field": error.field})
        except ResearchUnavailable as error:
            self.send_json(503, {"error": str(error)})
        except ResearchError as error:
            self.send_json(502, {"error": str(error)})
        except Exception:
            LOGGER.exception("Unhandled endpoint failure")
            self.send_json(500, {"error": "Kalkulasi gagal. Periksa log server; tidak ada perubahan proyek yang diterapkan."})


def create_server(host="0.0.0.0", port=8080):
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    # Bound reads so incomplete uploads cannot retain a handler indefinitely.
    original_finish_request = server.finish_request
    def finish_request(request, client_address):
        request.settimeout(30)
        original_finish_request(request, client_address)
    server.finish_request = finish_request
    return server


def main():
    parser = argparse.ArgumentParser(description="EO agent dashboard")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = create_server(args.host, args.port)
    LOGGER.info("EO dashboard listening on http://%s:%s", args.host, server.server_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
