"use strict";

// ===== State =====
const state = {
  sessionId: null,
  rendering: false,
  images: [],   // { file, preview, name }
  script: "",
  config: {},
};

// ===== API helpers =====
async function api(path, opts = {}) {
  const { body, ...rest } = opts;
  const headers = { ...(rest.headers || {}) };
  let finalBody = body;

  if (!(body instanceof FormData) && body != null) {
    headers["Content-Type"] = "application/json";
    finalBody = JSON.stringify(body);
  }

  const res = await fetch(path, {
    credentials: "same-origin",
    ...rest,
    headers,
    body: finalBody,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  if (rest.noJson) return res;
  return res.json();
}

// ===== Tabs =====
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initScriptEditor();
  initImageUpload();
  initSettings();
  initOutputs();
  initRender();
  loadConfig();
  loadOutputs();
  pingServer();
});

function initTabs() {
  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.dataset.tab;
      document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const panel = document.getElementById(`tab-${tabId}`);
      if (panel) panel.classList.add("active");
    });
  });
}

// ===== Script Editor =====
function initScriptEditor() {
  const editor = document.getElementById("scriptEditor");
  const sceneCount = document.getElementById("sceneCount");
  const charCount = document.getElementById("charCount");
  const clearBtn = document.getElementById("clearScriptBtn");
  const loadSampleBtn = document.getElementById("loadSampleBtn");

  function updateCounts() {
    const text = editor.value;
    const matches = (text.match(/\[.*?\]/g) || []).length;
    sceneCount.textContent = `${matches} scene`;
    charCount.textContent = `${text.length} ky tu`;
    state.script = text;
  }

  editor.addEventListener("input", updateCounts);
  updateCounts();

  clearBtn.addEventListener("click", () => {
    editor.value = "";
    updateCounts();
  });

  loadSampleBtn.addEventListener("click", async () => {
    try {
      const res = await api("/static/sample_script.txt", { noJson: true });
      editor.value = await res.text();
      updateCounts();
    } catch {
      // fallback inline sample
      editor.value = `[Scene_001.jpg] Welcome to an incredible discovery about the human brain.\n[Scene_002.jpg] Have you ever felt your phone vibrate, only to find nothing there?\n[Scene_003.jpg] This phenomenon is called Phantom Vibration Syndrome.\n[Scene_004.jpg] Scientists first studied this in 2013.\n[Scene_005.jpg] Up to 89 percent of people experience it.\n[Scene_006.jpg] Your brain is constantly on alert for notifications.\n[Scene_007.jpg] The anticipation creates false sensations.\n[Scene_008.jpg] This happens more often with heavy smartphone users.\n[Scene_009.jpg] It's completely normal and not a sign of dependency.\n[Scene_010.jpg] Simply knowing about it can reduce anxiety.\n[Scene_011.jpg] Thank you for watching this video.\n[Scene_012.jpg] If you enjoyed it, please subscribe for more content like this.`;
      updateCounts();
    }
  });

  document.getElementById("scriptFileUpload").addEventListener("change", e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      editor.value = ev.target.result;
      updateCounts();
    };
    reader.readAsText(file);
    e.target.value = "";
  });
}

