/* ═══════════════════════════════════════════════════
   Meesho OMS — Frontend JavaScript
═══════════════════════════════════════════════════ */

const API = "";   // same origin

// ── State ────────────────────────────────────────
let charts = {};
let pendingItems = [];
let currentFileHash = "";

// ── Init ─────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setTodayDate();
  setDefaultDates();
  setupNav();
  setupDropZone();
  loadDashboard();
  loadDeadStock();
  loadCategories();
  checkLogin();
});

function setTodayDate() {
  const d = new Date();
  document.getElementById("todayDate").textContent =
    d.toLocaleDateString("en-IN", { day:"numeric", month:"short", year:"numeric" });
}

function setDefaultDates() {
  const today = new Date();
  const monthAgo = new Date(today); monthAgo.setMonth(today.getMonth() - 1);
  document.getElementById("filterFrom").value = fmt(monthAgo);
  document.getElementById("filterTo").value   = fmt(today);

  const today2 = fmt(today);
  ["moDate","scDate","pkgDate","dailyDate","purDate"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = today2;
  });
}

function fmt(d) {
  return d.toISOString().slice(0,10);
}

// ── Navigation ────────────────────────────────────
function setupNav() {
  document.querySelectorAll("[data-page]").forEach(link => {
    link.addEventListener("click", e => {
      e.preventDefault();
      const page = link.dataset.page;
      document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
      link.classList.add("active");
      document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
      document.getElementById("page-" + page).classList.add("active");
      document.getElementById("pageTitle").textContent =
        link.querySelector("span").textContent;
      // Lazy-load
      if (page === "orders") loadOrders();
      if (page === "stock")  loadStock();
      if (page === "logs")   loadLogs();
      if (page === "packaging") loadPackaging();
      if (page === "payments")  loadPayments();
      if (page === "daily") loadDailySummary();
      if (page === "suppliers") loadSuppliers();
      // Close mobile sidebar
      document.getElementById("sidebar").classList.remove("open");
    });
  });

  document.getElementById("sidebarToggle").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });
}

// ── Toast ─────────────────────────────────────────
function toast(msg, type="success") {
  const el = document.getElementById("toastMsg");
  el.className = `toast align-items-center border-0 text-bg-${type==="error"?"danger":type==="warn"?"warning":"success"}`;
  document.getElementById("toastBody").textContent = msg;
  bootstrap.Toast.getOrCreateInstance(el, {delay:3500}).show();
}

// ── Dashboard ─────────────────────────────────────
async function loadDashboard() {
  const from = document.getElementById("filterFrom").value;
  const to   = document.getElementById("filterTo").value;
  const cat  = document.getElementById("filterCategory").value;

  let qs = `?date_from=${from}&date_to=${to}&category=${cat}`;
  const [metrics, predict, alerts] = await Promise.all([
    fetch(`${API}/api/dashboard/metrics${qs}`).then(r=>r.json()),
    fetch(`${API}/api/dashboard/predict`).then(r=>r.json()),
    fetch(`${API}/api/dashboard/alerts`).then(r=>r.json()),
  ]);

  // ── Alerts Bar ──────────────────────────────────
  const alertsBar = document.getElementById("alertsBar");
  let alertHtml = "";

  if (alerts.low_stock && alerts.low_stock.length > 0) {
    alerts.low_stock.forEach(item => {
      alertHtml += `
        <div class="alert-strip alert-red">
          <i class="bi bi-exclamation-triangle-fill me-2"></i>
          <strong>Low Stock:</strong> ${item.item_name} — sirf <strong>${item.qty}</strong> bacha hai!
        </div>`;
    });
  }

  if (alerts.low_packaging && alerts.low_packaging.length > 0) {
    alerts.low_packaging.forEach(item => {
      alertHtml += `
        <div class="alert-strip alert-orange">
          <i class="bi bi-box-seam me-2"></i>
          <strong>Packaging Kam:</strong> ${item.item_name} — sirf <strong>${item.qty}</strong> bacha!
        </div>`;
    });
  }

  if (alerts.pending_payments > 0) {
    alertHtml += `
      <div class="alert-strip alert-blue">
        <i class="bi bi-cash-coin me-2"></i>
        <strong>${alerts.pending_payments}</strong> orders ka payment Meesho se aana baaki hai!
        <a href="#" onclick="document.querySelector('[data-page=payments]').click()" class="ms-2 fw-600">Dekho →</a>
      </div>`;
  }

  alertsBar.innerHTML = alertHtml;

  // KPIs
// KPIs
document.getElementById("kpiOrders").textContent     = metrics.total_orders || 0;
document.getElementById("kpiReturns").textContent    = metrics.return_orders || 0;
document.getElementById("kpiRevenue").textContent    = "₹" + fmtNum(metrics.total_revenue || 0);
document.getElementById("kpiProfit").textContent     = "₹" + fmtNum(metrics.profit || 0);
document.getElementById("kpiRealProfit").textContent = "₹" + fmtNum(metrics.real_profit || 0);
document.getElementById("kpiCommission").textContent = "₹" + fmtNum((metrics.total_commission||0) + (metrics.total_tds||0));

// Profit Breakdown
document.getElementById("bkRevenue").textContent    = "₹" + fmtNum(metrics.total_revenue || 0);
document.getElementById("bkCost").textContent       = "₹" + fmtNum(metrics.total_cost || 0);
document.getElementById("bkCommission").textContent = "₹" + fmtNum((metrics.total_commission||0) + (metrics.total_tds||0));
document.getElementById("bkPackaging").textContent  = "₹" + fmtNum(metrics.packaging_cost || 0);
const rp = metrics.real_profit || 0;
const rpEl = document.getElementById("bkRealProfit");
rpEl.textContent = "₹" + fmtNum(rp);
rpEl.className = "breakdown-val " + (rp >= 0 ? "text-success" : "text-danger");

  // Charts
  renderBarChart("chartCategory",
    (metrics.orders_by_category||[]).map(r=>r.category),
    (metrics.orders_by_category||[]).map(r=>r.total_orders),
    "Orders"
  );
  renderLineChart("chartDate",
    (metrics.orders_by_date||[]).map(r=>r.date_label),
    (metrics.orders_by_date||[]).map(r=>r.total_orders),
    "Daily Orders"
  );
  // Best Selling + Revenue by Category
    loadBestSelling();
    renderRevenueChart("chartRevCategory", metrics.orders_by_category||[]);
    renderPredictChart("chartPredict", predict||[]);
}

