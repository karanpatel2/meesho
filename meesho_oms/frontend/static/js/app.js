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
  loadCategories();
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
  ["moDate","scDate"].forEach(id => {
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
  const [metrics, predict] = await Promise.all([
    fetch(`${API}/api/dashboard/metrics${qs}`).then(r=>r.json()),
    fetch(`${API}/api/dashboard/predict`).then(r=>r.json()),
  ]);

  // KPIs
  document.getElementById("kpiOrders").textContent  = metrics.total_orders || 0;
  document.getElementById("kpiReturns").textContent = metrics.return_orders || 0;
  document.getElementById("kpiRevenue").textContent = "₹" + fmtNum(metrics.total_revenue || 0);
  document.getElementById("kpiProfit").textContent  = "₹" + fmtNum(metrics.profit || 0);

  // Chart: Orders by Category
  renderBarChart("chartCategory",
    (metrics.orders_by_category||[]).map(r=>r.category),
    (metrics.orders_by_category||[]).map(r=>r.total_orders),
    "Orders"
  );

  // Chart: Orders by Date
  renderLineChart("chartDate",
    (metrics.orders_by_date||[]).map(r=>r.date_label),
    (metrics.orders_by_date||[]).map(r=>r.total_orders),
    "Daily Orders"
  );

  // Chart: Predictions
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
    tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted py-4">No orders found.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((r,i) => `
    <tr>
      <td class="mono text-muted">${r.id}</td>
      <td>${r.date}</td>
      <td>${r.category}</td>
      <td class="fw-500">${r.item_name}</td>
      <td>${r.qty}</td>
      <td>₹${fmtNum(r.sell_price)}</td>
      <td class="fw-600">₹${fmtNum(r.total_amount)}</td>
      <td>${r.is_return
        ? `<span class="badge-return">Return</span>`
        : `<span class="badge-sale">Sale</span>`}</td>
      <td class="mono text-muted">${r.invoice_id||"—"}</td>
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
  const body = {
    category:   document.getElementById("moCategory").value.trim(),
    item_name:  document.getElementById("moItem").value.trim(),
    qty:        parseInt(document.getElementById("moQty").value),
    sell_price: parseFloat(document.getElementById("moPrice").value),
    date:       document.getElementById("moDate").value,
    is_return:  document.getElementById("moReturn").checked,
  };
  if (!body.category || !body.item_name || !body.qty || !body.sell_price) {
    showStatus("manualOrderStatus","Fill all fields","warn"); return;
  }
  const res  = await fetch(`${API}/api/orders`, {
    method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)
  });
  const data = await res.json();
  if (res.ok) {
    toast("Order saved"); showStatus("manualOrderStatus","Order saved ✓","success");
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
