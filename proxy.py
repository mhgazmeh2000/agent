#!/usr/bin/env python3
import http.server
import socketserver
import urllib.parse
import http.client
import socket
import socks
import threading

SOCKS_HOST = '127.0.0.1'
SOCKS_PORT = 12334
PROXY_PORT = 8787

def create_socks_connection(address, timeout=30):
    sock = socks.socksocket()
    sock.set_proxy(socks.SOCKS5, SOCKS_HOST, SOCKS_PORT)
    sock.settimeout(timeout)
    sock.connect(address)
    return sock

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self): self._handle('GET')
    def do_POST(self): self._handle('POST')
    def do_PUT(self): self._handle('PUT')
    def do_DELETE(self): self._handle('DELETE')
    def do_OPTIONS(self): self._send_response(200, [])

    def _send_response(self, status, headers, body=b''):
        self.send_response(status)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept')
        self.send_header('Access-Control-Expose-Headers', '*')
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _handle(self, method):
        parsed = urllib.parse.urlparse(self.path)
        target = urllib.parse.parse_qs(parsed.query).get('url', [None])[0]
        if not target:
            self._send_response(400, [], b'Missing ?url=')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        headers = {}
        for k, v in self.headers.items():
            if k.lower() in ('content-type', 'authorization', 'accept'):
                headers[k] = v

        parsed_target = urllib.parse.urlparse(target)
        is_https = parsed_target.scheme == 'https'
        port = parsed_target.port or (443 if is_https else 80)

        conn = http.client.HTTPSConnection(parsed_target.hostname, port, timeout=30) if is_https else http.client.HTTPConnection(parsed_target.hostname, port, timeout=30)
        # جایگزینی سوکت با سوکت SOCKS5
        conn.sock = create_socks_connection((parsed_target.hostname, port), timeout=30)
        conn.request(method, parsed_target.path or '/', body=body, headers=headers)
        resp = conn.getresponse()

        # ارسال پاسخ به صورت استریم (تکه‌تکه)
        self.send_response(resp.status)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept')
        self.send_header('Access-Control-Expose-Headers', '*')
        for k, v in resp.getheaders():
            if k.lower() in ('content-type', 'cache-control'):
                self.send_header(k, v)
        self.end_headers()

        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            self.wfile.write(chunk)
        conn.close()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    try:
        import socks
    except ImportError:
        print('PySocks not installed. Run: pip install pysocks')
        exit(1)

    with ThreadedTCPServer(('127.0.0.1', PROXY_PORT), ProxyHandler) as httpd:
        print(f'Proxy running on http://127.0.0.1:{PROXY_PORT} (SOCKS5 via {SOCKS_HOST}:{SOCKS_PORT})')
        print('Streaming supported. Press Ctrl+C to stop.')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nProxy stopped.')