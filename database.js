const Database = require('better-sqlite3');
const path = require('path');

const DB_PATH = path.join(__dirname, 'remoterise.db');

let db;

function getDb() {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    initializeDb();
  }
  return db;
}

function initializeDb() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS registrations (
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
    )
  `);
}

function insertRegistration(data) {
  const db = getDb();
  const stmt = db.prepare(`
    INSERT INTO registrations (
      full_name, whatsapp_number, email, age, college_name, hostel_city,
      source, job_types, available_hours, english_level, device_access,
      work_experience, family_member_name, family_member_phone, agreed_terms
    ) VALUES (
      @full_name, @whatsapp_number, @email, @age, @college_name, @hostel_city,
      @source, @job_types, @available_hours, @english_level, @device_access,
      @work_experience, @family_member_name, @family_member_phone, @agreed_terms
    )
  `);

  const result = stmt.run({
    full_name: data.full_name || '',
    whatsapp_number: data.whatsapp_number || '',
    email: data.email || '',
    age: data.age || '',
    college_name: data.college_name || '',
    hostel_city: data.hostel_city || '',
    source: data.source || '',
    job_types: data.job_types || '',
    available_hours: data.available_hours || '',
    english_level: data.english_level || '',
    device_access: data.device_access || '',
    work_experience: data.work_experience || '',
    family_member_name: data.family_member_name || '',
    family_member_phone: data.family_member_phone || '',
    agreed_terms: data.agreed_terms ? 1 : 0
  });

  return result.lastInsertRowid;
}

function getAllRegistrations(filters = {}) {
  const db = getDb();
  let query = 'SELECT * FROM registrations';
  const conditions = [];
  const params = {};

  if (filters.status) {
    conditions.push('status = @status');
    params.status = filters.status;
  }

  if (filters.search) {
    conditions.push('(full_name LIKE @search OR email LIKE @search OR whatsapp_number LIKE @search OR college_name LIKE @search)');
    params.search = `%${filters.search}%`;
  }

  if (conditions.length > 0) {
    query += ' WHERE ' + conditions.join(' AND ');
  }

  query += ' ORDER BY submitted_at DESC';

  if (filters.limit) {
    query += ' LIMIT @limit';
    params.limit = filters.limit;
  }

  return db.prepare(query).all(params);
}

function getRegistrationById(id) {
  const db = getDb();
  return db.prepare('SELECT * FROM registrations WHERE id = ?').get(id);
}

function updateRegistrationStatus(id, status) {
  const db = getDb();
  return db.prepare('UPDATE registrations SET status = ? WHERE id = ?').run(status, id);
}

function deleteRegistration(id) {
  const db = getDb();
  return db.prepare('DELETE FROM registrations WHERE id = ?').run(id);
}

function getStats() {
  const db = getDb();
  const total = db.prepare('SELECT COUNT(*) as count FROM registrations').get().count;
  const today = db.prepare("SELECT COUNT(*) as count FROM registrations WHERE date(submitted_at) = date('now')").get().count;
  const thisWeek = db.prepare("SELECT COUNT(*) as count FROM registrations WHERE submitted_at >= datetime('now', '-7 days')").get().count;
  const byStatus = db.prepare('SELECT status, COUNT(*) as count FROM registrations GROUP BY status').all();

  return { total, today, thisWeek, byStatus };
}

module.exports = {
  getDb,
  insertRegistration,
  getAllRegistrations,
  getRegistrationById,
  updateRegistrationStatus,
  deleteRegistration,
  getStats
};
