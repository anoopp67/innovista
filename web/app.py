import sys, os, threading, time, re
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "python"))

from database import (
    get_today_records, get_stats, init_database,
    register_student_web, log_attendance, unmark_attendance,
    get_registered_user
)
from flask import Flask, render_template_string, jsonify, request
import sqlite3

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "attendance.db")

# ── Serial reader ──────────────────────────────────────────────────────────────
_last_uid      = {"uid": None, "ts": 0}
_serial_status = {"connected": False, "port": None}
_serial_lock   = threading.Lock()
BAUD_RATE      = 9600
ARDUINO_HINTS  = ["arduino","ch340","usb-serial","usb serial",
                  "wchusbserial","usbmodem","usbserial","silicon labs","cp210"]

def _find_port():
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        if not ports: return None
        if len(ports) == 1: return ports[0].device
        for p in ports:
            txt = f"{p.description or ''} {p.manufacturer or ''}".lower()
            if any(h in txt for h in ARDUINO_HINTS):
                return p.device
        return ports[0].device
    except Exception:
        return None

def _extract_uid(raw):
    m = re.search(r'([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2})+)', raw)
    return m.group(1).upper() if m else None

def _serial_thread():
    try:
        import serial
    except ImportError:
        print("[SERIAL] pyserial not installed.")
        return
    while True:
        port = _find_port()
        if not port:
            with _serial_lock:
                _serial_status["connected"] = False
                _serial_status["port"] = None
            time.sleep(3); continue
        try:
            import serial as _s
            ser = _s.Serial(port, BAUD_RATE, timeout=1)
            time.sleep(2)
            with _serial_lock:
                _serial_status["connected"] = True
                _serial_status["port"] = port
            print(f"[SERIAL] Connected on {port}")
            while True:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw: continue
                print(f"[SERIAL] Raw: {repr(raw)}")
                uid = _extract_uid(raw)
                if uid:
                    with _serial_lock:
                        _last_uid["uid"] = uid
                        _last_uid["ts"]  = time.time()
                    print(f"[SERIAL] UID: {uid}")
        except Exception as e:
            print(f"[SERIAL] Error: {e}")
            with _serial_lock:
                _serial_status["connected"] = False
                _serial_status["port"] = None
            time.sleep(3)

threading.Thread(target=_serial_thread, daemon=True).start()

