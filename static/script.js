
// ---- Busy State Management ----
function setBusy(busy, status = '') {
  if (busy) {
    console.log(`[BUSY] ${status}`);
  } else {
    console.log(`[READY] ${status}`);
  }
}

// Tab Management System
class TabManager {
  constructor() {
    this.tabs = [];
    this.activeTabId = null;
    this.loadFromStorage();
    
    // If no tabs, create initial tab (without auto-switching since DOM not ready yet)
    if (this.tabs.length === 0) {
      this.createTab('home', false);
    }
    
    // Clear Home tab messages on initial load to show welcome screen
    const homeTab = this.tabs.find(t => t.id === 'home');
    if (homeTab && homeTab.messages.length > 0) {
      homeTab.messages = [];
      this.saveToStorage();
    }
    
    this.renderTabs();
  }
  
  initializeActiveTab() {
    // Switch to active tab or Home tab on initial load (called after DOM is ready)
    const homeTab = this.tabs.find(t => t.id === 'home');
    if (this.activeTabId) {
      this.switchToTab(this.activeTabId);
    } else if (homeTab) {
      this.switchToTab('home');
    }
  }
  
  getDatePrefix() {
    const now = new Date();
    const yy = String(now.getFullYear()).slice(2);
    const mm = String(now.getMonth() + 1).padStart(2, '0');
    const dd = String(now.getDate()).padStart(2, '0');
    return `${yy}${mm}${dd}`;
  }
  
  getNextTaskNumber() {
    const datePrefix = this.getDatePrefix();
    const todayTabs = this.tabs.filter(t => t.name.startsWith(datePrefix));
    return todayTabs.length + 1;
  }
  
  createTab(type = 'task', autoSwitch = true) {
    let name, tabId;
    if (type === 'home') {
      name = 'Home';
      tabId = 'home';
    } else {
      const datePrefix = this.getDatePrefix();
      const taskNum = this.getNextTaskNumber();
      name = `${datePrefix}_T${taskNum}`;
      tabId = `${datePrefix}_T${taskNum}`;
    }
    
    const sessionId = (crypto.randomUUID && crypto.randomUUID()) || (Date.now().toString(36) + Math.random().toString(36).slice(2,8));
    
    const tab = {
      id: tabId,
      name: name,
      sessionId: sessionId,
      messages: [],
      files: [],
      outputs: []
    };
    
    this.tabs.push(tab);
    this.activeTabId = tabId;
    this.saveToStorage();
    this.renderTabs();
    
    if (autoSwitch) {
      this.switchToTab(tabId);
    }
    
    return tab;
  }
  
  switchToTab(tabId) {
    this.activeTabId = tabId;
    this.saveToStorage();
    this.renderTabs();
    
    const tab = this.getActiveTab();
    if (tab) {
      // Update global sessionId
      window.currentSessionId = tab.sessionId;
      
      // Restore chat messages (with skipSave flag to prevent duplication)
      thread.innerHTML = '';
      
      // Show welcome screen for empty Home tab
      if (tab.id === 'home' && tab.messages.length === 0) {
        this.showWelcomeScreen();
      } else {
        tab.messages.forEach(msg => {
          const opts = msg.options || {};
          opts.skipSave = true;  // Don't save replayed messages
          addMsg(msg.role, msg.text, opts);
        });
      }
      
      // Refresh file and output lists
      refreshUploads();
      refreshOutputs();
    }
  }
  
