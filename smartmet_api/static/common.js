// Shared helpers for the SmartMet4QC dashboard pages.

const REFRESH_MS = 10000;
const SEVERITY_ORDER = { critical: 0, warning: 1, info: 2 };

const LABELS = {
  temperature_c: { name: "Temperature", unit: "°C", digits: 1 },
  ph: { name: "pH", unit: "", digits: 2 },
  brix: { name: "Brix", unit: "°Bx", digits: 1 },
  turbidity_ntu: { name: "Turbidity", unit: "NTU", digits: 0 },
  ethanol_percent: { name: "Ethanol", unit: "%", digits: 1 },
};

const RULE_NAMES = {
  temperature_high: "Too hot",
  temperature_low: "Too cold",
  ph_low: "pH too low",
  turbidity_high: "Too cloudy",
  fermentation_stuck: "Fermentation stuck",
  batch_finished: "Fermentation finished",
  sensor_spike: "Sensor jump",
  sensor_stuck: "Sensor frozen",
  sensor_missing: "Sensor no value",
};

// Never put text from the server into HTML without escaping it.
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => null);
  return { ok: response.ok, status: response.status, body };
}

function fmtTime(iso) {
  if (!iso) return "–";
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function errorText(body) {
  if (!body) return "Server did not answer.";
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join("; ");
  return JSON.stringify(body);
}

function sortAlerts(alerts) {
  return [...alerts].sort((a, b) =>
    SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] || b.opened_at.localeCompare(a.opened_at));
}

function alertItem(alert, { showBatch = false } = {}) {
  const batch = showBatch
    ? `<a href="/batches/${encodeURIComponent(alert.batch_id)}">${esc(alert.batch_id)}</a> · ` : "";
  const when = alert.status === "resolved"
    ? `${fmtTime(alert.opened_at)} → resolved ${fmtTime(alert.resolved_at)}`
    : `since ${fmtTime(alert.opened_at)}`;
  return `<li class="${esc(alert.status)}">
    <span class="pill ${esc(alert.severity)}">${esc(RULE_NAMES[alert.rule] || alert.rule)}</span>
    <span>${esc(alert.message)}</span>
    <span class="meta">${batch}${when}</span>
  </li>`;
}

function deviceItem(device, { showBatch = false, unassign = false } = {}) {
  const state = !device.active ? `<span class="pill">key revoked</span>`
    : device.online ? `<span class="pill info">online</span>` : `<span class="pill warning">offline</span>`;
  const batch = !showBatch ? ""
    : device.batch_id ? ` · measures <a href="/batches/${encodeURIComponent(device.batch_id)}">${esc(device.batch_id)}</a>`
    : " · no batch assigned";
  const button = unassign
    ? ` <button type="button" class="small" data-unassign="${esc(device.name)}">Stop measuring</button>` : "";
  return `<li>
    ${state}
    <span><strong>${esc(device.name)}</strong>${batch}${button}</span>
    <span class="meta">last contact ${device.last_seen_at ? fmtTime(device.last_seen_at) : "never"}</span>
  </li>`;
}

function stamp(el) {
  el.textContent = "Updated " + new Date().toLocaleTimeString();
}
