# app.py  –  Smart Attendance Dashboard
# Run: python app.py  →  http://localhost:5000

from flask import Flask, render_template_string, jsonify
from database import get_today_records, get_stats, init_database

app = Flask(__name__)

TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Smart Attendance</title>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet"/>
  <style>
    :root {
      --bg:        #0d1117;
      --surface:   #161b22;
      --border:    #21262d;
      --accent:    #58a6ff;
      --green:     #3fb950;
      --yellow:    #d29922;
      --red:       #f85149;
      --muted:     #8b949e;
      --text:      #e6edf3;
      --mono:      'IBM Plex Mono', monospace;
      --sans:      'IBM Plex Sans', sans-serif;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--sans);
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 18px 32px;
      border-bottom: 1px solid var(--border);
      background: var(--surface);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .logo {
      display: flex;
      align-items: center;
      gap: 10px;
      font-family: var(--mono);
      font-size: 15px;
      font-weight: 600;
      letter-spacing: 0.04em;
      color: var(--accent);
    }
    .live-badge {
      display: flex;
      align-items: center;
      gap: 6px;
      font-family: var(--mono);
      font-size: 11px;
      color: var(--green);
      letter-spacing: 0.08em;
    }
    .pulse {
      width: 8px; height: 8px;
      background: var(--green);
      border-radius: 50%;
      animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50%       { opacity: 0.4; transform: scale(0.85); }
    }
    #clock {
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
    }
    main { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
    .stats {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 32px;
    }
    .stat-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px 22px;
      position: relative;
      overflow: hidden;
    }
    .stat-card::before {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 2px;
    }
    .stat-card.total::before   { background: var(--accent); }
    .stat-card.present::before { background: var(--green); }
    .stat-card.absent::before  { background: var(--red); }
    .stat-card.pct::before     { background: var(--yellow); }
    .stat-label {
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.1em;
      color: var(--muted);
      text-transform: uppercase;
      margin-bottom: 10px;
    }
    .stat-value {
      font-family: var(--mono);
      font-size: 36px;
      font-weight: 600;
      line-height: 1;
    }
    .stat-card.total   .stat-value { color: var(--accent); }
    .stat-card.present .stat-value { color: var(--green); }
    .stat-card.absent  .stat-value { color: var(--red); }
    .stat-card.pct     .stat-value { color: var(--yellow); }
    .progress-wrap {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px 22px;
      margin-bottom: 32px;
    }
    .progress-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }
    .progress-title {
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .progress-pct {
      font-family: var(--mono);
      font-size: 12px;
      color: var(--text);
    }
    .progress-bar {
      height: 6px;
      background: var(--border);
      border-radius: 3px;
      overflow: hidden;
    }
    .progress-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--green), var(--accent));
      border-radius: 3px;
      transition: width 0.6s ease;
    }
    .table-wrap {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }
    .table-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 22px;
      border-bottom: 1px solid var(--border);
    }
    .table-title {
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
    }
    .record-count {
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
    }
    table { width: 100%; border-collapse: collapse; }
    thead th {
      padding: 10px 22px;
      text-align: left;
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      background: rgba(255,255,255,0.02);
      border-bottom: 1px solid var(--border);
    }
    tbody tr {
      border-bottom: 1px solid var(--border);
      transition: background 0.15s;
    }
    tbody tr:last-child { border-bottom: none; }
    tbody tr:hover { background: rgba(88,166,255,0.04); }
    tbody td { padding: 13px 22px; font-size: 13px; vertical-align: middle; }
    .td-id   { font-family: var(--mono); font-size: 12px; color: var(--muted); }
    .td-name { font-weight: 500; }
    .td-time { font-family: var(--mono); font-size: 12px; color: var(--muted); }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 9px;
      border-radius: 4px;
      font-size: 11px;
      font-family: var(--mono);
      font-weight: 600;
      letter-spacing: 0.04em;
    }
    .badge-present {
      background: rgba(63,185,80,0.12);
      color: var(--green);
      border: 1px solid rgba(63,185,80,0.25);
    }
    .empty {
      text-align: center;
      padding: 64px 24px;
      color: var(--muted);
    }
    .empty-icon { font-size: 40px; margin-bottom: 12px; }
    .empty-msg  { font-size: 14px; margin-bottom: 4px; color: var(--text); }
    .empty-sub  { font-size: 12px; }
    .refresh-btn {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--muted);
      font-family: var(--mono);
      font-size: 11px;
      padding: 5px 12px;
      cursor: pointer;
      transition: color 0.15s, border-color 0.15s;
    }
    .refresh-btn:hover { color: var(--accent); border-color: var(--accent); }
    @media (max-width: 700px) {
      .stats  { grid-template-columns: repeat(2, 1fr); }
      header  { padding: 14px 16px; }
      main    { padding: 20px 12px; }
    }
  </style>