  showWelcomeScreen() {
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'msg ai welcome-screen';
    welcomeDiv.style.maxWidth = '100%';
    welcomeDiv.style.textAlign = 'center';
    
    const message = document.createElement('div');
    message.textContent = 'What can I build for you?';
    message.style.fontSize = '18px';
    message.style.marginBottom = '20px';
    
    const buttonContainer = document.createElement('div');
    buttonContainer.style.display = 'flex';
    buttonContainer.style.gap = '12px';
    buttonContainer.style.justifyContent = 'center';
    buttonContainer.style.flexWrap = 'wrap';
    
    // Task Build button (active)
    const taskBuildBtn = document.createElement('button');
    taskBuildBtn.textContent = 'Task Build';
    taskBuildBtn.className = 'welcome-btn';
    taskBuildBtn.style.padding = '12px 24px';
    taskBuildBtn.style.fontSize = '16px';
    taskBuildBtn.style.background = '#10b981';
    taskBuildBtn.style.color = '#fff';
    taskBuildBtn.style.border = 'none';
    taskBuildBtn.style.borderRadius = '8px';
    taskBuildBtn.style.cursor = 'pointer';
    taskBuildBtn.onclick = () => {
      // Clear welcome screen and enable normal chat
      thread.innerHTML = '';
      // AI prompts for task
      addMsg('ai', 'What task would you like to build?');
      textInput.focus();
    };
    
    // Create New Project Build button (disabled)
    const newProjectBtn = document.createElement('button');
    newProjectBtn.textContent = 'Create New Project Build';
    newProjectBtn.className = 'welcome-btn';
    newProjectBtn.style.padding = '12px 24px';
    newProjectBtn.style.fontSize = '16px';
    newProjectBtn.style.background = '#374151';
    newProjectBtn.style.color = '#6b7280';
    newProjectBtn.style.border = 'none';
    newProjectBtn.style.borderRadius = '8px';
    newProjectBtn.style.cursor = 'not-allowed';
    newProjectBtn.style.opacity = '0.5';
    newProjectBtn.onclick = () => {
      alert('Coming soon!');
    };
    
    // Open Project Build button (disabled)
    const openProjectBtn = document.createElement('button');
    openProjectBtn.textContent = 'Open Project Build';
    openProjectBtn.className = 'welcome-btn';
    openProjectBtn.style.padding = '12px 24px';
    openProjectBtn.style.fontSize = '16px';
    openProjectBtn.style.background = '#374151';
    openProjectBtn.style.color = '#6b7280';
    openProjectBtn.style.border = 'none';
    openProjectBtn.style.borderRadius = '8px';
    openProjectBtn.style.cursor = 'not-allowed';
    openProjectBtn.style.opacity = '0.5';
    openProjectBtn.onclick = () => {
      alert('Coming soon!');
    };
    
    buttonContainer.appendChild(taskBuildBtn);
    buttonContainer.appendChild(newProjectBtn);
    buttonContainer.appendChild(openProjectBtn);
    
    welcomeDiv.appendChild(message);
    welcomeDiv.appendChild(buttonContainer);
    thread.appendChild(welcomeDiv);
  }
  
  async closeTab(tabId) {
    const index = this.tabs.findIndex(t => t.id === tabId);
    if (index === -1) return;
    
    // Don't close the last tab
    if (this.tabs.length === 1) return;
    
    // Don't close the home tab
    if (tabId === 'home') return;
    
    // Switch to this tab first so the confirmation appears in the right place
    if (this.activeTabId !== tabId) {
      this.switchToTab(tabId);
    }
    
    // Check if there's an active task - if so, ask for confirmation
    try {
      const r = await fetch('/commands/run', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ 
          text: 'finished', 
          session: window.currentSessionId 
        })
      });
      const j = await r.json();
      
      // If needs confirmation, show the message and let the yes/no buttons handle it
      if (j.needs_finish_confirmation) {
        // The response will be shown through the normal chat flow
        if (j.message) {
          addMsg('ai', j.message, {
            needs_finish_confirmation: j.needs_finish_confirmation,
            task_name: j.task_name,
            message: j.message
          });
        }
        return; // Don't close yet - wait for user confirmation
      }
      
      // No active task or already confirmed - proceed with closing
      this.forceCloseTab(tabId);
      
    } catch (error) {
      console.error('Error checking task status:', error);
      // On error, just close the tab
      this.forceCloseTab(tabId);
    }
  }
  
  forceCloseTab(tabId) {
    // Actually close the tab without confirmation
    const index = this.tabs.findIndex(t => t.id === tabId);
    if (index === -1) return;
    
    this.tabs.splice(index, 1);
    
    // If closing active tab, switch to previous or next
    if (this.activeTabId === tabId) {
      const newIndex = Math.min(index, this.tabs.length - 1);
      this.activeTabId = this.tabs[newIndex].id;
    }
    
    this.saveToStorage();
    this.renderTabs();
    this.switchToTab(this.activeTabId);
  }
  
  getActiveTab() {
    return this.tabs.find(t => t.id === this.activeTabId);
  }
  
  saveMessage(role, text, options) {
    const tab = this.getActiveTab();
    if (tab) {
      tab.messages.push({ role, text, options });
      this.saveToStorage();
    }
  }
  
  renderTabs() {
    const tabBar = document.getElementById('tabBar');
    tabBar.innerHTML = '';
    
    this.tabs.forEach(tab => {
      const tabEl = document.createElement('div');
      tabEl.className = 'tab' + (tab.id === this.activeTabId ? ' active' : '');
      tabEl.innerHTML = `${tab.name}${tab.id !== 'home' ? '<span class="tab-close">×</span>' : ''}`;
      
      tabEl.addEventListener('click', (e) => {
        if (e.target.classList.contains('tab-close')) {
          this.closeTab(tab.id);
        } else {
          this.switchToTab(tab.id);
        }
      });
      
      tabBar.appendChild(tabEl);
    });
  }
  
  saveToStorage() {
    try {
      localStorage.setItem('tabs', JSON.stringify({
        tabs: this.tabs,
        activeTabId: this.activeTabId
      }));
    } catch (e) {
      console.error('Failed to save tabs:', e);
    }
  }
  
  loadFromStorage() {
    try {
      const data = localStorage.getItem('tabs');
      if (data) {
        const parsed = JSON.parse(data);
        this.tabs = parsed.tabs || [];
        this.activeTabId = parsed.activeTabId;
      }
    } catch (e) {
      console.error('Failed to load tabs:', e);
    }
  }
}