async function loadCategories() {
  const cats = await fetch(`${API}/api/dashboard/categories`).then(r=>r.json()).catch(()=>[]);
  const sel  = document.getElementById("filterCategory");
  cats.forEach(c => {
    const opt = document.createElement("option"); opt.value = c; opt.textContent = c;
    sel.appendChild(opt);
  });
}

// ── Charts ────────────────────────────────────────
const CHART_COLORS = [
  "#E8553E","#4A7CF7","#2ECC8B","#F5A623","#9B59B6",
  "#1ABC9C","#E74C3C","#3498DB","#F39C12","#27AE60"
];

function renderBarChart(id, labels, data, label) {
  if (charts[id]) charts[id].destroy();
  const ctx = document.getElementById(id).getContext("2d");
  charts[id] = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label,
        data,
        backgroundColor: CHART_COLORS.slice(0, labels.length),
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: "#F0EDE9" } }
      },
      responsive: true,
    }
  });
}

function renderLineChart(id, labels, data, label) {
  if (charts[id]) charts[id].destroy();
  const ctx = document.getElementById(id).getContext("2d");
  charts[id] = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label,
        data,
        borderColor: "#4A7CF7",
        backgroundColor: "rgba(74,124,247,.08)",
        tension: 0.4,
        fill: true,
        pointRadius: 4,
        pointHoverRadius: 6,
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: "#F0EDE9" } }
      },
      responsive: true,
    }
  });
}

function renderPredictChart(id, predictions) {
  if (charts[id]) charts[id].destroy();
  if (!predictions.length) return;
  const ctx = document.getElementById(id).getContext("2d");
  const colorMap = { high: "#2ECC8B", medium: "#F5A623", low: "#E8553E" };
  charts[id] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: predictions.map(p=>p.category),
      datasets: [{
        label: "Predicted Orders (Next Month)",
        data: predictions.map(p=>p.predicted_qty),
        backgroundColor: predictions.map(p => colorMap[p.confidence] || "#4A7CF7"),
        borderRadius: 6,
        borderSkipped: false,
      }]
    },
    options: {
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: (ctx2) => {
              const conf = predictions[ctx2.dataIndex]?.confidence;
              return `Confidence: ${conf}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: "#F0EDE9" } }
      },
      responsive: true,
    }
  });
}

// ── Orders ────────────────────────────────────────
async function loadOrders() {
  const rows = await fetch(`${API}/api/orders`).then(r=>r.json()).catch(()=>[]);
  const tbody = document.getElementById("ordersBody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="text-center text-muted py-4">Koi order nahi.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="mono text-muted">${r.id}</td>
      <td>${r.date}</td>
      <td>${r.category}</td>
      <td class="fw-500">${r.item_name}</td>
      <td>${r.qty}</td>
      <td>₹${fmtNum(r.sell_price)}</td>
      <td class="fw-600">₹${fmtNum(r.total_amount)}</td>
      <td class="text-success fw-600">₹${fmtNum(r.net_payment||0)}</td>
      <td>${r.is_return
        ? `<span class="badge-return">Return</span>`
        : `<span class="badge-sale">Sale</span>`}</td>
      <td>${r.return_reason
        ? `<span class="return-reason-badge">${r.return_reason}</span>`
        : `<span class="text-muted">—</span>`}</td>
      <td><button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deleteOrder(${r.id})"><i class="bi bi-trash3"></i></button></td>
    </tr>
  `).join("");
}

async function deleteOrder(id) {
  if (!confirm("Delete this order and restore stock?")) return;
  const res = await fetch(`${API}/api/orders/${id}`, {method:"DELETE"});
  if (res.ok) { toast("Order deleted"); loadOrders(); }
  else toast("Error deleting order","error");
}

function exportOrders() { window.location = `${API}/api/orders/export`; }

