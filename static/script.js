async function refreshBucket() {
  const res = await fetch('/bucket/list');
  const data = await res.json();
  const ul = document.getElementById('bucketList');
  ul.innerHTML = '';
  data.files.forEach(f => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = '/bucket/file/' + encodeURIComponent(f);
    a.textContent = f;
    a.target = '_blank';
    li.appendChild(a);
    ul.appendChild(li);
  });
}

async function refreshOutputs() {
  const res = await fetch('/outputs/list');
  const data = await res.json();
  const ul = document.getElementById('outputs');
  ul.innerHTML = '';
  data.files.forEach(f => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = '/out/' + encodeURIComponent(f);
    a.textContent = f;
    a.target = '_blank';
    li.appendChild(a);
    ul.appendChild(li);
  });
}

function setupDropzone() {
  const dz = document.getElementById('dropzone');
  const input = document.getElementById('fileInput');

  dz.addEventListener('click', () => input.click());
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
  dz.addEventListener('dragleave', e => { dz.classList.remove('dragover'); });
  dz.addEventListener('drop', async e => {
    e.preventDefault();
    dz.classList.remove('dragover');
    const files = e.dataTransfer.files;
    await uploadFiles(files);
  });
  input.addEventListener('change', async e => {
    await uploadFiles(input.files);
    input.value = '';
  });
}

async function uploadFiles(fileList) {
  const form = new FormData();
  for (let f of fileList) form.append('files', f);
  await fetch('/upload', { method: 'POST', body: form });
  await refreshBucket();
}

function setupMic() {
  const micBtn = document.getElementById('micBtn');
  const txt = document.getElementById('commandText');
  let recognition = null;

  if ('webkitSpeechRecognition' in window) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    micBtn.addEventListener('mousedown', () => {
      recognition.start();
      micBtn.classList.add('recording');
    });
    micBtn.addEventListener('mouseup', () => {
      recognition.stop();
      micBtn.classList.remove('recording');
    });
    recognition.onresult = (event) => {
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        if (res.isFinal) final += res[0].transcript;
      }
      if (final) txt.value = (txt.value + ' ' + final).trim();
    };
  } else {
    micBtn.disabled = true;
    micBtn.textContent = '🎙️ Speech not supported';
  }

  document.getElementById('runBtn').addEventListener('click', async () => {
    const text = txt.value.trim();
    if (!text) return;
    const res = await fetch('/commands/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    alert(data.message || 'Command executed.');
    await refreshOutputs();
  });
}

async function setupClearBucket() {
  document.getElementById('clearBucket').addEventListener('click', async () => {
    if (!confirm('Delete all files in the bucket?')) return;
    await fetch('/bucket/clear', { method: 'POST' });
    await refreshBucket();
  });
}

window.addEventListener('DOMContentLoaded', async () => {
  setupDropzone();
  setupMic();
  setupClearBucket();
  await refreshBucket();
  await refreshOutputs();
});