// Initialize tab manager
const tabManager = new TabManager();

// Session ID for isolated files (now managed by tab manager)
let sessionId = tabManager.getActiveTab()?.sessionId || (crypto.randomUUID && crypto.randomUUID()) || (Date.now().toString(36) + Math.random().toString(36).slice(2,8));
window.currentSessionId = sessionId;

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
const textInput = document.getElementById('textInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const buildBtn = document.getElementById('buildBtn');
const outputsList = document.getElementById('outputsList');
const uploadsList = document.getElementById('uploadsList');
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');

let lastPlan = null; // store latest planner JSON
let lastIntent = null;

// Initialize active tab now that DOM elements are ready
tabManager.initializeActiveTab();

// Helpers
function addMsg(role, text, options = {}) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  
  if (options.needs_confirmation || options.needs_finish_confirmation) {
    // Render confirmation message with Yes/No buttons
    const taskName = options.task_name || 'this task';
    const message = options.message || text;
    
    // Parse the message to find and highlight the task name
    const messageContainer = document.createElement('div');
    messageContainer.style.marginBottom = '10px';
    
    // Replace task name with highlighted version
    const highlightedMessage = message.replace(
      new RegExp(`(${taskName})`, 'gi'),
      '<span class="task-highlight">$1</span>'
    );
    messageContainer.innerHTML = highlightedMessage;
    
    // Create button container
    const buttonContainer = document.createElement('div');
    buttonContainer.style.display = 'flex';
    buttonContainer.style.gap = '10px';
    buttonContainer.style.marginTop = '10px';
    
    // Yes button
    const yesBtn = document.createElement('button');
    yesBtn.textContent = 'Yes';
    yesBtn.className = 'confirm-btn yes-btn';
    yesBtn.onclick = () => {
      // If this is task confirmation (not finish confirmation), create a new tab
      if (options.needs_confirmation && !options.needs_finish_confirmation) {
        // Get current tab and its messages
        const currentTab = tabManager.getActiveTab();
        const taskSessionId = currentTab.sessionId; // This session has the task context
        
        // Create new task tab WITHOUT auto-switching
        const newTab = tabManager.createTab('task', false);
        
        // Task tab INHERITS the current session ID to maintain backend context
        newTab.sessionId = taskSessionId;
        
        // Move current conversation to new tab
        newTab.messages = [...currentTab.messages];
        
        // Give home tab a NEW session ID for next task
        if (currentTab.id === 'home') {
          currentTab.messages = [];
          currentTab.sessionId = (crypto.randomUUID && crypto.randomUUID()) || (Date.now().toString(36) + Math.random().toString(36).slice(2,8));
        }
        
        // Save updated tab state
        tabManager.saveToStorage();
        
        // Now switch to the new tab (will restore messages with skipSave)
        tabManager.switchToTab(newTab.id);
        
        // Update global session to the task tab's session (same as old session)
        window.currentSessionId = newTab.sessionId;
        
        // Send "yes" to confirm the task (in the task tab's context)
        textInput.value = 'yes';
        sendBtn.click();
      } else {
        // For finish confirmation, just send yes
        textInput.value = 'yes';
        sendBtn.click();
      }
    };
    
    // No button
    const noBtn = document.createElement('button');
    noBtn.textContent = 'No';
    noBtn.className = 'confirm-btn no-btn';
    noBtn.onclick = () => {
      textInput.value = 'no';
      sendBtn.click();
    };
    
    buttonContainer.appendChild(yesBtn);
    buttonContainer.appendChild(noBtn);
    
    div.appendChild(messageContainer);
    div.appendChild(buttonContainer);
  } else {
    div.textContent = text;
  }
  
  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;
  
  // Save message to tab ONLY if not replaying from storage
  if (!options.skipSave) {
    tabManager.saveMessage(role, text, options);
  }
  
  if (role === 'ai' && !options.needs_confirmation && !options.needs_finish_confirmation && !options.text_only) {
    speak(text, options.tts_override);
  }
}
function speak(text, tts_override) {
  if (!('speechSynthesis' in window)) return;
  // Use tts_override if provided, otherwise use first sentence
  const speechText = tts_override || text;
  const match = speechText.match(/^.*?[.!?]/);
  const firstSentence = match ? match[0] : speechText;
  const u = new SpeechSynthesisUtterance(firstSentence);
  u.rate = 0.95;
  u.pitch = 0.7; // deeper tone
  u.volume = 1.0;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

// Voice input
let rec = null;
let isRecording = false;
let silenceTimer = null;

if ('webkitSpeechRecognition' in window) {
  rec = new webkitSpeechRecognition();
  rec.continuous = true; 
  rec.interimResults = true; 
  rec.lang = 'en-US';
  
  rec.onstart = () => {
    isRecording = true;
    micBtn.style.background = '#ff4444';
    console.log('Speech recognition started');
    
    // Start silence timer
    silenceTimer = setTimeout(() => {
      if (isRecording) {
        rec.stop();
        console.log('Stopped due to 3 seconds of silence');
      }
    }, 3000);
  };
  
  rec.onresult = (e) => {
    // Reset silence timer on any speech detection
    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = setTimeout(() => {
        if (isRecording) {
          rec.stop();
          console.log('Stopped due to 3 seconds of silence');
        }
      }, 3000);
    }
    
    // Get final transcript
    const txt = e.results[e.results.length - 1][0].transcript;
    if (e.results[e.results.length - 1].isFinal) {
      textInput.value = txt;
      console.log('Speech recognized:', txt);
    }
  };
  
  rec.onerror = (e) => {
    console.error('Speech recognition error:', e.error);
    isRecording = false;
    micBtn.style.background = '';
    if (silenceTimer) clearTimeout(silenceTimer);
    
    if (e.error === 'no-speech') {
      addMsg('ai', 'No speech detected. Please try again.');
    } else if (e.error === 'not-allowed') {
      addMsg('ai', 'Microphone permission denied. Please allow microphone access in your browser settings.');
    } else if (e.error !== 'aborted') {
      addMsg('ai', `Speech recognition error: ${e.error}`);
    }
  };
  
  rec.onend = () => {
    isRecording = false;
    micBtn.style.background = '';
    if (silenceTimer) clearTimeout(silenceTimer);
    console.log('Speech recognition ended');
  };
}

