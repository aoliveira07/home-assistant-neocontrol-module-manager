const state = {
  status: null,
  scenes: [],
  modules: [],
  packets: [],
  capturePaused: false,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function appUrl(path) {
  return new URL(String(path).replace(/^\/+/, ""), document.baseURI).toString();
}

async function api(path, options = {}) {
  const response = await fetch(appUrl(path), {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail || detail;
    } catch (_) {
      // Keep the HTTP status text when the response is not JSON.
    }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[character]);
}

let toastTimer;
function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.toggle("error", error);
  node.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("show"), 3200);
}

function setStatusCard(selector, mode, text) {
  const card = $(selector);
  card.classList.remove("is-online", "is-warning", "is-offline");
  card.classList.add(`is-${mode}`);
  card.querySelector("small").textContent = text;
}

function formatPacket(packet) {
  return packet ? JSON.stringify(packet, null, 2) : "Nenhum pacote capturado";
}

function renderStatus() {
  const status = state.status;
  if (!status) return;
  const udp = status.udp || {};
  const mqtt = status.mqtt || {};
  const rx = Number(udp.rx_packets || 0);
  const tx = Number(udp.tx_packets || 0);

  $("#app-version").textContent = status.app_version || "—";
  $("#scene-count").textContent = `${state.scenes.length} cadastrada${state.scenes.length === 1 ? "" : "s"}`;
  setStatusCard("#udp-status-card", udp.active ? "online" : "offline", udp.active ? `Online · porta ${udp.port}` : `Indisponível · porta ${udp.port}`);
  setStatusCard("#mqtt-status-card", mqtt.connected ? "online" : (mqtt.available ? "warning" : "offline"), mqtt.connected ? "Conectado" : (mqtt.available ? "Desconectado" : "Não configurado"));
  setStatusCard("#bridge-status-card", udp.active ? "online" : "offline", udp.active ? `${rx} RX · ${tx} TX` : "Listener indisponível");

  $("#last-rx").textContent = formatPacket(udp.last_received);
  $("#last-tx").textContent = formatPacket(udp.last_transmitted);
  $("#lab-toggle").checked = Boolean(status.protocol_lab_enabled);
}

function sceneCard(scene) {
  const enabled = Boolean(scene.enabled);
  return `<article class="entity-card">
    <div class="entity-icon" aria-hidden="true">◉</div>
    <div class="entity-main">
      <strong>${escapeHtml(scene.name)}</strong>
      <small>scene_${scene.id} · Cena ${scene.scene_number}</small>
      <span class="entity-badge ${enabled ? "" : "off"}">${enabled ? "● Habilitada" : "○ Desabilitada"}</span>
    </div>
    <div class="entity-meta"><span>Home Assistant MQTT</span><strong>button.neocontrol_scene_${scene.id}</strong><small>Discovery ${enabled ? "publicado" : "desativado"}</small></div>
    <div class="entity-actions">
      <button class="button primary" onclick="testScene(${scene.id})">Testar</button>
      <button class="button secondary" onclick="editScene(${scene.id})">Editar</button>
      <button class="button secondary" onclick="toggleScene(${scene.id}, ${!enabled})">${enabled ? "Desativar" : "Ativar"}</button>
      <button class="button danger" onclick="deleteScene(${scene.id})">Excluir</button>
    </div>
  </article>`;
}

function renderScenes() {
  const empty = `<div class="empty-state">Nenhuma cena cadastrada. Use o formulário na aba Cenas para criar a primeira.</div>`;
  const markup = state.scenes.length ? state.scenes.map(sceneCard).join("") : empty;
  $("#scene-list").innerHTML = markup;
  $("#dashboard-scene-list").innerHTML = state.scenes.length ? state.scenes.slice(0, 6).map(sceneCard).join("") : empty;
}

function moduleCard(item) {
  const raw = item.raw_hex ? ` · ${escapeHtml(item.raw_hex)}` : "";
  return `<article class="entity-card">
    <div class="entity-icon" aria-hidden="true">▤</div>
    <div class="entity-main"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.logical_name)} · ${escapeHtml(item.module_type)}${raw}</small><span class="entity-badge">● Cadastro local</span></div>
    <div class="entity-meta"><span>Mapeamento físico</span><strong>Protocol Lab</strong><small>${item.notes ? escapeHtml(item.notes) : "Aguardando captura real"}</small></div>
    <div class="entity-actions"><button class="button danger" onclick="deleteModule(${item.id})">Excluir</button></div>
  </article>`;
}