// ── Stock ─────────────────────────────────────────
async function loadStock() {
  const rows = await fetch(`${API}/api/stock`).then(r=>r.json()).catch(()=>[]);
  const tbody = document.getElementById("stockBody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No stock entries.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="mono text-muted">${r.id}</td>
      <td>${r.category}</td>
      <td class="fw-500">${r.item_name}</td>
      <td class="fw-700 ${r.qty<=5?"text-danger":r.qty<=20?"text-warning":""}">${r.qty}</td>
      <td>₹${fmtNum(r.cost_per_product)}</td>
      <td>₹${fmtNum(r.total_cost)}</td>
      <td>${r.date}</td>
      <td><button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deleteStock(${r.id})"><i class="bi bi-trash3"></i></button></td>
    </tr>
  `).join("");
}

async function addStock() {
  const body = {
    category:         document.getElementById("scCategory").value.trim(),
    item_name:        document.getElementById("scItem").value.trim(),
    qty:              parseInt(document.getElementById("scQty").value),
    cost_per_product: parseFloat(document.getElementById("scCost").value),
    date:             document.getElementById("scDate").value,
  };
  if (!body.category || !body.item_name || !body.qty || !body.cost_per_product) {
    showStatus("stockStatus","Please fill all fields","warn"); return;
  }
  const res  = await fetch(`${API}/api/stock`, {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  const data = await res.json();
  if (res.ok) {
    toast(`Stock ${data.action} successfully`);
    showStatus("stockStatus","Stock saved ✓","success");
    loadStock();
  } else {
    showStatus("stockStatus", data.error||"Error","error");
  }
}

async function deleteStock(id) {
  if (!confirm("Delete this stock entry?")) return;
  await fetch(`${API}/api/stock/${id}`, {method:"DELETE"});
  toast("Stock entry deleted"); loadStock();
}

function exportStock() { window.location = `${API}/api/stock/export`; }

// ── Manual Order ──────────────────────────────────
async function submitManualOrder() {
  const isReturn = document.getElementById("moReturn").checked;
  const body = {
    category:      document.getElementById("moCategory").value.trim(),
    item_name:     document.getElementById("moItem").value.trim(),
    qty:           parseInt(document.getElementById("moQty").value),
    sell_price:    parseFloat(document.getElementById("moPrice").value),
    date:          document.getElementById("moDate").value,
    is_return:     isReturn,
    return_reason: isReturn ? document.getElementById("moReturnReason").value : "",
  };
  if (!body.category || !body.item_name || !body.qty || !body.sell_price) {
    showStatus("manualOrderStatus","Sab fields bharo","warn"); return;
  }
  if (isReturn && !body.return_reason) {
    showStatus("manualOrderStatus","Return reason select karo","warn"); return;
  }
  const res  = await fetch(`${API}/api/orders`, {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  const data = await res.json();
  if (res.ok) {
    toast("Order saved ✅");
    showStatus("manualOrderStatus","Order saved ✓","success");
    // Reset form
    document.getElementById("moReturn").checked = false;
    document.getElementById("returnReasonBox").style.display = "none";
  } else {
    showStatus("manualOrderStatus", data.error||"Error","error");
  }
}
// ── OCR Upload ────────────────────────────────────
function setupDropZone() {
  const dz = document.getElementById("dropZone");
  const fi = document.getElementById("fileInput");

  dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("drag-over"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag-over"));
  dz.addEventListener("drop", e => {
    e.preventDefault(); dz.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });
  fi.addEventListener("change", () => { if (fi.files[0]) uploadFile(fi.files[0]); });
}

async function uploadFile(file) {
  const status = document.getElementById("uploadStatus");
  const review = document.getElementById("reviewPanel");
  status.innerHTML = `<div class="upload-spinner"><div class="spinner-border spinner-border-sm text-primary"></div> Processing OCR…</div>`;
  review.innerHTML = `<div class="empty-state"><i class="bi bi-hourglass-split"></i><p>Extracting data…</p></div>`;

  const fd = new FormData(); fd.append("file", file);
  const res  = await fetch(`${API}/api/ocr/upload`, { method:"POST", body:fd });
  const data = await res.json();

  if (!res.ok) {
    status.innerHTML = `<div class="alert alert-danger py-2">${data.error||"Upload failed"}</div>`;
    review.innerHTML = `<div class="empty-state text-danger"><i class="bi bi-exclamation-triangle"></i><p>${data.error||"Error"}</p></div>`;
    return;
  }

  const conf = data.confidence || 0;
  const confClass = conf >= 75 ? "conf-high" : conf >= 45 ? "conf-medium" : "conf-low";
  const confFill  = conf >= 75 ? "conf-high-fill" : conf >= 45 ? "conf-medium-fill" : "conf-low-fill";

  status.innerHTML = `
    <div class="conf-bar-wrap">
      <div class="conf-bar-label">OCR Confidence: ${conf}%</div>
      <div class="conf-bar"><div class="conf-bar-fill ${confFill}" style="width:${conf}%"></div></div>
    </div>
    <div class="text-muted" style="font-size:12px">Found <strong>${data.items.length}</strong> item(s). Review below.</div>
  `;

  pendingItems  = data.items;
  currentFileHash = data.file_hash;

  if (!pendingItems.length) {
    review.innerHTML = `<div class="empty-state"><i class="bi bi-exclamation-circle"></i><p>No items could be extracted. Try a clearer image.</p></div>`;
    return;
  }

  review.innerHTML = `
    <div id="reviewItems">
      ${pendingItems.map((item, i) => `
        <div class="review-item" id="ri-${i}">
          <div class="d-flex justify-content-between align-items-start">
            <div class="item-name">${item.item_name}</div>
            <span class="confidence-badge ${item.confidence>=75?"conf-high":item.confidence>=45?"conf-medium":"conf-low"}">${item.confidence}%</span>
          </div>
          <div class="item-meta mt-1">
            <span class="me-3"><i class="bi bi-tag me-1"></i>
              <input type="text" value="${item.category}" class="inline-input" onchange="pendingItems[${i}].category=this.value"/>
            </span>
            <span class="me-3">Qty:
              <input type="number" value="${item.qty}" min="1" class="inline-input w-50px" onchange="pendingItems[${i}].qty=parseInt(this.value)"/>
            </span>
            <span class="me-3">₹
              <input type="number" value="${item.sell_price}" step="0.01" class="inline-input w-80px" onchange="pendingItems[${i}].sell_price=parseFloat(this.value)"/>
            </span>
            <span>Date:
              <input type="date" value="${item.date}" class="inline-input" onchange="pendingItems[${i}].date=this.value"/>
            </span>
          </div>
          ${item.matched_stock_name ? `<div class="mt-1" style="font-size:11px;color:#2ECC8B"><i class="bi bi-link-45deg"></i> Matched: <strong>${item.matched_stock_name}</strong> (${item.match_score}%)</div>` : `<div class="mt-1" style="font-size:11px;color:#E8553E"><i class="bi bi-exclamation-circle"></i> No stock match found — add stock first</div>`}
        </div>
      `).join("")}
    </div>
    <button class="btn btn-success w-100 mt-3" onclick="confirmOCROrder()">
      <i class="bi bi-check-circle-fill me-2"></i>Confirm & Save ${pendingItems.length} Item(s)
    </button>
  `;

  // Inline editable inputs style injection (if not already in CSS)
  if (!document.getElementById("inlineStyle")) {
    const s = document.createElement("style");
    s.id = "inlineStyle";
    s.textContent = `.inline-input{border:none;border-bottom:1px dashed #ccc;background:transparent;font-size:12px;font-family:inherit;outline:none;padding:0 2px;color:#1A1714}.w-50px{width:45px}.w-80px{width:70px}`;
    document.head.appendChild(s);
  }
}

async function confirmOCROrder() {
  if (!pendingItems.length) return;
  const items = pendingItems.map(item => ({
    ...item,
    item_name: item.matched_stock_name || item.item_name,
  }));
  const res  = await fetch(`${API}/api/orders/bulk`, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ items })
  });
  const data = await res.json();
  const created = data.created?.length || 0;
  const errors  = data.errors?.length  || 0;
  if (created > 0) {
    toast(`${created} order(s) saved!`);
    document.getElementById("reviewPanel").innerHTML = `<div class="empty-state text-success"><i class="bi bi-check-circle-fill"></i><p>${created} item(s) saved successfully.</p>${errors?`<p class="text-danger">${errors} failed.</p>`:""}</div>`;
    pendingItems = [];
  } else {
    toast(data.errors?.[0]?.reason || "Failed to save orders", "error");
  }
}