micBtn.addEventListener('click', () => {
  if (!rec) return;
  
  if (isRecording) {
    // Stop recording
    rec.stop();
  } else {
    // Start recording
    try {
      rec.start();
    } catch (e) {
      console.error('Failed to start recording:', e);
    }
  }
});

// Drag & drop
async function uploadFiles(files) {
  if (!files || files.length === 0) return;
  
  // Show files immediately with spinner
  const fileArray = [...files];
  fileArray.forEach(file => {
    const li = document.createElement('li');
    li.className = 'uploading';
    li.innerHTML = `<span class="spinner">⟳</span> ${file.name}`;
    li.dataset.filename = file.name;
    uploadsList.appendChild(li);
  });
  
  try {
    const fd = new FormData();
    for (const file of fileArray) {
      fd.append('files', file);
    }
    const r = await fetch('/bucket/upload?session=' + encodeURIComponent(window.currentSessionId), { method:'POST', body: fd });
    
    if (!r.ok) {
      throw new Error(`Upload failed: ${r.status} ${r.statusText}`);
    }
    
    const j = await r.json();
    
    // Remove spinner items and refresh with actual uploaded files
    uploadsList.querySelectorAll('.uploading').forEach(el => el.remove());
    refreshUploads();
    
    // Display OCR results if any
    if (j.ocr_results && j.ocr_results.length > 0) {
      for (const result of j.ocr_results) {
        if (result.error) {
          addMsg('ai', `OCR failed for ${result.filename}: ${result.error}`, { text_only: true });
        } else {
          // Show panel parameters found
          if (result.parameters && result.parameters.length > 0) {
            const paramList = result.parameters.join(', ');
            addMsg('ai', `Found ${result.parameters.length} panel parameters from ${result.filename}: ${paramList} (confidence: ${result.confidence}%)`, { text_only: true });
          }
          
          // Show circuit/breaker data found
          if (result.breaker_notifications && result.breaker_notifications.length > 0) {
            const circuitInfo = result.breaker_notifications.join('\n');
            addMsg('ai', `Found circuit data from ${result.filename}:\n${circuitInfo}`, { text_only: true });
          }
          
          // Show aggregation summary if multiple sources
          if (result.aggregation_summary && result.aggregation_summary.total_observations > result.aggregation_summary.total_circuits) {
            addMsg('ai', `Data aggregated: ${result.aggregation_summary.total_observations} observations across ${result.aggregation_summary.total_circuits} circuits from ${result.aggregation_summary.sources?.length || 1} photo(s)`, { text_only: true });
          }
        }
      }
    }
    
  } catch (error) {
    console.error('Upload error:', error);
    uploadsList.querySelectorAll('.uploading').forEach(el => {
      el.className = 'upload-error';
      el.innerHTML = `<span class="error">✗</span> ${el.dataset.filename} - Failed`;
    });
    addMsg('ai', `Upload failed. ${error.message}`);
  }
}
dropzone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => uploadFiles(e.target.files));
dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('hover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('hover'));
dropzone.addEventListener('drop', (e) => { 
  e.preventDefault(); 
  e.stopPropagation(); // Prevent event from bubbling to document.body
  dropzone.classList.remove('hover'); 
  uploadFiles(e.dataTransfer.files); 
});

// EXPANDED DROP ZONE: Make the entire window accept drag-and-drop
let dragCounter = 0; // Track nested drag events

document.body.addEventListener('dragenter', (e) => {
  e.preventDefault();
  dragCounter++;
  if (dragCounter === 1) {
    dropzone.classList.add('hover'); // Show visual feedback on the dropzone
  }
});

document.body.addEventListener('dragover', (e) => {
  e.preventDefault(); // Required to allow drop
});

document.body.addEventListener('dragleave', (e) => {
  e.preventDefault();
  dragCounter--;
  if (dragCounter === 0) {
    dropzone.classList.remove('hover');
  }
});

document.body.addEventListener('drop', (e) => {
  e.preventDefault();
  dragCounter = 0;
  dropzone.classList.remove('hover');
  
  // Only process if files were dropped
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    uploadFiles(e.dataTransfer.files);
  }
});