// ===== Image Upload =====
function initImageUpload() {
  const grid = document.getElementById("imageGrid");
  const empty = document.getElementById("imageEmpty");
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("imageFilesUpload");
  const zipInput = document.getElementById("imageZipUpload");

  function addImageCard(file) {
    if (!file.type.startsWith("image/")) return;
    const id = Math.random().toString(36).slice(2);
    const preview = URL.createObjectURL(file);
    state.images.push({ id, file, preview, name: file.name });

    const card = document.createElement("div");
    card.className = "image-card";
    card.dataset.id = id;
    card.innerHTML = `
      <img src="${preview}" alt="${file.name}">
      <div class="image-card-info">${file.name}</div>
      <button class="image-card-remove" title="Xoa">&times;</button>
    `;
    card.querySelector(".image-card-remove").addEventListener("click", e => {
      e.stopPropagation();
      removeImage(id);
    });
    if (empty) empty.style.display = "none";
    grid.appendChild(card);
    updateDropZone();
  }

  function removeImage(id) {
    const idx = state.images.findIndex(img => img.id === id);
    if (idx >= 0) {
      URL.revokeObjectURL(state.images[idx].preview);
      state.images.splice(idx, 1);
    }
    const card = grid.querySelector(`[data-id="${id}"]`);
    if (card) card.remove();
    if (state.images.length === 0 && empty) {
      empty.style.display = "";
    }
    updateDropZone();
    updateRenderInfo();
  }

  function updateDropZone() {
    if (state.images.length > 0) {
      dropZone.style.display = "none";
    } else {
      dropZone.style.display = "";
    }
  }

  // File input
  fileInput.addEventListener("change", e => {
    Array.from(e.target.files).forEach(addImageCard);
    e.target.value = "";
  });

  // ZIP support (basic — just list files, prompt user to upload individually)
  zipInput.addEventListener("change", async e => {
    const file = e.target.files[0];
    if (!file) return;
    alert("Vui long tai anh truc tiep (chuc nang ZIP chi ho tro khi render phia server).");
    e.target.value = "";
  });

  // Drag and drop on whole content area
  const content = document.querySelector(".content");
  let dragCounter = 0;

  content.addEventListener("dragenter", e => {
    e.preventDefault();
    dragCounter++;
    dropZone.classList.add("drag-over");
  });
  content.addEventListener("dragleave", e => {
    e.preventDefault();
    dragCounter--;
    if (dragCounter === 0) dropZone.classList.remove("drag-over");
  });
  content.addEventListener("dragover", e => e.preventDefault());
  content.addEventListener("drop", e => {
    e.preventDefault();
    dragCounter = 0;
    dropZone.classList.remove("drag-over");
    Array.from(e.dataTransfer.files).forEach(f => {
      if (f.type.startsWith("image/")) addImageCard(f);
    });
  });
}


// ===== Settings =====
function initSettings() {
  // Pitch range
  const pitchRange = document.getElementById("cfg_pitch");
  const pitchVal = document.getElementById("pitchVal");
  pitchRange.addEventListener("input", () => {
    pitchVal.textContent = parseFloat(pitchRange.value).toFixed(1);
  });

  // Font size range
  const fontRange = document.getElementById("cfg_sub_fontsize");
  const fontVal = document.getElementById("fontsizeVal");
  fontRange.addEventListener("input", () => {
    fontVal.textContent = fontRange.value + "px";
  });

  // Preset cards
  document.querySelectorAll(".preset-card").forEach(card => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".preset-card").forEach(c => c.classList.remove("active"));
      card.classList.add("active");
    });
  });
}

async function loadConfig() {
  try {
    const cfg = await api("/api/config");
    state.config = cfg;

    // Fill form from config
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val;
    };
    const setCheck = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.checked = val;
    };

    const tts = cfg.tts || {};
    const ren = cfg.render || {};
    const sub = cfg.subtitle || {};
    const mus = cfg.music || {};
    const tim = cfg.timing || {};

    set("cfg_language", tts.language || "en");
    set("cfg_speed", tts.speed || "0.95");
    set("cfg_pitch", tts.pitch_shift || "-1");
    document.getElementById("pitchVal").textContent = parseFloat(tts.pitch_shift || "-1").toFixed(1);

    set("cfg_crf", ren.crf || "20");
    set("cfg_preset", ren.preset || "slow");
    set("cfg_fps", ren.fps || "24");

    setCheck("cfg_music_enabled", mus.enabled || false);
    setCheck("cfg_sub_enabled", sub.enabled !== false);
    setCheck("cfg_sub_burnin", sub.burn_in !== false);
    set("cfg_sub_position", sub.position || "bottom");
    set("cfg_sub_fontsize", sub.font_size || "48");
    document.getElementById("fontsizeVal").textContent = (sub.font_size || "48") + "px";

    set("cfg_min_scene", tim.min_scene_duration || "4.0");
    set("cfg_max_scene", tim.max_scene_duration || "15.0");
    set("cfg_wpm", tim.words_per_minute || "140");

    // Preset
    const preset = cfg.active_preset || "axen";
    document.querySelectorAll(".preset-card").forEach(c => {
      c.classList.toggle("active", c.dataset.preset === preset);
    });

  } catch (e) {
    console.warn("Could not load config:", e);
  }
}

