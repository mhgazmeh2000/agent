#!/usr/bin/env python3
"""
Codespace Agent Server — HTTP + SQLite
======================================
"""
import http.server, json, sqlite3, os, sys, re, urllib.parse, time, socketserver

HTTP_PORT = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == '--port' else int(os.environ.get('PORT', 8000))
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'codespace.db')
START_TIME = time.time()
LOG_BUFFER = []

def log_event(msg):
    ts = time.strftime('%H:%M:%S')
    LOG_BUFFER.append(f"[{ts}] {msg}")
    if len(LOG_BUFFER) > 200:
        LOG_BUFFER[:] = LOG_BUFFER[-100:]

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, content TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS chat_sessions (id TEXT PRIMARY KEY, title TEXT, mode TEXT, messages TEXT, created_at INTEGER, updated_at INTEGER);
        CREATE INDEX IF NOT EXISTS idx_chat_updated ON chat_sessions(updated_at DESC);
    """)
    db.commit(); db.close()
    print(f"[DB] Ready: {DB_PATH}")

init_db()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML = os.path.join(SCRIPT_DIR, 'index.html')

def get_static():
    if os.path.exists(INDEX_HTML):
        with open(INDEX_HTML, 'r', encoding='utf-8') as f:
            return f.read()
    return '<h1>File not found</h1>'

# ===== API Handlers =====
def api_files_list():
    db = get_db()
    rows = db.execute("SELECT path FROM files ORDER BY path").fetchall()
    db.close()
    return [r['path'] for r in rows]

def api_files_get(path):
    db = get_db()
    row = db.execute("SELECT content FROM files WHERE path = ?", (path,)).fetchone()
    db.close()
    return row['content'] if row else None

def api_files_put(path, content):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO files (path, content) VALUES (?, ?)", (path, content))
    db.commit(); db.close()
    log_event("file saved: " + path)

def api_files_delete(path):
    db = get_db()
    db.execute("DELETE FROM files WHERE path = ?", (path,))
    db.commit(); db.close()
    log_event("file deleted: " + path)

def api_settings_get():
    db = get_db()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    db.close()
    return {r['key']: r['value'] for r in rows}

def api_settings_put(data):
    db = get_db()
    for k, v in data.items():
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
    db.commit(); db.close()

def api_chat_list():
    db = get_db()
    rows = db.execute("SELECT id, title, mode, created_at, updated_at FROM chat_sessions ORDER BY updated_at DESC").fetchall()
    db.close()
    return [dict(r) for r in rows]

def api_chat_post(data):
    db = get_db()
    sid = data.get('id', 'sess_' + str(int(time.time()*1000)))
    db.execute("INSERT OR REPLACE INTO chat_sessions (id,title,mode,messages,created_at,updated_at) VALUES (?,?,?,?,?,?)",
               (sid, data.get('title','چت جدید'), data.get('mode','agent'),
                json.dumps(data.get('messages',[])), data.get('createdAt',0), data.get('updatedAt',0)))
    db.commit(); db.close()
    log_event("chat created: " + data.get('mode','?'))
    return {'id': sid}

def api_chat_put(sid, data):
    db = get_db()
    fields = {k: v for k, v in data.items() if k in ('title','mode','messages','updated_at')}
    if 'messages' in fields:
        fields['messages'] = json.dumps(fields['messages'])
    if fields:
        sets = ', '.join(f"{k}=?" for k in fields)
        vals = list(fields.values()) + [sid]
        db.execute(f"UPDATE chat_sessions SET {sets} WHERE id=?", vals)
    db.commit(); db.close()

def api_chat_delete(sid):
    db = get_db()
    db.execute("DELETE FROM chat_sessions WHERE id=?", (sid,))
    db.commit(); db.close()
    log_event("chat deleted: " + sid[:20])

def api_chat_get_messages(sid):
    db = get_db()
    row = db.execute("SELECT messages FROM chat_sessions WHERE id=?", (sid,)).fetchone()
    db.close()
    return json.loads(row['messages']) if row else []

def api_system_status():
    dbs = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    return {
        'uptime_seconds': int(time.time() - START_TIME),
        'python_version': sys.version,
        'platform': sys.platform,
        'db_size_mb': round(dbs/1024/1024, 2),
        'pid': os.getpid(),
    }

def api_system_db_stats():
    db = get_db()
    stats = {}
    stats['files'] = db.execute("SELECT COUNT(*) as n FROM files").fetchone()['n']
    stats['settings'] = db.execute("SELECT COUNT(*) as n FROM settings").fetchone()['n']
    stats['sessions'] = db.execute("SELECT COUNT(*) as n FROM chat_sessions").fetchone()['n']
    rows = db.execute("SELECT mode, COUNT(*) as n FROM chat_sessions GROUP BY mode").fetchall()
    stats['by_mode'] = {r['mode']: r['n'] for r in rows}
    rows = db.execute("SELECT path, LENGTH(content) as s FROM files ORDER BY s DESC LIMIT 15").fetchall()
    stats['top_files'] = [{'path': r['path'], 'kb': round(r['s']/1024,1)} for r in rows]
    db.close()
    return stats

def api_system_files():
    db = get_db()
    rows = db.execute("SELECT path, LENGTH(content) as size FROM files ORDER BY path").fetchall()
    db.close()
    return [{'path': r['path'], 'size_kb': round(r['size']/1024,1)} for r in rows]

def api_system_logs():
    return {'logs': LOG_BUFFER[-50:]}

# ===== CORS =====
def cors():
    return [
        ('Access-Control-Allow-Origin', '*'),
        ('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS'),
        ('Access-Control-Allow-Headers', 'Content-Type,Authorization'),
    ]

def send_json(h, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode()
    h.send_response(status)
    h.send_header('Content-Type', 'application/json; charset=utf-8')
    h.send_header('Content-Length', str(len(body)))
    for k, v in cors(): h.send_header(k, v)
    h.end_headers()
    h.wfile.write(body)

def read_body(h):
    length = int(h.headers.get('Content-Length', 0))
    return json.loads(h.rfile.read(length)) if length else {}

# ===== Handler =====
class H(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in cors(): self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p == '/api/files': return send_json(self, api_files_list())
        m = re.match(r'^/api/files/(.+)$', p)
        if m:
            c = api_files_get(urllib.parse.unquote(m.group(1)))
            return send_json(self, {'path': m.group(1), 'content': c}) if c else send_json(self, {'error':'not found'}, 404)
        if p == '/api/settings': return send_json(self, api_settings_get())
        if p == '/api/chat/sessions': return send_json(self, api_chat_list())
        m = re.match(r'^/api/chat/sessions/([^/]+)/messages$', p)
        if m: return send_json(self, api_chat_get_messages(m.group(1)))
        if p == '/api/system/status': return send_json(self, api_system_status())
        if p == '/api/system/db-stats': return send_json(self, api_system_db_stats())
        if p == '/api/system/files': return send_json(self, api_system_files())
        if p == '/api/system/logs': return send_json(self, api_system_logs())
        # Static
        html = get_static().encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        d = read_body(self)
        if p == '/api/chat/sessions':
            return send_json(self, api_chat_post(d), 201)
        send_json(self, {'error':'not found'}, 404)

    def do_PUT(self):
        p = urllib.parse.urlparse(self.path).path
        d = read_body(self)
        m = re.match(r'^/api/files/(.+)$', p)
        if m: api_files_put(urllib.parse.unquote(m.group(1)), d.get('content','')); return send_json(self, {'ok':True})
        if p == '/api/settings': api_settings_put(d); return send_json(self, {'ok':True})
        m = re.match(r'^/api/chat/sessions/([^/]+)$', p)
        if m: api_chat_put(m.group(1), d); return send_json(self, {'ok':True})
        send_json(self, {'error':'not found'}, 404)

    def do_DELETE(self):
        p = urllib.parse.urlparse(self.path).path
        m = re.match(r'^/api/files/(.+)$', p)
        if m: api_files_delete(urllib.parse.unquote(m.group(1))); return send_json(self, {'ok':True})
        m = re.match(r'^/api/chat/sessions/([^/]+)$', p)
        if m: api_chat_delete(m.group(1)); return send_json(self, {'ok':True})
        send_json(self, {'error':'not found'}, 404)

    def log_message(self, fmt, *args):
        if '/api/' in str(args[0]): sys.stderr.write(f"[api] {args[0]}\n")

class TS(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == '__main__':
    print('='*50)
    print(f'   Codespace Agent Server  :8000')
    print(f'   DB: {DB_PATH}')
    print('='*50)
    s = TS(('0.0.0.0', HTTP_PORT), H)
    try: s.serve_forever()
    except KeyboardInterrupt: print('\nStopped.'); s.shutdown()
