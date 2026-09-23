"""tests 共享 fixture：本地假 HTTP 服务器（离线可跑，不依赖外网）"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


class _Handler(BaseHTTPRequestHandler):
    call_count = {}  # path -> 调用次数（用于重试测试）

    def log_message(self, *args):  # 静默默认日志
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]  # 忽略 query string
        if path == "/user":
            self._send(200, {"code": 0, "data": {"id": 42, "name": "tester",
                                                 "token": "tok123"}})
        elif path == "/flaky":
            n = self.call_count.get(self.path, 0) + 1
            self.call_count[self.path] = n
            self._send(200 if n >= 3 else 500, {"attempt": n})
        elif path == "/slow":
            import time
            time.sleep(0.3)
            self._send(200, {"slow": True})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        if path == "/echo":
            self._send(200, {"code": 0, "echo": json.loads(raw or b"{}")})
        elif path == "/flaky_post":
            self._send(500, {"error": "always fail"})
        else:
            self._send(404, {"error": "not found"})


@pytest.fixture(scope="session")
def fake_base_url():
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
