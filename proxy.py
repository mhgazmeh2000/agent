#!/usr/bin/env python3
"""
CORS Proxy + SOCKS5 Tunnel (Hiddify)
=====================================
درخواست HTTP از مرورگر میاد → CORS headers اضافه میشه
→ از طریق SOCKS5 (Hiddify:127.0.0.1:12334) به API مقصد فوروارد میشه

این نسخه با مانکی‌پچ کردن socket.create_connection کار میکنه
یعنی تمام http.client خودکار از SOCKS5 رد میشن.
"""

import http.server
import socketserver
import urllib.parse
import http.client
import socket
import socks
import ssl
import sys

# ===== تنظیمات =====
SOCKS_HOST = sys.argv[sys.argv.index('--socks-host') + 1] if '--socks-host' in sys.argv else os.environ.get('SOCKS_HOST', '127.0.0.1')
SOCKS_PORT = int(sys.argv[sys.argv.index('--socks-port') + 1]) if '--socks-port' in sys.argv else int(os.environ.get('SOCKS_PORT', '12334'))
PROXY_PORT = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else int(os.environ.get('PROXY_PORT', '8787'))
TIMEOUT = 60

# ===== مانکی‌پچ: تمام کانکشن‌ها از SOCKS5 رد بشن =====
socks.set_default_proxy(socks.SOCKS5, SOCKS_HOST, SOCKS_PORT)
socks.wrap_module(socket)

# ===== CORS Headers =====
CORS_HEADERS = [
    ('Access-Control-Allow-Origin', '*'),
    ('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS,PATCH'),
    ('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept,X-Requested-With'),
    ('Access-Control-Expose-Headers', '*'),
    ('Access-Control-Max-Age', '86400'),
]


def forward_headers(headers_dict):
    """فقط هدرهای مفید رو فوروارد کن"""
    allowed = {'content-type', 'authorization', 'accept', 'x-requested-with'}
    return {k: v for k, v in headers_dict.items() if k.lower() in allowed}


def do_request(method, url, headers, body):
    """
    ارسال درخواست به مقصد از طریق SOCKS5
    برمیگردونه: (status_code, response_headers, body_bytes)
    """
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    path = parsed.path or '/'
    if parsed.query:
        path += '?' + parsed.query

    fwd = forward_headers(headers)
    if body and 'content-type' in headers:
        fwd['Content-Type'] = headers['content-type']
    if body:
        fwd['Content-Length'] = str(len(body))

    conn = http.client.HTTPSConnection(hostname, port, timeout=TIMEOUT) \
        if parsed.scheme == 'https' \
        else http.client.HTTPConnection(hostname, port, timeout=TIMEOUT)

    try:
        conn.request(method, path, body=body or None, headers=fwd)
        resp = conn.getresponse()
        status = resp.status
        resp_headers = [(k, v) for k, v in resp.getheaders()
                        if k.lower() in ('content-type', 'cache-control', 'content-length')]
        resp_body = resp.read()
        return (status, resp_headers, resp_body)
    finally:
        conn.close()


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """هندلر پروکسی CORS"""

    def do_OPTIONS(self):
        self._send_cors(204)

    def do_GET(self):
        self._handle('GET')

    def do_POST(self):
        self._handle('POST')

    def do_PUT(self):
        self._handle('PUT')

    def do_DELETE(self):
        self._handle('DELETE')

    def _send_cors(self, status, extra_headers=None, body=b''):
        self.send_response(status)
        for k, v in CORS_HEADERS:
            self.send_header(k, v)
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        if body:
            self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _handle(self, method):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        target = params.get('url', [None])[0]

        if not target:
            self._send_cors(400, body=b'Missing ?url= parameter')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''

        try:
            status, resp_headers, resp_body = do_request(
                method, target, dict(self.headers), body
            )
            self._send_cors(status, resp_headers, resp_body)
        except Exception as e:
            msg = str(e).encode()
            self._send_cors(502, body=b'Proxy Error: ' + msg)

    def log_message(self, format, *args):
        # لاگ خلاصه
        sys.stderr.write(f"[proxy] {args[0]}\n")


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    print('=' * 55)
    print('   Codespace Agent — CORS + SOCKS5 Proxy')
    print(f'   CORS Proxy : http://127.0.0.1:{PROXY_PORT}')
    print(f'   Tunnel     : SOCKS5 → {SOCKS_HOST}:{SOCKS_PORT} (Hiddify)')
    print('   Ctrl+C to stop')
    print('=' * 55)

    with ThreadedTCPServer(('127.0.0.1', PROXY_PORT), ProxyHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nProxy stopped.')