</head>
<body>
<header>
  <div class="logo">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
      <rect x="2" y="5" width="20" height="14" rx="2"/>
      <path d="M6 9h4M6 12h6M6 15h3"/>
      <rect x="15" y="9" width="4" height="6" rx="1" fill="currentColor" opacity=".4"/>
    </svg>
    SMART ATTENDANCE
  </div>
  <div style="display:flex;align-items:center;gap:20px;">
    <span id="clock"></span>
    <div class="live-badge"><div class="pulse"></div>LIVE</div>
  </div>
</header>

<main>
  <div class="stats">
    <div class="stat-card total">
      <div class="stat-label">Total Students</div>
      <div class="stat-value" id="s-total">—</div>
    </div>
    <div class="stat-card present">
      <div class="stat-label">Present Today</div>
      <div class="stat-value" id="s-present">—</div>
    </div>
    <div class="stat-card absent">
      <div class="stat-label">Absent</div>
      <div class="stat-value" id="s-absent">—</div>
    </div>
    <div class="stat-card pct">
      <div class="stat-label">Attendance %</div>
      <div class="stat-value" id="s-pct">—</div>
    </div>
  </div>

  <div class="progress-wrap">
    <div class="progress-header">
      <span class="progress-title">Today's Attendance Rate</span>
      <span class="progress-pct" id="prog-label">0%</span>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" id="prog-fill" style="width:0%"></div>
    </div>
  </div>

  <div class="table-wrap">
    <div class="table-header">
      <span class="table-title">Today's Records</span>
      <div style="display:flex;align-items:center;gap:12px;">
        <span class="record-count" id="rec-count">0 records</span>
        <button class="refresh-btn" onclick="refresh()">↻ Refresh</button>
      </div>
    </div>
    <div id="table-body">
      <div class="empty">
        <div class="empty-icon">📡</div>
        <div class="empty-msg">No scans yet today</div>
        <div class="empty-sub">Waiting for card scans from Arduino…</div>
      </div>
    </div>
  </div>
</main>

<script>
  function updateClock() {
    const now = new Date();
    document.getElementById('clock').textContent =
      now.toLocaleDateString('en-IN', { weekday:'short', month:'short', day:'numeric' }) +
      '  ' + now.toLocaleTimeString('en-IN', { hour:'2-digit', minute:'2-digit', second:'2-digit' });
  }
  setInterval(updateClock, 1000);
  updateClock();

  async function refresh() {
    try {
      const [statsRes, recsRes] = await Promise.all([
        fetch('/api/stats'),
        fetch('/api/records')
      ]);
      const stats = await statsRes.json();
      const records = await recsRes.json();
      renderStats(stats);
      renderTable(records);
    } catch (e) {
      console.error('Refresh error:', e);
    }
  }

  function renderStats(s) {
    document.getElementById('s-total').textContent   = s.total;
    document.getElementById('s-present').textContent = s.present;
    document.getElementById('s-absent').textContent  = s.absent;
    document.getElementById('s-pct').textContent     = s.pct + '%';
    document.getElementById('prog-fill').style.width = s.pct + '%';
    document.getElementById('prog-label').textContent = s.pct + '%';
  }

  function renderTable(records) {
    const count = records.length;
    document.getElementById('rec-count').textContent = count + ' record' + (count !== 1 ? 's' : '');
    if (count === 0) {
      document.getElementById('table-body').innerHTML = `
        <div class="empty">
          <div class="empty-icon">📡</div>
          <div class="empty-msg">No scans yet today</div>
          <div class="empty-sub">Waiting for card scans from Arduino…</div>
        </div>`;
      return;
    }
    const rows = records.map((r, i) => `
      <tr>
        <td class="td-id">${String(i + 1).padStart(2, '0')}</td>
        <td class="td-id">${r.student_id}</td>
        <td class="td-name">${r.student_name}</td>
        <td class="td-time">${r.timestamp}</td>
        <td><span class="badge badge-present">✓ Present</span></td>
      </tr>`).join('');
    document.getElementById('table-body').innerHTML = `
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Student ID</th>
            <th>Name</th>
            <th>Time</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  refresh();
  setInterval(refresh, 10000);
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(TEMPLATE)

@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())

@app.route("/api/records")
def api_records():
    return jsonify(get_today_records())

if __name__ == "__main__":
    init_database()
    print("[INFO] Dashboard running at http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)