// This script generates the HTML files for the project
const fs = require('fs');
const path = require('path');

// Read the user's original form and modify submission
const formJS = `
  document.getElementById('fullName').addEventListener('input', function() {
    document.getElementById('nameDisplay').textContent = this.value.trim() || '—';
  });
  function updateProgress() {
    const name = document.getElementById('fullName').value.trim();
    const phone = document.getElementById('phone').value.trim();
    const college = document.getElementById('college').value.trim();
    const ref = document.getElementById('refName').value.trim();
    const agree = document.getElementById('agreeCheck').checked;
    let done = 0;
    if (name && phone) done++;
    if (college) done++;
    if (ref) done++;
    if (agree) done++;
    for (let i = 1; i <= 4; i++) {
      const el = document.getElementById('ps' + i);
      el.className = 'ps';
      if (i < done) el.classList.add('done');
      else if (i === done || (done === 0 && i === 1)) el.classList.add('active');
    }
    const labels = ['Step 1 of 4','Step 2 of 4','Step 3 of 4','Step 4 of 4','Complete ✓'];
    document.getElementById('progressLabel').textContent = labels[Math.min(done, 4)];
  }
  document.querySelectorAll('input, select, textarea').forEach(el => {
    el.addEventListener('input', updateProgress);
    el.addEventListener('change', updateProgress);
  });
  function setErr(id, show) {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('has-error', show);
  }
  const validPhone = v => /^[6-9]\\d{9}$/.test(v);
  const validEmail = v => /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(v);
  document.getElementById('mainForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const name = document.getElementById('fullName').value.trim();
    const phone = document.getElementById('phone').value.trim();
    const email = document.getElementById('email').value.trim();
    const college = document.getElementById('college').value.trim();
    const refName = document.getElementById('refName').value.trim();
    const refPhone = document.getElementById('refPhone').value.trim();
    const agree = document.getElementById('agreeCheck').checked;
    let ok = true;
    setErr('f-name', !name); if (!name) ok = false;
    setErr('f-phone', !validPhone(phone)); if (!validPhone(phone)) ok = false;
    setErr('f-email', !validEmail(email)); if (!validEmail(email)) ok = false;
    setErr('f-college', !college); if (!college) ok = false;
    setErr('f-refName', !refName); if (!refName) ok = false;
    setErr('f-refPhone', !validPhone(refPhone)); if (!validPhone(refPhone)) ok = false;
    const agreeLabel = document.getElementById('f-agree');
    if (!agree) { agreeLabel.style.borderColor='#ef4444'; agreeLabel.style.background='#fff5f5'; ok=false; }
    else { agreeLabel.style.borderColor=''; agreeLabel.style.background=''; }
    if (!ok) { document.querySelector('.has-error')?.scrollIntoView({behavior:'smooth',block:'center'}); return; }
    const submitBtn = document.querySelector('.submit-btn');
    submitBtn.textContent = 'Submitting...';
    submitBtn.disabled = true;
    const formData = new FormData(this);
    try {
      const response = await fetch('/api/register', { method:'POST', body: formData, headers:{'Accept':'application/json'} });
      const result = await response.json();
      if (result.ok) {
        document.getElementById('mainForm').style.display = 'none';
        document.getElementById('successScreen').style.display = 'block';
        document.getElementById('successName').textContent = name;
        window.scrollTo({top:0,behavior:'smooth'});
      } else {
        submitBtn.textContent = 'Submit My Application →';
        submitBtn.disabled = false;
        alert(result.errors ? result.errors.join('\\n') : 'Something went wrong.');
      }
    } catch(error) {
      submitBtn.textContent = 'Submit My Application →';
      submitBtn.disabled = false;
      alert('Network error. Please check your connection.');
    }
  });
`;

console.log('Form JS generated. Length:', formJS.length);
console.log('Done - HTML files will be created by the main tool');