// ── Logs ──────────────────────────────────────────
async function loadLogs() {
  const rows = await fetch(`${API}/api/dashboard/logs`).then(r=>r.json()).catch(()=>[]);
  const tbody = document.getElementById("logsBody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">No logs yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="mono text-muted">${r.id}</td>
      <td>${r.filename||"—"}</td>
      <td><span class="badge ${r.status==="success"?"bg-success":"bg-danger"}">${r.status}</span></td>
      <td>${r.items_found}</td>
      <td class="text-muted">${new Date(r.created_at).toLocaleString("en-IN")}</td>
      <td class="text-danger" style="font-size:12px">${r.error_msg||""}</td>
    </tr>
  `).join("");
}

// ── Helpers ───────────────────────────────────────
function fmtNum(n) {
  return Number(n).toLocaleString("en-IN", {minimumFractionDigits:0, maximumFractionDigits:2});
}

function showStatus(id, msg, type) {
  const el = document.getElementById(id);
  const cls = type==="success"?"alert-success":type==="warn"?"alert-warning":"alert-danger";
  el.innerHTML = `<div class="alert ${cls} py-1 px-3 mt-1" style="font-size:13px">${msg}</div>`;
  setTimeout(() => el.innerHTML = "", 4000);
}
// ── Packaging ─────────────────────────────────────
async function loadPackaging() {
  const rows = await fetch(`${API}/api/dashboard/packaging`).then(r=>r.json()).catch(()=>[]);
  const tbody = document.getElementById("packagingBody");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No packaging items.</td></tr>`; return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td class="mono text-muted">${r.id}</td>
      <td class="fw-500">${r.item_name}</td>
      <td class="fw-700 ${r.qty <= r.low_stock_alert ? 'text-danger' : ''}">${r.qty} ${r.qty <= r.low_stock_alert ? '⚠️' : ''}</td>
      <td>₹${fmtNum(r.cost_per_unit)}</td>
      <td>₹${fmtNum(r.total_cost)}</td>
      <td>${r.low_stock_alert}</td>
      <td>${r.date}</td>
      <td><button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="deletePackaging(${r.id})"><i class="bi bi-trash3"></i></button></td>
    </tr>
  `).join("");
}

async function addPackaging() {
  const body = {
    item_name:       document.getElementById("pkgItem").value.trim(),
    qty:             parseInt(document.getElementById("pkgQty").value),
    cost_per_unit:   parseFloat(document.getElementById("pkgCost").value),
    low_stock_alert: parseInt(document.getElementById("pkgAlert").value) || 50,
    date:            document.getElementById("pkgDate").value,
  };
  if (!body.item_name || !body.qty || !body.cost_per_unit) {
    showStatus("packagingStatus","Sab fields bharo","warn"); return;
  }
  const res  = await fetch(`${API}/api/dashboard/packaging`, {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  const data = await res.json();
  if (res.ok) { toast(`Packaging ${data.action}!`); loadPackaging(); }
  else showStatus("packagingStatus", data.error||"Error","error");
}

async function deletePackaging(id) {
  if (!confirm("Delete karein?")) return;
  await fetch(`${API}/api/dashboard/packaging/${id}`, {method:"DELETE"});
  toast("Deleted"); loadPackaging();
}

// ── Payments ──────────────────────────────────────
async function loadPayments() {
  const [orders, summary] = await Promise.all([
    fetch(`${API}/api/orders?is_return=false`).then(r=>r.json()).catch(()=>[]),
    fetch(`${API}/api/dashboard/payment-summary`).then(r=>r.json()).catch(()=>({})),
  ]);

  // Summary cards
  document.getElementById("pendingAmt").textContent    = "₹" + fmtNum(summary.pending_amount  || 0);
  document.getElementById("receivedAmt").textContent   = "₹" + fmtNum(summary.received_amount || 0);
  document.getElementById("totalCommission").textContent = "₹" + fmtNum(summary.total_commission || 0);
  document.getElementById("totalTds").textContent      = "₹" + fmtNum(summary.total_tds || 0);

  // Pending orders table
  const pending = orders.filter(o => o.payment_status === "pending");
  const tbody   = document.getElementById("paymentsBody");
  if (!pending.length) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted py-4">Koi pending payment nahi! 🎉</td></tr>`; return;
  }
  tbody.innerHTML = pending.map(r => `
    <tr>
      <td class="mono text-muted">${r.id}</td>
      <td>${r.date}</td>
      <td class="fw-500">${r.item_name}</td>
      <td>${r.qty}</td>
      <td>₹${fmtNum(r.sell_price)}</td>
      <td class="text-danger">-₹${fmtNum(r.meesho_commission)}</td>
      <td class="text-danger">-₹${fmtNum(r.tds_amount)}</td>
      <td class="fw-700 text-success">₹${fmtNum(r.net_payment)}</td>
      <td><span class="badge-return">Pending</span></td>
      <td>
        <button class="btn btn-sm btn-success py-0 px-2" onclick="markPaymentReceived(${r.id})">
          <i class="bi bi-check-lg"></i> Received
        </button>
      </td>
    </tr>
  `).join("");
}

