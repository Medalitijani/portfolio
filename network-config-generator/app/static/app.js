const $ = (id) => document.getElementById(id);
let latestDesign = null;
let activeConfig = "switch-config";

function showNotice(message, isError = false) {
  $("notice").textContent = message;
  $("notice").style.color = isError ? "#ff9a9f" : "#91a3b8";
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function renderDesign(design, mode) {
  latestDesign = design;
  $("empty").hidden = true;
  $("results").hidden = false;
  $("mode").textContent = mode.toUpperCase();
  $("vlan-count").textContent = design.vlans.length;
  $("employee-count").textContent = design.request.employees;
  $("validation-state").textContent = design.validation_passed ? "PASS" : "REVIEW";
  $("validation-state").style.color = design.validation_passed ? "#64d6a3" : "#ff7d83";
  $("vlan-rows").innerHTML = design.vlans.map((v) => `
    <tr><td class="vlan-id">${escapeHtml(v.vlan_id)}</td><td>${escapeHtml(v.name)}</td><td>${escapeHtml(v.subnet)}</td><td>${escapeHtml(v.gateway)}</td></tr>
  `).join("");
  $("findings").innerHTML = design.findings.map((f) => `
    <div class="finding ${escapeHtml(f.severity)}"><strong>${escapeHtml(f.severity.toUpperCase())} · ${escapeHtml(f.code)}</strong>${escapeHtml(f.message)}</div>
  `).join("");
  $("switch-config").textContent = design.switch_config;
  $("router-config").textContent = design.router_config;
  $("notes").innerHTML = design.generation_notes.map((n) => `<li>${escapeHtml(n)}</li>`).join("");
  activateTab("switch-config");
}

function activateTab(target) {
  activeConfig = target;
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.target === target));
  $("switch-config").hidden = target !== "switch-config";
  $("router-config").hidden = target !== "router-config";
  $("code-label").textContent = target === "switch-config" ? "SWITCH CONFIG" : "ROUTER CONFIG";
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => activateTab(tab.dataset.target)));

$("generate").addEventListener("click", async () => {
  const prompt = $("prompt").value.trim();
  if (prompt.length < 10) return showNotice("Please provide a more detailed network brief.", true);
  $("generate").disabled = true;
  $("generate").querySelector("span").textContent = "Analyzing requirements…";
  showNotice("Interpreting requirements and generating a deterministic network plan…");
  try {
    const interpretResponse = await fetch("/api/interpret", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({prompt})
    });
    if (!interpretResponse.ok) throw new Error((await interpretResponse.json()).detail || "Requirement interpretation failed.");
    const interpreted = await interpretResponse.json();
    const designResponse = await fetch("/api/design", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(interpreted.requirements)
    });
    if (!designResponse.ok) throw new Error((await designResponse.json()).detail || "Network design failed.");
    const design = await designResponse.json();
    renderDesign(design, interpreted.interpretation_mode);
    showNotice(interpreted.note);
  } catch (error) {
    showNotice(error.message || "Unexpected error. Check the API server.", true);
  } finally {
    $("generate").disabled = false;
    $("generate").querySelector("span").textContent = "Generate network plan";
  }
});

$("copy-config").addEventListener("click", async () => {
  const value = $(activeConfig).textContent;
  try {
    await navigator.clipboard.writeText(value);
    $("copy-config").textContent = "Copied";
    setTimeout(() => $("copy-config").textContent = "Copy", 1200);
  } catch {
    showNotice("Clipboard access was blocked by the browser.", true);
  }
});

$("download").addEventListener("click", () => {
  if (!latestDesign) return;
  const blob = new Blob([JSON.stringify(latestDesign, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "network-design-report.json";
  link.click();
  URL.revokeObjectURL(url);
});
