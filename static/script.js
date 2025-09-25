
// ---- Wave Visualizer ----
class WaveVisualizer {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.running = false;
    this.synthetic = true;
    this.t = 0;
    this.amplitude = 0.5;
    this.noiseSeed = Math.random() * 1000;
    this.resize = this.resize.bind(this);
    window.addEventListener('resize', this.resize);
    this.resize();
  }
  attachAudioSource(audioElement) {
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      this.audioCtx = new AC();
      this.source = this.audioCtx.createMediaElementSource(audioElement);
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 1024;
      this.buffer = new Uint8Array(this.analyser.frequencyBinCount);
      this.source.connect(this.analyser);
      this.analyser.connect(this.audioCtx.destination);
      this.synthetic = false;
    } catch(e) { /* fallback to synthetic */ }
  }
  start() {
    if (this.running) return;
    this.running = true;
    this.t = 0;
    const loop = () => {
      if (!this.running) return;
      this.draw();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
  stop() { this.running = false; }
  resize() {
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = Math.floor(this.canvas.clientWidth * dpr);
    this.canvas.height = Math.floor(this.canvas.clientHeight * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  draw() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    const ctx = this.ctx;
    ctx.clearRect(0,0,w,h);
    // Determine amplitude
    let amp = 0.2;
    if (this.synthetic) {
      // Smoothly vary amplitude while speaking
      this.t += 0.02;
      amp = 0.15 + 0.1*Math.sin(this.t*1.3) + 0.05*Math.sin(this.t*2.7);
    } else if (this.analyser) {
      this.analyser.getByteFrequencyData(this.buffer);
      // Use low frequency energy as amplitude
      let sum = 0;
      for (let i=1;i<12;i++) sum += this.buffer[i]||0;
      amp = Math.min(0.4, 0.05 + (sum/12)/255 * 0.35);
    }
    // Draw layered sine bands
    const bands = 4;
    for (let b=0; b<bands; b++) {
      const yBase = h*(0.35 + 0.15*b);
      ctx.beginPath();
      const k = 0.0025 + b*0.0008;
      const a = amp * (1 - b*0.18) * h*0.15;
      for (let x=0; x<w; x+=4) {
        const y = yBase + Math.sin((x*this.t*0.04 + x*k) + b*1.7) * a;
        if (x===0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = b===0 ? 'rgba(16,185,129,0.65)' :
                        b===1 ? 'rgba(59,130,246,0.55)' :
                        b===2 ? 'rgba(147,197,253,0.35)' :
                                'rgba(34,197,94,0.28)';
      ctx.lineWidth = 2 - b*0.25;
      ctx.stroke();
    }
  }
}


// Session ID for isolated files
const sessionId = (crypto.randomUUID && crypto.randomUUID()) || (Date.now().toString(36) + Math.random().toString(36).slice(2,8));

const checklistEl = document.getElementById('checklist');

function deriveChecklist(plan) {
  const items = [];
  if (!plan) return items;
  if (plan.service_voltage || plan.service_amperes) items.push('Confirm service voltage & ampacity assumptions.');
  if (Array.isArray(plan.panels) && plan.panels.length) items.push('Verify panel ratings, AIC, and feeder sizes.');
  if (Array.isArray(plan.loads) && plan.loads.length) items.push('Validate load calc (NEC 220), demand vs connected.');
  if (Array.isArray(plan.rooms) && plan.rooms.length) items.push('Check device locations vs egress/ADA constraints.');
  items.push('Grounding/bonding per NEC 250.');
  items.push('Overcurrent protection & coordination (NEC 240).');
  return items;
}

function renderChecklist(plan) {
  const items = deriveChecklist(plan);
  checklistEl.innerHTML = '';
  items.forEach(t => {
    const li = document.createElement('li'); li.textContent = t; checklistEl.appendChild(li);
  });
}


const thread = document.getElementById('thread');
const wavesCanvas = document.getElementById('waves');
const waveviz = new WaveVisualizer(wavesCanvas);
const textInput = document.getElementById('textInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const buildBtn = document.getElementById('buildBtn');
const outputsList = document.getElementById('outputsList');
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');

let lastPlan = null; // store latest planner JSON
let lastIntent = null;

// Helpers
function addMsg(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = text;
  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;
  if (role === 'ai') speak(text);
}
function speak(text) {
  if (!('speechSynthesis' in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.95;
  u.pitch = 0.7; // deeper tone
  u.volume = 1.0;
  u.onstart = () => { waveviz.synthetic = true; waveviz.start(); };
  u.onend = () => { waveviz.stop(); };
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

// Voice input
let rec = null;
if ('webkitSpeechRecognition' in window) {
  rec = new webkitSpeechRecognition();
  rec.continuous = false; rec.interimResults = false; rec.lang = 'en-US';
  rec.onresult = (e) => {
    const txt = e.results[0][0].transcript;
    textInput.value = txt;
  };
}

micBtn.addEventListener('mousedown', () => rec && rec.start());
micBtn.addEventListener('mouseup', () => rec && rec.stop());
micBtn.addEventListener('mouseleave', () => rec && rec.stop());

// Drag & drop
function uploadFiles(files) {
  [...files].forEach(async (file) => {
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch('/bucket/upload?session=' + encodeURIComponent(sessionId), { method:'POST', body: fd });
    const j = await r.json();
    refreshOutputs();
  });
}
dropzone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => uploadFiles(e.target.files));
dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('hover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('hover'));
dropzone.addEventListener('drop', (e) => { e.preventDefault(); dropzone.classList.remove('hover'); uploadFiles(e.dataTransfer.files); });

// Send
sendBtn.addEventListener('click', async () => {
  const text = textInput.value.trim();
  if (!text) return;
  addMsg('user', text);
  textInput.value='';
  const r = await fetch('/commands/run', {
    method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ text, session: sessionId })
  });
  const j = await r.json();
  // The backend returns summary + plan when a task matched; otherwise message
  if (j.summary) addMsg('ai', j.summary);
  if (j.plan) lastPlan = j.plan;
  if (j.plan && j.plan.task) lastIntent = j.plan.task;
  if (j.message) addMsg('ai', j.message);
  refreshOutputs();
});

async function refreshOutputs() {
  const r = await fetch('/outputs/list?session=' + encodeURIComponent(sessionId));
  const j = await r.json();
  outputsList.innerHTML = '';
  j.files.forEach(name => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = '/out/' + name;
    a.textContent = name;
    li.appendChild(a);
    outputsList.appendChild(li);
  });
}

// Build
buildBtn.addEventListener('click', async () => {
  if (!lastPlan || !lastIntent) {
    addMsg('ai', 'Tell me what to build (one-line, power plan, or lighting plan), then press Build.');
    return;
  }
  addMsg('ai', 'Building your package now…');
  const r = await fetch('/export/build_zip', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ intent: lastIntent, plan: lastPlan, outputs: ['dxf','pdf','csv'], session: sessionId })
  });
  const j = await r.json();
  if (j.zip) {
    addMsg('ai', 'Build complete. Your downloadable ZIP is in the outputs list.');
    refreshOutputs();
  } else {
    addMsg('ai', 'I hit an issue creating the ZIP. Check server logs.');
  }
});

// Initial load
refreshOutputs();


(function tryAttachAudio(){
  const el = document.getElementById('ttsAudio');
  if (!el) return;
  // Only attach once
  if (!window.__wave_audio_attached) {
    window.__wave_audio_attached = true;
    try { waveviz.attachAudioSource(el); } catch(e){ /* ignore */ }
  }
})();