async function markPaymentReceived(id) {
  const res = await fetch(`${API}/api/orders/${id}/payment`, {
    method:"PUT", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({payment_status:"received"})
  });
  if (res.ok) { toast("Payment received mark hua! ✅"); loadPayments(); }
  else toast("Error","error");
}

// ── Return Reason ─────────────────────────────────
function toggleReturnReason() {
  const isReturn = document.getElementById("moReturn").checked;
  const box      = document.getElementById("returnReasonBox");
  box.style.display = isReturn ? "block" : "none";
}

// ── Best Selling ──────────────────────────────────
async function loadBestSelling() {
  const from = document.getElementById("filterFrom").value;
  const to   = document.getElementById("filterTo").value;
  const rows = await fetch(`${API}/api/dashboard/best-selling?date_from=${from}&date_to=${to}`)
                     .then(r=>r.json()).catch(()=>[]);

  const el = document.getElementById("bestSellingList");
  if (!rows.length) {
    el.innerHTML = `<div class="empty-state"><i class="bi bi-inbox"></i><p>Abhi koi data nahi</p></div>`;
    return;
  }

  const max = rows[0].total_qty;
  el.innerHTML = rows.map((r, i) => `
    <div class="best-item">
      <div class="best-rank ${i===0?'gold':i===1?'silver':i===2?'bronze':''}">${i+1}</div>
      <div class="best-info">
        <div class="best-name">${r.item_name}</div>
        <div class="best-bar-wrap">
          <div class="best-bar" style="width:${Math.round((r.total_qty/max)*100)}%"></div>
        </div>
      </div>
      <div class="best-stats">
        <div class="best-qty">${r.total_qty} sold</div>
        <div class="best-rev">₹${fmtNum(r.total_revenue)}</div>
      </div>
    </div>
  `).join("");
}