// Send
sendBtn.addEventListener('click', async () => {
  const text = textInput.value.trim();
  if (!text) return;
  addMsg('user', text);
  textInput.value='';
  const r = await fetch('/commands/run', {
    method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ text, session: window.currentSessionId })
  });
  const j = await r.json();
  // The backend returns summary + plan when a task matched; otherwise message
  // Only show summary if it's different from message (avoid duplicates)
  if (j.summary && j.summary !== j.message) addMsg('ai', j.summary);
  if (j.plan) {
    lastPlan = j.plan;
    renderChecklist(j.plan);
  }
  if (j.plan && j.plan.task) lastIntent = j.plan.task;
  
  // Handle confirmation messages with Yes/No buttons
  if (j.message) {
    if (j.needs_confirmation || j.needs_finish_confirmation) {
      addMsg('ai', j.message, {
        needs_confirmation: j.needs_confirmation,
        needs_finish_confirmation: j.needs_finish_confirmation,
        task_name: j.task_name,
        message: j.message,
        tts_override: j.tts_override
      });
    } else {
      addMsg('ai', j.message, {
        tts_override: j.tts_override,
        text_only: j.text_only
      });
    }
  }
  
  // Auto-close tab when task is finished (task: "none")
  if (j.plan && j.plan.task === "none") {
    const currentTab = tabManager.getActiveTab();
    // Only close if this is NOT the home tab
    if (currentTab && currentTab.id !== 'home') {
      // Close this tab and switch to home (force close without confirmation since already confirmed)
      setTimeout(() => {
        tabManager.forceCloseTab(currentTab.id);
        tabManager.switchToTab('home');
      }, 1000); // Small delay so user sees the "finished" message
    }
  }
  
  refreshOutputs();
});

