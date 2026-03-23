import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class MockPortalHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[MOCK SERVER] {self.address_string()} - {format % args}")

    def _send_html(self, code, body):
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/addtenantpgverification.htm":
            html = (
                "<html><body>\n"
                "<form method=\"POST\" action=\"/addtenantpgverification.htm\">\n"
                "<button type=\"submit\" id=\"submit123\">Submit</button>\n"
                "</form>\n"
                "</body></html>"
            )
            self._send_html(200, html)
        else:
            self._send_html(404, "Not Found")

    def do_POST(self):
        if self.path == "/addtenantpgverification.htm":
            content_length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(content_length)
            print("[MOCK SERVER] POST received — sleeping 35 seconds...")
            time.sleep(35)
            print("[MOCK SERVER] Sleep complete — sending success response")
            html = (
                "<html><body>\n"
                "Service Request Number 816726116784 has been registered\n"
                "on 22/03/2026 at 21:16\n"
                "<a href=\"javascript:openNewWindowForPrint('getTenantReport.htm');\">\n"
                "Click here to Print</a>\n"
                "</body></html>"
            )
            self._send_html(200, html)
        else:
            self._send_html(404, "Not Found")

def start_mock_server(port=8080):
    server = ThreadingHTTPServer(("", port), MockPortalHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[MOCK SERVER] Started on http://localhost:{port}")
    return server

def stop_mock_server(server):
    server.shutdown()
    print("[MOCK SERVER] Stopped")