function renderModules() {
  $("#module-list").innerHTML = state.modules.length
    ? state.modules.map(moduleCard).join("")
    : `<div class="empty-state">Nenhum módulo experimental cadastrado. O App inicia normalmente sem módulos na rede.</div>`;
}

function renderPackets() {
  const table = $("#packet-table");
  if (!state.packets.length) {
    table.innerHTML = `<tr><td colspan="5">Nenhum pacote no buffer.</td></tr>`;
    return;
  }
  table.innerHTML = state.packets.map((packet) => `<tr>
    <td>${escapeHtml(new Date(packet.timestamp).toLocaleTimeString())}</td>
    <td>${escapeHtml(String(packet.direction || "").toUpperCase())}</td>
    <td>${escapeHtml(packet.source_ip)}</td>
    <td>${escapeHtml(packet.length)}</td>
    <td title="${escapeHtml(packet.interpretation || "")}">${escapeHtml(packet.payload_hex)}</td>
  </tr>`).join("");
}

async function fetchPackets() {
  const params = new URLSearchParams();
  if ($("#filter-ip").value) params.set("source_ip", $("#filter-ip").value);
  if ($("#filter-length").value) params.set("length", $("#filter-length").value);
  if ($("#filter-prefix").value) params.set("prefix_hex", $("#filter-prefix").value);
  const query = params.toString();
  return api(`api/packets${query ? `?${query}` : ""}`);
}

async function refreshDiagnostics() {
  try {
    $("#diagnostics-json").textContent = JSON.stringify(await api("api/diagnostics"), null, 2);
  } catch (_) {
    // The main status remains usable when diagnostics are temporarily unavailable.
  }
}

async function refreshAll() {
  try {
    const [status, scenes, modules, packets] = await Promise.all([
      api("api/status"),
      api("api/scenes"),
      api("api/modules"),
      state.capturePaused ? Promise.resolve(state.packets) : fetchPackets(),
    ]);
    state.status = status;
    state.scenes = scenes;
    state.modules = modules;
    state.packets = packets;
    renderStatus();
    renderScenes();
    renderModules();
    renderPackets();
    await refreshDiagnostics();
  } catch (error) {
    toast(error.message, true);
  }
}