// Enter key to send
textInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    sendBtn.click();
  }
});

async function refreshUploads() {
  const r = await fetch('/bucket/list?session=' + encodeURIComponent(window.currentSessionId));
  const j = await r.json();
  uploadsList.innerHTML = '';
  j.files.forEach(name => {
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = '/bucket/file/' + name + '?session=' + encodeURIComponent(window.currentSessionId);
    a.download = name;
    a.textContent = name;
    li.appendChild(a);
    uploadsList.appendChild(li);
  });
}

async function refreshOutputs() {
  const r = await fetch('/outputs/list?session=' + encodeURIComponent(window.currentSessionId));
  const j = await r.json();
  outputsList.innerHTML = '';
  
  // File type icons and labels
  const fileInfo = {
    '.xlsx': { icon: '📊', label: 'Excel' },
    '.pdf': { icon: '📄', label: 'PDF' },
    '.docx': { icon: '📝', label: 'Word' },
    '.zip': { icon: '📦', label: 'ZIP Bundle' },
    '.dxf': { icon: '📐', label: 'CAD' },
    '.csv': { icon: '📋', label: 'CSV' },
    '.txt': { icon: '📃', label: 'Text' },
    '.json': { icon: '🔧', label: 'JSON' }
  };
  
  j.files.forEach(name => {
    const ext = name.substring(name.lastIndexOf('.')).toLowerCase();
    const info = fileInfo[ext] || { icon: '📁', label: 'File' };
    
    const li = document.createElement('li');
    li.className = 'output-item';
    
    const a = document.createElement('a');
    a.href = '/out/' + name + '?session=' + encodeURIComponent(window.currentSessionId);
    a.download = name;
    a.className = 'output-link';
    a.innerHTML = `<span class="file-icon">${info.icon}</span><span class="file-name">${name}</span><span class="download-btn">⬇️</span>`;
    
    li.appendChild(a);
    outputsList.appendChild(li);
  });
}

async function exportZip(ir, confirm = false) {
  const sessionParam = `session=${encodeURIComponent(window.currentSessionId)}`;
  const url = confirm ? `/panel/export/zip?confirm=true&${sessionParam}` : `/panel/export/zip?${sessionParam}`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ir),
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "");
    throw new Error("Export failed: " + (detail || resp.status));
  }

  // derive filename from Content-Disposition if present
  let filename = "panel_schedule_bundle.zip";
  const cd = resp.headers.get("Content-Disposition");
  if (cd) {
    const m = /filename\*?=(?:UTF-8'')?([^;]+)/i.exec(cd);
    if (m && m[1]) {
      try { filename = decodeURIComponent(m[1].replace(/"/g, "")); } catch {}
    }
  }

  // download blob
  const blob = await resp.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(a.href);
    a.remove();
  }, 0);

  if (typeof refreshOutputs === "function") {
    try { await refreshOutputs(); } catch {}
  }
  if (typeof setBusy === "function") setBusy(false, "Build complete");
  if (typeof addMsg === "function") addMsg("ai", "Build complete. ZIP downloaded.");
}