// ===== Outputs =====
function initOutputs() {
  document.getElementById("refreshOutputsBtn").addEventListener("click", loadOutputs);
  document.getElementById("cleanAllBtn").addEventListener("click", async () => {
    if (!confirm("Xoa tat ca video output?")) return;
    try {
      await api("/api/cleanup", { method: "POST" });
      loadOutputs();
    } catch (e) {
      alert("Loi: " + e.message);
    }
  });
}

async function loadOutputs() {
  try {
    const data = await api("/api/outputs");
    const grid = document.getElementById("outputsGrid");
    const empty = document.getElementById("outputEmpty");
    grid.querySelectorAll(".output-card").forEach(c => c.remove());

    if (!data.files || data.files.length === 0) {
      if (empty) empty.style.display = "";
      return;
    }
    if (empty) empty.style.display = "none";

    for (const f of data.files) {
      const card = document.createElement("div");
      card.className = "output-card";

      const sizeMB = (f.size / 1024 / 1024).toFixed(1);
      const date = new Date(f.modified * 1000).toLocaleString("vi-VN");
      const thumbId = `thumb-${f.name.replace(/\W/g, "")}`;

      card.innerHTML = `
        <div class="output-thumb">
          <video id="${thumbId}" class="video-placeholder" preload="none" playsinline>
            <source src="/api/preview/${encodeURIComponent(f.name)}" type="video/mp4">
          </video>
        </div>
        <div class="output-info">
          <div class="output-name">${f.name}</div>
          <div class="output-meta">
            <span class="output-size">${sizeMB} MB</span>
            <div class="output-actions">
              <button class="btn btn-outline btn-sm download-btn" data-filename="${f.name}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Tai
              </button>
              <button class="btn btn-outline btn-sm play-btn" data-filename="${f.name}" data-thumb="${thumbId}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polygon points="5,3 19,12 5,21" fill="currentColor" stroke="none"/></svg>
                Xem
              </button>
            </div>
          </div>
          <div style="font-size:11px;color:var(--text-muted);margin-top:4px">${date}</div>
        </div>
      `;

      card.querySelector(".download-btn").addEventListener("click", () => {
        window.location.href = `/api/download/${encodeURIComponent(f.name)}`;
      });

      card.querySelector(".play-btn").addEventListener("click", () => {
        const thumb = document.getElementById(thumbId);
        if (thumb.paused) {
          thumb.play();
        } else {
          thumb.pause();
          thumb.currentTime = 0;
        }
      });

      grid.appendChild(card);
    }
  } catch (e) {
    console.warn("Could not load outputs:", e);
  }
}

// ===== Render =====
function initRender() {
  const renderBtn = document.getElementById("renderBtn");
  const progressModal = document.getElementById("progressModal");
  const closeModalBtn = document.getElementById("closeModalBtn");
  const openVideoBtn = document.getElementById("openVideoBtn");

  renderBtn.addEventListener("click", startRender);

  closeModalBtn.addEventListener("click", () => {
    progressModal.classList.remove("show");
  });

  openVideoBtn.addEventListener("click", () => {
    if (state.lastOutputFile) {
      window.open(`/api/preview/${encodeURIComponent(state.lastOutputFile)}`, "_blank");
    }
    progressModal.classList.remove("show");
  });
}

