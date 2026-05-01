#!/usr/bin/env python3
"""RemoteRise Backend - Flask + PostgreSQL for Render.com deployment"""

import os, json, csv, io, re, base64
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, Response
import psycopg2
import psycopg2.extras

app = Flask(__name__, static_folder='public', static_url_path='')

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'remoterise2026')
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# ─── DATABASE ────────────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS registrations (
        id SERIAL PRIMARY KEY,
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
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'new'
    )''')
    conn.commit()
    cur.close()
    conn.close()

# ─── AUTH ─────────────────────────────────────────────────────

def check_admin():
    auth = request.authorization
    if auth and auth.username == ADMIN_USER and auth.password == ADMIN_PASS:
        return True
    return False

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_admin():
            return Response('Auth required', 401, {'WWW-Authenticate': 'Basic realm="RemoteRise Admin"'})
        return f(*args, **kwargs)
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
        if not re.match(r'^[6-9]\d{9}$', reg['family_member_phone']): errors.append('Valid family member phone required')

        if errors:
            return jsonify({'ok': False, 'errors': errors}), 400

        conn = get_db()
        cur = conn.cursor()
        cur.execute('''INSERT INTO registrations
            (full_name,whatsapp_number,email,age,college_name,hostel_city,source,job_types,available_hours,english_level,device_access,work_experience,family_member_name,family_member_phone,agreed_terms)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
            [reg['full_name'],reg['whatsapp_number'],reg['email'],reg['age'],reg['college_name'],reg['hostel_city'],reg['source'],reg['job_types'],reg['available_hours'],reg['english_level'],reg['device_access'],reg['work_experience'],reg['family_member_name'],reg['family_member_phone'],1])
        rid = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        print(f"\n✅ NEW REGISTRATION #{rid}: {reg['full_name']} | {reg['whatsapp_number']} | {reg['college_name']}\n")
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
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = 'SELECT * FROM registrations'
    conditions, params = [], []
    status = request.args.get('status')
    search = request.args.get('search')
    if status:
        conditions.append('status = %s')
        params.append(status)
    if search:
        conditions.append('(full_name ILIKE %s OR email ILIKE %s OR whatsapp_number ILIKE %s OR college_name ILIKE %s)')
        s = f'%{search}%'
        params.extend([s, s, s, s])
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY submitted_at DESC'
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    # Convert datetime to string
    for r in rows:
        if r.get('submitted_at'):
            r['submitted_at'] = r['submitted_at'].isoformat()
    return jsonify({'ok': True, 'data': rows, 'count': len(rows)})

@app.route('/api/admin/registrations/<int:rid>')
@admin_required
def get_registration(rid):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM registrations WHERE id = %s', [rid])
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({'ok': False, 'error': 'Not found'}), 404
    if row.get('submitted_at'):
        row['submitted_at'] = row['submitted_at'].isoformat()
    return jsonify({'ok': True, 'data': row})

@app.route('/api/admin/registrations/<int:rid>/status', methods=['PATCH'])
@admin_required
def update_status(rid):
    status = request.json.get('status')
    if status not in ('new', 'contacted', 'training', 'placed', 'rejected'):
        return jsonify({'ok': False, 'error': 'Invalid status'}), 400
    conn = get_db()
    cur = conn.cursor()
    cur.execute('UPDATE registrations SET status = %s WHERE id = %s', [status, rid])
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True, 'message': 'Status updated'})

@app.route('/api/admin/registrations/<int:rid>', methods=['DELETE'])
@admin_required
def delete_registration(rid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM registrations WHERE id = %s', [rid])
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'ok': True, 'message': 'Deleted'})

@app.route('/api/admin/stats')
@admin_required
def get_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM registrations')
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM registrations WHERE submitted_at::date = CURRENT_DATE")
    today = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM registrations WHERE submitted_at >= NOW() - INTERVAL '7 days'")
    week = cur.fetchone()[0]
    cur.execute('SELECT status, COUNT(*) as count FROM registrations GROUP BY status')
    by_status = [{'status': r[0], 'count': r[1]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify({'ok': True, 'data': {'total': total, 'today': today, 'thisWeek': week, 'byStatus': by_status}})

@app.route('/api/admin/export')
@admin_required
def export_csv():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM registrations ORDER BY submitted_at DESC')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Full Name','WhatsApp','Email','Age','College','Hostel/City','Source','Job Types','Hours','English','Device','Experience','Family Name','Family Phone','Status','Submitted At'])
    for r in rows:
        writer.writerow([r['id'],r['full_name'],r['whatsapp_number'],r['email'],r['age'],r['college_name'],r['hostel_city'],r['source'],r['job_types'],r['available_hours'],r['english_level'],r['device_access'],r['work_experience'],r['family_member_name'],r['family_member_phone'],r['status'],r['submitted_at']])
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=remoterise-export-{datetime.now().strftime("%Y-%m-%d")}.csv'})

# ─── STATIC FILES ─────────────────────────────────────────────

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('public', path)

# ─── INIT ─────────────────────────────────────────────────────

with app.app_context():
    if DATABASE_URL:
        init_db()
        print("✅ Database initialized")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    print(f"\n🚀 RemoteRise running on http://localhost:{port}")
    print(f"🔑 Admin: http://localhost:{port}/admin (admin / {ADMIN_PASS})\n")
    app.run(host='0.0.0.0', port=port, debug=False)