// --- GPT-driven Preflight Review (no recursion!) ---
async function runPreflight(ir) {
  const resp = await fetch("/panel/preflight/gpt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ir),
  });
  if (!resp.ok) {
    const detail = await resp.text().catch(() => "");
    throw new Error("GPT Preflight failed: " + (detail || resp.status));
  }
  const pf = await resp.json();

  // Stash IR + GPT results so the YES button can pass them to the exporter
  const yesBtn = document.getElementById("confirm-build");
  yesBtn._ir = {
    ...ir,
    _kva_formulas: pf.formulas || {},
    _inferred_system: pf.system || "",
  };

  return pf;
}

// --- Handler to start the preflight process when the user clicks BUILD ---
async function handleBuildClick() {
  // Show build starting message
  addMsg("ai", "Build in Progress, AI performing checks. Review AI checks in outputs.", {
    tts_override: "Build in Progress"
  });
  
  let ir;
  
  // Try to build IR from session first
  try {
    setBusy?.(true, "Building panel schedule from your inputs…");
    const buildResp = await fetch('/panel/build_from_session', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ session: window.currentSessionId })
    });
    
    if (buildResp.ok) {
      ir = await buildResp.json();
      console.log("Built panel IR from session successfully:", ir);
    } else {
      const errorText = await buildResp.text();
      console.error("Build failed with status:", buildResp.status, errorText);
      throw new Error(`Failed to build from session: ${buildResp.status} - ${errorText}`);
    }
  } catch (e) {
    console.error("Error building from session:", e.message || e);
    
    // Fallback: check for stored IR
    const storedIR = sessionStorage.getItem('panel_ir');
    if (storedIR) {
      try {
        ir = JSON.parse(storedIR);
      } catch (parseErr) {
        addMsg("ai", "Unable to build panel schedule. Please provide panel information via chat first.", { text_only: true });
        setBusy?.(false, "Build failed");
        return;
      }
    } else {
      addMsg("ai", "No panel schedule to build. Please start by saying 'Create a panel schedule' and then provide details like voltage, circuits, etc.", { text_only: true });
      setBusy?.(false, "Build failed");
      return;
    }
  }

  setBusy?.(true, "Generating outputs…");

  try {
    // Run preflight in background (results saved to Word doc)
    const pf = await runPreflight(ir);

    // Add IR metadata from preflight (no chat output)
    const enrichedIR = {
      ...ir,
      _kva_formulas: pf.formulas || {},
      _inferred_system: pf.system || "",
    };
    
    // Call panel export endpoint - this saves files to task-specific output directory
    // AI review runs to generate Word doc, JSON, and TXT files
    const exportResp = await fetch(`/panel/export/zip?skip_ai_review=false&session=${encodeURIComponent(window.currentSessionId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(enrichedIR)
    });

    if (!exportResp.ok) {
      const detail = await exportResp.text().catch(() => "");
      throw new Error("Build failed: " + (detail || exportResp.status));
    }

    // Discard the ZIP response body (we just want the side effect of files being saved)
    await exportResp.blob();

    // Files are now in /out directory - refresh the outputs list
    await refreshOutputs();
    
    setBusy?.(false, "Build complete");
    addMsg("ai", "Build complete.", { text_only: true });
    
  } catch (e) {
    console.error(e);
    addMsg("ai", `Build error: ${e.message || String(e)}`, { text_only: true });
    setBusy?.(false, "Error");
  }
}

// --- YES button (continue build) ---
document.getElementById("confirm-build").addEventListener("click", async () => {
  document.getElementById("confirm-modal").style.display = "none";
  const ir = document.getElementById("confirm-build")._ir;
  if (!ir) return;
  setBusy(true, "Building (confirmed) …");
  try {
    await exportZip(ir, /*confirm*/ true);
  } catch (e) {
    console.error(e);
    alert(e.message || String(e));
    setBusy(false, "Error");
  }
});

// --- NO button ---
document.getElementById("cancel-build").addEventListener("click", () => {
  document.getElementById("confirm-modal").style.display = "none";
});

// Build
buildBtn.removeEventListener?.('click', handleBuildClick);
buildBtn.addEventListener('click', handleBuildClick);

// Initial load
refreshUploads();
refreshOutputs();
