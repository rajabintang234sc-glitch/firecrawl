"use strict";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const clone = (value) => JSON.parse(JSON.stringify(value));
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const icon = (name, small = false) =>
  `<svg class="icon${small ? " small" : ""}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
const numberFormat = new Intl.NumberFormat("id-ID", {
  maximumFractionDigits: 0,
});
const rp = (value) => `Rp ${numberFormat.format(value ?? 0)}`;
const pct = (value) =>
  value == null
    ? "—"
    : `${new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 }).format(value)}%`;
const compact = (value) =>
  Math.abs(value) >= 1e9
    ? `${new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 }).format(value / 1e9)} M`
    : Math.abs(value) >= 1e6
      ? `${new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 }).format(value / 1e6)} jt`
      : numberFormat.format(value);
const dateLabel = (value) =>
  new Intl.DateTimeFormat("id-ID", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
const uid = () =>
  globalThis.crypto?.randomUUID?.() ||
  `event-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
const STORAGE = "panggung.eo.project.v1";
const CATEGORIES = {
  production: "Produksi",
  creative: "Creative",
  management: "Management",
  venue: "Venue",
  hospitality: "Hospitality",
  talent: "Talent",
  logistics: "Logistik",
  safety: "Safety & legal",
};
const COLORS = {
  production: "#799761",
  creative: "#a390bc",
  management: "#bccf9c",
  venue: "#98b49a",
  hospitality: "#d9bc83",
  talent: "#cfbda8",
  logistics: "#8faaa7",
  safety: "#ccd2bc",
};
const TYPE_LABELS = {
  corporate: "Corporate gathering",
  launch: "Product launch",
  activation: "Brand activation",
};
const AGENT_ICONS = {
  rab: "list",
  hpp: "chart",
  budget: "shield",
  pricing: "coins",
  creative: "spark",
  operations: "clock",
};
const STATUS = {
  complete: ["green", "Selesai"],
  review: ["amber", "Review"],
  blocked: ["red", "Perlu revisi"],
};
const TABS = ["overview", "rab", "pricing", "agents", "learning"];
const initialTab = location.hash.slice(1);
const state = {
  project: null,
  report: null,
  bootstrap: null,
  tab: TABS.includes(initialTab) ? initialTab : "overview",
  dirty: false,
  busy: false,
  revision: 0,
  controller: null,
  timer: null,
  error: "",
  rabQuery: "",
  rabCategory: "all",
  focusAgent: null,
  dialogSubmit: null,
  research: null,
  researchBusy: false,
};

async function fetchJSON(path, body, signal) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error || `Permintaan gagal (${response.status}).`);
  return data;
}

function toast(message, error = false) {
  const node = document.createElement("div");
  node.className = `toast${error ? " error" : ""}`;
  node.innerHTML = `${icon(error ? "alert" : "check")}<span>${esc(message)}</span>`;
  $("#toasts").append(node);
  setTimeout(() => node.remove(), 5500);
}

function save() {
  try {
    localStorage.setItem(STORAGE, JSON.stringify(state.project));
  } catch {
    toast(
      "Penyimpanan browser tidak tersedia. Gunakan export JSON untuk menyimpan proyek.",
      true,
    );
  }
}

function markDirty() {
  state.revision++;
  state.dirty = true;
  state.error = "";
  updateChrome();
  clearTimeout(state.timer);
  state.timer = setTimeout(() => runAnalysis(), 650);
}

async function runAnalysis(notify = false) {
  if (!state.project) return false;
  clearTimeout(state.timer);
  state.controller?.abort();
  const controller = new AbortController();
  state.controller = controller;
  const revision = state.revision;
  state.busy = true;
  updateChrome();
  try {
    const result = await fetchJSON(
      "/api/analyze",
      clone(state.project),
      controller.signal,
    );
    if (revision !== state.revision) return false;
    state.project = result.project;
    state.report = result.report;
    state.dirty = false;
    state.error = "";
    save();
    render();
    if (notify)
      toast(
        `6 agent selesai. ${result.report.review.warningCount} hal perlu review.`,
      );
    return true;
  } catch (error) {
    if (error.name === "AbortError") return false;
    if (revision === state.revision) {
      state.error = error.message;
      state.dirty = true;
      if (notify) toast(error.message, true);
    }
    return false;
  } finally {
    if (state.controller === controller) {
      state.busy = false;
      updateChrome();
    }
  }
}

function updateChrome() {
  $$("[data-tab]").forEach((node) => {
    const selected = node.dataset.tab === state.tab;
    node.classList.toggle("active", selected);
    if (node.getAttribute("role") === "tab")
      node.setAttribute("aria-selected", String(selected));
    if (node.classList.contains("nav-item"))
      selected
        ? node.setAttribute("aria-current", "page")
        : node.removeAttribute("aria-current");
  });
  const sync = $("#sync-state");
  sync.className = `sync-state${state.busy ? " busy" : state.dirty ? " dirty" : ""}`;
  sync.innerHTML = `<span class="tiny-dot"></span>${state.busy ? "Menghitung 6 agent…" : state.dirty ? "Perubahan belum dihitung" : state.report ? "6 agent tersinkron" : "Menyiapkan agent"}`;
  const run = $("#run-agents");
  run.disabled = state.busy || !state.project;
  run.setAttribute("aria-busy", String(state.busy));
  $("span", run).textContent = state.busy ? "Menghitung…" : "Jalankan agent";
  const banner = $("#validation-banner");
  banner.textContent = state.error
    ? `Kalkulasi belum diperbarui: ${state.error} Hasil di bawah adalah snapshot terakhir, bukan hasil perubahan ini.`
    : "";
  banner.classList.toggle("hidden", !state.error);
  if (state.project?.event) {
    $("#side-project-name").textContent = state.project.event.name;
    $("#side-project-meta").textContent =
      `${state.project.event.city} · ${state.project.event.attendees} pax`;
  }
}

function renderProject() {
  const e = state.project.event;
  $("#project-strip").innerHTML =
    `<div class="project-strip-left"><span class="project-symbol">${icon("file")}</span><div><div class="project-title-row"><h2>${esc(e.name)}</h2><span class="badge draft">Draf · estimasi</span></div><div class="project-meta"><span>${icon("location")}${esc(e.city)}</span><span>${icon("users")}${numberFormat.format(e.attendees)} peserta</span><span>${icon("clock")}${e.eventDays} hari event + ${e.setupDays} setup</span><span>${dateLabel(e.date)}</span></div></div></div><div class="project-strip-right"><select class="select-clean" id="template-picker" aria-label="Ganti template proyek">${state.bootstrap.templates.map((t) => `<option value="${t.id}"${t.id === e.type ? " selected" : ""}>${esc(t.label)}</option>`).join("")}</select><button class="button secondary small" data-edit-brief>${icon("edit")}Edit brief</button></div>`;
}

