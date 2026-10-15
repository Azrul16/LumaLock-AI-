"use strict";
const $ = id => document.getElementById(id);
const icons = {
  save: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M5 16v4h14v-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  edit: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 5 5 5M4 20l5-1L20 8a2 2 0 0 0-5-5L4 14v6Z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
};
let snapshot = null, selectedChat = localStorage.getItem("lumalock-chat"), lastRender = "", polling = false, uploading = false, selecting = false, submitting = false, initialized = false, stopped = false, refreshSequence = 0;
const imageUrl = name => `/api/images/${encodeURIComponent(name.split("/").pop())}`;
const busy = () => uploading || selecting || submitting || ["running", "stopping"].includes(snapshot?.job?.status);
const node = (tag, className, text) => { const item = document.createElement(tag); if (className) item.className = className; if (text !== undefined) item.textContent = text; return item; };
function duration(seconds) {
  seconds = Math.max(0, Math.round(seconds || 0));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return minutes < 60 ? `${minutes}m ${seconds % 60}s` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}
function progressMetrics(className = "progress-metrics") {
  const metrics = node("div", className);
  metrics.append(node("span", "progress-percent"), node("span", "progress-eta"), node("span", "progress-elapsed"), node("span", "progress-budget"));
  return metrics;
}
function updateMetrics(container, job) {
  if (!container || !job) return;
  const percent = Number.isFinite(job.progress) && job.progress >= 0 ? Math.min(100, Math.floor(job.progress)) : null;
  container.querySelector(".progress-percent").textContent = percent === null ? "Measuring progress…" : `This stage: ${percent}%`;
  container.querySelector(".progress-eta").textContent = job.status === "stopping" ? "Stopping safely…" : Number.isFinite(job.eta_seconds) ? `About ${duration(job.eta_seconds)} left in this stage` : "Time remaining: estimating…";
  container.querySelector(".progress-elapsed").textContent = Number.isFinite(job.elapsed_seconds) ? `Elapsed ${duration(job.elapsed_seconds)}` : "Restart server to enable timing";
  const budget = container.querySelector(".progress-budget"); budget.hidden = !Number.isFinite(job.limit_seconds);
  if (!budget.hidden) budget.textContent = `Execution limit ${duration(job.limit_seconds)} · ${duration(Math.max(0, job.limit_seconds - (job.elapsed_seconds || 0)))} remaining`;
}
function notice(message = "") { $("notice").textContent = message; $("notice").hidden = !message; }
function toast(message) { $("toast").textContent = message; $("toast").hidden = false; setTimeout(() => { $("toast").hidden = true; }, 3500); }
async function api(path, options = {}) {
  const headers = { "X-LumaLock": "1", ...(options.headers || {}) };
  if (options.body && typeof options.body === "string") headers["Content-Type"] = "application/json";
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  const data = await response.json().catch(() => ({ error: "The local server could not complete this request." }));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}
const post = (path, data = {}) => api(path, { method: "POST", body: JSON.stringify(data) });
const offlineNotice = "The local server is unavailable. Start Launch LumaLock AI.cmd again, then refresh this tab.";
async function stopOperation(button) {
  if (button) button.disabled = true;
  try { await post("/api/cancel"); await refresh(true); }
  catch (error) { notice(error.message); if (snapshot) renderState(); }
}
async function deleteChat(identifier, title) {
  if (busy()) return;
  if (!confirm(`Delete "${title}"? This removes the conversation and its unshared chat images. Your source photos and other chats are kept.`)) return;
  selecting = true; renderState();
  try {
    const result = await api(`/api/chats/${encodeURIComponent(identifier)}`, { method: "DELETE" });
    if (selectedChat === identifier) { selectedChat = result.next_chat_id; $("prompt").value = ""; $("edit-mode").value = "Natural"; $("preset").value = ""; $("preserve").checked = true; }
    localStorage.setItem("lumalock-chat", selectedChat); lastRender = ""; notice(); toast("Chat deleted.");
  } catch (error) { notice(error.message); }
  finally { selecting = false; await refresh(true); }
}
function photo(name, className, description) {
  const img = node("img", className); img.src = imageUrl(name) + `?preview=${className === "result-image" ? 1024 : 320}`; img.alt = description; img.loading = "lazy"; img.decoding = "async";
  img.addEventListener("click", () => { $("full-image").src = imageUrl(name); $("image-dialog").showModal(); });
  img.addEventListener("error", () => { img.alt = "Image unavailable. Attach your photo again."; });
  return img;
}
async function chooseImage(name) {
  if (busy()) return false;
  selecting = true; renderState();
  try { await post(`/api/chats/${selectedChat}/select`, { image: name }); notice(); $("prompt").focus(); toast("Image selected. Describe your next change."); return true; }
  catch (error) { notice(error.message); return false; }
  finally { selecting = false; await refresh(true); }
}
function renderConversation(chat) {
  const signature = `${busy()}:${JSON.stringify(chat)}`;
  if (signature === lastRender) return;
  const firstRender = !lastRender;
  lastRender = signature;
  const thread = $("thread"), nearBottom = firstRender || thread.scrollHeight - thread.scrollTop - thread.clientHeight < 140;
  const messages = $("messages"); messages.replaceChildren();
  if (!chat.turns.length) {
    const welcome = node("div", "welcome");
    welcome.append(node("div", "welcome-mark", "L"), node("h1", "", "What would you like to change?"), node("p", "", "Add a photo. Describe your edit. Make it yours."));
    if (chat.selected_image) welcome.append(photo(chat.selected_image, "welcome-photo", "Your attached photo"));
    else {
      const suggestions = node("div", "suggestions");
      for (const [label, prompt] of [["Natural light", "Improve the lighting naturally and balance the colors. Preserve every person and the scene."], ["Cinematic color", "Give this photo subtle cinematic colors while keeping it realistic. Preserve people and composition."], ["A cleaner background", "Simplify the background while preserving the person, face and clothing exactly."]]) {
        const button = node("button", "", label); button.type = "button"; button.addEventListener("click", () => { $("prompt").value = prompt; $("prompt").focus(); }); suggestions.append(button);
      }
      welcome.append(suggestions);
    }
    messages.append(welcome);
  }
  for (const turn of chat.turns) {
    const wrapper = node("article", "turn"), user = node("div", "user-message");
    user.append(node("p", "", turn.prompt), photo(turn.source, "", "Photo used for this request"));
    const author = node("div", "assistant-label"); author.append(node("span", "assistant-mark", "L"), node("span", "", "LumaLock"));
    wrapper.append(user, author);
    if (turn.status === "complete" && turn.result) {
      wrapper.append(photo(turn.result, "result-image", "Edited image"));
      const actions = node("div", "image-actions"), save = node("a"), edit = node("button");
      save.href = imageUrl(turn.result) + "?download=1"; save.download = "LumaLock-edit-4K.png"; save.innerHTML = icons.save; save.append(document.createTextNode("Save 4K image"));
      edit.type = "button"; edit.innerHTML = icons.edit; edit.append(document.createTextNode("Edit image")); edit.disabled = busy(); edit.addEventListener("click", () => chooseImage(turn.result));
      actions.append(save, edit, node("span", "image-caption", `${turn.method === "photo_correction" ? "Original-resolution photo correction" : turn.method === "flux" ? "FLUX edit - " + turn.quality : "Legacy result"}. 4K save enlarges smaller images.`)); wrapper.append(actions);
      const compare = node("button", "", "Before / after"); compare.type = "button"; compare.addEventListener("click", () => { $("compare-before").src = imageUrl(turn.root) + "?preview=1024"; $("compare-after").src = imageUrl(turn.result) + "?preview=1024"; $("compare-dialog").showModal(); }); actions.append(compare);
    } else if (turn.status === "failed") {
      const error = node("div", "error-message"); error.append(node("p", "", turn.error || "This edit could not finish."));
      const retry = node("button", "", "Retry edit"); retry.type = "button"; retry.disabled = busy(); retry.addEventListener("click", async () => { try { if (!await chooseImage(turn.source)) return; $("prompt").value = turn.prompt; $("preserve").checked = turn.preserve_people; $("edit-mode").value = turn.mode || "Natural"; $("preset").value = turn.preset || ""; await post(`/api/chats/${selectedChat}/protection`, {shapes: turn.protection || []}); await send(); } catch (error) { notice(error.message); } });
      error.append(retry); wrapper.append(error);
    } else {
      const working = node("div", "generation-placeholder");
      working.dataset.turn = turn.id;
      working.setAttribute("aria-label", "Image generation in progress");
      working.setAttribute("aria-busy", "true");
      const canvas = node("div", "skeleton-image"); canvas.setAttribute("aria-hidden", "true");
      canvas.append(node("span", "skeleton-orb"), node("span", "skeleton-landscape"));
      const heading = node("div", "working-message"); heading.append(node("span", "spinner"), node("span", "generation-stage", "Preparing your image…"));
      const stop = node("button", "stop-edit", "Stop"); stop.type = "button"; stop.setAttribute("aria-label", "Stop edit"); stop.addEventListener("click", () => stopOperation(stop)); heading.append(stop);
      const bar = node("progress", "generation-progress"); bar.max = 100; bar.setAttribute("aria-label", "Current stage completion");
      working.append(canvas, heading, bar, progressMetrics(), node("p", "progress-note", "Current-stage progress. Execution limit: 30 minutes, including loading and final processing."));
      wrapper.append(working);
    }
    messages.append(wrapper);
  }
  if (nearBottom || !chat.turns.length) {
    const scrollLatest = () => { if (lastRender === signature) thread.scrollTop = thread.scrollHeight; };
    requestAnimationFrame(scrollLatest);
    for (const image of messages.querySelectorAll("img")) image.addEventListener("load", scrollLatest, { once: true });
  }
}
function renderState() {
  const chat = snapshot.chat;
  const active = busy();
  $("chat-title").textContent = chat.title;
  const list = $("chat-list"); list.replaceChildren();
  for (const item of snapshot.chats) {
    const row = node("div", `chat-row${item.id === selectedChat ? " selected" : ""}`);
    const button = node("button", "chat-open", item.title); button.type = "button";
    button.disabled = active; button.addEventListener("click", async () => { selectedChat = item.id; localStorage.setItem("lumalock-chat", selectedChat); lastRender = ""; notice(); await refresh(true); if (innerWidth <= 650) $("sidebar").classList.remove("mobile-open"); });
    const remove = node("button", "delete-chat"); remove.type = "button"; remove.disabled = active; remove.title = "Delete chat"; remove.setAttribute("aria-label", `Delete chat: ${item.title}`);
    remove.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/></svg>';
    remove.addEventListener("click", () => deleteChat(item.id, item.title)); row.append(button, remove); list.append(row);
  }
  renderConversation(chat);
  $("protect-area").disabled = active || !chat.selected_root;
  $("edit-mode").disabled = $("preset").disabled = active;
  $("protection-count").textContent = chat.protection?.length ? `(${chat.protection.length})` : "";
  $("attachment").hidden = !chat.selected_image;
  if (chat.selected_image) {
    const url = imageUrl(chat.selected_image) + "?preview=320"; if ($("attachment-image").getAttribute("src") !== url) $("attachment-image").src = url;
    const result = chat.turns.some(turn => turn.result === chat.selected_image);
    $("attachment-title").textContent = result ? "Editing selected result" : "Photo attached";
    $("attachment-description").textContent = result ? "Your next prompt starts from this image" : "Ready for your prompt";
  }
  for (const id of ["send", "attach", "remove-attachment", "new-chat", "quality", "preserve", "device", "download-models", "verify-models"]) $(id).disabled = active;
  const inlineEdit = active && snapshot.job?.kind === "edit" && Array.from(document.querySelectorAll(".generation-placeholder")).some(item => item.dataset.turn === snapshot.job.turn_id);
  const modelJob = snapshot.job && snapshot.job.kind !== "edit";
  const modelActive = modelJob && ["running", "stopping"].includes(snapshot.job.status);
  $("job").hidden = !active || inlineEdit || (modelActive && $("settings-dialog").open);
  if (uploading || selecting || submitting) {
    $("job-text").textContent = uploading ? "Opening your photo…" : selecting ? "Selecting image…" : "Sending your request…"; $("job-progress").removeAttribute("value"); $("stop-job").disabled = true;
  } else if (snapshot.job && active) {
    $("job-text").textContent = snapshot.job.message;
    if (snapshot.job.progress < 0) $("job-progress").removeAttribute("value"); else $("job-progress").value = snapshot.job.progress;
    $("stop-job").disabled = snapshot.job.status === "stopping";
  }
  $("job-metrics").hidden = !active || uploading || selecting || submitting;
  if (snapshot.job) {
    updateMetrics($("job-metrics"), snapshot.job);
    updateMetrics($("model-metrics"), snapshot.job);
    for (const placeholder of document.querySelectorAll(".generation-placeholder")) {
      if (placeholder.dataset.turn !== snapshot.job.turn_id) continue;
      placeholder.querySelector(".generation-stage").textContent = snapshot.job.message;
      placeholder.classList.toggle("stopping", snapshot.job.status === "stopping");
      placeholder.querySelector(".stop-edit").disabled = snapshot.job.status === "stopping";
      const bar = placeholder.querySelector("progress");
      if (snapshot.job.progress >= 0) bar.value = snapshot.job.progress; else bar.removeAttribute("value");
      updateMetrics(placeholder.querySelector(".progress-metrics"), snapshot.job);
    }
  }
  $("model-job").hidden = !modelJob;
  $("model-job-text").textContent = modelJob ? snapshot.job.message : "";
  $("model-progress").hidden = !modelActive;
  $("model-metrics").hidden = !modelActive;
  if (modelJob && snapshot.job.progress >= 0) $("model-progress").value = snapshot.job.progress; else $("model-progress").removeAttribute("value");
  $("pause-models").hidden = !modelActive;
  $("pause-models").disabled = snapshot.job?.status === "stopping";
  $("download-models").textContent = modelJob && snapshot.job.status === "cancelled" ? "Resume download / repair" : "Download / repair models";
  const models = $("model-list"); models.replaceChildren();
  for (const model of snapshot.models) {
    const row = node("div", "model-row"), details = node("div");
    details.append(node("strong", "", model.name), node("small", "", `${model.gib} GiB · includes text conditioning and VAE`));
    for (const component of model.components || []) details.append(node("small", "", `${component.name}: ${component.present ? "file present" : "missing"}`));
    row.append(details, node("span", `model-status${model.complete ? " ready" : ""}`, model.complete ? (model.available ? "Ready" : "Runtime missing") : "Setup needed")); models.append(row);
  }
  $("hardware").textContent = `${snapshot.hardware.gpu} · ${snapshot.hardware.vram_gb} GiB VRAM · ${snapshot.hardware.ram_gb} GiB RAM`;
  $("memory-guidance").hidden = snapshot.hardware.ram_gb > 16;
  const hasGPU = snapshot.hardware.vram_gb > 0;
  $("device").querySelector('[value="auto"]').textContent = hasGPU ? "CPU + GPU (automatic)" : "Automatic (CPU)";
  $("device").querySelector('[value="cuda"]').disabled = !hasGPU;
  $("device-guidance").textContent = hasGPU ? "CPU handles image preparation and host work; CUDA handles image computation. Supported transfers can overlap through one asynchronous stream. Memory recovery may use CPU fallback." : "Image processing runs on the CPU because no NVIDIA GPU was detected.";
  if (!initialized) {
    $("quality").value = snapshot.settings.quality; $("device").value = snapshot.settings.device; $("license").checked = snapshot.settings.license_accepted;
    for (const name of snapshot.presets || []) { const option = node("option", "", name); option.value = name; $("preset").append(option); }
    initialized = true;
    if (snapshot.models.some(model => !model.complete)) $("settings-dialog").showModal();
  }
  if (!active && !snapshot.models.every(model => model.complete)) $("download-models").disabled = !$("license").checked;
}
async function refresh(force = false) {
  if (stopped || (polling && !force)) return;
  polling = true;
  const sequence = ++refreshSequence;
  try {
    const query = selectedChat ? `?chat=${encodeURIComponent(selectedChat)}` : "";
    let data;
    try { data = await api("/api/state" + query); }
    catch (error) { if (selectedChat && error.message.includes("not found")) { selectedChat = null; data = await api("/api/state"); } else throw error; }
    if (sequence !== refreshSequence) return;
    snapshot = data; selectedChat = data.chat.id; localStorage.setItem("lumalock-chat", selectedChat);
    if ($("notice").textContent === offlineNotice) notice();
    $("connection").classList.remove("offline"); $("connection").replaceChildren(node("i"), document.createTextNode("Local workspace"));
    renderState();
  } catch (error) {
    if (sequence !== refreshSequence) return;
    $("connection").classList.add("offline"); $("connection").replaceChildren(node("i"), document.createTextNode("Server disconnected"));
    $("send").disabled = true; notice(offlineNotice);
  } finally { if (sequence === refreshSequence) polling = false; }
}
async function send() {
  if (busy()) return;
  const prompt = $("prompt").value.trim();
  if (!prompt) return notice("Describe the change you want to make.");
  if (!snapshot?.chat?.selected_image) return notice("Attach a photo first using + Photo, or drop it into the chat.");
  if (snapshot.models.some(model => !model.complete)) { $("settings-dialog").showModal(); return notice("Complete model setup, then send your prompt again."); }
  submitting = true; renderState();
  try {
    snapshot.job = await post(`/api/chats/${selectedChat}/edit`, { prompt, preserve: $("preserve").checked, quality: $("quality").value, device: $("device").value, mode: $("edit-mode").value, preset: $("preset").value || null });
    if ($("prompt").value.trim() === prompt) $("prompt").value = ""; notice(); lastRender = "";
  } catch (error) { notice(error.message); }
  finally { submitting = false; await refresh(true); $("thread").scrollTop = $("thread").scrollHeight; }
}
async function upload(file) {
  if (!file || busy()) return;
  if (file.size > 64 * 1024 * 1024) return notice("This photo exceeds 64 MiB. Choose a smaller file.");
  uploading = true; renderState(); notice("Opening your photo…");
  try {
    await api(`/api/chats/${selectedChat}/upload`, { method: "POST", body: file, headers: { "Content-Type": file.type || "application/octet-stream", "X-Filename": encodeURIComponent(file.name) } });
    notice(); lastRender = "";
  } catch (error) { notice(error.message); }
  finally { uploading = false; $("photo-input").value = ""; await refresh(true); $("prompt").focus(); }
}
$("composer").addEventListener("submit", event => { event.preventDefault(); send(); });
$("preset").addEventListener("change", () => { if (!$("prompt").value.trim() && $("preset").value) $("prompt").value = `Apply the ${$("preset").value} photographic look.`; });
let protectionDraft = [], protectionActive = null, protectionImage = null;
function drawProtection() {
  const canvas = $("protection-canvas"), ctx = canvas.getContext("2d");
  if (!protectionImage) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.drawImage(protectionImage, 0, 0, canvas.width, canvas.height);
  const overlay = document.createElement("canvas"); overlay.width = canvas.width; overlay.height = canvas.height;
  const paint = overlay.getContext("2d"); paint.fillStyle = paint.strokeStyle = "#76e5b1"; paint.lineCap = paint.lineJoin = "round";
  for (const shape of [...protectionDraft, ...(protectionActive ? [protectionActive] : [])]) {
    const points = shape.points.map(([x, y]) => [x * canvas.width, y * canvas.height]);
    const radius = shape.radius * Math.min(canvas.width, canvas.height);
    paint.globalCompositeOperation = shape.tool === "erase" ? "destination-out" : "source-over";
    paint.beginPath();
    if (["brush", "erase"].includes(shape.tool)) {
      paint.lineWidth = radius * 2;
      if (points.length === 1) { paint.arc(...points[0], radius, 0, Math.PI * 2); paint.fill(); }
      else { paint.moveTo(...points[0]); for (const point of points.slice(1)) paint.lineTo(...point); paint.stroke(); }
    } else if (points.length === 2) {
      const [a, b] = points, left = Math.min(a[0], b[0]), top = Math.min(a[1], b[1]), width = Math.abs(b[0] - a[0]), height = Math.abs(b[1] - a[1]);
      if (shape.tool === "rectangle") paint.rect(left, top, width, height);
      else paint.ellipse(left + width / 2, top + height / 2, Math.max(1, width / 2), Math.max(1, height / 2), 0, 0, 2 * Math.PI);
      paint.fill();
    }
  }
  ctx.globalAlpha = 0.42; ctx.drawImage(overlay, 0, 0); ctx.globalAlpha = 1;
}
function protectionPoint(event) {
  const box = $("protection-canvas").getBoundingClientRect();
  return [Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)), Math.max(0, Math.min(1, (event.clientY - box.top) / box.height))];
}
$("protect-area").addEventListener("click", () => {
  if (busy() || !snapshot.chat.selected_root) return;
  protectionDraft = structuredClone(snapshot.chat.protection || []); protectionActive = null;
  $("protection-status").textContent = "Loading photo…"; $("apply-protection").disabled = true;
  const image = new Image(); protectionImage = null;
  image.onload = () => { protectionImage = image; const canvas = $("protection-canvas"); canvas.width = image.width; canvas.height = image.height; drawProtection(); $("protection-status").textContent = "Green areas keep their original pixels."; $("apply-protection").disabled = false; };
  image.onerror = () => { $("protection-status").textContent = "Photo unavailable. Close this dialog and attach it again."; };
  image.src = imageUrl(snapshot.chat.selected_root) + "?preview=1024"; $("protection-dialog").showModal();
});
$("protection-canvas").addEventListener("pointerdown", event => {
  if (!protectionImage) return;
  if (protectionDraft.length >= 256) { $("protection-status").textContent = "Protection limit reached. Undo or Clear before adding more strokes."; return; }
  event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId);
  const point = protectionPoint(event), tool = $("protection-tool").value;
  protectionActive = { tool, points: [point], radius: Number($("protection-size").value) / 100 };
  if (["ellipse", "rectangle"].includes(tool)) protectionActive.points.push(point);
  drawProtection();
});
$("protection-canvas").addEventListener("pointermove", event => {
  if (!protectionActive) return;
  const point = protectionPoint(event);
  if (["ellipse", "rectangle"].includes(protectionActive.tool)) protectionActive.points[1] = point;
  else if (protectionActive.points.length < 2048) protectionActive.points.push(point);
  drawProtection();
});
$("protection-canvas").addEventListener("pointerup", () => { if (protectionActive) protectionDraft.push(protectionActive); protectionActive = null; drawProtection(); });
$("protection-canvas").addEventListener("pointercancel", () => { protectionActive = null; drawProtection(); });
$("undo-protection").addEventListener("click", () => { protectionDraft.pop(); drawProtection(); });
$("clear-protection").addEventListener("click", () => { protectionDraft = []; protectionActive = null; drawProtection(); });
$("close-protection").addEventListener("click", () => $("protection-dialog").close());
$("apply-protection").addEventListener("click", async () => {
  if (busy()) return;
  selecting = true; $("apply-protection").disabled = true;
  try { await post(`/api/chats/${selectedChat}/protection`, { shapes: protectionDraft }); $("protection-dialog").close(); if (protectionDraft.length) $("preserve").checked = true; notice(); }
  catch (error) { $("protection-status").textContent = error.message; }
  finally { selecting = false; $("apply-protection").disabled = false; await refresh(true); }
});
$("prompt").addEventListener("keydown", event => { if (event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); send(); } });
$("attach").addEventListener("click", () => $("photo-input").click());
$("photo-input").addEventListener("change", event => upload(event.target.files[0]));
$("remove-attachment").addEventListener("click", async () => { try { await post(`/api/chats/${selectedChat}/select`, { image: null }); lastRender = ""; await refresh(true); } catch (error) { notice(error.message); } });
$("new-chat").addEventListener("click", async () => { try { const chat = await post("/api/chats"); selectedChat = chat.id; $("prompt").value = ""; $("edit-mode").value = "Natural"; $("preset").value = ""; $("preserve").checked = true; notice(); lastRender = ""; await refresh(true); $("prompt").focus(); } catch (error) { notice(error.message); } });
for (const id of ["open-settings", "settings-shortcut"]) $(id).addEventListener("click", () => { $("settings-dialog").showModal(); if (snapshot) renderState(); });
$("close-settings").addEventListener("click", () => $("settings-dialog").close());
$("settings-dialog").addEventListener("close", () => { if (snapshot) renderState(); });
$("close-image").addEventListener("click", () => $("image-dialog").close());
$("close-compare").addEventListener("click", () => $("compare-dialog").close());
$("compare-dialog").addEventListener("close", () => { $("compare-before").removeAttribute("src"); $("compare-after").removeAttribute("src"); });
$("toggle-sidebar").addEventListener("click", () => $("sidebar").classList.toggle(innerWidth <= 650 ? "mobile-open" : "collapsed"));
$("license").addEventListener("change", () => { if (!busy()) $("download-models").disabled = !$("license").checked; });
for (const [id, verify] of [["download-models", false], ["verify-models", true]]) $(id).addEventListener("click", async () => {
  try { await post("/api/models", { keys: ["flux"], accept_license: $("license").checked, verify }); notice(); await refresh(true); }
  catch (error) { $("model-job").hidden = false; $("model-job-text").textContent = error.message; }
});
$("pause-models").addEventListener("click", event => stopOperation(event.currentTarget));
$("stop-job").addEventListener("click", event => stopOperation(event.currentTarget));
$("quit-server").addEventListener("click", async () => {
  if (!confirm("Stop LumaLock's local server? Any running operation will be cancelled safely.")) return;
  try { await post("/api/stop"); stopped = true; $("settings-dialog").close(); notice("LumaLock is stopping. Start Launch LumaLock AI.cmd to reopen your workspace."); $("send").disabled = true; }
  catch (error) { notice(error.message); }
});
let dragDepth = 0;
document.addEventListener("dragenter", event => { if (event.dataTransfer?.types.includes("Files")) { event.preventDefault(); dragDepth++; $("drop-overlay").hidden = false; } });
document.addEventListener("dragover", event => { if (event.dataTransfer?.types.includes("Files")) event.preventDefault(); });
document.addEventListener("dragleave", event => { event.preventDefault(); if (--dragDepth <= 0) { dragDepth = 0; $("drop-overlay").hidden = true; } });
document.addEventListener("drop", event => { event.preventDefault(); dragDepth = 0; $("drop-overlay").hidden = true; upload(event.dataTransfer?.files[0]); });
document.addEventListener("paste", event => { const file = Array.from(event.clipboardData?.items || []).find(item => item.kind === "file" && item.type.startsWith("image/")); if (file) { event.preventDefault(); upload(file.getAsFile()); } });
document.addEventListener("keydown", event => { if (event.ctrlKey && event.key.toLowerCase() === "o") { event.preventDefault(); if (!busy()) $("photo-input").click(); } });
const jobMetrics = progressMetrics(); jobMetrics.id = "job-metrics"; jobMetrics.hidden = true; $("job").append(jobMetrics);
const modelMetrics = progressMetrics(); modelMetrics.id = "model-metrics"; modelMetrics.hidden = true; $("model-job").append(modelMetrics);
const memoryGuidance = node("p", "resource-note", "This model bundle is larger than system RAM. Preview quality reduces image processing work; Windows may still page model weights to disk. Tiled image encoding/decoding is enabled on low-memory systems."); memoryGuidance.id = "memory-guidance"; memoryGuidance.hidden = true; $("hardware").after(memoryGuidance);
const deviceGuidance = node("p", "resource-note"); deviceGuidance.id = "device-guidance"; document.querySelector(".device-setting").after(deviceGuidance);
const resourcePanel = node("details", "resource-monitor"); resourcePanel.id = "resource-monitor";
const resourceSummary = node("summary"); resourceSummary.setAttribute("aria-label", "Live system resource usage");
for (const [name, label] of [["cpu", "CPU"], ["ram", "RAM"], ["gpu", "GPU"]]) {
  const chip = node("span", "resource-chip"); chip.append(node("small", "", label), node("b", "", "--")); chip.id = `resource-${name}`; resourceSummary.append(chip);
}
const resourceDetails = node("div", "resource-details"); resourceDetails.append(node("strong", "", "System resources"), node("p", "resource-description", "Live usage across your computer, not a benchmark score."));
const resourceRows = {};
for (const [key, label] of [["cpu", "Processor"], ["ram", "System memory"], ["gpu", "GPU utilization"], ["vram", "GPU memory"], ["temperature", "GPU temperature"], ["read", "System disk read"], ["write", "System disk write"], ["storage", "Project drive storage"]]) {
  const row = node("div", "resource-row"), value = node("span", "", "Measuring…"); row.append(node("span", "", label), value); resourceDetails.append(row); resourceRows[key] = value;
}
const resourceNote = node("p", "resource-note", "Waiting for the first sample…"); resourceDetails.append(resourceNote);
resourcePanel.append(resourceSummary, resourceDetails); document.querySelector(".header-actions").prepend(resourcePanel);
const percentText = value => Number.isFinite(value) ? `${Math.round(value)}%` : "Unavailable";
const fixedText = (value, suffix) => Number.isFinite(value) ? `${value.toFixed(1)} ${suffix}` : "Unavailable";
let resourcesPolling = false;
async function refreshResources() {
  if (stopped || document.hidden || resourcesPolling) return;
  resourcesPolling = true;
  try {
    const data = await api("/api/resources");
    const fresh = !data.stale;
    for (const [key, value] of [["cpu", data.cpu_percent], ["ram", data.ram_percent], ["gpu", data.gpu?.percent]]) {
      $(`resource-${key}`).querySelector("b").textContent = fresh && Number.isFinite(value) ? percentText(value) : "--";
      $(`resource-${key}`).classList.toggle("high", fresh && Number.isFinite(value) && value >= 90);
    }
    resourceRows.cpu.textContent = fresh ? percentText(data.cpu_percent) : "Unavailable";
    resourceRows.ram.textContent = fresh && Number.isFinite(data.ram_used_gib) ? `${data.ram_used_gib.toFixed(1)} / ${data.ram_total_gib.toFixed(1)} GiB (${percentText(data.ram_percent)})` : "Unavailable";
    resourceRows.gpu.textContent = fresh ? percentText(data.gpu?.percent) : "Unavailable";
    resourceRows.vram.textContent = fresh && Number.isFinite(data.gpu?.used_mib) && Number.isFinite(data.gpu?.total_mib) ? `${(data.gpu.used_mib / 1024).toFixed(1)} / ${(data.gpu.total_mib / 1024).toFixed(1)} GiB` : "Unavailable";
    resourceRows.temperature.textContent = fresh ? fixedText(data.gpu?.temperature_c, "°C") : "Unavailable";
    resourceRows.read.textContent = fresh ? fixedText(data.disk_read_mib_s, "MiB/s") : "Unavailable";
    resourceRows.write.textContent = fresh ? fixedText(data.disk_write_mib_s, "MiB/s") : "Unavailable";
    resourceRows.storage.textContent = fresh && Number.isFinite(data.disk_free_gib) ? `${data.disk_drive} ${data.disk_free_gib.toFixed(1)} GiB free (${percentText(data.disk_used_percent)} used)` : "Unavailable";
    resourceNote.textContent = !fresh ? "Resource readings are not available yet." : data.ram_percent >= 90 ? "Memory pressure is high. Preview quality reduces inference work. Disk activity can increase when Windows pages memory." : "Updates every few seconds. Disk transfer activity and storage capacity are separate measurements.";
    resourcePanel.title = fresh ? `System CPU ${percentText(data.cpu_percent)} · RAM ${percentText(data.ram_percent)} · GPU ${percentText(data.gpu?.percent)}` : "System readings unavailable";
  } catch {
    for (const key of ["cpu", "ram", "gpu"]) $(`resource-${key}`).querySelector("b").textContent = "--";
    for (const value of Object.values(resourceRows)) value.textContent = "Unavailable";
    resourceNote.textContent = "Resource monitor unavailable. Start the updated local server.";
  } finally { resourcesPolling = false; }
}
document.addEventListener("click", event => { if (!resourcePanel.contains(event.target)) resourcePanel.open = false; });
document.addEventListener("visibilitychange", () => { if (!document.hidden) { refreshResources(); refresh(); } });
refreshResources(); setInterval(refreshResources, 3000);
refresh(); setInterval(() => refresh(), 1000);