# ── Template ───────────────────────────────────────────────────────────────────
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Presidential Graduate School — Attendance</title>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
  <style>
    :root {
      --primary:#FF6B35; --dark-blue:#003366; --blue:#0052CC;
      --red:#E63946; --green:#06A77D; --gold:#FFB703;
      --bg:#F0F2F5; --white:#FFFFFF; --gray:#6C757D;
      --dark:#212529; --border:#DEE2E6;
      --mono:'IBM Plex Mono',monospace; --sans:'IBM Plex Sans',sans-serif;
    }
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:var(--sans);background:var(--bg);color:var(--dark);min-height:100vh}

    /* Header */
    header{background:linear-gradient(90deg,var(--dark-blue),var(--blue));color:#fff;padding:15px 28px;position:sticky;top:0;z-index:200;box-shadow:0 2px 12px rgba(0,0,0,.2)}
    .hc{max-width:1400px;margin:0 auto;display:flex;align-items:center;justify-content:space-between}
    .logo{display:flex;align-items:center;gap:12px}
    .logo-box{width:40px;height:40px;background:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center}
    .logo-box svg{width:32px;height:32px}
    .logo h1{font-size:16px;font-weight:700;letter-spacing:-.3px}
    .logo p{font-size:10px;color:var(--gold);font-weight:600;letter-spacing:.06em;margin-top:1px}
    .hr{display:flex;align-items:center;gap:12px}
    #clock{font-family:var(--mono);font-size:12px;color:var(--gold)}
    .ser-badge{font-family:var(--mono);font-size:10px;padding:4px 9px;border-radius:12px;font-weight:600}
    .ser-on{background:rgba(6,167,125,.2);color:#04a06a;border:1px solid rgba(6,167,125,.4)}
    .ser-off{background:rgba(230,57,70,.15);color:#c0282e;border:1px solid rgba(230,57,70,.3)}
    .live-dot{display:flex;align-items:center;gap:5px;font-family:var(--mono);font-size:11px;background:rgba(6,167,125,.25);padding:5px 10px;border-radius:20px;border:1px solid rgba(6,167,125,.5)}
    .dot{width:7px;height:7px;background:var(--green);border-radius:50%;animation:pulse 2s ease-in-out infinite}
    @keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.85)}}

    /* Main layout */
    main{max-width:1400px;margin:0 auto;padding:22px 20px}

    /* Stats */
    .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
    .sc{background:var(--white);border-radius:12px;padding:18px 20px;box-shadow:0 2px 8px rgba(0,0,0,.07)}
    .sc.t{border-top:4px solid var(--blue)}
    .sc.p{border-top:4px solid var(--green)}
    .sc.a{border-top:4px solid var(--red)}
    .sc.r{border-top:4px solid var(--primary)}
    .sl{font-size:10px;font-weight:700;letter-spacing:.1em;color:var(--gray);text-transform:uppercase;margin-bottom:8px}
    .sv{font-family:var(--mono);font-size:34px;font-weight:700}
    .sc.t .sv{color:var(--blue)} .sc.p .sv{color:var(--green)}
    .sc.a .sv{color:var(--red)}  .sc.r .sv{color:var(--primary)}

    /* Two-section grid */
    .two-col{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:22px}

    /* Section headers */
    .section-label{font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--gray);margin-bottom:10px;display:flex;align-items:center;gap:7px}
    .section-label::after{content:'';flex:1;height:1px;background:var(--border)}

    /* Card */
    .card{background:var(--white);border:1px solid var(--border);border-radius:14px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.07)}
    .card-head{display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid var(--border);background:linear-gradient(90deg,rgba(0,51,102,.02),rgba(0,82,204,.02))}
    .card-title{font-size:13px;font-weight:700;color:var(--dark-blue);text-transform:uppercase;letter-spacing:.05em;display:flex;align-items:center;gap:8px}

    /* ── CHECK-IN SECTION ── */
    .scan-area{padding:24px 20px}
    .scan-box{border:2.5px dashed var(--border);border-radius:14px;padding:32px 20px;text-align:center;transition:all .4s;background:#fafafa;min-height:220px;display:flex;flex-direction:column;align-items:center;justify-content:center}
    .scan-box.wait{border-color:var(--border)}
    .scan-box.ready{border-color:var(--blue);background:rgba(0,82,204,.03);animation:borderPulse 2s ease-in-out infinite}
    @keyframes borderPulse{0%,100%{border-color:var(--blue)}50%{border-color:#7aaefc}}
    .scan-box.success{border-color:var(--green);background:rgba(6,167,125,.06);animation:flashG .5s ease}
    .scan-box.fail{border-color:var(--red);background:rgba(230,57,70,.06);animation:flashR .5s ease}
    .scan-box.dupe{border-color:var(--gold);background:rgba(255,183,3,.06);animation:flashY .5s ease}
    @keyframes flashG{0%,100%{background:rgba(6,167,125,.06)}50%{background:rgba(6,167,125,.2)}}
    @keyframes flashR{0%,100%{background:rgba(230,57,70,.06)}50%{background:rgba(230,57,70,.18)}}
    @keyframes flashY{0%,100%{background:rgba(255,183,3,.06)}50%{background:rgba(255,183,3,.18)}}
    .scan-icon{font-size:52px;margin-bottom:12px;line-height:1}
    .scan-name{font-size:20px;font-weight:700;color:var(--dark);margin-bottom:4px;min-height:26px}
    .scan-id{font-family:var(--mono);font-size:12px;color:var(--gray);margin-bottom:10px;min-height:16px}
    .scan-tag{display:inline-block;padding:6px 18px;border-radius:8px;font-size:13px;font-weight:700;min-height:32px}
    .tag-ok{background:rgba(6,167,125,.15);color:var(--green);border:2px solid var(--green)}
    .tag-fail{background:rgba(230,57,70,.12);color:var(--red);border:2px solid var(--red)}
    .tag-dupe{background:rgba(255,183,3,.15);color:#7a5c00;border:2px solid var(--gold)}
    .conn-status{font-size:12px;color:var(--gray);margin-top:14px;text-align:center}
    .conn-status span{font-weight:700}

    /* Feed */
    .feed{max-height:300px;overflow-y:auto}
    .feed-item{display:flex;align-items:center;gap:10px;padding:11px 18px;border-bottom:1px solid var(--border);animation:fadeIn .3s ease}
    @keyframes fadeIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
    .feed-item:last-child{border-bottom:none}
    .fdot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
    .fdot.ok{background:var(--green)} .fdot.dup{background:var(--gold)} .fdot.err{background:var(--red)}
    .fname{font-weight:600;font-size:13px;flex:1}
    .fuid{font-family:var(--mono);font-size:10px;color:var(--gray)}
    .ftime{font-family:var(--mono);font-size:10px;color:var(--gray);white-space:nowrap}
    .ftag{font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;text-transform:uppercase;white-space:nowrap}
    .ftag.ok{background:rgba(6,167,125,.12);color:var(--green)}
    .ftag.dup{background:rgba(255,183,3,.15);color:#7a5c00}
    .ftag.err{background:rgba(230,57,70,.1);color:var(--red)}

    /* ── REGISTER SECTION ── */
    .reg-body{padding:22px 20px}
    .fg{margin-bottom:16px}
    .fl{display:block;font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--dark-blue);margin-bottom:7px}
    .fi{width:100%;padding:10px 13px;border:1.5px solid var(--border);border-radius:8px;font-size:14px;font-family:var(--sans);color:var(--dark);outline:none;background:var(--white);transition:border-color .2s}
    .fi:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(255,107,53,.1)}
    .fi.mono{font-family:var(--mono);letter-spacing:.06em}
    .fh{font-size:11px;color:var(--gray);margin-top:5px;line-height:1.5}
    .uid-row{display:flex;gap:8px;align-items:center}
    .uid-row .fi{flex:1}
    .scan-pill{font-family:var(--mono);font-size:10px;padding:5px 9px;border-radius:6px;white-space:nowrap;font-weight:600}
    .pill-on{background:rgba(6,167,125,.1);color:var(--green);border:1px solid rgba(6,167,125,.3)}
    .pill-off{background:rgba(230,57,70,.08);color:var(--red);border:1px solid rgba(230,57,70,.2)}
    .fa{display:flex;gap:10px;justify-content:flex-end;margin-top:18px}
    .reg-alert{padding:11px 15px;border-radius:8px;font-size:13px;font-weight:500;margin-bottom:16px;display:none}
    .reg-alert.show{display:block}
    .al-s{background:rgba(6,167,125,.1);color:#04784f;border:1px solid rgba(6,167,125,.3)}
    .al-e{background:rgba(230,57,70,.1);color:#b0272d;border:1px solid rgba(230,57,70,.3)}

    /* ── ALL STUDENTS TABLE ── */
    .students-section{margin-top:0}
    table{width:100%;border-collapse:collapse}
    thead th{padding:11px 18px;text-align:left;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--dark-blue);background:#F8F9FA;border-bottom:2px solid var(--border)}
    tbody tr{border-bottom:1px solid var(--border);transition:background .15s}
    tbody tr:last-child{border-bottom:none}
    tbody tr:hover{background:rgba(255,107,53,.02)}
    tbody td{padding:12px 18px;font-size:13px;vertical-align:middle}
    .mid{font-family:var(--mono);font-size:11px;color:var(--gray)}
    .mname{font-weight:600}

    /* Badges */
    .badge{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border-radius:6px;font-size:11px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;white-space:nowrap}
    .bp{background:rgba(6,167,125,.12);color:var(--green);border:1px solid var(--green)}
    .ba{background:rgba(230,57,70,.1);color:var(--red);border:1px solid var(--red)}

    /* Buttons */
    .btn{display:inline-flex;align-items:center;gap:5px;padding:8px 16px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;border:none;transition:all .2s;font-family:var(--sans)}
    .btn-primary{background:var(--primary);color:#fff}
    .btn-primary:hover{background:#e55a27}
    .btn-outline{background:var(--white);border:1.5px solid var(--border);color:var(--gray)}
    .btn-outline:hover{border-color:var(--primary);color:var(--primary)}
    .btn-g{background:var(--green);color:#fff;font-size:11px;padding:5px 10px;border-radius:6px;cursor:pointer;border:none;font-weight:600;font-family:var(--sans);transition:background .2s}
    .btn-g:hover{background:#058f6b}
    .btn-r{background:var(--red);color:#fff;font-size:11px;padding:5px 10px;border-radius:6px;cursor:pointer;border:none;font-weight:600;font-family:var(--sans);transition:background .2s}
    .btn-r:hover{background:#c62d3a}

    /* Empty */
    .empty{text-align:center;padding:44px 24px}
    .ei{font-size:40px;margin-bottom:10px}
    .em{font-size:14px;font-weight:600;color:var(--dark);margin-bottom:4px}
    .es{font-size:12px;color:var(--gray)}

    .rc{font-family:var(--mono);font-size:11px;color:var(--gray)}
    .spin{display:inline-block;width:12px;height:12px;border:2px solid rgba(255,255,255,.4);border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite}
    @keyframes spin{to{transform:rotate(360deg)}}

    @media(max-width:1000px){
      .two-col{grid-template-columns:1fr}
      .stats{grid-template-columns:repeat(2,1fr)}
      .hc{flex-direction:column;gap:10px}
    }
  </style>
</head>
<body>
<header>
  <div class="hc">
    <div class="logo">
      <div class="logo-box">
        <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
          <polygon points="50,10 90,50 50,90 10,50" fill="#FF6B35"/>
          <text x="50" y="65" font-size="50" font-weight="bold" text-anchor="middle" fill="white" font-family="Georgia,serif">P</text>
        </svg>
      </div>
      <div>
        <h1>PRESIDENTIAL GRADUATE SCHOOL</h1>
        <p>Smart Attendance System</p>
      </div>
    </div>
    <div class="hr">
      <span id="clock"></span>
      <span id="ser-badge" class="ser-badge ser-off">⚡ No Arduino</span>
      <div class="live-dot"><div class="dot"></div>LIVE</div>
    </div>
  </div>
</header>

<main>
  <!-- Stats -->
  <div class="stats">
    <div class="sc t"><div class="sl">Total Students</div><div class="sv" id="s-total">—</div></div>
    <div class="sc p"><div class="sl">Present Today</div><div class="sv" id="s-present">—</div></div>
    <div class="sc a"><div class="sl">Absent</div>        <div class="sv" id="s-absent">—</div></div>
    <div class="sc r"><div class="sl">Attendance %</div>  <div class="sv" id="s-pct">—</div></div>
  </div>

  <!-- ── TWO SECTIONS: Check-In + Register ── -->
  <div class="two-col">

    <!-- LEFT: Check-In -->
    <div>
      <div class="section-label">🪪 Attendance Check-In</div>
      <div class="card">
        <div class="card-head">
          <span class="card-title">📡 Scan Card to Check In</span>
          <span class="rc" id="feed-count">0 scans today</span>
        </div>
        <div class="scan-area">
          <div class="scan-box wait" id="scan-box">
            <div class="scan-icon" id="scan-icon">📡</div>
            <div class="scan-name" id="scan-name">Waiting for card…</div>
            <div class="scan-id"   id="scan-id"></div>
            <div class="scan-tag"  id="scan-tag"></div>
          </div>
          <div class="conn-status">
            Arduino reader is <span id="rdr-txt" style="color:var(--red)">not connected</span>
          </div>
        </div>
        <!-- Live feed -->
        <div style="border-top:1px solid var(--border)">
          <div style="padding:10px 18px 6px;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--gray)">Live Feed</div>
          <div id="feed-list" class="feed">
            <div class="empty"><div class="ei">📭</div><div class="em">No scans yet today</div></div>
          </div>
        </div>
      </div>
    </div>

    <!-- RIGHT: Register -->
    <div>
      <div class="section-label">➕ Register New Student</div>
      <div class="card">
        <div class="card-head">
          <span class="card-title">🎓 New Student Registration</span>
        </div>
        <div class="reg-body">
          <div id="reg-alert" class="reg-alert"></div>
          <div class="fg">
            <label class="fl">RFID Card UID</label>
            <div class="uid-row">
              <input class="fi mono" id="reg-uid" type="text" placeholder="Scan card or type e.g. A1:B2:C3:D4" oninput="fmtUID(this)"/>
              <span id="scan-pill" class="scan-pill pill-off">No reader</span>
            </div>
            <div class="fh">Hold the card to the Arduino reader — UID fills in automatically. Or type it manually.</div>
          </div>
          <div class="fg">
            <label class="fl">Student Full Name</label>
            <input class="fi" id="reg-name" type="text" placeholder="e.g. John Smith"/>
          </div>
          <div class="fg">
            <label class="fl">Student ID <span style="font-weight:400;text-transform:none;letter-spacing:0;color:var(--gray)">(auto-assigned if blank)</span></label>
            <input class="fi mono" id="reg-sid" type="text" placeholder="e.g. STU003 (optional)"/>
          </div>
          <div class="fa">
            <button class="btn btn-outline" onclick="clearReg()">Clear</button>
            <button class="btn btn-primary" id="reg-btn" onclick="doRegister()">Register Student</button>
          </div>
        </div>
      </div>

      <!-- Registered students mini-list -->
      <div style="margin-top:16px">
        <div class="section-label">👥 All Students</div>
        <div class="card students-section">
          <div class="card-head">
            <span class="card-title">Student Roster</span>
            <div style="display:flex;align-items:center;gap:10px">
              <span class="rc" id="student-count">—</span>
              <button class="btn btn-outline" onclick="refreshStudents()">↻</button>
            </div>
          </div>
          <div id="table-students">
            <div class="empty"><div class="ei">👥</div><div class="em">Loading…</div></div>
          </div>
        </div>
      </div>
    </div>

  </div><!-- end two-col -->

</main>

<script>
  /* Clock */
  setInterval(()=>{
    const n=new Date();
    document.getElementById('clock').textContent=
      n.toLocaleDateString('en-IN',{weekday:'long',month:'long',day:'numeric'})+'  '+
      n.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  },1000);

  /* Stats */
  function renderStats(s){
    document.getElementById('s-total').textContent=s.total;
    document.getElementById('s-present').textContent=s.present;
    document.getElementById('s-absent').textContent=s.absent;
    document.getElementById('s-pct').textContent=s.pct+'%';
  }
  async function refreshStats(){
    const s=await(await fetch('/api/stats')).json();
    renderStats(s);
  }

  /* ── CHECK-IN polling ── */
  let lastTs=0, feedItems=[];

  async function pollCheckin(){
    try{
      const data=await(await fetch('/api/poll')).json();

      /* Serial badge */
      const sb=document.getElementById('ser-badge');
      const rt=document.getElementById('rdr-txt');
      if(data.connected){
        sb.textContent='⚡ '+data.port; sb.className='ser-badge ser-on';
        rt.textContent='connected ✓'; rt.style.color='var(--green)';
        document.getElementById('scan-pill').textContent='⚡ Scanning';
        document.getElementById('scan-pill').className='scan-pill pill-on';
        document.getElementById('scan-box').classList.remove('wait');
        document.getElementById('scan-box').classList.add('ready');
      } else {
        sb.textContent='⚡ No Arduino'; sb.className='ser-badge ser-off';
        rt.textContent='not connected'; rt.style.color='var(--red)';
        document.getElementById('scan-pill').textContent='No reader';
        document.getElementById('scan-pill').className='scan-pill pill-off';
      }

      /* New scan */
      if(data.scan && data.scan.ts>lastTs){
        lastTs=data.scan.ts;
        animateScan(data.scan);
        feedItems.unshift(data.scan);
        renderFeed();
        refreshStats();
        /* auto-fill UID in register form if empty */
        const ru=document.getElementById('reg-uid');
        if(!ru.value) ru.value=data.scan.uid;
      }
    }catch(e){}
  }

  function animateScan(scan){
    const box=document.getElementById('scan-box');
    const icon=document.getElementById('scan-icon');
    const name=document.getElementById('scan-name');
    const sid=document.getElementById('scan-id');
    const tag=document.getElementById('scan-tag');

    if(scan.result==='logged'){
      box.className='scan-box success';
      icon.textContent='✅';
      name.textContent=scan.name;
      sid.textContent=scan.student_id;
      tag.className='scan-tag tag-ok';
      tag.textContent='✓ Checked In';
    } else if(scan.result==='duplicate'){
      box.className='scan-box dupe';
      icon.textContent='⚠️';
      name.textContent=scan.name;
      sid.textContent='Already marked present today';
      tag.className='scan-tag tag-dupe';
      tag.textContent='Already Present';
    } else {
      box.className='scan-box fail';
      icon.textContent='❌';
      name.textContent='Unknown Card';
      sid.textContent=scan.uid;
      tag.className='scan-tag tag-fail';
      tag.textContent='Not Registered';
    }
    setTimeout(()=>{
      box.className='scan-box ready';
      icon.textContent='📡';
      name.textContent='Waiting for card…';
      sid.textContent=''; tag.className='scan-tag'; tag.textContent='';
    },4000);
  }

  function renderFeed(){
    const n=feedItems.length;
    document.getElementById('feed-count').textContent=n+' scan'+(n!==1?'s':'')+' today';
    if(!n){document.getElementById('feed-list').innerHTML='<div class="empty"><div class="ei">📭</div><div class="em">No scans yet today</div></div>';return;}
    document.getElementById('feed-list').innerHTML=feedItems.map(s=>{
      const cls=s.result==='logged'?'ok':s.result==='duplicate'?'dup':'err';
      const tag=s.result==='logged'?'Checked In':s.result==='duplicate'?'Duplicate':'Unknown';
      const t=new Date(s.ts*1000).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
      return`<div class="feed-item">
        <div class="fdot ${cls}"></div>
        <div style="flex:1"><div class="fname">${s.name||'Unknown'}</div><div class="fuid">${s.uid}</div></div>
        <span class="ftag ${cls}">${tag}</span>
        <span class="ftime">${t}</span>
      </div>`;
    }).join('');
  }

  /* ── REGISTER ── */
  function fmtUID(inp){
    let v=inp.value.replace(/[^0-9A-Fa-f]/g,'').toUpperCase();
    inp.value=(v.match(/.{1,2}/g)||[]).join(':').substring(0,11);
  }
  function clearReg(){
    ['reg-uid','reg-name','reg-sid'].forEach(id=>document.getElementById(id).value='');
    const a=document.getElementById('reg-alert'); a.className='reg-alert'; a.textContent='';
  }
  function showAlert(msg,type){
    const el=document.getElementById('reg-alert');
    el.textContent=msg; el.className='reg-alert show al-'+type;
    el.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  async function doRegister(){
    const uid=document.getElementById('reg-uid').value.trim().toUpperCase();
    const name=document.getElementById('reg-name').value.trim();
    if(!uid){showAlert('Please enter or scan the RFID card UID.','e');return;}
    if(!name){showAlert('Please enter the student name.','e');return;}
    const btn=document.getElementById('reg-btn');
    btn.disabled=true; btn.innerHTML='<span class="spin"></span> Registering…';
    try{
      const d=await(await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({uid,name})})).json();
      if(d.ok){showAlert('✓ '+d.message,'s'); clearReg(); refreshStudents(); refreshStats();}
      else    {showAlert(d.message||'Registration failed.','e');}
    }catch(e){showAlert('Network error. Try again.','e');}
    btn.disabled=false; btn.textContent='Register Student';
  }

  /* ── ALL STUDENTS ── */
  async function refreshStudents(){
    const students=await(await fetch('/api/students')).json();
    const n=students.length;
    document.getElementById('student-count').textContent=n+' student'+(n!==1?'s':'');
    if(!n){document.getElementById('table-students').innerHTML='<div class="empty"><div class="ei">👥</div><div class="em">No students yet</div></div>';return;}
    document.getElementById('table-students').innerHTML=`<table>
      <thead><tr><th>#</th><th>ID</th><th>Name</th><th>RFID</th><th>Status</th><th>Action</th></tr></thead>
      <tbody>${students.map((s,i)=>`<tr>
        <td class="mid">${String(i+1).padStart(2,'0')}</td>
        <td class="mid">${s.student_id}</td>
        <td class="mname">${s.name}</td>
        <td class="mid">${s.rfid_uid}</td>
        <td><span class="badge ${s.present?'bp':'ba'}" id="badge-${s.student_id}">${s.present?'✓ Present':'✗ Absent'}</span></td>
        <td>${s.present
          ?`<button class="btn-r" onclick="unmark('${s.student_id}','${s.name}',this)">Unmark</button>`
          :`<button class="btn-g" onclick="mark('${s.student_id}','${s.name}',this)">Mark Present</button>`
        }</td>
      </tr>`).join('')}</tbody></table>`;
  }

  async function mark(id,name,btn){
    btn.disabled=true;btn.textContent='…';
    const d=await(await fetch('/api/mark',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({student_id:id,student_name:name})})).json();
    if(d.ok){document.getElementById('badge-'+id).className='badge bp';document.getElementById('badge-'+id).textContent='✓ Present';btn.outerHTML=`<button class="btn-r" onclick="unmark('${id}','${name}',this)">Unmark</button>`;refreshStats();}
    else{alert(d.message);btn.disabled=false;btn.textContent='Mark Present';}
  }
  async function unmark(id,name,btn){
    btn.disabled=true;btn.textContent='…';
    const d=await(await fetch('/api/unmark',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({student_id:id})})).json();
    if(d.ok){document.getElementById('badge-'+id).className='badge ba';document.getElementById('badge-'+id).textContent='✗ Absent';btn.outerHTML=`<button class="btn-g" onclick="mark('${id}','${name}',this)">Mark Present</button>`;refreshStats();}
    else{alert(d.message);btn.disabled=false;btn.textContent='Unmark';}
  }

  /* ── Init ── */
  async function initFeed(){
    const recs=await(await fetch('/api/records')).json();
    feedItems=recs.map(r=>({uid:r.rfid_uid||'—',name:r.student_name,student_id:r.student_id,result:'logged',ts:new Date(r.timestamp).getTime()/1000}));
    renderFeed();
  }

  refreshStats();
  refreshStudents();
  initFeed();
  setInterval(pollCheckin,800);
  setInterval(refreshStats,15000);
  setInterval(refreshStudents,15000);
</script>
</body>
</html>
"""

@app.route("/")
def index(): return render_template_string(TEMPLATE)

@app.route("/api/stats")
def api_stats(): return jsonify(get_stats())

@app.route("/api/records")
def api_records(): return jsonify(get_today_records())

@app.route("/api/students")
def api_students():
    import datetime as dt
    today=dt.datetime.now().strftime("%Y-%m-%d")
    conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row
    students=conn.execute("SELECT * FROM students ORDER BY name").fetchall()
    result=[]
    for s in students:
        present=conn.execute("SELECT record_id FROM attendance WHERE student_id=? AND date=?",(s['student_id'],today)).fetchone()
        result.append({"student_id":s['student_id'],"name":s['name'],"rfid_uid":s['rfid_uid'],"present":bool(present)})
    conn.close(); return jsonify(result)

@app.route("/api/poll")
def api_poll():
    with _serial_lock:
        connected=_serial_status["connected"]; port=_serial_status["port"]
        uid=_last_uid["uid"]; ts=_last_uid["ts"]
    scan=None
    if uid and ts>0:
        user=get_registered_user(uid)
        if user:
            result=log_attendance(user["id"],user["name"])
            scan={"uid":uid,"name":user["name"],"student_id":user["id"],"result":result,"ts":ts}
        else:
            scan={"uid":uid,"name":None,"student_id":None,"result":"unknown","ts":ts}
        with _serial_lock:
            _last_uid["uid"]=None; _last_uid["ts"]=0
    return jsonify({"connected":connected,"port":port,"scan":scan})

@app.route("/api/register",methods=["POST"])
def api_register():
    data=request.get_json(force=True)
    uid=(data.get("uid") or "").strip().upper()
    name=(data.get("name") or "").strip()
    if not uid or not name: return jsonify({"ok":False,"message":"UID and name are required."})
    ok,message,student_id=register_student_web(uid,name)
    return jsonify({"ok":ok,"message":message,"student_id":student_id})

@app.route("/api/mark",methods=["POST"])
def api_mark():
    data=request.get_json(force=True)
    sid=data.get("student_id","").strip(); sname=data.get("student_name","").strip()
    if not sid: return jsonify({"ok":False,"message":"student_id required."})
    result=log_attendance(sid,sname)
    if result=="logged":    return jsonify({"ok":True,"message":"Attendance marked."})
    if result=="duplicate": return jsonify({"ok":False,"message":f"{sname} is already marked present today."})
    return jsonify({"ok":False,"message":"Could not log attendance."})

@app.route("/api/unmark",methods=["POST"])
def api_unmark():
    data=request.get_json(force=True)
    sid=data.get("student_id","").strip()
    if not sid: return jsonify({"ok":False,"message":"student_id required."})
    unmark_attendance(sid)
    return jsonify({"ok":True,"message":"Attendance removed."})

if __name__ == "__main__":
    init_database()
    print("[INFO] Dashboard → http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)