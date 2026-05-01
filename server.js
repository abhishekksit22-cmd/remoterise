const express = require('express');
const path = require('path');
const {
  insertRegistration,
  getAllRegistrations,
  getRegistrationById,
  updateRegistrationStatus,
  deleteRegistration,
  getStats
} = require('./database');

const app = express();
const PORT = process.env.PORT || 3000;

// Admin credentials (change these!)
const ADMIN_USER = process.env.ADMIN_USER || 'admin';
const ADMIN_PASS = process.env.ADMIN_PASS || 'remoterise2026';

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Simple basic auth middleware for admin routes
function adminAuth(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Basic ')) {
    res.setHeader('WWW-Authenticate', 'Basic realm="RemoteRise Admin"');
    return res.status(401).json({ error: 'Authentication required' });
  }

  const base64 = authHeader.split(' ')[1];
  const [user, pass] = Buffer.from(base64, 'base64').toString().split(':');

  if (user === ADMIN_USER && pass === ADMIN_PASS) {
    next();
  } else {
    res.setHeader('WWW-Authenticate', 'Basic realm="RemoteRise Admin"');
    return res.status(401).json({ error: 'Invalid credentials' });
  }
}

// ─── PUBLIC ROUTES ──────────────────────────────────────────

// Serve the registration form
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Handle form submission
app.post('/api/register', (req, res) => {
  try {
    const body = req.body;

    // Build job types array from checkbox values
    let jobTypes = '';
    if (body.jobType) {
      jobTypes = Array.isArray(body.jobType) ? body.jobType.join(', ') : body.jobType;
    }

    const data = {
      full_name: body['Full Name'] || body.fullName || '',
      whatsapp_number: body['WhatsApp Number'] || body.phone || '',
      email: body['Email'] || body.email || '',
      age: body['Age'] || body.age || '',
      college_name: body['College Name'] || body.college || '',
      hostel_city: body['Hostel/City'] || body.hostel || '',
      source: body.source || '',
      job_types: jobTypes || body['Job Types'] || '',
      available_hours: body['Available Hours'] || body.hours || '',
      english_level: body['English Level'] || body.english || '',
      device_access: body.device || '',
      work_experience: body['Work Experience'] || body.experience || '',
      family_member_name: body['Family Member Name'] || body.refName || '',
      family_member_phone: body['Family Member Phone'] || body.refPhone || '',
      agreed_terms: body.agreeCheck === 'on' || body.agreed === true || body.agreed === 'true'
    };

    // Validate required fields
    const errors = [];
    if (!data.full_name) errors.push('Full name is required');
    if (!/^[6-9]\d{9}$/.test(data.whatsapp_number)) errors.push('Valid WhatsApp number is required');
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email)) errors.push('Valid email is required');
    if (!data.college_name) errors.push('College name is required');
    if (!data.family_member_name) errors.push('Family member name is required');
    if (!/^[6-9]\d{9}$/.test(data.family_member_phone)) errors.push('Valid family member phone is required');

    if (errors.length > 0) {
      return res.status(400).json({ ok: false, errors });
    }

    const id = insertRegistration(data);

    // Log to console for immediate visibility
    console.log(`\n✅ NEW REGISTRATION #${id}`);
    console.log(`   Name: ${data.full_name}`);
    console.log(`   Phone: ${data.whatsapp_number}`);
    console.log(`   Email: ${data.email}`);
    console.log(`   College: ${data.college_name}`);
    console.log(`   Time: ${new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}\n`);

    res.json({ ok: true, id, message: 'Registration successful!' });
  } catch (err) {
    console.error('Registration error:', err);
    res.status(500).json({ ok: false, error: 'Something went wrong. Please try again.' });
  }
});

// ─── ADMIN ROUTES ───────────────────────────────────────────

// Admin dashboard page
app.get('/admin', adminAuth, (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'admin.html'));
});

// Get all registrations
app.get('/api/admin/registrations', adminAuth, (req, res) => {
  try {
    const { status, search, limit } = req.query;
    const filters = {};
    if (status) filters.status = status;
    if (search) filters.search = search;
    if (limit) filters.limit = parseInt(limit);

    const registrations = getAllRegistrations(filters);
    res.json({ ok: true, data: registrations, count: registrations.length });
  } catch (err) {
    console.error(err);
    res.status(500).json({ ok: false, error: 'Failed to fetch registrations' });
  }
});

// Get single registration
app.get('/api/admin/registrations/:id', adminAuth, (req, res) => {
  try {
    const reg = getRegistrationById(parseInt(req.params.id));
    if (!reg) return res.status(404).json({ ok: false, error: 'Not found' });
    res.json({ ok: true, data: reg });
  } catch (err) {
    res.status(500).json({ ok: false, error: 'Failed to fetch registration' });
  }
});

// Update status
app.patch('/api/admin/registrations/:id/status', adminAuth, (req, res) => {
  try {
    const { status } = req.body;
    const validStatuses = ['new', 'contacted', 'training', 'placed', 'rejected'];
    if (!validStatuses.includes(status)) {
      return res.status(400).json({ ok: false, error: 'Invalid status' });
    }

    updateRegistrationStatus(parseInt(req.params.id), status);
    res.json({ ok: true, message: 'Status updated' });
  } catch (err) {
    res.status(500).json({ ok: false, error: 'Failed to update status' });
  }
});

// Delete registration
app.delete('/api/admin/registrations/:id', adminAuth, (req, res) => {
  try {
    deleteRegistration(parseInt(req.params.id));
    res.json({ ok: true, message: 'Registration deleted' });
  } catch (err) {
    res.status(500).json({ ok: false, error: 'Failed to delete' });
  }
});

// Get stats
app.get('/api/admin/stats', adminAuth, (req, res) => {
  try {
    const stats = getStats();
    res.json({ ok: true, data: stats });
  } catch (err) {
    res.status(500).json({ ok: false, error: 'Failed to fetch stats' });
  }
});

// Export CSV
app.get('/api/admin/export', adminAuth, (req, res) => {
  try {
    const registrations = getAllRegistrations();

    const headers = [
      'ID', 'Full Name', 'WhatsApp', 'Email', 'Age', 'College',
      'Hostel/City', 'Source', 'Job Types', 'Hours', 'English',
      'Device', 'Experience', 'Family Name', 'Family Phone',
      'Status', 'Submitted At'
    ];

    const escCsv = (v) => `"${String(v || '').replace(/"/g, '""')}"`;

    let csv = headers.join(',') + '\n';
    for (const r of registrations) {
      csv += [
        r.id, r.full_name, r.whatsapp_number, r.email, r.age, r.college_name,
        r.hostel_city, r.source, r.job_types, r.available_hours, r.english_level,
        r.device_access, r.work_experience, r.family_member_name, r.family_member_phone,
        r.status, r.submitted_at
      ].map(escCsv).join(',') + '\n';
    }

    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', `attachment; filename=remoterise-registrations-${new Date().toISOString().split('T')[0]}.csv`);
    res.send(csv);
  } catch (err) {
    res.status(500).json({ ok: false, error: 'Failed to export' });
  }
});

// Start server
app.listen(PORT, () => {
  console.log(`\n🚀 RemoteRise Server Running!`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
  console.log(`📋 Registration Form: http://localhost:${PORT}`);
  console.log(`🔑 Admin Dashboard:   http://localhost:${PORT}/admin`);
  console.log(`   Username: ${ADMIN_USER}`);
  console.log(`   Password: ${ADMIN_PASS}`);
  console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);
});
