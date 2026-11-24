const $ = (id) => document.getElementById(id);
let latestDesign = null;
let activeConfig = "switch-config";
let busy = false;

function setNotice(message, kind = "info") {
  const notice = $("notice");
  notice.dataset.kind = kind;
  notice.querySelector("span:last-child").textContent = message;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function setServiceStatus(healthy, label) {
  $("status-dot").classList.toggle("offline", !healthy);
  $("service-state").textContent = label;
}

async function checkService() {
  try {
    const response = await fetch("/api/health", {headers: {"Accept": "application/json"}});
    if (!response.ok) throw new Error("Service unavailable");
    const data = await response.json();
    setServiceStatus(true, "API operational · v" + data.version);
  } catch {
    setServiceStatus(false, "API status unavailable");
  }
}

function updateCharacterCount() {
  $("char-count").textContent = $("prompt").value.length.toLocaleString() + " / 2,000";
}

function setBusy(value) {
  busy = value;
  $("generate").disabled = value;
  $("generate").querySelector(".btn-label").textContent = value ? "Building architecture…" : "Generate network architecture";
  $("generate").querySelector(".btn-icon").textContent = value ? "◌" : "✦";
}

function renderDesign(design, mode, note) {
  latestDesign = design;
  $("empty").hidden = true;
  $("results").hidden = false;
  $("mode").textContent = mode === "llm" ? "AI INTERPRETED" : mode === "demo-fallback" ? "LOCAL FALLBACK" : "DEMO MODE";
  $("mode").className = "pill " + (mode === "llm" ? "success" : "warning");
  $("result-company").textContent = design.request.company_name || "Network design generated";
  $("result-time").textContent = new Date().toLocaleString();
  $("vlan-count").textContent = design.vlans.length;
  $("employee-count").textContent = Number(design.request.employees).toLocaleString();
  $("validation-state").textContent = design.validation_passed ? "PASS" : "REVIEW";
  $("validation-state").className = "metric-state " + (design.validation_passed ? "good" : "bad");
  $("validation-caption").textContent = design.validation_passed ? "No blocking errors" : "Review blocking findings";
  $("subnet-base").textContent = "BASE " + design.request.base_network;
  $("vlan-rows").innerHTML = design.vlans.map((v) => `
    <tr><td><span class="vlan-badge">${escapeHtml(v.vlan_id)}</span></td><td><b>${escapeHtml(v.name)}</b><small class="cell-subtitle">${escapeHtml(v.purpose || "")}</small></td><td class="mono">${escapeHtml(v.subnet)}</td><td class="mono">${escapeHtml(v.gateway)}</td><td class="mono">${escapeHtml(v.dhcp_start)} – ${escapeHtml(v.dhcp_end)}</td></tr>
  `).join("");
  const findings = Array.isArray(design.findings) ? design.findings : [];
  $("finding-count").textContent = findings.length + " FINDING" + (findings.length === 1 ? "" : "S");
  $("findings").innerHTML = findings.length ? findings.map((f) => `
    <article class="finding ${escapeHtml(f.severity)}"><span class="finding-symbol">${f.severity === "error" ? "!" : f.severity === "warning" ? "△" : "✓"}</span><div><b>${escapeHtml(String(f.severity).toUpperCase())} · ${escapeHtml(f.code)}</b><p>${escapeHtml(f.message)}</p></div></article>
  `).join("") : '<div class="finding success"><span class="finding-symbol">✓</span><div><b>NO FINDINGS</b><p>No validation findings were returned.</p></div></div>';
  $("switch-config").textContent = design.switch_config || "! No switch configuration was generated.";
  $("router-config").textContent = design.router_config || "! No router configuration was generated.";
  $("notes").innerHTML = (design.generation_notes || []).map((n) => `<li>${escapeHtml(n)}</li>`).join("");
  activateTab("switch-config");
  setNotice(note || "Architecture generated. Review all findings and configuration drafts before use.", "success");
}

function activateTab(target) {
  activeConfig = target;
  document.querySelectorAll(".tab").forEach((tab) => {
    const selected = tab.dataset.target === target;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
  $("switch-config").hidden = target !== "switch-config";
  $("router-config").hidden = target !== "router-config";
  $("code-label").textContent = target === "switch-config" ? "SWITCH CONFIGURATION" : "ROUTER / L3 CONFIGURATION";
}

function downloadText(filename, content, type = "text/plain") {
  const blob = new Blob([content], {type});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function readApiError(response, fallback) {
  const payload = await response.json().catch(() => ({}));
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) return payload.detail.map((item) => item.msg || "Invalid input").join("; ");
  return fallback;
}

$("prompt").addEventListener("input", updateCharacterCount);
document.querySelectorAll(".example-chip").forEach((button) => {
  button.addEventListener("click", () => {
    $("prompt").value = button.dataset.prompt;
    updateCharacterCount();
    $("prompt").focus();
  });
});
document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => activateTab(tab.dataset.target)));

$("generate").addEventListener("click", async () => {
  if (busy) return;
  const prompt = $("prompt").value.trim();
  if (prompt.length < 10) {
    setNotice("Please provide at least 10 characters describing the network.", "error");
    $("prompt").focus();
    return;
  }
  setBusy(true);
  setNotice("Interpreting requirements and generating the network design…");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 55000);
  try {
    const interpretResponse = await fetch("/api/interpret", {
      method: "POST", headers: {"Content-Type": "application/json", "Accept": "application/json"},
      body: JSON.stringify({prompt}), signal: controller.signal
    });
    if (!interpretResponse.ok) throw new Error(await readApiError(interpretResponse, "Requirement interpretation failed."));
    const interpreted = await interpretResponse.json();
    const designResponse = await fetch("/api/design", {
      method: "POST", headers: {"Content-Type": "application/json", "Accept": "application/json"},
      body: JSON.stringify(interpreted.requirements), signal: controller.signal
    });
    if (!designResponse.ok) throw new Error(await readApiError(designResponse, "Network design generation failed."));
    const design = await designResponse.json();
    renderDesign(design, interpreted.interpretation_mode, interpreted.note);
    $("results").scrollIntoView({behavior: "smooth", block: "start"});
  } catch (error) {
    const message = error.name === "AbortError" ? "The request timed out. Please try again." : (error.message || "Unexpected server error.");
    setNotice(message, "error");
  } finally {
    clearTimeout(timeout);
    setBusy(false);
  }
});

$("copy-config").addEventListener("click", async () => {
  if (!latestDesign) return;
  try {
    await navigator.clipboard.writeText($(activeConfig).textContent);
    $("copy-config").textContent = "Copied ✓";
    setTimeout(() => $("copy-config").textContent = "Copy", 1500);
  } catch {
    setNotice("Clipboard access was blocked by your browser. Select and copy the configuration manually.", "error");
  }
});

$("download-config").addEventListener("click", () => {
  if (!latestDesign) return;
  const filename = activeConfig === "switch-config" ? "switch-configuration.txt" : "router-configuration.txt";
  downloadText(filename, $(activeConfig).textContent);
});

$("download").addEventListener("click", () => {
  if (!latestDesign) return;
  downloadText("netarchitect-network-design.json", JSON.stringify(latestDesign, null, 2), "application/json");
});

updateCharacterCount();
checkService();
