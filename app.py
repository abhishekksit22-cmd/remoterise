#!/usr/bin/env python3
"""RemoteRise Backend - Flask + SQLite for PythonAnywhere deployment"""

import os, json, csv, io, re, sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, Response, g

app = Flask(__name__, static_folder='public', static_url_path='')

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'remoterise2026')
DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'remoterise.db'))

# ─── DATABASE ────────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
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

# ─── AUTH ─────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if auth and auth.username == ADMIN_USER and auth.password == ADMIN_PASS:
            return f(*args, **kwargs)
        return Response('Auth required', 401, {'WWW-Authenticate': 'Basic realm="RemoteRise Admin"'})
    return decorated

# ─── PUBLIC ROUTES ────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.form.to_dict(flat=False)
        job_types = ', '.join(data.get('jobType', []))
        reg = {
            'full_name': data.get('Full Name', [''])[0],
            'whatsapp_number': data.get('WhatsApp Number', [''])[0],
            'email': data.get('Email', [''])[0],
            'age': data.get('Age', [''])[0],
            'college_name': data.get('College Name', [''])[0],
            'hostel_city': data.get('Hostel/City', [''])[0],
            'source': data.get('source', [''])[0],
            'job_types': job_types,
            'available_hours': data.get('Available Hours', [''])[0],
            'english_level': data.get('English Level', [''])[0],
            'device_access': data.get('device', [''])[0],
            'work_experience': data.get('Work Experience', [''])[0],
            'family_member_name': data.get('Family Member Name', [''])[0],
            'family_member_phone': data.get('Family Member Phone', [''])[0],
        }
        errors = []
        if not reg['full_name']: errors.append('Full name required')
        if not re.match(r'^[6-9]\d{9}$', reg['whatsapp_number']): errors.append('Valid WhatsApp number required')
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', reg['email']): errors.append('Valid email required')
        if not reg['college_name']: errors.append('College name required')
        if not reg['family_member_name']: errors.append('Family member name required')
        if not re.match(r'^[6-9]\d{9}$', reg['family_member_phone']): errors.append('Valid family phone required')
        if errors:
            return jsonify({'ok': False, 'errors': errors}), 400

        db = get_db()
        cur = db.execute('''INSERT INTO registrations
            (full_name,whatsapp_number,email,age,college_name,hostel_city,source,job_types,available_hours,english_level,device_access,work_experience,family_member_name,family_member_phone,agreed_terms)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            [reg['full_name'],reg['whatsapp_number'],reg['email'],reg['age'],reg['college_name'],reg['hostel_city'],reg['source'],reg['job_types'],reg['available_hours'],reg['english_level'],reg['device_access'],reg['work_experience'],reg['family_member_name'],reg['family_member_phone'],1])
        db.commit()
        rid = cur.lastrowid
        print(f"✅ NEW #{rid}: {reg['full_name']} | {reg['whatsapp_number']} | {reg['college_name']}")
        return jsonify({'ok': True, 'id': rid, 'message': 'Registration successful!'})
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'ok': False, 'error': 'Something went wrong'}), 500

# ─── ADMIN ROUTES ─────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin_page():
    return send_from_directory('public', 'admin.html')

@app.route('/api/admin/registrations')
@admin_required
def get_registrations():
    db = get_db()
    query = 'SELECT * FROM registrations'
    conditions, params = [], []
    status = request.args.get('status')
    search = request.args.get('search')
    if status:
        conditions.append('status = ?')
        params.append(status)
    if search:
        s = f'%{search}%'
        conditions.append('(full_name LIKE ? OR email LIKE ? OR whatsapp_number LIKE ? OR college_name LIKE ?)')
        params.extend([s, s, s, s])
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY submitted_at DESC'
    rows = [dict(r) for r in db.execute(query, params).fetchall()]
    return jsonify({'ok': True, 'data': rows, 'count': len(rows)})

@app.route('/api/admin/registrations/<int:rid>')
@admin_required
def get_registration(rid):
    db = get_db()
    row = db.execute('SELECT * FROM registrations WHERE id = ?', [rid]).fetchone()
    if not row: return jsonify({'ok': False, 'error': 'Not found'}), 404
    return jsonify({'ok': True, 'data': dict(row)})

@app.route('/api/admin/registrations/<int:rid>/status', methods=['PATCH'])
@admin_required
def update_status(rid):
    status = request.json.get('status')
    if status not in ('new','contacted','training','placed','rejected'):
        return jsonify({'ok': False, 'error': 'Invalid status'}), 400
    db = get_db()
    db.execute('UPDATE registrations SET status=? WHERE id=?', [status, rid])
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/admin/registrations/<int:rid>', methods=['DELETE'])
@admin_required
def delete_reg(rid):
    db = get_db()
    db.execute('DELETE FROM registrations WHERE id=?', [rid])
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/admin/stats')
@admin_required
def get_stats():
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM registrations').fetchone()[0]
    today = db.execute("SELECT COUNT(*) FROM registrations WHERE date(submitted_at)=date('now')").fetchone()[0]
    week = db.execute("SELECT COUNT(*) FROM registrations WHERE submitted_at>=datetime('now','-7 days')").fetchone()[0]
    by_status = [dict(r) for r in db.execute('SELECT status, COUNT(*) as count FROM registrations GROUP BY status').fetchall()]
    return jsonify({'ok': True, 'data': {'total': total, 'today': today, 'thisWeek': week, 'byStatus': by_status}})

@app.route('/api/admin/export')
@admin_required
def export_csv():
    db = get_db()
    rows = [dict(r) for r in db.execute('SELECT * FROM registrations ORDER BY submitted_at DESC').fetchall()]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Name','WhatsApp','Email','Age','College','City','Source','Jobs','Hours','English','Device','Experience','Family Name','Family Phone','Status','Date'])
    for r in rows:
        writer.writerow([r['id'],r['full_name'],r['whatsapp_number'],r['email'],r['age'],r['college_name'],r['hostel_city'],r['source'],r['job_types'],r['available_hours'],r['english_level'],r['device_access'],r['work_experience'],r['family_member_name'],r['family_member_phone'],r['status'],r['submitted_at']])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=remoterise-{datetime.now().strftime("%Y-%m-%d")}.csv'})

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)

# ─── INIT ─────────────────────────────────────────────────────
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f"\n🚀 RemoteRise: http://localhost:{port}")
    print(f"🔑 Admin: http://localhost:{port}/admin\n")
    app.run(host='0.0.0.0', port=port, debug=False)