async function testScene(id) {
  try {
    await api(`api/scenes/${id}/test`, { method: "POST" });
    toast("Cena transmitida");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
}

async function editScene(id) {
  const scene = state.scenes.find((item) => item.id === id);
  if (!scene) return;
  const name = prompt("Nome da cena", scene.name);
  if (name === null) return;
  const number = prompt("Número da cena", scene.scene_number);
  if (number === null) return;
  try {
    await api(`api/scenes/${id}`, { method: "PUT", body: JSON.stringify({ name, scene_number: Number(number) }) });
    toast("Cena atualizada");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
}

async function toggleScene(id, enabled) {
  try {
    await api(`api/scenes/${id}`, { method: "PUT", body: JSON.stringify({ enabled }) });
    toast("Cena atualizada");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
}

async function deleteScene(id) {
  if (!confirm("Excluir esta cena?")) return;
  try {
    await api(`api/scenes/${id}`, { method: "DELETE" });
    toast("Cena excluída");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
}

async function deleteModule(id) {
  if (!confirm("Excluir este módulo?")) return;
  try {
    await api(`api/modules/${id}`, { method: "DELETE" });
    toast("Módulo excluído");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
}

function updateIndividualPreview() {
  const form = $("#individual-form");
  const raw = (form.module_raw_hex.value || "").replace(/[^0-9a-f]/gi, "");
  let moduleBytes = raw.length === 16
    ? raw.match(/../g)
    : [...(form.module_name.value || "")].map((character) => character.charCodeAt(0).toString(16).padStart(2, "0"));
  moduleBytes = (moduleBytes || []).slice(0, 8);
  while (moduleBytes.length < 8) moduleBytes.push("00");
  const moduleHex = moduleBytes.join(" ").toUpperCase();
  const functionHex = Number(form.function.value || 0).toString(16).padStart(2, "0").toUpperCase();
  const subfunctionHex = Number(form.subfunction.value || 0).toString(16).padStart(2, "0").toUpperCase();
  $("#individual-preview").textContent = `14 00 ${moduleHex} ${functionHex} ${subfunctionHex} FF`;
}

$("#scene-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  data.scene_number = Number(data.scene_number);
  data.enabled = Boolean(event.target.enabled.checked);
  try {
    await api("api/scenes", { method: "POST", body: JSON.stringify(data) });
    event.target.reset();
    event.target.enabled.checked = true;
    toast("Cena cadastrada");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
});

$("#module-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  if (!data.raw_hex || !data.raw_hex.trim()) data.raw_hex = null;
  try {
    await api("api/modules", { method: "POST", body: JSON.stringify(data) });
    event.target.reset();
    toast("Módulo cadastrado");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
});

$("#lab-toggle").addEventListener("change", async (event) => {
  const enabled = event.target.checked;
  if (enabled && !confirm("O Protocol Lab pode acionar equipamentos. Confirmar habilitação?")) {
    event.target.checked = false;
    return;
  }
  try {
    await api("api/settings/protocol-lab", { method: "POST", body: JSON.stringify({ enabled, confirmed: enabled }) });
    toast(enabled ? "Protocol Lab habilitado" : "Protocol Lab desabilitado");
    await refreshAll();
  } catch (error) {
    event.target.checked = false;
    toast(error.message, true);
  }
});

$("#individual-form").addEventListener("input", updateIndividualPreview);
$("#individual-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  data.function = Number(data.function);
  data.subfunction = Number(data.subfunction);
  if (!data.module_raw_hex || !data.module_raw_hex.trim()) data.module_raw_hex = null;
  try {
    await api("api/protocol/send-individual", { method: "POST", body: JSON.stringify(data) });
    toast("Frame individual transmitido");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
});

$("#raw-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target));
  try {
    await api("api/protocol/send-raw", { method: "POST", body: JSON.stringify(data) });
    toast("Payload raw transmitido");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
});

$("#refresh-button").addEventListener("click", refreshAll);
$("#capture-toggle").addEventListener("click", () => {
  state.capturePaused = !state.capturePaused;
  $("#capture-toggle").textContent = state.capturePaused ? "Retomar visualização" : "Pausar visualização";
  if (!state.capturePaused) refreshAll();
});
$("#clear-capture").addEventListener("click", async () => {
  try {
    await api("api/packets", { method: "DELETE" });
    state.packets = [];
    renderPackets();
    toast("Captura limpa; o listener continua ativo");
    await refreshAll();
  } catch (error) { toast(error.message, true); }
});
$("#download-diagnostics").addEventListener("click", async () => {
  try {
    const data = await api("api/diagnostics");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "neocontrol-diagnostics.json";
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (error) { toast(error.message, true); }
});

let filterTimer;
["#filter-ip", "#filter-length", "#filter-prefix"].forEach((selector) => $(selector).addEventListener("input", () => {
  clearTimeout(filterTimer);
  filterTimer = setTimeout(async () => {
    try {
      state.packets = await fetchPackets();
      renderPackets();
    } catch (error) { toast(error.message, true); }
  }, 220);
}));

$$(".nav-item").forEach((button) => button.addEventListener("click", () => {
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item === button));
  $$(".panel").forEach((panel) => panel.classList.toggle("active", panel.id === button.dataset.tab));
}));

window.testScene = testScene;
window.editScene = editScene;
window.toggleScene = toggleScene;
window.deleteScene = deleteScene;
window.deleteModule = deleteModule;

setInterval(async () => {
  try {
    state.status = await api("api/status");
    if (!state.capturePaused) state.packets = await fetchPackets();
    renderStatus();
    renderPackets();
  } catch (_) {
    // The next interval retries without interrupting the active UI.
  }
}, 3000);

updateIndividualPreview();
refreshAll();
