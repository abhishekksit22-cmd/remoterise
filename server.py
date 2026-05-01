#!/usr/bin/env python3
"""RemoteRise Backend Server - Python/Flask-free implementation using only stdlib"""

import http.server
import json
import sqlite3
import os
import urllib.parse
import base64
import io
import csv
from datetime import datetime, timedelta
from pathlib import Path

PORT = int(os.environ.get('PORT', 3000))
ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'remoterise2026')
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'remoterise.db')
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        whatsapp_number TEXT NOT NULL,
        email TEXT NOT NULL,
        age TEXT,
        college_name TEXT NOT NULL,
        hostel_city TEXT,
        source TEXT,
        job_types TEXT,
        available_hours TEXT,
        english_level TEXT,
        device_access TEXT,
        work_experience TEXT,
        family_member_name TEXT NOT NULL,
        family_member_phone TEXT NOT NULL,
        agreed_terms INTEGER DEFAULT 0,
        submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'new'
    )''')
    conn.commit()
    conn.close()


def parse_multipart(content_type, body):
    """Parse multipart/form-data"""
    boundary = content_type.split('boundary=')[1].strip()
    parts = body.split(('--' + boundary).encode())
    data = {}
    for part in parts:
        if b'Content-Disposition' not in part:
            continue
        header_body = part.split(b'\r\n\r\n', 1)
        if len(header_body) < 2:
            continue
        header = header_body[0].decode('utf-8', errors='replace')
        value = header_body[1].rstrip(b'\r\n--').decode('utf-8', errors='replace').strip()
        name_start = header.find('name="') + 6
        name_end = header.find('"', name_start)
        name = header[name_start:name_end]
        if name in data:
            if isinstance(data[name], list):
                data[name].append(value)
            else:
                data[name] = [data[name], value]
        else:
            data[name] = value
    return data


def parse_urlencoded(body):
    """Parse application/x-www-form-urlencoded"""
    return {k: v[0] if len(v) == 1 else v for k, v in urllib.parse.parse_qs(body.decode(), keep_blank_values=True).items()}


class RemoteRiseHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, filepath):
        ext_map = {'.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
                    '.png': 'image/png', '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.svg': 'image/svg+xml'}
        ext = os.path.splitext(filepath)[1]
        ctype = ext_map.get(ext, 'application/octet-stream')
        try:
            with open(filepath, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', ctype + ('; charset=utf-8' if ext in ('.html', '.css', '.js') else ''))
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def check_admin(self):
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Basic '):
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="RemoteRise Admin"')
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Auth required'}).encode())
            return False
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            user, passwd = decoded.split(':', 1)
            if user == ADMIN_USER and passwd == ADMIN_PASS:
                return True
        except Exception:
            pass
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="RemoteRise Admin"')
        self.end_headers()
        self.wfile.write(json.dumps({'error': 'Invalid credentials'}).encode())
        return False

    def read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length) if length > 0 else b''

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == '/':
            return self.send_file(os.path.join(PUBLIC_DIR, 'index.html'))
        if path == '/admin':
            if not self.check_admin():
                return
            return self.send_file(os.path.join(PUBLIC_DIR, 'admin.html'))

        # API routes
        if path == '/api/admin/registrations':
            if not self.check_admin():
                return
            qs = urllib.parse.parse_qs(parsed.query)
            conn = get_db()
            query = 'SELECT * FROM registrations'
            conditions, params = [], []
            if 'status' in qs:
                conditions.append('status = ?')
                params.append(qs['status'][0])
            if 'search' in qs:
                s = f"%{qs['search'][0]}%"
                conditions.append('(full_name LIKE ? OR email LIKE ? OR whatsapp_number LIKE ? OR college_name LIKE ?)')
                params.extend([s, s, s, s])
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
            query += ' ORDER BY submitted_at DESC'
            rows = conn.execute(query, params).fetchall()
            conn.close()
            data = [dict(r) for r in rows]
            return self.send_json({'ok': True, 'data': data, 'count': len(data)})

        if path.startswith('/api/admin/registrations/') and path.count('/') == 4:
            if not self.check_admin():
                return
            rid = path.split('/')[-1]
            conn = get_db()
            row = conn.execute('SELECT * FROM registrations WHERE id = ?', [rid]).fetchone()
            conn.close()
            if not row:
                return self.send_json({'ok': False, 'error': 'Not found'}, 404)
            return self.send_json({'ok': True, 'data': dict(row)})

        if path == '/api/admin/stats':
            if not self.check_admin():
                return
            conn = get_db()
            total = conn.execute('SELECT COUNT(*) FROM registrations').fetchone()[0]
            today = conn.execute("SELECT COUNT(*) FROM registrations WHERE date(submitted_at)=date('now')").fetchone()[0]
            week = conn.execute("SELECT COUNT(*) FROM registrations WHERE submitted_at>=datetime('now','-7 days')").fetchone()[0]
            by_status = [dict(r) for r in conn.execute('SELECT status, COUNT(*) as count FROM registrations GROUP BY status').fetchall()]
            conn.close()
            return self.send_json({'ok': True, 'data': {'total': total, 'today': today, 'thisWeek': week, 'byStatus': by_status}})

        if path == '/api/admin/export':
            if not self.check_admin():
                return
            conn = get_db()
            rows = conn.execute('SELECT * FROM registrations ORDER BY submitted_at DESC').fetchall()
            conn.close()
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['ID','Full Name','WhatsApp','Email','Age','College','Hostel/City','Source','Job Types','Hours','English','Device','Experience','Family Name','Family Phone','Status','Submitted At'])
            for r in rows:
                d = dict(r)
                writer.writerow([d['id'],d['full_name'],d['whatsapp_number'],d['email'],d['age'],d['college_name'],d['hostel_city'],d['source'],d['job_types'],d['available_hours'],d['english_level'],d['device_access'],d['work_experience'],d['family_member_name'],d['family_member_phone'],d['status'],d['submitted_at']])
            body = output.getvalue().encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv')
            self.send_header('Content-Disposition', f'attachment; filename=remoterise-export-{datetime.now().strftime("%Y-%m-%d")}.csv')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        # Static files
        safe_path = os.path.normpath(os.path.join(PUBLIC_DIR, path.lstrip('/')))
        if safe_path.startswith(PUBLIC_DIR) and os.path.isfile(safe_path):
            return self.send_file(safe_path)

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/register':
            body = self.read_body()
            ct = self.headers.get('Content-Type', '')
            if 'multipart/form-data' in ct:
                data = parse_multipart(ct, body)
            elif 'json' in ct:
                data = json.loads(body)
            else:
                data = parse_urlencoded(body)

            job_types = data.get('jobType', '')
            if isinstance(job_types, list):
                job_types = ', '.join(job_types)

            reg = {
                'full_name': data.get('Full Name', ''),
                'whatsapp_number': data.get('WhatsApp Number', ''),
                'email': data.get('Email', ''),
                'age': data.get('Age', ''),
                'college_name': data.get('College Name', ''),
                'hostel_city': data.get('Hostel/City', ''),
                'source': data.get('source', ''),
                'job_types': job_types,
                'available_hours': data.get('Available Hours', ''),
                'english_level': data.get('English Level', ''),
                'device_access': data.get('device', ''),
                'work_experience': data.get('Work Experience', ''),
                'family_member_name': data.get('Family Member Name', ''),
                'family_member_phone': data.get('Family Member Phone', ''),
            }

            import re
            errors = []
            if not reg['full_name']:
                errors.append('Full name is required')
            if not re.match(r'^[6-9]\d{9}$', reg['whatsapp_number']):
                errors.append('Valid WhatsApp number required')
            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', reg['email']):
                errors.append('Valid email required')
            if not reg['college_name']:
                errors.append('College name required')
            if not reg['family_member_name']:
                errors.append('Family member name required')
            if not re.match(r'^[6-9]\d{9}$', reg['family_member_phone']):
                errors.append('Valid family member phone required')

            if errors:
                return self.send_json({'ok': False, 'errors': errors}, 400)

            conn = get_db()
            cur = conn.execute('''INSERT INTO registrations
                (full_name,whatsapp_number,email,age,college_name,hostel_city,source,job_types,available_hours,english_level,device_access,work_experience,family_member_name,family_member_phone,agreed_terms)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                [reg['full_name'],reg['whatsapp_number'],reg['email'],reg['age'],reg['college_name'],reg['hostel_city'],reg['source'],reg['job_types'],reg['available_hours'],reg['english_level'],reg['device_access'],reg['work_experience'],reg['family_member_name'],reg['family_member_phone'],1])
            conn.commit()
            rid = cur.lastrowid
            conn.close()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n✅ NEW REGISTRATION #{rid}")
            print(f"   Name: {reg['full_name']}")
            print(f"   Phone: {reg['whatsapp_number']}")
            print(f"   Email: {reg['email']}")
            print(f"   College: {reg['college_name']}")
            print(f"   Time: {now}\n")

            return self.send_json({'ok': True, 'id': rid, 'message': 'Registration successful!'})

        self.send_response(404)
        self.end_headers()

    def do_PATCH(self):
        if '/api/admin/registrations/' in self.path and self.path.endswith('/status'):
            if not self.check_admin():
                return
            rid = self.path.split('/')[-2]
            body = json.loads(self.read_body())
            status = body.get('status')
            if status not in ('new', 'contacted', 'training', 'placed', 'rejected'):
                return self.send_json({'ok': False, 'error': 'Invalid status'}, 400)
            conn = get_db()
            conn.execute('UPDATE registrations SET status=? WHERE id=?', [status, rid])
            conn.commit()
            conn.close()
            return self.send_json({'ok': True, 'message': 'Status updated'})
        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        if '/api/admin/registrations/' in self.path:
            if not self.check_admin():
                return
            rid = self.path.split('/')[-1]
            conn = get_db()
            conn.execute('DELETE FROM registrations WHERE id=?', [rid])
            conn.commit()
            conn.close()
            return self.send_json({'ok': True, 'message': 'Deleted'})
        self.send_response(404)
        self.end_headers()


if __name__ == '__main__':
    init_db()
    server = http.server.HTTPServer(('0.0.0.0', PORT), RemoteRiseHandler)
    print(f"\n🚀 RemoteRise Server Running!")
    print(f"{'━' * 42}")
    print(f"📋 Registration Form: http://localhost:{PORT}")
    print(f"🔑 Admin Dashboard:   http://localhost:{PORT}/admin")
    print(f"   Username: {ADMIN_USER}")
    print(f"   Password: {ADMIN_PASS}")
    print(f"{'━' * 42}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped.")
        server.server_close()