function updateRenderInfo() {
  const info = document.getElementById("renderBarInfo");
  const btn = document.getElementById("renderBtn");
  const nImages = state.images.length;
  const nScenes = (state.script.match(/\[.*?\]/g) || []).length;

  if (nImages > 0 && nScenes > 0) {
    info.innerHTML = `<strong>${nScenes} scene</strong> &middot; <strong>${nImages} anh</strong> &middot; San sang`;
    btn.disabled = false;
  } else if (nScenes > 0) {
    info.textContent = `${nScenes} scene duoc dinh nghia (chua co anh)`;
    btn.disabled = true;
  } else if (nImages > 0) {
    info.textContent = `${nImages} anh duoc tai (chua co kich ban)`;
    btn.disabled = true;
  } else {
    info.textContent = "Chua co kich ban hoac anh nao";
    btn.disabled = true;
  }
}

async function startRender() {
  const script = document.getElementById("scriptEditor").value.trim();
  if (!script) {
    alert("Vui long nhap kich ban.");
    document.querySelector('[data-tab="script"]').click();
    document.getElementById("scriptEditor").focus();
    return;
  }
  if (state.images.length === 0) {
    alert("Vui long tai anh len.");
    document.querySelector('[data-tab="images"]').click();
    return;
  }

  state.rendering = true;
  state.lastOutputFile = null;
  setStatus("busy", "Dang render...");

  const modal = document.getElementById("progressModal");
  const progressBar = document.getElementById("progressBar");
  const progressDetail = document.getElementById("progressDetail");
  const progressStep = document.getElementById("progressStep");
  const progressLogs = document.getElementById("progressLogs");
  const actions = document.getElementById("progressActions");

  modal.classList.add("show");
  progressBar.style.width = "0%";
  progressDetail.textContent = "Dang gui yeu cau...";
  progressLogs.innerHTML = "";
  progressLogs.classList.remove("show");
  actions.style.display = "none";
  document.getElementById("renderBtn").disabled = true;

  // Build form data
  const formData = new FormData();
  formData.append("script_text", script);

  // Add images
  state.images.forEach((img, idx) => {
    formData.append(`image_${idx}`, img.file);
  });

  // Settings
  const getVal = id => {
    const el = document.getElementById(id);
    return el ? el.value : "";
  };
  const getCheck = id => {
    const el = document.getElementById(id);
    return el ? el.checked : false;
  };

  const activePreset = document.querySelector(".preset-card.active");
  formData.append("active_preset", activePreset ? activePreset.dataset.preset : "axen");
  formData.append("cfg_crf", getVal("cfg_crf"));
  formData.append("cfg_preset", getVal("cfg_preset"));
  formData.append("cfg_fps", getVal("cfg_fps"));
  formData.append("cfg_language", getVal("cfg_language"));
  formData.append("cfg_speed", getVal("cfg_speed"));
  formData.append("cfg_pitch", getVal("cfg_pitch"));
  formData.append("cfg_sub_position", getVal("cfg_sub_position"));
  formData.append("cfg_sub_fontsize", getVal("cfg_sub_fontsize"));
  formData.append("cfg_sub_enabled", getCheck("cfg_sub_enabled"));
  formData.append("cfg_sub_burnin", getCheck("cfg_sub_burnin"));
  formData.append("cfg_music_enabled", getCheck("cfg_music_enabled"));
  formData.append("cfg_min_scene", getVal("cfg_min_scene"));
  formData.append("cfg_max_scene", getVal("cfg_max_scene"));
  formData.append("cfg_wpm", getVal("cfg_wpm"));

  try {
    const result = await api("/api/render", {
      method: "POST",
      body: formData,
    });
    state.sessionId = result.session_id;

    // Save config
    const cfgData = buildConfigPayload();
    api("/api/save-config", { method: "POST", body: cfgData }).catch(() => {});

    // Start SSE progress
    connectProgress(result.session_id, {
      onProgress: (pct, detail) => {
        progressBar.style.width = pct + "%";
        progressDetail.textContent = detail || "Dang xu ly...";
        updateStepLabel(pct, progressStep);
      },
      onLog: line => {
        progressLogs.classList.add("show");
        const div = document.createElement("div");
        div.className = "log-line" + (line.includes("LOI") || line.includes("ERROR") ? " error" : "");
        div.textContent = line;
        progressLogs.appendChild(div);
        progressLogs.scrollTop = progressLogs.scrollHeight;
      },
      onComplete: filename => {
        state.lastOutputFile = filename;
        progressBar.style.width = "100%";
        progressDetail.textContent = "Render hoan tat!";
        progressStep.textContent = "Hoan tat 100%";
        state.rendering = false;
        setStatus("ready", "Hoan thanh!");
        actions.style.display = "flex";
        loadOutputs();
        updateRenderInfo();
      },
      onError: msg => {
        progressDetail.textContent = "Loi: " + msg;
        progressDetail.style.color = "var(--danger)";
        state.rendering = false;
        setStatus("error", "Loi");
        document.getElementById("renderBtn").disabled = false;
      },
    });

  } catch (e) {
    modal.classList.remove("show");
    alert("Loi bat dau render: " + e.message);
    state.rendering = false;
    setStatus("ready", "San sang");
    document.getElementById("renderBtn").disabled = false;
  }
}

