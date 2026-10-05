const state = { status: null, scenes: [], modules: [], packets: [], capturePaused: false };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function toast(message, error = false) {
  const node = $("#toast"); node.textContent = message; node.classList.toggle("error", error); node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 3200);
}

function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[ch])); }

function renderStatus() {
  const s = state.status; if (!s) return;
  const udp = s.udp, mqtt = s.mqtt;
  $("#global-status").textContent = `UDP ${udp.active ? "ativo" : "inativo"} · MQTT ${mqtt.connected ? "online" : "offline"}`;
  $("#global-status").classList.toggle("online", udp.active && mqtt.connected);
  const metrics = [
    [s.app_version, "App version"], [udp.active ? "Ativo" : "Inativo", `UDP :${udp.port}`],
    [mqtt.connected ? "Conectado" : (mqtt.available ? "Desconectado" : "Indisponível"), "MQTT"],
    [s.uptime_seconds + "s", "Uptime"], [udp.rx_packets, "Pacotes RX"], [udp.tx_packets, "Pacotes TX"],
    [udp.broadcast_address, "Broadcast"], [s.capture_buffer_size, "Buffer atual"],
  ];
  $("#status-grid").innerHTML = metrics.map(([value, label]) => `<div class="metric"><div class="value">${escapeHtml(value)}</div><div class="label">${escapeHtml(label)}</div></div>`).join("");
  $("#last-rx").textContent = udp.last_received ? JSON.stringify(udp.last_received, null, 2) : "Nenhum pacote recebido";
  $("#last-tx").textContent = udp.last_transmitted ? JSON.stringify(udp.last_transmitted, null, 2) : "Nenhum pacote transmitido";
  $("#lab-toggle").checked = Boolean(s.protocol_lab_enabled);
  $("#lab-warning").style.display = s.protocol_lab_enabled ? "block" : "block";
}

function renderScenes() {
  $("#scene-list").innerHTML = state.scenes.length ? state.scenes.map((scene) => `<article class="item"><div class="item-main"><strong>${escapeHtml(scene.name)}</strong><small>Cena ${scene.scene_number} · ${scene.enabled ? "habilitada" : "desabilitada"} · button.neocontrol_scene_${scene.id}</small></div><div class="item-actions"><button onclick="testScene(${scene.id})">Testar</button><button onclick="editScene(${scene.id})">Editar</button><button onclick="toggleScene(${scene.id}, ${!scene.enabled})">${scene.enabled ? "Desabilitar" : "Habilitar"}</button><button class="danger" onclick="deleteScene(${scene.id})">Excluir</button></div></article>`).join("") : `<div class="notice">Nenhuma cena cadastrada.</div>`;
}

function renderModules() {
  $("#module-list").innerHTML = state.modules.length ? state.modules.map((item) => `<article class="item"><div class="item-main"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.logical_name)} · ${escapeHtml(item.module_type)}${item.raw_hex ? ` · ${escapeHtml(item.raw_hex)}` : ""}</small></div><div class="item-actions"><button class="danger" onclick="deleteModule(${item.id})">Excluir</button></div></article>`).join("") : `<div class="notice">Nenhum módulo experimental cadastrado.</div>`;
}

function renderPackets() {
  $("#packet-table").innerHTML = state.packets.length ? state.packets.map((packet) => `<tr><td>${escapeHtml(new Date(packet.timestamp).toLocaleTimeString())}</td><td>${escapeHtml(packet.direction.toUpperCase())}</td><td>${escapeHtml(packet.source_ip)}</td><td>${packet.length}</td><td>${escapeHtml(packet.payload_hex)}</td></tr>`).join("") : `<tr><td colspan="5">Nenhum pacote no buffer.</td></tr>`;
}

async function refreshAll() {
  try { [state.status, state.scenes, state.modules, state.packets] = await Promise.all([api("/api/status"), api("/api/scenes"), api("/api/modules"), fetchPackets()]); renderStatus(); renderScenes(); renderModules(); renderPackets(); await refreshDiagnostics(); } catch (error) { toast(error.message, true); }
}

async function fetchPackets() {
  const params = new URLSearchParams(); if ($("#filter-ip").value) params.set("source_ip", $("#filter-ip").value); if ($("#filter-length").value) params.set("length", $("#filter-length").value); if ($("#filter-prefix").value) params.set("prefix_hex", $("#filter-prefix").value); return api(`/api/packets?${params}`);
}