// ── Revenue by Category Pie Chart ─────────────────
function renderRevenueChart(id, data) {
  if (charts[id]) charts[id].destroy();
  if (!data.length) return;
  const ctx = document.getElementById(id).getContext("2d");
  charts[id] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: data.map(d => d.category),
      datasets: [{
        data: data.map(d => d.revenue),
        backgroundColor: CHART_COLORS.slice(0, data.length),
        borderWidth: 2,
        borderColor: "#fff",
      }]
    },
    options: {
      plugins: {
        legend: { position: "bottom", labels: { font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ₹${fmtNum(ctx.parsed)}`
          }
        }
      },
      responsive: true,
      cutout: "60%",
    }
  });
}

// ── Dead Stock ────────────────────────────────────
async function loadDeadStock() {
  const rows = await fetch(`${API}/api/dashboard/dead-stock?days=30`)
                     .then(r=>r.json()).catch(()=>[]);

  const section = document.getElementById("deadStockSection");
  const countEl = document.getElementById("deadStockCount");
  const tbody   = document.getElementById("deadStockBody");

  if (!rows.length) {
    section.style.display = "none";
    return;
  }

  section.style.display = "block";
  countEl.textContent   = rows.length;

  const today = new Date();
  tbody.innerHTML = rows.map(r => {
    const stockedDate = new Date(r.stocked_date);
    const lastSold    = r.last_sold_date ? new Date(r.last_sold_date) : null;
    const refDate     = lastSold || stockedDate;
    const daysIdle    = Math.floor((today - refDate) / (1000*60*60*24));
    const urgency     = daysIdle > 60 ? "text-danger fw-700" : daysIdle > 30 ? "text-warning fw-600" : "";

    return `
      <tr>
        <td class="mono text-muted">${r.id}</td>
        <td>${r.category}</td>
        <td class="fw-500">${r.item_name}</td>
        <td class="fw-700">${r.qty}</td>
        <td>₹${fmtNum(r.cost_per_product)}</td>
        <td class="fw-700 text-danger">₹${fmtNum(r.stuck_value)}</td>
        <td>${r.last_sold_date || '<span class="text-muted">Kabhi nahi</span>'}</td>
        <td>${r.stocked_date}</td>
        <td class="${urgency}">${daysIdle} din</td>
      </tr>
    `;
  }).join("");

  // Total stuck value alert
  const totalStuck = rows.reduce((sum, r) => sum + (r.stuck_value||0), 0);
  const alertsBar  = document.getElementById("alertsBar");
  alertsBar.innerHTML += `
    <div class="alert-strip alert-orange">
      <i class="bi bi-archive-fill me-2"></i>
      <strong>Dead Stock:</strong> ${rows.length} items — 
      ₹${fmtNum(totalStuck)} ka maal 30+ din se nahi bika!
      <a href="#" onclick="toggleDeadStock()" class="ms-2 fw-600">Dekho →</a>
    </div>`;
}

function toggleDeadStock() {
  const table = document.getElementById("deadStockTable");
  const eye   = document.getElementById("deadStockEye");
  const isOpen = table.style.display === "block";
  table.style.display = isOpen ? "none" : "block";
  eye.className = isOpen ? "bi bi-eye" : "bi bi-eye-slash";
}

// ── Daily Summary ─────────────────────────────────
async function loadDailySummary() {
  const date = document.getElementById("dailyDate").value;
  const data = await fetch(`${API}/api/dashboard/daily-summary?date=${date}`)
                     .then(r=>r.json()).catch(()=>null);
  if (!data) return;

  const t = data.today;
  const y = data.yesterday;

  // KPI Cards
  document.getElementById("dlyOrders").textContent     = t.total_orders || 0;
  document.getElementById("dlyReturns").textContent    = t.returns || 0;
  document.getElementById("dlyRevenue").textContent    = "₹" + fmtNum(t.revenue || 0);
  document.getElementById("dlyNetPay").textContent     = "₹" + fmtNum(t.net_payment || 0);
  document.getElementById("dlyItems").textContent      = t.items_sold || 0;
  document.getElementById("dlyCommission").textContent = "₹" + fmtNum(t.commission || 0);

  // Aaj vs Kal comparison
  document.getElementById("cmpTodayOrders").textContent = t.total_orders || 0;
  document.getElementById("cmpYestOrders").textContent  = y.total_orders || 0;
  document.getElementById("cmpTodayRev").textContent    = "₹" + fmtNum(t.revenue || 0);
  document.getElementById("cmpYestRev").textContent     = "₹" + fmtNum(y.revenue || 0);

  // Difference
  const diff    = (t.revenue||0) - (y.revenue||0);
  const diffEl  = document.getElementById("cmpDiff");
  const sign    = diff >= 0 ? "+" : "";
  const color   = diff >= 0 ? "text-success" : "text-danger";
  const icon    = diff >= 0 ? "bi-arrow-up-circle-fill" : "bi-arrow-down-circle-fill";
  diffEl.innerHTML = `
    <span class="compare-label">Change</span>
    <span class="compare-val ${color}">
      <i class="bi ${icon} me-1"></i>${sign}₹${fmtNum(Math.abs(diff))}
    </span>`;

  // Top Items
  const topEl = document.getElementById("dailyTopItems");
  if (!data.top_items.length) {
    topEl.innerHTML = `<div class="empty-state"><i class="bi bi-inbox"></i><p>No orders found</p></div>`;
  } else {
    topEl.innerHTML = data.top_items.map((item, i) => `
      <div class="best-item">
        <div class="best-rank ${i===0?'gold':i===1?'silver':i===2?'bronze':''}">${i+1}</div>
        <div class="best-info">
          <div class="best-name">${item.item_name}</div>
        </div>
        <div class="best-stats">
          <div class="best-qty">${item.qty} sold</div>
          <div class="best-rev">₹${fmtNum(item.revenue)}</div>
        </div>
      </div>
    `).join("");
  }

  // Weekly chart
  renderWeeklyChart(data.weekly);
}

function renderWeeklyChart(weekly) {
  if (charts["chartWeekly"]) charts["chartWeekly"].destroy();
  const ctx = document.getElementById("chartWeekly").getContext("2d");
  charts["chartWeekly"] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: weekly.map(w => w.date),
      datasets: [{
        label: "Orders",
        data:  weekly.map(w => w.orders),
        backgroundColor: "#4A7CF7",
        borderRadius: 6,
        borderSkipped: false,
      },{
        label: "Revenue",
        data:  weekly.map(w => w.revenue),
        backgroundColor: "#2ECC8B",
        borderRadius: 6,
        borderSkipped: false,
        yAxisID: "y2",
      }]
    },
    options: {
      plugins: { legend: { display: true, position: "bottom" } },
      scales: {
        x:  { grid: { display: false } },
        y:  { beginAtZero: true, grid: { color: "#F0EDE9" }, title: { display: true, text: "₹ Revenue" } },
        y2: { beginAtZero: true, position: "right", grid: { display: false }, title: { display: true, text: "₹ Revenue" } }
      },
      responsive: true,
    }
  });
}

// ── Suppliers ─────────────────────────────────────
async function loadSuppliers() {
  const [suppliers, purchases] = await Promise.all([
    fetch(`${API}/api/dashboard/suppliers`).then(r=>r.json()).catch(()=>[]),
    fetch(`${API}/api/dashboard/suppliers/purchases`).then(r=>r.json()).catch(()=>[]),
  ]);

  // Suppliers table
  const tbody = document.getElementById("suppliersBody");
  if (!suppliers.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-3">No suppliers yet</td></tr>`;
  } else {
    tbody.innerHTML = suppliers.map(s => `
      <tr>
        <td class="fw-600">${s.name}</td>
        <td>${s.phone||"—"}</td>
        <td>${s.category||"—"}</td>
        <td class="fw-700 ${s.pending_payment>0?'text-danger':'text-success'}">
          ₹${fmtNum(s.pending_payment)}
        </td>
        <td>₹${fmtNum(s.total_purchased)}</td>
        <td>
          <button class="btn btn-sm btn-outline-danger py-0 px-2"
            onclick="deleteSupplier(${s.id})">
            <i class="bi bi-trash3"></i>
          </button>
        </td>
      </tr>
    `).join("");
  }

  // Supplier dropdown
  const sel = document.getElementById("purSupplier");
  sel.innerHTML = `<option value="">Select Supplier</option>`;
  suppliers.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.id; opt.textContent = s.name;
    sel.appendChild(opt);
  });

  // Purchases table
  const ptbody = document.getElementById("purchasesBody");
  if (!purchases.length) {
    ptbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted py-4">No purchases yet</td></tr>`;
  } else {
    ptbody.innerHTML = purchases.map(p => `
      <tr>
        <td class="mono text-muted">${p.id}</td>
        <td>${p.date}</td>
        <td class="fw-600">${p.supplier_name||"—"}</td>
        <td>${p.item_name}</td>
        <td>${p.qty}</td>
        <td>₹${fmtNum(p.cost_per_unit)}</td>
        <td class="fw-700">₹${fmtNum(p.total_cost)}</td>
        <td class="text-success">₹${fmtNum(p.paid_amount)}</td>
        <td class="fw-700 ${p.pending>0?'text-danger':'text-success'}">
          ₹${fmtNum(p.pending)}
        </td>
        <td>
          ${p.pending > 0 ? `
            <button class="btn btn-sm btn-success py-0 px-2"
              onclick="paySupplier(${p.id}, ${p.pending})">
              Pay
            </button>` : `<span class="badge-sale">Paid</span>`}
        </td>
      </tr>
    `).join("");
  }
}