function buildConfigPayload() {
  const getVal = id => document.getElementById(id)?.value || "";
  const getCheck = id => document.getElementById(id)?.checked ?? false;

  return {
    active_preset: document.querySelector(".preset-card.active")?.dataset.preset || "axen",
    render: {
      crf: parseInt(getVal("cfg_crf")),
      preset: getVal("cfg_preset"),
      fps: parseInt(getVal("cfg_fps")),
    },
    tts: {
      language: getVal("cfg_language"),
      speed: parseFloat(getVal("cfg_speed")),
      pitch_shift: parseFloat(getVal("cfg_pitch")),
    },
    subtitle: {
      position: getVal("cfg_sub_position"),
      font_size: parseInt(getVal("cfg_sub_fontsize")),
      enabled: getCheck("cfg_sub_enabled"),
      burn_in: getCheck("cfg_sub_burnin"),
    },
    music: {
      enabled: getCheck("cfg_music_enabled"),
    },
    timing: {
      min_scene_duration: parseFloat(getVal("cfg_min_scene")),
      max_scene_duration: parseFloat(getVal("cfg_max_scene")),
      words_per_minute: parseInt(getVal("cfg_wpm")),
    },
  };
}

function updateStepLabel(pct, el) {
  const steps = ["Parse", "Anh", "Duration", "TTS", "Subtitle", "Music", "Render"];
  const idx = Math.min(Math.floor(pct / (100 / steps.length)), steps.length - 1);
  el.textContent = `Buoc ${idx + 1}/${steps.length} — ${steps[idx]}`;
}

function connectProgress(sessionId, { onProgress, onLog, onComplete, onError }) {
  let finished = false;
  const es = new EventSource(`/api/progress/${sessionId}`);

  es.onmessage = e => {
    if (finished) return;
    try {
      const data = JSON.parse(e.data);

      if (data.type === "progress") {
        onProgress(data.percent, data.detail);
        if (data.detail) onLog(data.detail);
      } else if (data.type === "complete") {
        finished = true;
        es.close();
        onComplete(data.filename || null);
      } else if (data.type === "error") {
        finished = true;
        es.close();
        onError(data.message);
      }
    } catch (err) {
      console.warn("SSE parse error:", err);
    }
  };

  es.onerror = () => {
    if (!finished) {
      finished = true;
      es.close();
      onError("Mat ket noi voi server.");
    }
  };
}

function setStatus(type, text) {
  const dot = document.getElementById("statusDot");
  const txt = document.getElementById("statusText");
  dot.className = "status-dot" + (type === "busy" ? " busy" : type === "error" ? " error" : "");
  txt.textContent = text;
}

async function pingServer() {
  try {
    await api("/api/ping");
    setStatus("ready", "San sang");
  } catch {
    setStatus("error", "Server chua bat");
  }
}

// Re-export for use in render flow
window.updateRenderInfo = updateRenderInfo;