async function refreshDiagnostics() { try { $("#diagnostics-json").textContent = JSON.stringify(await api("/api/diagnostics"), null, 2); } catch (_) {} }
async function testScene(id) { try { await api(`/api/scenes/${id}/test`, { method: "POST" }); toast("Cena transmitida"); await refreshAll(); } catch (error) { toast(error.message, true); } }
async function editScene(id) { const scene = state.scenes.find((item) => item.id === id); if (!scene) return; const name = prompt("Nome da cena", scene.name); if (name === null) return; const number = prompt("Número da cena", scene.scene_number); if (number === null) return; try { await api(`/api/scenes/${id}`, { method: "PUT", body: JSON.stringify({ name, scene_number: Number(number) }) }); await refreshAll(); toast("Cena atualizada"); } catch (error) { toast(error.message, true); } }
async function toggleScene(id, enabled) { try { await api(`/api/scenes/${id}`, { method: "PUT", body: JSON.stringify({ enabled }) }); await refreshAll(); toast("Cena atualizada"); } catch (error) { toast(error.message, true); } }
async function deleteScene(id) { if (!confirm("Excluir esta cena?")) return; try { await api(`/api/scenes/${id}`, { method: "DELETE" }); await refreshAll(); toast("Cena excluída"); } catch (error) { toast(error.message, true); } }
async function deleteModule(id) { if (!confirm("Excluir este módulo?")) return; try { await api(`/api/modules/${id}`, { method: "DELETE" }); await refreshAll(); toast("Módulo excluído"); } catch (error) { toast(error.message, true); } }

$("#scene-form").addEventListener("submit", async (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); data.scene_number = Number(data.scene_number); data.enabled = Boolean(event.target.enabled.checked); try { await api("/api/scenes", { method: "POST", body: JSON.stringify(data) }); event.target.reset(); event.target.enabled.checked = true; await refreshAll(); toast("Cena cadastrada"); } catch (error) { toast(error.message, true); } });
$("#module-form").addEventListener("submit", async (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); if (!data.raw_hex.trim()) data.raw_hex = null; try { await api("/api/modules", { method: "POST", body: JSON.stringify(data) }); event.target.reset(); await refreshAll(); toast("Módulo cadastrado"); } catch (error) { toast(error.message, true); } });
$("#lab-toggle").addEventListener("change", async (event) => { const enabled = event.target.checked; if (enabled && !confirm("O Protocol Lab pode acionar equipamentos. Confirmar habilitação?")) { event.target.checked = false; return; } try { await api("/api/settings/protocol-lab", { method: "POST", body: JSON.stringify({ enabled, confirmed: enabled }) }); toast(enabled ? "Protocol Lab habilitado" : "Protocol Lab desabilitado"); await refreshAll(); } catch (error) { event.target.checked = false; toast(error.message, true); } });
$("#individual-form").addEventListener("submit", async (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); data.function = Number(data.function); data.subfunction = Number(data.subfunction); if (!data.module_raw_hex.trim()) data.module_raw_hex = null; try { await api("/api/protocol/send-individual", { method: "POST", body: JSON.stringify(data) }); toast("Frame individual transmitido"); await refreshAll(); } catch (error) { toast(error.message, true); } });
$("#raw-form").addEventListener("submit", async (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); try { await api("/api/protocol/send-raw", { method: "POST", body: JSON.stringify(data) }); toast("Payload raw transmitido"); await refreshAll(); } catch (error) { toast(error.message, true); } });
$("#capture-toggle").addEventListener("click", () => { state.capturePaused = !state.capturePaused; $("#capture-toggle").textContent = state.capturePaused ? "Retomar visualização" : "Pausar visualização"; });
$("#clear-capture").addEventListener("click", async () => { try { await api("/api/packets", { method: "DELETE" }); state.packets = []; renderPackets(); toast("Captura limpa; o listener continua ativo"); } catch (error) { toast(error.message, true); } });
$("#download-diagnostics").addEventListener("click", async () => { const data = await api("/api/diagnostics"); const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "neocontrol-diagnostics.json"; link.click(); URL.revokeObjectURL(link.href); });
$("#individual-form").addEventListener("input", () => { const f = $("#individual-form"); const name = f.module_name.value.padEnd(8, "\0").slice(0, 8); const hex = [...name].map((ch) => ch.charCodeAt(0).toString(16).padStart(2, "0")).join(" ").toUpperCase(); $("#individual-preview").textContent = `14 00 ${hex} ${Number(f.function.value || 0).toString(16).padStart(2, "0").toUpperCase()} ${Number(f.subfunction.value || 0).toString(16).padStart(2, "0").toUpperCase()} FF`; });
[...document.querySelectorAll(".tab")].forEach((button) => button.addEventListener("click", () => { $$(".tab").forEach((item) => item.classList.remove("active")); button.classList.add("active"); $$(".panel").forEach((panel) => panel.classList.toggle("active", panel.id === button.dataset.tab)); }));
setInterval(async () => { try { state.status = await api("/api/status"); if (!state.capturePaused) state.packets = await fetchPackets(); renderStatus(); renderPackets(); } catch (_) {} }, 3000);
refreshAll();

