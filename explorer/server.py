"""Small web UI and JSON API for browsing Charades labels.

Standard library only (http.server). Routes:

    GET /                      the single-page UI
    GET /api/meta              dataset stats + filter options
    GET /api/videos?...        filtered, sorted, paginated video list
    GET /api/videos/<id>       full labels for one video
    GET /healthz               liveness check (for hosting platforms)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .loader import DEFAULT_DATA_DIR, Dataset, DatasetNotFound, load_dataset
from .search import Filters, facets, search

STATIC_DIR = Path(__file__).resolve().parent / "static"
# Explicit allow-list, so request paths never touch the filesystem directly.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
MAX_LIMIT = 200


def make_handler(ds: Dataset):
    meta = {"stats": ds.stats(), **facets(ds.videos, ds.classes)}

    class Handler(BaseHTTPRequestHandler):
        server_version = "CharadesExplorer/1.0"

        def do_GET(self) -> None:
            url = urlparse(self.path)
            path = url.path
            params = {k: v[-1] for k, v in parse_qs(url.query).items()}

            if path in STATIC_FILES:
                self.send_static(*STATIC_FILES[path])
            elif path == "/healthz":
                self.send_json({"ok": True})
            elif path == "/api/meta":
                self.send_json(meta)
            elif path == "/api/videos":
                self.list_videos(params)
            elif path.startswith("/api/videos/"):
                self.get_video(unquote(path.rsplit("/", 1)[-1]))
            else:
                self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def list_videos(self, params: dict) -> None:
            try:
                filters = Filters.from_params(params)
                limit = min(MAX_LIMIT, max(1, int(params.get("limit", 50))))
                offset = max(0, int(params.get("offset", 0)))
                total, page = search(ds.videos, filters, params.get("sort", "id"), limit, offset)
            except ValueError as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.send_json({
                "total": total,
                "offset": offset,
                "limit": limit,
                "results": [v.summary_dict() for v in page],
            })

        def get_video(self, video_id: str) -> None:
            video = ds.by_id.get(video_id.upper())
            if video is None:
                self.send_json({"error": f"no video {video_id!r}"}, HTTPStatus.NOT_FOUND)
            else:
                self.send_json(video.detail_dict())

        def send_json(self, payload, status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_static(self, filename: str, content_type: str) -> None:
            body = (STATIC_DIR / filename).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:
            sys.stderr.write(f"[http] {self.address_string()} {fmt % args}\n")

    return Handler


def main(argv=None) -> int:
    # Hosting platforms (Render, Railway, Replit...) pass the port via $PORT
    # and need the server reachable from outside the container.
    env_port = os.environ.get("PORT")
    parser = argparse.ArgumentParser(prog="run.sh", description="Serve the Charades Explorer web UI.")
    parser.add_argument("--host", default="0.0.0.0" if env_port else "127.0.0.1")
    parser.add_argument("--port", type=int, default=int(env_port or 8000))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args(argv)

    started = time.perf_counter()
    try:
        ds = load_dataset(args.data_dir)
    except DatasetNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    s = ds.stats()
    print(f"Loaded {s['videos']:,} videos and {s['segments']:,} action segments "
          f"in {time.perf_counter() - started:.2f}s")
    if ds.warnings:
        print(f"({len(ds.warnings)} malformed label entries skipped)")

    server = ThreadingHTTPServer((args.host, args.port), make_handler(ds))
    shown_host = "localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host
    print(f"Charades Explorer running at http://{shown_host}:{args.port}  (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