async function addSupplier() {
  const body = {
    name:     document.getElementById("supName").value.trim(),
    phone:    document.getElementById("supPhone").value.trim(),
    category: document.getElementById("supCategory").value.trim(),
    notes:    document.getElementById("supNotes").value.trim(),
  };
  if (!body.name) { showStatus("supplierStatus","Name required","warn"); return; }
  const res  = await fetch(`${API}/api/dashboard/suppliers`, {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  const data = await res.json();
  if (res.ok) { toast("Supplier added! ✅"); loadSuppliers(); }
  else showStatus("supplierStatus", data.error||"Error","error");
}

async function deleteSupplier(id) {
  if (!confirm("Delete this supplier?")) return;
  await fetch(`${API}/api/dashboard/suppliers/${id}`, {method:"DELETE"});
  toast("Supplier deleted"); loadSuppliers();
}

async function addPurchase() {
  const body = {
    supplier_id:   parseInt(document.getElementById("purSupplier").value),
    item_name:     document.getElementById("purItem").value.trim(),
    category:      document.getElementById("purCategory").value.trim(),
    qty:           parseInt(document.getElementById("purQty").value),
    cost_per_unit: parseFloat(document.getElementById("purCost").value),
    paid_amount:   parseFloat(document.getElementById("purPaid").value) || 0,
    date:          document.getElementById("purDate").value,
  };
  if (!body.supplier_id || !body.item_name || !body.qty || !body.cost_per_unit) {
    showStatus("purchaseStatus","Sab fields bharo","warn"); return;
  }
  const res  = await fetch(`${API}/api/dashboard/suppliers/purchases`, {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  const data = await res.json();
  if (res.ok) {
    toast("Purchase saved & Stock updated! ✅");
    showStatus("purchaseStatus", data.message, "success");
    loadSuppliers();
  } else {
    showStatus("purchaseStatus", data.error||"Error","error");
  }
}

async function paySupplier(pid, pending) {
  const amount = prompt(`Kitna pay karna hai? (Max: ₹${fmtNum(pending)})`, pending);
  if (!amount) return;
  const res = await fetch(`${API}/api/dashboard/suppliers/purchases/${pid}/pay`, {
    method:"PUT", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({amount: parseFloat(amount)})
  });
  if (res.ok) { toast("Payment recorded! ✅"); loadSuppliers(); }
  else toast("Error","error");
}

// Live calculation
["purQty","purCost","purPaid"].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener("input", updatePurCalc);
});

function updatePurCalc() {
  const qty     = parseFloat(document.getElementById("purQty").value) || 0;
  const cost    = parseFloat(document.getElementById("purCost").value) || 0;
  const paid    = parseFloat(document.getElementById("purPaid").value) || 0;
  const total   = qty * cost;
  const pending = total - paid;
  const el      = document.getElementById("purCalc");
  if (!el || !total) return;
  el.innerHTML = `
    <span class="me-3">Total: <strong>₹${fmtNum(total)}</strong></span>
    <span class="me-3 text-success">Paid: <strong>₹${fmtNum(paid)}</strong></span>
    <span class="${pending>0?'text-danger':'text-success'}">
      Pending: <strong>₹${fmtNum(pending)}</strong>
    </span>`;
}

// ── CSV Import ────────────────────────────────────
let csvFile = null;

document.addEventListener("DOMContentLoaded", () => {
  const csvInput   = document.getElementById("csvInput");
  const csvDropZone = document.getElementById("csvDropZone");

  if (csvInput) {
    csvInput.addEventListener("change", () => {
      if (csvInput.files[0]) setCsvFile(csvInput.files[0]);
    });
  }

  if (csvDropZone) {
    csvDropZone.addEventListener("dragover", e => {
      e.preventDefault();
      csvDropZone.classList.add("drag-over");
    });
    csvDropZone.addEventListener("dragleave", () => {
      csvDropZone.classList.remove("drag-over");
    });
    csvDropZone.addEventListener("drop", e => {
      e.preventDefault();
      csvDropZone.classList.remove("drag-over");
      const file = e.dataTransfer.files[0];
      if (file && file.name.endsWith(".csv")) setCsvFile(file);
      else toast("Only CSV files allowed", "error");
    });
  }
});

function setCsvFile(file) {
  csvFile = file;
  document.getElementById("csvFileName").textContent = file.name;
  document.getElementById("csvFileInfo").classList.remove("d-none");
  document.getElementById("csvImportBtn").disabled = false;
  showStatus("csvStatus",
    `File ready: ${file.name} (${(file.size/1024).toFixed(1)} KB)`,
    "success");
}

async function importCSV() {
  if (!csvFile) { toast("Pehle CSV file select karo", "error"); return; }

  const btn = document.getElementById("csvImportBtn");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>Importing…`;

  const fd = new FormData();
  fd.append("file", csvFile);

  const res  = await fetch(`${API}/api/orders/import-csv`, {
    method: "POST", body: fd
  });
  const data = await res.json();

  btn.disabled = false;
  btn.innerHTML = `<i class="bi bi-cloud-upload-fill me-2"></i>Import Orders`;

  if (res.ok) {
    toast(`✅ ${data.imported} orders imported!`);
    showStatus("csvStatus",
      `✅ Imported: ${data.imported} | ⏭️ Skipped: ${data.skipped} | ❌ Errors: ${data.errors}`,
      "success");
    csvFile = null;
    document.getElementById("csvFileInfo").classList.add("d-none");
    document.getElementById("csvImportBtn").disabled = true;
  } else {
    showStatus("csvStatus", data.error || "Import failed", "error");
    toast("Import failed", "error");
  }
}

// ── Auth ──────────────────────────────────────────
async function checkLogin() {
  const res  = await fetch("/api/auth/me").catch(()=>null);
  if (!res || !res.ok) {
    window.location.href = "/login";
    return;
  }
  const data = await res.json();
  if (!data.logged_in) {
    window.location.href = "/login";
    return;
  }
  const el = document.getElementById("topbarUser");
  if (el) el.textContent = data.full_name || data.username;
}

async function doLogout() {
  await fetch("/api/auth/logout", {method:"POST"});
  window.location.href = "/login";
}