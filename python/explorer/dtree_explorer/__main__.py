"""Start the DTree Explorer: a local web page that computes with the installed triordinal-dtree.

    dtree-explorer                 open the Explorer in the browser
    dtree-explorer --port 8765     use a fixed port (default: a free one)
    dtree-explorer --no-browser    only start the server and print its address
    dtree-explorer --save FILE     write the page as one HTML file and exit

The server listens on 127.0.0.1 only and serves the page and one computing endpoint;
nothing leaves your machine. Stop it with Ctrl+C.
"""

import argparse
import json
import platform
import sys
import webbrowser
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources

import triordinal.dtree as dtree

from . import __version__, bridge

MAX_INPUT = 4 * 1024 * 1024  # bytes of tree description per request


def page() -> bytes:
    return resources.files(__package__).joinpath("explorer.html").read_bytes()


class Handler(BaseHTTPRequestHandler):
    server_version = "DTreeExplorer/" + __version__

    def _local_host(self) -> bool:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost")       # refuses requests under other host names

    def _send(self, code, kind, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._local_host():
            return self._send(403, "text/plain", b"forbidden")
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            return self._send(200, "text/html; charset=utf-8", page())
        if path == "/api/info":
            info = {"dtree": dtree.__version__, "python": platform.python_version(), "explorer": __version__}
            return self._send(200, "application/json", json.dumps(info).encode())
        self._send(404, "text/plain", b"not found")

    def do_POST(self):
        if not self._local_host():
            return self._send(403, "text/plain", b"forbidden")
        path, _, query = self.path.partition("?")
        if path != "/api/encode":
            return self._send(404, "text/plain", b"not found")
        q = parse_qs(query)
        kind = q.get("kind", ["dtree"])[0]
        positions = q.get("positions", ["rational"])[0]
        if kind not in bridge.KINDS or positions not in bridge.POSITIONS:
            return self._send(400, "text/plain", b"kind must be dtree, dtree2 or euler, positions rational or integer")
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_INPUT:
            return self._send(413, "text/plain", b"description too large")
        text = self.rfile.read(n).decode("utf-8", "replace")
        self._send(200, "application/json", bridge.encode(text, kind=kind, positions=positions).encode())

    def log_message(self, *args):  # quiet
        pass


def serve(port=0):
    """Create the server (not yet running); port 0 picks a free port."""
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dtree-explorer", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=0, help="port on 127.0.0.1 (default: a free one)")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ap.add_argument("--save", metavar="FILE", help="write the page as one HTML file and exit")
    ap.add_argument("--version", action="version", version=f"DTree Explorer {__version__}, triordinal-dtree {dtree.__version__}")
    args = ap.parse_args(argv)
    if args.save:
        with open(args.save, "wb") as fh:
            fh.write(page())
        print(f"Wrote {args.save}. Open it in a browser; it loads Python (Pyodide) from the internet.")
        return 0
    httpd = serve(args.port)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"DTree Explorer {__version__} with triordinal-dtree {dtree.__version__} at {url}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