function render(preserveFocus = true) {
  updateChrome();
  if (!state.project || !state.report) return;
  const active = document.activeElement;
  const focusId =
    preserveFocus && $("#content").contains(active) ? active.id : null;
  let caret;
  try {
    caret = active.selectionStart;
  } catch {
    caret = null;
  }
  renderProject();
  const renderers = {
    overview: renderOverview,
    rab: renderRab,
    pricing: renderPricing,
    agents: renderAgents,
    learning: renderLearning,
  };
  $("#content").innerHTML = renderers[state.tab]();
  $("#content").setAttribute("aria-labelledby", `tab-${state.tab}`);
  $$("[data-width]").forEach((node) => {
    node.style.width = `${Math.max(0, Math.min(100, Number(node.dataset.width) || 0))}%`;
  });
  if (focusId) {
    const replacement = document.getElementById(focusId);
    if (replacement) {
      replacement.focus({ preventScroll: true });
      try {
        if (caret != null) replacement.setSelectionRange(caret, caret);
      } catch {
        /* Number inputs do not support selection ranges. */
      }
    }
  }
  if (state.focusAgent && state.tab === "agents") {
    const target = document.getElementById(`agent-${state.focusAgent}`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    state.focusAgent = null;
  }
}

function setTab(tab, agentId = null) {
  if (!TABS.includes(tab)) return;
  state.tab = tab;
  state.focusAgent = agentId;
  history.replaceState(null, "", `#${tab}`);
  $("#sidebar").classList.remove("open");
  render(false);
}

function metric(label, value, foot, symbol, highlight = false, money = true) {
  return `<article class="metric-card${highlight ? " highlight" : ""}"><div class="metric-top"><span>${esc(label)}</span>${icon(symbol)}</div><div class="metric-value">${money ? '<span class="currency">Rp</span>' : ""}${esc(value)}</div><div class="metric-foot">${esc(foot)}</div></article>`;
}

function agentCard(agent) {
  const [color, label] = STATUS[agent.status];
  const issueCount = agent.insights.filter((i) =>
    ["warning", "critical"].includes(i.level),
  ).length;
  const tone =
    agent.id === "creative"
      ? " purple"
      : agent.id === "pricing"
        ? " amber"
        : "";
  return `<article class="agent-card"><div class="agent-heading"><span class="agent-icon${tone}">${icon(AGENT_ICONS[agent.id])}</span><div><h3>${esc(agent.name)}</h3><p>${esc(agent.role)}</p></div><span class="badge ${color}">${label}</span></div><p>${esc(agent.summary)}</p><div class="agent-card-foot"><span>${issueCount ? `${issueCount} catatan review` : "Pemeriksaan selesai"}</span><button data-agent-detail="${agent.id}">Lihat temuan ${icon("arrow")}</button></div></article>`;
}

function miniInsight(item) {
  return `<div class="insight-mini ${item.level}"><span class="insight-dot">${icon(["warning", "critical"].includes(item.level) ? "alert" : "check")}</span><div><strong>${esc(item.title)}</strong><p>${esc(item.description)}</p></div></div>`;
}

function renderOverview() {
  const r = state.report,
    t = r.totals,
    p = r.pricing,
    b = r.budget;
  const categories = r.rab.categories;
  let offset = 0;
  const segments = categories
    .map((c) => {
      const length = c.sharePercent * 3.0159;
      const markup = `<circle cx="80" cy="80" r="48" fill="none" stroke="${COLORS[c.id]}" stroke-width="15" stroke-dasharray="${Math.max(0, length - 2)} ${301.59 - Math.max(0, length - 2)}" stroke-dashoffset="${-offset}"/>`;
      offset += length;
      return markup;
    })
    .join("");
  const selectedInsights = [];
  const relevantCodes = [
    "quotes-pending",
    "tax-unconfirmed",
    "working-capital",
    "budget-gap",
    "below-floor",
    "budget-fits",
  ];
  for (const entry of r.insights)
    if (relevantCodes.includes(entry.code)) selectedInsights.push(entry);
  const health = selectedInsights.slice(0, 3);
  const verified = r.quality.freshQuoteCount;
  return `<div class="metrics-grid">${metric("Budget klien", compact(b.clientBudget), b.includesVat ? "Plafon termasuk PPN" : "Plafon sebelum PPN", "coins")}${metric("HPP proyek", compact(t.hpp), `${rp(t.hppPerAttendee)} per peserta · full cost`, "chart")}${metric("Harga jual ideal", compact(p.recommendedPrice), `Sebelum PPN · cadangan ${pct(state.project.finance.contingencyPercent)}`, "spark", true)}${metric("Margin penawaran aktif", pct(p.marginPercent), `Target ${pct(state.project.finance.targetMarginPercent)} · setelah cadangan`, "shield", false, false)}</div>
  <div class="two-column"><article class="panel"><div class="panel-header"><div><h2>Ke mana budget produksi mengalir?</h2><p>Komposisi biaya langsung, sebelum overhead & cadangan.</p></div><span class="badge green">${categories.length} area</span></div><div class="panel-body"><div class="allocation-layout"><div class="donut-wrap"><svg viewBox="0 0 160 160" aria-label="Distribusi biaya langsung"><circle cx="80" cy="80" r="48" fill="none" stroke="#edf1e6" stroke-width="15"/>${segments}</svg><div class="donut-center"><small>BIAYA LANGSUNG</small><strong>${compact(t.directCost)}</strong><small>IDR / ${r.quality.itemCount} item biaya</small></div></div><div class="allocation-legend">${categories.map((c) => `<div class="legend-row"><svg width="7" height="7" aria-hidden="true"><rect width="7" height="7" rx="2" fill="${COLORS[c.id]}"/></svg><span>${esc(c.name)}</span><strong>${rp(c.total)}</strong><em>${Math.round(c.sharePercent)}%</em></div>`).join("") || '<p class="muted">Belum ada biaya langsung.</p>'}</div></div><div class="allocation-footer">${icon("info")}<span>Overhead ${rp(t.overhead)} dan cadangan ${rp(t.contingency)} dihitung terpisah. Tidak ada management fee tambahan yang dihitung dua kali.</span></div></div></article>
  <article class="panel"><div class="panel-header"><div><h2>Financial health check</h2><p>Kelayakan budget, bukti tarif, dan ruang negosiasi.</p></div>${icon("shield")}</div><div class="panel-body"><div class="budget-status"><div><small>${b.recommendedGap ? "GAP KE HARGA IDEAL" : "SISA BUDGET PENAWARAN AKTIF"}</small><strong>${rp(b.recommendedGap || b.headroom)}</strong></div><span class="badge ${b.recommendedFits ? "green" : "amber"}">${b.recommendedFits ? "Budget mencukupi" : "Review scope"}</span></div><div class="budget-progress"><div class="budget-progress-fill${(b.utilizationPercent || 0) > 100 ? " over" : ""}" data-width="${b.utilizationPercent || 0}"></div></div><div class="budget-axis"><span>${pct(b.utilizationPercent)} budget terpakai</span><span>${rp(b.clientBudget)}</span></div><div class="insight-mini-list">${health.map(miniInsight).join("")}</div></div></article></div>
  <div class="section-heading"><div><h2>Tim agent Anda, bekerja bersama.</h2><p>Satu snapshot biaya. Enam perspektif untuk keputusan yang lebih utuh.</p></div><span class="subtle-tag"><span class="tiny-dot"></span>${r.execution.agentCount} agent · parallel rules</span></div><div class="agent-grid">${r.agents.map(agentCard).join("")}</div>
  <div class="notice-strip">${icon("info")}<div><strong>Transparan dari awal.</strong> ${verified}/${r.quality.itemCount} tarif didukung quote aktif untuk tanggal event. Semua tarif template adalah ilustrasi; margin merupakan kebijakan internal, bukan klaim standar industri. <a href="#rab" data-tab="rab">Tinjau RAB ↗</a></div></div>`;
}

function renderRab() {
  const r = state.report,
    t = r.totals;
  const filtered = r.rab.items.filter(
    (i) =>
      (state.rabCategory === "all" || i.category === state.rabCategory) &&
      `${i.name} ${i.vendor} ${CATEGORIES[i.category]}`
        .toLowerCase()
        .includes(state.rabQuery.toLowerCase()),
  );
  const priority = {
    essential: "Esensial",
    flexible: "Fleksibel",
    optional: "Opsional",
  };
  return `<div class="view-heading"><div><h2>RAB yang bisa ditelusuri.</h2><p>Volume × durasi × tarif. Semua biaya produksi, creative, dan management.</p></div><div class="actions"><button class="button secondary small" data-export="csv">${icon("download")}CSV internal</button><button class="button primary small" data-add-item>${icon("plus")}Tambah item</button></div></div><article class="panel"><div class="table-tools"><div class="search-field">${icon("search")}<input class="field-control" id="rab-search" placeholder="Cari item atau vendor…" aria-label="Cari baris RAB" value="${esc(state.rabQuery)}"></div><select class="field-control" id="rab-category" aria-label="Filter kategori"><option value="all">Semua area</option>${Object.entries(
    CATEGORIES,
  )
    .map(
      ([id, name]) =>
        `<option value="${id}"${state.rabCategory === id ? " selected" : ""}>${name}</option>`,
    )
    .join(
      "",
    )}</select><span class="table-count">${filtered.length} dari ${r.quality.itemCount} item</span></div><div class="table-scroll"><table class="rab-table"><thead><tr><th>Kebutuhan / deliverable</th><th>Volume</th><th>Durasi</th><th>Tarif satuan (Rp)</th><th>Total (Rp)</th><th>Bukti tarif</th><th><span class="muted">Aksi</span></th></tr></thead><tbody>${filtered.map((i) => `<tr><td><div class="row-name">${esc(i.name)}</div><div class="row-detail">${esc(CATEGORIES[i.category])} · ${esc(i.unit)} · ${priority[i.priority]}${i.kind === "overhead" ? " · Overhead" : ""}</div></td><td><input class="table-number" type="number" min="0.000001" max="1000000" step="any" id="qty-${i.id}" data-item-id="${i.id}" data-item-field="quantity" value="${i.quantity}" aria-label="Volume ${esc(i.name)}"></td><td><input class="table-number" type="number" min="0.000001" max="365" step="any" id="duration-${i.id}" data-item-id="${i.id}" data-item-field="duration" value="${i.duration}" aria-label="Durasi ${esc(i.name)}"></td><td><input class="table-number price" type="number" min="0" max="1000000000000" step="any" id="price-${i.id}" data-item-id="${i.id}" data-item-field="unitPrice" value="${i.unitPrice}" aria-label="Tarif satuan ${esc(i.name)}"></td><td class="money-cell">${numberFormat.format(i.total)}</td><td><span class="badge ${i.freshQuote ? "green" : i.confidence === "estimate" ? "draft" : "amber"}">${i.confidence === "estimate" ? "Estimasi" : i.freshQuote ? "Quote aktif" : "Cek quote"}</span></td><td><div class="row-actions"><button class="icon-button" data-edit-item="${i.id}" aria-label="Detail ${esc(i.name)}">${icon("edit")}</button><button class="icon-button danger" data-delete-item="${i.id}" aria-label="Hapus ${esc(i.name)}">${icon("trash")}</button></div></td></tr>`).join("")}</tbody></table>${!filtered.length ? '<div class="empty-state"><h3>Item tidak ditemukan</h3><p>Ubah kata pencarian atau filter kategori.</p></div>' : ""}</div><div class="table-summary"><div><small>BIAYA LANGSUNG</small><strong>${rp(t.directCost)}</strong></div><div><small>OVERHEAD (${pct(state.project.finance.overheadPercent)} alokasi)</small><strong>${rp(t.overhead)}</strong></div><div><small>HPP PROYEK</small><strong>${rp(t.hpp)}</strong></div><div><small>CADANGAN TERPISAH</small><strong>${rp(t.contingency)}</strong></div></div></article><div class="notice-strip">${icon("info")}<div><strong>Tarif harus memakai basis biaya yang konsisten.</strong> Masukkan biaya neto setelah diskon vendor. PPN masukan yang dapat dikreditkan tidak masuk biaya; pajak vendor yang tidak dapat dikreditkan harus sudah termasuk tarif. Tanggal, satuan, load-in/out, dan bukti quote dapat diubah melalui detail item.</div></div>`;
}

function financeField(key, label, suffix = "%", help = "", maximum = 100) {
  const value = state.project.finance[key];
  return `<label class="form-field"><span>${label}</span><div class="input-suffix"><input class="field-control" type="number" id="f-${key}" data-finance="${key}" min="0" max="${maximum}" step="any" value="${value}">${suffix ? `<span>${suffix}</span>` : ""}</div>${help ? `<small>${help}</small>` : ""}</label>`;
}

function costLine(label, value, total = false, highlight = false) {
  return `<div class="cost-line${total ? " total" : ""}${highlight ? " highlight" : ""}"><span>${label}</span><strong>${rp(value)}</strong></div>`;
}

function renderTimeline(timeline) {
  return `<div class="timeline">${timeline.map((phase, index) => `<div class="timeline-row"><span class="timeline-node">${index + 1}</span><div class="timeline-content"><div><strong>${esc(phase.title)}</strong><p>${esc(phase.owner)}</p><small>${esc(phase.deliverable)}</small></div><time datetime="${phase.date}">${dateLabel(phase.date)}</time></div></div>`).join("")}</div>`;
}

function renderPricing() {
  const r = state.report,
    p = r.pricing,
    t = r.totals,
    f = state.project.finance,
    c = r.cashflow;
  const operation = r.agents.find((a) => a.id === "operations");
  return `<div class="view-heading"><div><h2>Harga sehat. Arus kas terkendali.</h2><p>Harga berbasis full cost dan risiko, bukan sekadar menambahkan markup.</p></div><button class="button secondary small" data-export="proposal">${icon("file")}Draft penawaran</button></div><div class="pricing-scenarios">${p.scenarios.map((s) => `<article class="scenario-card${s.id === "target" ? " recommended" : ""}"><div class="scenario-header"><h3>${s.label}</h3>${s.id === "target" ? '<span class="badge green">Rekomendasi</span>' : `<span class="badge ${s.id === "premium" ? "purple" : "draft"}">Margin ${pct(s.targetMarginPercent)}</span>`}</div><div class="scenario-price"><small>Rp</small> ${compact(s.price)}</div><div class="scenario-meta"><span>Margin efektif ${pct(s.marginPercent)}</span><span>Sebelum PPN</span></div><button class="button ${s.id === "target" ? "primary" : "secondary"}" data-scenario="${s.id}">${p.selectedPrice === s.price ? `${icon("check")}Harga aktif` : "Gunakan skenario"}</button></article>`).join("")}</div>
  <div class="notice-strip">${icon("info")}<div>Ketiga skenario memakai <strong>scope yang sama</strong> dan hanya mengubah target margin. Skenario value-added bukan validasi harga pasar; deliverable tambahan harus dianggarkan dan disepakati.</div></div>
  <div class="finance-layout"><article class="panel finance-form"><div class="panel-header"><div><h2>Kebijakan biaya & pajak</h2><p>Asumsi bisa diubah. Perubahan dihitung ulang secara otomatis.</p></div>${icon("edit")}</div><div class="panel-body"><div class="form-grid">${financeField("clientBudget", "Budget klien (Rp)", "", "", 1000000000000)}${financeField("targetMarginPercent", "Margin target", "%", "Margin terhadap harga jual.", 79.99)}${financeField("minimumMarginPercent", "Margin minimum", "%", "Batas negosiasi, bukan harga pasar.", 79.99)}${financeField("overheadPercent", "Overhead alokasi", "%", "0% jika overhead dirinci per baris.")}${financeField("contingencyPercent", "Cadangan risiko", "%", "Dihitung atas HPP, bukan laba.")}<label class="form-field"><span>Status perusahaan</span><select class="field-control" id="f-taxStatus" data-finance="taxStatus"><option value="unconfirmed"${f.taxStatus === "unconfirmed" ? " selected" : ""}>Belum dikonfirmasi</option><option value="pkp"${f.taxStatus === "pkp" ? " selected" : ""}>PKP</option><option value="non_pkp"${f.taxStatus === "non_pkp" ? " selected" : ""}>Non-PKP</option></select></label>${financeField("vatPercent", "PPN efektif", "%", "Input efektif, bukan otomatis tarif nominal.")}${financeField("withholdingPercent", "Pemotongan PPh klien", "%", "Mengurangi kas, bukan laba/HPP.")}${financeField("withholdingBasePercent", "Basis pemotongan PPh", "%", "Porsi harga sebelum PPN yang dipotong.")}${financeField("downPaymentPercent", "DP klien", "%", "Persentase invoice sebelum event.")}<label class="form-field"><span>Pembulatan harga</span><select class="field-control" id="f-rounding" data-finance="rounding">${[1, 1000, 10000, 50000, 100000, 1000000].map((v) => `<option value="${v}"${f.rounding === v ? " selected" : ""}>${rp(v)}</option>`).join("")}</select><small>Selalu ke atas agar margin terjaga.</small></label></div><label class="checkbox-field"><input type="checkbox" id="f-budgetIncludesVat" data-finance="budgetIncludesVat"${f.budgetIncludesVat ? " checked" : ""}>Budget klien termasuk PPN</label><label class="checkbox-field"><input type="checkbox" id="f-taxVerified" data-finance="taxVerified"${f.taxVerified ? " checked" : ""}>Saya telah meninjau status, tarif, dan basis pajak transaksi ini</label><div class="references"><strong>Referensi awal, bukan konfirmasi aturan setiap transaksi:</strong> mekanisme 12% × 11/12 dijelaskan dalam artikel DJP tentang PMK 131/2024 <a href="https://pajak.go.id/index.php/en/node/113453" target="_blank" rel="noopener noreferrer">[1]</a>. Ketentuan PPh 23 EO dan pengecualian basis yang membutuhkan bukti dibahas DDTC <a href="https://news.ddtc.co.id/berita/nasional/1806174/jasa-event-organizer-kena-pph-pasal-23-begini-ketentuannya" target="_blank" rel="noopener noreferrer">[2]</a>. Periksa ketentuan terbaru dengan bagian pajak. Default 0% = belum diasumsikan, bukan bebas pajak.</div></div></article>
  <article class="panel sale-card"><div class="panel-header"><div><h2>Dari biaya ke penawaran</h2><p>Rumus dan komponen tampil apa adanya.</p></div><span class="badge ${p.marginPercent != null && p.selectedPrice >= p.floorPrice ? "green" : "red"}">${p.selectedPrice >= p.floorPrice && p.marginPercent != null ? "Di atas batas" : "Perlu revisi"}</span></div><div class="panel-body"><div class="cost-waterfall">${costLine("Biaya langsung", t.directCost)}${costLine("Overhead proyek", t.overhead)}${costLine("HPP full cost", t.hpp, true)}${costLine(`Cadangan risiko ${pct(f.contingencyPercent)}`, t.contingency)}${costLine("Basis pricing: HPP + cadangan", t.riskAdjustedCost, false, true)}</div><div class="offer-control"><label for="f-offerPrice">Harga penawaran manual (Rp), 0 = otomatis ideal</label><input class="field-control" id="f-offerPrice" type="number" data-finance="offerPrice" min="0" max="1000000000000" step="1" value="${f.offerPrice}"></div><div class="cost-waterfall">${costLine("Penawaran aktif sebelum PPN", p.selectedPrice)}${costLine(`PPN efektif ${pct(f.vatPercent)}`, p.vat)}${costLine("Total invoice", p.invoiceTotal, true)}${costLine("PPh dipotong klien", p.withholding)}${costLine("Penerimaan kas invoice", p.clientReceipt)}${costLine("Laba proyeksi setelah cadangan*", p.projectedProfit)}</div><p class="cost-note">Margin setelah cadangan: <strong>${pct(p.marginPercent)}</strong> · markup biaya: ${pct(p.markupPercent)}.<br>Harga ideal = (HPP + cadangan) ÷ (1 − margin target).<br>*Sebelum pajak penghasilan badan. PPh dipotong klien diperlakukan sebagai kredit pajak dalam simulasi; bukan pengurang laba. Ini bukan modul akuntansi/faktur pajak.</p><button class="button ghost" data-reset-offer>Gunakan harga ideal otomatis ${icon("arrow")}</button></div></article></div>
  <div class="finance-layout"><article class="panel"><div class="panel-header"><div><h2>Modal kerja sebelum event</h2><p>DP neto vs komitmen biaya. PPN bukan modal operasional.</p></div>${icon("coins")}</div><div class="panel-body"><div class="cashflow-grid"><div class="cash-metric"><small>DP NETO TERSEDIA</small><strong>${rp(c.availableDownPayment)}</strong><p>Sesudah PPh, tanpa PPN.</p></div><div class="cash-metric"><small>KEBUTUHAN PRA-EVENT</small><strong>${rp(c.preEventNeed)}</strong><p>Uang muka + alokasi + cadangan.</p></div><div class="cash-metric${c.fundingGap ? " warning" : ""}"><small>GAP MODAL KERJA</small><strong>${rp(c.fundingGap)}</strong><p>${c.fundingGap ? "Butuh modal / ubah termin." : "Tertutup pada simulasi ini."}</p></div></div><div class="cost-waterfall">${costLine("Uang muka biaya per baris", c.vendorPreEvent)}${costLine("Overhead alokasi disisihkan", c.overheadReserve)}${costLine("Cadangan disisihkan", c.riskReserve)}</div><p class="cost-note">DP neto minimum secara hitungan: ${pct(c.requiredDownPaymentPercent)}. ${esc(c.note)} Ubah DP vendor melalui detail RAB. Jika kebutuhan DP melebihi 100%, termin saja tidak cukup.</p></div></article><article class="panel"><div class="panel-header"><div><h2>Jalur produksi sampai rekonsiliasi</h2><p>Jadwal awal; sesuaikan dengan lead time vendor dan venue.</p></div>${icon("clock")}</div><div class="panel-body">${renderTimeline(operation.timeline)}</div></article></div>`;
}

function renderAgents() {
  const r = state.report;
  return `<div class="view-heading"><div><h2>Enam spesialis. Satu sumber angka.</h2><p>Agent rule-based berjalan paralel setelah validasi snapshot biaya.</p></div><span class="badge green">${r.execution.durationMs} ms · engine</span></div><div class="pipeline"><div class="pipeline-step">${icon("file")}<div><strong>Brief & input</strong><small>Validasi skema</small></div></div><span class="pipeline-arrow">→</span><div class="pipeline-step">${icon("chart")}<div><strong>Snapshot biaya</strong><small>Decimal · immutable</small></div></div><span class="pipeline-arrow">→</span><div class="pipeline-step">${icon("agents")}<div><strong>6 agent paralel</strong><small>Tanpa race condition</small></div></div><span class="pipeline-arrow">→</span><div class="pipeline-step">${icon("shield")}<div><strong>Review manusia</strong><small>Tidak auto-approve</small></div></div></div><div class="agent-detail-grid">${r.agents
    .map((agent) => {
      const [color, label] = STATUS[agent.status];
      return `<article class="panel agent-detail" id="agent-${agent.id}"><div class="agent-heading"><span class="agent-icon${agent.id === "creative" ? " purple" : ""}">${icon(AGENT_ICONS[agent.id])}</span><div><h3>${esc(agent.name)}</h3><p>${esc(agent.role)}</p></div><span class="badge ${color}">${label}</span></div><div class="agent-detail-body"><p>${esc(agent.summary)}</p><div class="agent-insights">${agent.insights.map((i) => `<div class="agent-insight ${i.level}"><strong>${esc(i.title)}</strong><p>${esc(i.description)}</p></div>`).join("")}</div>${agent.ideas ? `<ul class="idea-list">${agent.ideas.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : ""}${agent.id === "budget" && r.budget.recommendedGap && agent.scopeOptions.length ? `<div class="dialog-section-label">Opsi review scope, bukan pemotongan otomatis</div><ul class="idea-list">${agent.scopeOptions.map((i) => `<li>${esc(i.name)} — alokasi langsung ${rp(i.directSaving)}. ${esc(i.action)}</li>`).join("")}</ul>` : ""}${agent.id === "operations" ? `<p class="cost-note">Gap modal kerja ${rp(r.cashflow.fundingGap)} · ${agent.timeline.length} checkpoint produksi. <a href="#pricing" data-tab="pricing">Lihat timeline & cashflow ↗</a></p>` : ""}</div></article>`;
    })
    .join(
      "",
    )}</div><div class="notice-strip">${icon("shield")}<div><strong>Belum ada persetujuan otomatis.</strong> Hasil engine merupakan pemeriksaan rule-based, bukan keputusan LLM atau sertifikasi kelayakan. Quote, scope, izin, perpajakan, dan penawaran akhir tetap memerlukan penanggung jawab manusia.</div></div>`;
}

function renderLearning() {
  const learning = state.report.learning;
  const actualCount = state.project.items.filter(
    (i) => i.actualUnitPrice !== null,
  ).length;
  const research = state.research;
  return `<div class="learning-hero"><span class="learning-hero-icon">${icon("spark")}</span><div><h2>Semakin banyak realisasi, semakin tajam estimasi.</h2><p>Skill pembelajaran mengusulkan tarif dari event dengan kota, jenis, spesifikasi, dan satuan yang sama. Minimal ${learning.policy.minimumSamples} event berbeda, median tahan outlier, dan persetujuan sebelum perubahan.</p></div><span class="badge green">Review-gated learning</span></div><div class="learning-columns"><article class="panel"><div class="panel-header"><div><h2>Usulan pembaruan tarif</h2><p>Bukan mengubah kode sendiri. Kebijakan dapat diuji dan direview.</p></div>${icon("spark")}</div><div class="panel-body"><div class="learning-stats"><div class="learning-stat"><strong>${learning.observationCount}</strong><small>Observasi tercatat</small></div><div class="learning-stat"><strong>${learning.proposals.length}</strong><small>Usulan tarif</small></div><div class="learning-stat"><strong>${learning.eligibleCount}</strong><small>Layak direview</small></div><div class="learning-stat"><strong>${state.project.audit.length}</strong><small>Revisi disetujui</small></div></div>${learning.proposals.length ? `<div class="spaced-top">${learning.proposals.map((p) => `<div class="proposal-card"><h3>${esc(p.name)}</h3><div class="proposal-rates"><div><small>TARIF SAAT INI</small><strong>${rp(p.previousPrice)}</strong></div>${icon("arrow")}<div><small>USULAN ESTIMASI</small><strong>${rp(p.proposedPrice)}</strong></div></div><p>${p.sampleCount} event sebanding · median ${rp(p.medianActualPrice)} · deviasi ${pct(p.deviationPercent)}.</p>${p.reasons.map((reason) => `<p>${esc(reason)}</p>`).join("")}<div class="proposal-card-foot"><span class="badge ${p.eligible ? "green" : "amber"}">${p.eligible ? "Siap direview" : "Perlu data / review manual"}</span><button class="button secondary small" data-apply-item="${p.itemId}"${p.eligible ? "" : " disabled"}>Review & terapkan</button></div></div>`).join("")}</div>` : `<div class="empty-state">${icon("chart")}<h3>Belajar dari hasil, bukan tebakan.</h3><p>Belum ada observasi yang sebanding. Mulai dengan mencatat tarif satuan realisasi yang sudah diverifikasi.</p><div class="learn-step-list"><div class="learn-step"><span class="learn-step-number">1</span><div><strong>Catat realisasi per item</strong><p>Harga neto per satuan, bukan total faktur.</p></div></div><div class="learn-step"><span class="learn-step-number">2</span><div><strong>Kumpulkan event sebanding</strong><p>Event ID unik; pengulangan tidak menambah sampel.</p></div></div><div class="learn-step"><span class="learn-step-number">3</span><div><strong>Review sebelum diterapkan</strong><p>Tarif baru tetap estimasi, tidak menjadi quote.</p></div></div></div></div>`}<p class="cost-note">Jendela data ${learning.policy.historyWindowDays} hari · learning rate ${pct(learning.policy.learningRate * 100)} · deviasi maksimum ${pct(learning.policy.maximumDeviationPercent)}. Semua ini kebijakan internal, bukan ukuran harga pasar. Data dan audit lokal belum bersifat tamper-proof.</p></div></article>
  <article class="panel research-panel"><div class="panel-header"><div><h2>Riset vendor, dengan sumber.</h2><p>Firecrawl search opsional. Tarif tidak diambil alih otomatis.</p></div><span class="badge ${state.bootstrap.researchEnabled ? "green" : "draft"}">${state.bootstrap.researchEnabled ? "Terhubung" : "Belum dikonfigurasi"}</span></div><div class="panel-body"><form id="research-form" class="research-form"><input class="field-control" id="research-query" maxlength="300" placeholder="Contoh: sewa LED P3 indoor Jakarta" aria-label="Kata pencarian vendor" required value="${esc(research?.query || "")}"><button class="button primary small" type="submit"${state.researchBusy || !state.bootstrap.researchEnabled ? " disabled" : ""}>${icon("search")}${state.researchBusy ? "Mencari…" : "Cari sumber"}</button></form>${!state.bootstrap.researchEnabled ? '<p class="research-note">Administrator perlu mengatur <code>FIRECRAWL_API_KEY</code> dan <code>EO_ENABLE_RESEARCH=1</code> di lingkungan server lalu restart. Tidak ada API key yang diminta atau disimpan di browser. Riset tidak diperlukan untuk kalkulasi.</p>' : '<p class="research-note">Pencarian memakai kredit Firecrawl hanya saat tombol ditekan. Bandingkan spesifikasi, ukuran, kota, periode sewa, ketersediaan, dan pajak.</p>'}<div id="research-results">${research?.references?.length ? research.references.map((ref) => `<div class="research-result"><a href="${esc(ref.url)}" target="_blank" rel="noopener noreferrer">${esc(ref.title)} ${icon("external", true)}</a><p>${esc(ref.description)}</p><small>${esc(ref.url)}</small><span class="badge draft">Referensi web · bukan quote</span></div>`).join("") : research ? '<div class="empty-state"><h3>Tidak ada referensi yang ditemukan.</h3><p>Coba istilah vendor dan spesifikasi yang lebih tepat.</p></div>' : '<div class="empty-state">' + icon("search") + "<h3>Penawaran vendor tetap sumber utama.</h3><p>Riset membantu menemukan pembanding. Harga hanya diubah setelah Anda meninjau dan memasukkan penawaran.</p></div>"}</div><div class="notice-strip no-margin">${icon("shield")}<div>Konten web diperlakukan sebagai data tidak tepercaya. Tidak menjalankan instruksi, mengeksekusi kode, atau mengganti tarif dari halaman vendor.</div></div></div></article></div>
  <article class="panel"><div class="panel-header"><div><h2>Catat realisasi proyek ini</h2><p>Harga satuan neto sesuai spesifikasi. Kosong = belum diketahui, 0 = benar-benar nol.</p></div><button class="button secondary small" id="archive-actuals"${actualCount ? "" : " disabled"}>${icon("check")}Catat ${actualCount || ""} realisasi</button></div><div class="panel-body"><div class="table-scroll"><table class="history-table"><thead><tr><th>Item biaya</th><th>Estimasi / satuan</th><th>Realisasi / satuan (Rp)</th><th>Selisih tarif</th></tr></thead><tbody>${state.project.items.map((i) => `<tr><td><div class="row-name">${esc(i.name)}</div><div class="row-detail">${esc(i.unit)} · ${esc(CATEGORIES[i.category])}</div></td><td class="money-cell">${rp(i.unitPrice)}</td><td><input class="table-number price" id="actual-${i.id}" type="number" min="0" max="1000000000000" step="any" data-item-id="${i.id}" data-item-field="actualUnitPrice" value="${i.actualUnitPrice ?? ""}" placeholder="Belum diketahui" aria-label="Realisasi per satuan ${esc(i.name)}"></td><td class="money-cell">${i.actualUnitPrice == null ? "—" : rp(i.actualUnitPrice - i.unitPrice)}</td></tr>`).join("")}</tbody></table></div><p class="cost-note">Mencatat ulang event ID yang sama akan memperbarui observasi, bukan menambah sampel. Untuk event berikutnya gunakan proyek dari template agar ID baru dibuat, atau import proyek dengan ID unik. Riwayat tetap tersimpan di browser ini; backup melalui export JSON.</p></div></article>
  ${
    state.project.audit.length
      ? `<article class="panel spaced-top"><div class="panel-header"><div><h2>Jejak revisi yang disetujui</h2><p>Audit lokal; bukan log keamanan server atau akuntansi.</p></div>${icon("clock")}</div><div class="panel-body"><div class="audit-list">${[
          ...state.project.audit,
        ]
          .reverse()
          .slice(0, 10)
          .map(
            (a) =>
              `<div class="audit-item"><strong>${esc(state.project.items.find((i) => i.id === a.itemId)?.name || a.itemId)}</strong> · ${rp(a.previousPrice)} → ${rp(a.newPrice)}<small>${esc(a.reviewedAt)} · ${a.sampleCount} event sebanding · ${esc(a.proposalId)}</small></div>`,
          )
          .join("")}</div></div></article>`
      : ""
  }`;
}

function openDialog(
  title,
  body,
  submit = null,
  buttonLabel = "Simpan perubahan",
) {
  $("#dialog-title").textContent = title;
  $("#dialog-body").innerHTML = body;
  $("#dialog-error").textContent = "";
  $("#dialog-error").classList.add("hidden");
  state.dialogSubmit = submit;
  $("#dialog-submit").textContent = buttonLabel;
  $("#dialog-submit").classList.toggle("hidden", !submit);
  $("#dialog-submit").disabled = false;
  if (!$("#workspace-dialog").open) $("#workspace-dialog").showModal();
}

function closeDialog() {
  $("#workspace-dialog").close();
  state.dialogSubmit = null;
}

async function validateAndReplace(next) {
  const revision = state.revision;
  const result = await fetchJSON("/api/analyze", next);
  if (revision !== state.revision)
    throw new Error(
      "Input berubah. Tutup dialog, hitung ulang, dan coba kembali.",
    );
  clearTimeout(state.timer);
  state.controller?.abort();
  state.project = result.project;
  state.report = result.report;
  state.revision++;
  state.dirty = false;
  state.error = "";
  state.busy = false;
  save();
  render(false);
}

function editBrief() {
  const e = state.project.event;
  openDialog(
    "Brief & skala event",
    `<p class="dialog-description">Biaya dengan basis peserta dan durasi akan mengikuti perubahan skala. Biaya tetap tidak diubah otomatis. Tinjau kembali spesifikasi dan quote setelah perubahan.</p><div class="form-grid two"><label class="form-field full-width"><span>Nama proyek</span><input class="field-control" name="name" maxlength="120" required value="${esc(e.name)}"></label><label class="form-field"><span>Jenis event</span><select class="field-control" name="type">${Object.entries(
      TYPE_LABELS,
    )
      .map(
        ([id, label]) =>
          `<option value="${id}"${e.type === id ? " selected" : ""}>${label}</option>`,
      )
      .join(
        "",
      )}</select></label><label class="form-field"><span>Kota</span><input class="field-control" name="city" required maxlength="80" value="${esc(e.city)}"></label><label class="form-field"><span>Tanggal event</span><input class="field-control" type="date" name="date" required value="${e.date}"></label><label class="form-field"><span>Lingkungan</span><select class="field-control" name="environment">${["indoor", "outdoor", "hybrid"].map((v) => `<option value="${v}"${e.environment === v ? " selected" : ""}>${v[0].toUpperCase() + v.slice(1)}</option>`).join("")}</select></label><label class="form-field"><span>Jumlah peserta</span><input class="field-control" name="attendees" type="number" min="1" max="100000" required value="${e.attendees}"></label><label class="form-field"><span>Hari event</span><input class="field-control" name="eventDays" type="number" min="1" max="30" required value="${e.eventDays}"></label><label class="form-field"><span>Hari setup / rehearsal</span><input class="field-control" name="setupDays" type="number" min="0" max="30" required value="${e.setupDays}"></label><label class="form-field"><span>Budget klien (Rp)</span><input class="field-control" name="clientBudget" type="number" min="0" max="1000000000000" required value="${state.project.finance.clientBudget}"></label></div>`,
    async (form) => {
      const data = new FormData(form),
        next = clone(state.project),
        oldEvent = clone(next.event);
      for (const key of ["name", "type", "city", "date", "environment"])
        next.event[key] = data.get(key);
      for (const key of ["attendees", "eventDays", "setupDays"])
        next.event[key] = Number(data.get(key));
      next.finance.clientBudget = Number(data.get("clientBudget"));
      const changed = [
        "attendees",
        "eventDays",
        "setupDays",
        "date",
        "city",
        "type",
        "environment",
      ].some((key) => oldEvent[key] !== next.event[key]);
      for (const item of next.items) {
        if (item.quantityBasis === "attendees")
          item.quantity = next.event.attendees;
        if (item.durationBasis === "eventDays")
          item.duration = next.event.eventDays;
        if (item.durationBasis === "totalDays")
          item.duration = next.event.eventDays + next.event.setupDays;
        if (changed) {
          item.confidence = "estimate";
          item.verifiedAt = null;
          item.validUntil = null;
          item.actualUnitPrice = null;
        }
      }
      await validateAndReplace(next);
      closeDialog();
      toast(
        changed
          ? "Brief diperbarui. Skala biaya mengikuti basis; quote perlu dikonfirmasi ulang."
          : "Brief disimpan.",
      );
    },
  );
}

const TAG_LABELS = {
  venue: "Venue",
  stage: "Stage",
  audio: "Audio",
  led: "LED",
  power: "Power backup",
  design: "Design",
  motion: "Motion",
  video: "Dokumentasi",
  producer: "Producer",
  director: "Show director",
  crew: "Crew",
  mc: "MC",
  catering: "Catering",
  transport: "Trucking",
  safety: "Safety",
  medical: "Medis",
  permits: "Izin / asuransi",
};

function editItem(itemId = null) {
  const existing = state.project.items.find((i) => i.id === itemId);
  const item = existing
    ? clone(existing)
    : {
        id: uid(),
        name: "",
        category: "production",
        unit: "paket",
        quantity: 1,
        duration: 1,
        unitPrice: 0,
        kind: "direct",
        priority: "essential",
        quantityBasis: "fixed",
        durationBasis: "fixed",
        advancePercent: 50,
        confidence: "estimate",
        vendor: "",
        reference: "",
        verifiedAt: null,
        validUntil: null,
        actualUnitPrice: null,
        tags: [],
      };
  const options = (values, selected) =>
    Object.entries(values)
      .map(
        ([id, label]) =>
          `<option value="${id}"${id === selected ? " selected" : ""}>${label}</option>`,
      )
      .join("");
  const field = (
    name,
    label,
    value,
    type = "text",
    min = "",
    max = "",
    step = "any",
  ) =>
    `<label class="form-field"><span>${label}</span><input class="field-control" name="${name}" type="${type}" value="${esc(value ?? "")}"${min !== "" ? ` min="${min}"` : ""}${max !== "" ? ` max="${max}"` : ""}${type === "number" ? ` step="${step}"` : ""}${["name", "unit", "quantity", "duration", "unitPrice"].includes(name) ? " required" : ""}></label>`;
  openDialog(
    existing ? "Detail kebutuhan & quote" : "Tambah kebutuhan baru",
    `<div class="form-grid two">${field("name", "Nama kebutuhan / spesifikasi", item.name)}<label class="form-field"><span>Area biaya</span><select class="field-control" name="category">${options(CATEGORIES, item.category)}</select></label>${field("quantity", "Volume", item.quantity, "number", 0.000001, 1000000)}${field("unit", "Satuan harga", item.unit)}${field("duration", "Durasi / pengali periode", item.duration, "number", 0.000001, 365)}${field("unitPrice", "Tarif satuan neto (Rp)", item.unitPrice, "number", 0, 1000000000000)}<label class="form-field"><span>Jenis biaya</span><select class="field-control" name="kind">${options({ direct: "Biaya langsung", overhead: "Overhead rincian" }, item.kind)}</select></label><label class="form-field"><span>Prioritas scope</span><select class="field-control" name="priority">${options({ essential: "Esensial", flexible: "Fleksibel", optional: "Opsional" }, item.priority)}</select></label><label class="form-field"><span>Basis volume</span><select class="field-control" name="quantityBasis">${options({ fixed: "Tetap / manual", attendees: "Mengikuti peserta" }, item.quantityBasis)}</select></label><label class="form-field"><span>Basis durasi</span><select class="field-control" name="durationBasis">${options({ fixed: "Tetap / manual", eventDays: "Hari event", totalDays: "Setup + hari event" }, item.durationBasis)}</select></label>${field("advancePercent", "Biaya yang dibayar sebelum event (%)", item.advancePercent, "number", 0, 100)}<label class="form-field"><span>Bukti tarif</span><select class="field-control" name="confidence">${options({ estimate: "Estimasi (belum quote)", quote: "Penawaran vendor", contract: "Kontrak untuk event ini" }, item.confidence)}</select></label></div><hr class="dialog-divider"><div class="form-grid two">${field("vendor", "Nama vendor", item.vendor)}${field("reference", "Nomor penawaran / referensi dokumen", item.reference)}${field("verifiedAt", "Tanggal verifikasi", item.verifiedAt, "date")}${field("validUntil", "Quote berlaku sampai", item.validUntil, "date")}</div><p class="cost-note">Quote wajib vendor, referensi, dan tanggal verifikasi. Untuk dianggap aktif, quote harus baru dan berlaku sampai tanggal event; kontrak tanpa expiry diasumsikan mengikat event ini. Review manusia tetap wajib.</p><div class="dialog-section-label">Tag kebutuhan operasional (sesuai scope nyata)</div><div class="tag-checkboxes">${Object.entries(
      TAG_LABELS,
    )
      .map(
        ([tag, label]) =>
          `<label><input type="checkbox" name="tags" value="${tag}"${item.tags.includes(tag) ? " checked" : ""}>${label}</label>`,
      )
      .join("")}</div>`,
    async (form) => {
      const data = new FormData(form),
        next = clone(state.project),
        updated = clone(item);
      for (const key of [
        "name",
        "category",
        "unit",
        "kind",
        "priority",
        "quantityBasis",
        "durationBasis",
        "confidence",
        "vendor",
        "reference",
      ])
        updated[key] = data.get(key);
      for (const key of ["quantity", "duration", "unitPrice", "advancePercent"])
        updated[key] = Number(data.get(key));
      for (const key of ["verifiedAt", "validUntil"])
        updated[key] = data.get(key) || null;
      updated.tags = data.getAll("tags");
      if (existing)
        next.items[next.items.findIndex((i) => i.id === item.id)] = updated;
      else next.items.push(updated);
      if (updated.kind === "overhead" && next.finance.overheadPercent) {
        if (
          !confirm(
            "Overhead dirinci per baris. Set alokasi overhead menjadi 0% agar tidak dihitung dua kali?",
          )
        )
          return;
        next.finance.overheadPercent = 0;
      }
      await validateAndReplace(next);
      closeDialog();
      toast("Item biaya disimpan dan semua agent dihitung ulang.");
    },
  );
}

function chooseTemplate(templateId) {
  const template = state.bootstrap.templates.find((t) => t.id === templateId);
  if (!template) return;
  if (
    !confirm(
      "Buat proyek baru dari template? RAB aktif diganti. Export JSON terlebih dahulu jika ingin menyimpan proyek lama. Riwayat realisasi dan audit tetap dibawa.",
    )
  ) {
    renderProject();
    return;
  }
  clearTimeout(state.timer);
  state.controller?.abort();
  const previous = state.project;
  state.project = clone(template.project);
  state.project.event.id = uid();
  state.project.observations = clone(previous.observations);
  state.project.audit = clone(previous.audit);
  state.report = null;
  state.revision++;
  state.dirty = true;
  state.error = "";
  $("#content").innerHTML =
    '<div class="loading-card"><span class="loading-star">✳</span><h2>Menghitung proyek baru</h2><p>Riwayat tetap tersimpan; harga template masih ilustrasi.</p></div>';
  renderProject();
  runAnalysis(true);
}

function exportDialog() {
  openDialog(
    "Export & backup proyek",
    `<p class="dialog-description">RAB internal memuat biaya dan margin. Draft penawaran menyembunyikan HPP internal, tetapi tetap diberi label belum disetujui.</p><div class="export-options"><button class="export-option" type="button" data-export="csv">${icon("list")}<span><strong>RAB internal · CSV</strong><small>Baris biaya, HPP, cadangan, harga, dan margin.</small></span>${icon("arrow")}</button><button class="export-option" type="button" data-export="proposal">${icon("file")}<span><strong>Draft penawaran · HTML / cetak PDF</strong><small>Scope + total invoice. Buka file lalu cetak dari browser.</small></span>${icon("arrow")}</button><button class="export-option" type="button" data-export="json">${icon("download")}<span><strong>Backup workspace · JSON</strong><small>Input, observasi, audit lokal, dan snapshot kalkulasi.</small></span>${icon("arrow")}</button></div><div class="export-option-row"><button class="button secondary" type="button" id="import-trigger">${icon("upload")}Import backup JSON</button></div>`,
    null,
  );
}

function download(blob, name) {
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

async function exportProject(format) {
  if (state.dirty || !state.report)
    if (!(await runAnalysis())) {
      toast("Perbaiki input sebelum export.", true);
      return;
    }
  const snapshot = clone(state.project);
  if (format === "json") {
    download(
      new Blob(
        [
          JSON.stringify(
            { schemaVersion: 1, project: snapshot, report: state.report },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      ),
      "panggung-workspace.json",
    );
  } else {
    const response = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: snapshot, format }),
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error);
    }
    download(
      await response.blob(),
      format === "csv" ? "rab-internal.csv" : "draft-penawaran.html",
    );
  }
  toast(
    format === "proposal"
      ? "Draft diunduh. Buka file HTML untuk cetak / simpan PDF; review sebelum dikirim."
      : "Export berhasil diunduh.",
  );
  if ($("#workspace-dialog").open) closeDialog();
}

async function archiveActuals() {
  const items = state.project.items.filter((i) => i.actualUnitPrice !== null);
  if (!items.length) return;
  if (
    !confirm(
      `Catat ${items.length} tarif satuan realisasi yang sudah diverifikasi? Ini bukan mencatat estimasi. Event ID yang sama tidak menambah sampel.`,
    )
  )
    return;
  const next = clone(state.project),
    event = next.event;
  const ids = new Set(items.map((i) => i.id));
  next.observations = next.observations.filter(
    (o) => !(o.eventId === event.id && ids.has(o.itemId)),
  );
  for (const item of items)
    next.observations.push({
      itemId: item.id,
      eventId: event.id,
      eventType: event.type,
      city: event.city,
      unit: item.unit,
      specification: item.name,
      unitPrice: item.actualUnitPrice,
      recordedAt: state.report.asOf,
    });
  await validateAndReplace(next);
  toast(
    `${items.length} realisasi dicatat. Usulan tetap perlu minimal 3 event dan review.`,
  );
}

async function applyLearning(itemId) {
  if (state.dirty && !(await runAnalysis())) return;
  const proposal = state.report.learning.proposals.find(
    (p) => p.itemId === itemId,
  );
  if (!proposal?.eligible) return;
  if (
    !confirm(
      `Setujui estimasi ${proposal.name}: ${rp(proposal.previousPrice)} → ${rp(proposal.proposedPrice)} berdasarkan ${proposal.sampleCount} event? Quote lama akan dibatalkan; tarif baru tetap estimasi.`,
    )
  )
    return;
  const revision = state.revision;
  const result = await fetchJSON("/api/learning/apply", {
    project: clone(state.project),
    proposalIds: [proposal.id],
  });
  if (revision !== state.revision)
    throw new Error(
      "Input berubah saat review. Hitung ulang dan tinjau proposal baru.",
    );
  state.project = result.project;
  state.report = result.report;
  state.revision++;
  state.dirty = false;
  save();
  render();
  toast(
    "Revisi tarif disetujui. Audit lokal ditambahkan; tarif masih estimasi.",
  );
}

async function researchVendors(form) {
  if (state.researchBusy || !state.bootstrap.researchEnabled) return;
  const query = $("#research-query", form).value.trim();
  const city = state.project.event.city;
  state.researchBusy = true;
  try {
    const button = $("button", form);
    button.disabled = true;
    button.textContent = "Mencari…";
    state.research = await fetchJSON("/api/market/search", { query, city });
    if (state.tab === "learning") render();
    toast(
      "Referensi ditemukan. Verifikasi quote; tidak ada tarif yang diubah.",
    );
  } finally {
    state.researchBusy = false;
    if (state.tab === "learning") render();
  }
}

document.addEventListener("click", async (event) => {
  const node = event.target.closest("button,a[data-tab]");
  if (!node) return;
  try {
    if (node.dataset.tab) {
      event.preventDefault();
      setTab(node.dataset.tab);
    } else if (node.id === "run-agents") await runAnalysis(true);
    else if (node.id === "export-menu") exportDialog();
    else if (node.id === "mobile-menu") $("#sidebar").classList.toggle("open");
    else if (node.hasAttribute("data-close-dialog")) closeDialog();
    else if (node.hasAttribute("data-edit-brief")) editBrief();
    else if (node.hasAttribute("data-add-item")) editItem();
    else if (node.dataset.editItem) editItem(node.dataset.editItem);
    else if (node.dataset.agentDetail)
      setTab("agents", node.dataset.agentDetail);
    else if (node.dataset.export) await exportProject(node.dataset.export);
    else if (node.id === "import-trigger") $("#import-file").click();
    else if (node.dataset.deleteItem) {
      const item = state.project.items.find(
        (i) => i.id === node.dataset.deleteItem,
      );
      if (state.project.items.length === 1) {
        toast("RAB harus memiliki minimal satu item.", true);
        return;
      }
      if (
        !confirm(
          `Hapus ${item.name}?${item.priority === "essential" || item.category === "safety" ? " Item esensial/safety: pastikan kebutuhan sudah dialihkan, bukan dihilangkan demi budget." : ""}`,
        )
      )
        return;
      state.project.items = state.project.items.filter((i) => i.id !== item.id);
      markDirty();
      await runAnalysis();
    } else if (node.dataset.scenario) {
      state.project.finance.offerPrice = state.report.pricing.scenarios.find(
        (s) => s.id === node.dataset.scenario,
      ).price;
      markDirty();
      await runAnalysis();
    } else if (node.hasAttribute("data-reset-offer")) {
      state.project.finance.offerPrice = 0;
      markDirty();
      await runAnalysis();
    } else if (node.id === "archive-actuals") await archiveActuals();
    else if (node.dataset.applyItem)
      await applyLearning(node.dataset.applyItem);
    else if (node.id === "new-project")
      openDialog(
        "Pilih titik awal proyek",
        `<p class="dialog-description">Semua harga template adalah angka ilustrasi, bukan tarif pasar 2026. Proyek baru mendapat ID unik; riwayat realisasi tetap dibawa.</p><div class="export-options">${state.bootstrap.templates.map((t) => `<button type="button" class="export-option" data-template="${t.id}">${icon("file")}<span><strong>${esc(t.label)}</strong><small>${t.project.event.attendees} peserta · ${t.project.event.eventDays} hari event · budget ${rp(t.project.finance.clientBudget)}</small></span>${icon("arrow")}</button>`).join("")}</div>`,
        null,
      );
    else if (node.dataset.template) {
      closeDialog();
      chooseTemplate(node.dataset.template);
    }
  } catch (error) {
    toast(error.message, true);
  }
});

document.addEventListener("input", (event) => {
  const node = event.target;
  if (node.id === "rab-search") {
    state.rabQuery = node.value;
    render();
    return;
  }
  if (!state.project) return;
  if (node.dataset.finance && node.type === "number") {
    if (node.value !== "" && !Number.isFinite(Number(node.value))) return;
    state.project.finance[node.dataset.finance] =
      node.value === "" ? null : Number(node.value);
    if (
      ["vatPercent", "withholdingPercent", "withholdingBasePercent"].includes(
        node.dataset.finance,
      )
    )
      state.project.finance.taxVerified = false;
    markDirty();
  } else if (node.dataset.itemField) {
    const item = state.project.items.find((i) => i.id === node.dataset.itemId);
    if (!item) return;
    if (node.value === "" && node.dataset.itemField === "actualUnitPrice")
      item.actualUnitPrice = null;
    else if (node.value !== "" && Number.isFinite(Number(node.value)))
      item[node.dataset.itemField] = Number(node.value);
    else if (node.value === "") item[node.dataset.itemField] = null;
    else return;
    if (
      ["unitPrice", "quantity", "duration"].includes(node.dataset.itemField)
    ) {
      item.confidence = "estimate";
      item.verifiedAt = null;
      item.validUntil = null;
    }
    if (node.dataset.itemField === "quantity") item.quantityBasis = "fixed";
    if (node.dataset.itemField === "duration") item.durationBasis = "fixed";
    markDirty();
  }
});

document.addEventListener("change", async (event) => {
  const node = event.target;
  try {
    if (node.id === "rab-category") {
      state.rabCategory = node.value;
      render();
    } else if (node.id === "template-picker") chooseTemplate(node.value);
    else if (node.dataset.finance && node.type !== "number") {
      let value = node.type === "checkbox" ? node.checked : node.value;
      if (node.dataset.finance === "rounding") value = Number(value);
      state.project.finance[node.dataset.finance] = value;
      if (node.dataset.finance === "taxStatus") {
        state.project.finance.taxVerified = false;
        if (value === "non_pkp") state.project.finance.vatPercent = 0;
      }
      if (
        ["vatPercent", "withholdingPercent", "withholdingBasePercent"].includes(
          node.dataset.finance,
        )
      )
        state.project.finance.taxVerified = false;
      markDirty();
      await runAnalysis();
    } else if (node.id === "import-file" && node.files[0]) {
      const file = node.files[0];
      if (file.size > 1048576) throw new Error("Backup maksimal 1 MB.");
      const loaded = JSON.parse(await file.text()),
        next = loaded.project || loaded;
      if (
        !confirm(
          "Ganti proyek aktif dengan backup ini? Kalkulasi akan divalidasi ulang; hasil lama dari file tidak dipercaya.",
        )
      )
        return;
      await validateAndReplace(next);
      closeDialog();
      toast("Backup diimport dan seluruh kalkulasi dihitung ulang.");
    }
  } catch (error) {
    toast(error.message, true);
  } finally {
    if (node.id === "import-file") node.value = "";
  }
});

$("#dialog-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.dialogSubmit) return;
  $("#dialog-submit").disabled = true;
  $("#dialog-error").classList.add("hidden");
  try {
    await state.dialogSubmit(event.target);
  } catch (error) {
    $("#dialog-error").textContent = error.message;
    $("#dialog-error").classList.remove("hidden");
  } finally {
    $("#dialog-submit").disabled = false;
  }
});

document.addEventListener("submit", async (event) => {
  if (event.target.id !== "research-form") return;
  event.preventDefault();
  try {
    await researchVendors(event.target);
  } catch (error) {
    toast(error.message, true);
  }
});

$("#workspace-dialog").addEventListener("click", (event) => {
  if (event.target !== $("#workspace-dialog")) return;
  const box = event.target.getBoundingClientRect();
  if (
    event.clientX < box.left ||
    event.clientX > box.right ||
    event.clientY < box.top ||
    event.clientY > box.bottom
  )
    closeDialog();
});

window.addEventListener("hashchange", () => {
  if (TABS.includes(location.hash.slice(1))) setTab(location.hash.slice(1));
});
window.addEventListener("beforeunload", (event) => {
  if (state.dirty) {
    event.preventDefault();
    event.returnValue = "";
  }
});

async function initialize() {
  try {
    state.bootstrap = await fetchJSON("/api/bootstrap");
    let restored;
    try {
      restored = JSON.parse(localStorage.getItem(STORAGE) || "null");
    } catch {
      /* Recover below. */
    }
    state.project = restored || clone(state.bootstrap.templates[0].project);
    if (!restored) state.project.event.id = uid();
    if (!(await runAnalysis())) {
      if (!restored)
        throw new Error(state.error || "Workspace gagal dihitung.");
      state.project = clone(state.bootstrap.templates[0].project);
      state.project.event.id = uid();
      state.revision++;
      toast(
        "Backup browser tidak valid; workspace dibuka dari template. Import backup valid jika tersedia.",
        true,
      );
      if (!(await runAnalysis()))
        throw new Error(state.error || "Workspace gagal dihitung.");
    }
  } catch (error) {
    $("#content").innerHTML =
      `<div class="loading-card"><h2>Workspace belum dapat dibuka</h2><p>${esc(error.message)}</p><button class="button secondary spaced-top" id="reload-workspace">Muat ulang</button></div>`;
    $("#reload-workspace").addEventListener("click", () => location.reload());
  }
}

initialize();
