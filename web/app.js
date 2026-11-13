function loadStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("campus_user") || "null");
  } catch (_) {
    localStorage.removeItem("campus_user");
    return null;
  }
}

const state = {
  token: localStorage.getItem("campus_token") || "",
  user: loadStoredUser(),
  products: [],
  detail: null,
  authMode: "login",
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const artMap = {
  教材: { icon: "▤", label: "TEXTBOOKS", color: "#e8f1ff" },
  数码: { icon: "⌁", label: "DIGITAL", color: "#f0e9ff" },
  生活: { icon: "⌂", label: "LIVING", color: "#fff0ca" },
  兴趣: { icon: "✦", label: "HOBBY", color: "#dff4ee" },
  服饰: { icon: "◌", label: "STYLE", color: "#ffe8e3" },
};

function artFor(category) {
  return artMap[category] || { icon: "✦", label: "CAMPUS", color: "#e8f1ff" };
}

function showToast(message, isError = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.classList.add("hidden"), 3100);
}

function openModal(id) {
  $("#" + id).classList.remove("hidden");
  document.body.classList.add("modal-open");
}

function closeModal(id) {
  $("#" + id).classList.add("hidden");
  if ($$(".modal-backdrop:not(.hidden)").length === 0) document.body.classList.remove("modal-open");
}

function authHeaders() {
  return state.token ? { Authorization: `Bearer ${state.token}` } : {};
}

async function request(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...authHeaders(),
    ...(options.headers || {}),
  };
  const response = await fetch(path, { ...options, headers });
  let payload = {};
  try { payload = await response.json(); } catch (_) { /* empty body */ }
  if (!response.ok) throw new Error(payload.error || "请求没有成功");
  return payload;
}

function saveSession(data) {
  state.token = data.token || "";
  state.user = data.user || null;
  if (state.token) localStorage.setItem("campus_token", state.token);
  if (state.user) localStorage.setItem("campus_user", JSON.stringify(state.user));
  updateProfileButton();
}

function clearSession() {
  state.token = "";
  state.user = null;
  localStorage.removeItem("campus_token");
  localStorage.removeItem("campus_user");
  updateProfileButton();
}

function updateProfileButton() {
  const button = $("#profile-button");
  if (!state.user) {
    button.textContent = "登录 / 注册";
    return;
  }
  const name = state.user.display_name || state.user.email.split("@")[0];
  button.textContent = name.length > 8 ? `${name.slice(0, 8)}…` : name;
  button.title = `${state.user.email} · ${state.user.role}`;
}

function setAuthMode(mode) {
  state.authMode = mode;
  $$(".auth-tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.authMode === mode));
  $(".register-only").classList.toggle("hidden", mode !== "register");
  $("#auth-title").textContent = mode === "register" ? "创建你的集市身份" : "加入拾光集市";
  $("#auth-submit").innerHTML = mode === "register" ? "注册并继续 <span>→</span>" : "登录并继续 <span>→</span>";
  $("#auth-hint").textContent = mode === "register" ? "已经有账号？切换到登录，马上继续。" : "首次使用？切换到注册，30 秒就能开始。";
}

function requireLogin(next) {
  if (!state.user) {
    openModal("auth-modal");
    setAuthMode("login");
    showToast("浏览可以游客身份进行，预约前请先登录");
    return;
  }
  next();
}

async function loadProducts() {
  const params = new URLSearchParams();
  const keyword = $("#keyword").value.trim();
  const category = $("#category").value;
  const min = $("#min-price").value.trim();
  const max = $("#max-price").value.trim();
  if (keyword) params.set("keyword", keyword);
  if (category) params.set("category", category);
  if (min) params.set("min", min);
  if (max) params.set("max", max);
  params.set("sort", $("#sort").value);
  params.set("page_size", "48");
  $("#result-count").textContent = "加载中";
  try {
    const data = await request(`/api/products?${params}`);
    state.products = data.items || [];
    renderProducts();
  } catch (error) {
    $("#result-count").textContent = "读取失败";
    showToast(error.message, true);
  }
}

function renderProducts() {
  const grid = $("#product-grid");
  const empty = $("#empty-state");
  $("#hero-count").textContent = state.products.length;
  $("#result-count").textContent = `${state.products.length} 件好物`;
  grid.innerHTML = "";
  empty.classList.toggle("hidden", state.products.length > 0);
  state.products.forEach((product, index) => {
    const art = artFor(product.category);
    const card = document.createElement("article");
    card.className = "product-card";
    card.innerHTML = `<div class="product-art" style="background:${art.color}"><span class="art-label">${art.label}</span><span class="art-symbol">${art.icon}</span></div><div class="product-info"><div class="product-topline"><span class="product-category">${escapeHtml(product.category)}</span><span>${escapeHtml(product.city)}</span></div><h3 title="${escapeHtml(product.title)}">${escapeHtml(product.title)}</h3><p>${escapeHtml(product.description)}</p><div class="product-bottom"><span class="product-price"><small>¥</small>${escapeHtml(product.price)}</span><button class="product-action" type="button" data-product-index="${index}">查看详情 →</button></div></div>`;
    card.querySelector(".product-action").addEventListener("click", () => openDetail(product));
    grid.appendChild(card);
  });
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" }[char]));
}

function openDetail(product) {
  state.detail = product;
  const art = artFor(product.category);
  $("#detail-art").style.background = art.color;
  $("#detail-art").innerHTML = `<span class="art-symbol">${art.icon}</span>`;
  $("#detail-category").textContent = product.category;
  $("#detail-title").textContent = product.title;
  $("#detail-price").textContent = `¥${product.price}`;
  $("#detail-description").textContent = product.description;
  $("#detail-condition").textContent = product.condition;
  $("#detail-city").textContent = product.city;
  $("#detail-status").textContent = product.status === "PUBLISHED" ? "可预约" : "已被预约";
  $("#detail-reserve").textContent = product.status === "PUBLISHED" ? "登录后预约 →" : "商品已被预约";
  $("#detail-reserve").disabled = product.status !== "PUBLISHED";
  openModal("detail-modal");
}

async function reserveDetail() {
  if (!state.detail) return;
  requireLogin(async () => {
    if (state.user.role !== "BUYER") { showToast("当前账号不是买家，请使用买家身份预约", true); return; }
    try {
      await request("/api/reservations", { method: "POST", body: JSON.stringify({ product_id: state.detail.product_id, idempotency_key: `web-${state.detail.product_id}-${Date.now()}` }) });
      closeModal("detail-modal");
      showToast("预约已提交，等待卖家确认");
      await loadProducts();
    } catch (error) { showToast(error.message, true); }
  });
}

function openSell() {
  requireLogin(() => {
    if (state.user.role !== "SELLER") { showToast("发布闲置需要使用卖家身份", true); return; }
    openModal("sell-modal");
  });
}

async function submitAuth(event) {
  event.preventDefault();
  const body = { email: $("#auth-email").value.trim(), password: $("#auth-password").value, display_name: $("#auth-name").value.trim(), role: $("#auth-role").value, phone: $("#auth-phone").value.trim() };
  try {
    const data = await request(state.authMode === "register" ? "/api/auth/register" : "/api/auth/login", { method: "POST", body: JSON.stringify(body) });
    saveSession(data); closeModal("auth-modal"); showToast(state.authMode === "register" ? "注册成功，欢迎加入拾光集市" : "登录成功，欢迎回来");
  } catch (error) { showToast(error.message, true); }
}

async function submitSell(event) {
  event.preventDefault();
  if (!state.user || state.user.role !== "SELLER") return;
  const body = { title: $("#sell-title-input").value.trim(), description: $("#sell-description").value.trim(), category: $("#sell-category").value, price: $("#sell-price").value, condition: $("#sell-condition").value.trim(), city: $("#sell-city").value.trim(), contact: $("#sell-contact").value.trim() };
  try {
    const product = await request("/api/products", { method: "POST", body: JSON.stringify(body) });
    await request(`/api/products/${product.item.product_id}/submit`, { method: "POST" });
    closeModal("sell-modal"); $("#sell-form").reset(); showToast("商品已提交审核，审核通过后会出现在集市");
  } catch (error) { showToast(error.message, true); }
}

function wireEvents() {
  updateProfileButton();
  $("#search-button").addEventListener("click", loadProducts); $("#refresh-button").addEventListener("click", loadProducts);
  ["#keyword", "#min-price", "#max-price"].forEach((selector) => $(selector).addEventListener("keydown", (event) => { if (event.key === "Enter") loadProducts(); }));
  $("#category").addEventListener("change", () => {
    $$(".category-pill").forEach((item) => item.classList.toggle("active", item.dataset.category === $("#category").value));
    loadProducts();
  }); $("#sort").addEventListener("change", loadProducts);
  $$(".category-pill").forEach((button) => button.addEventListener("click", () => { $$(".category-pill").forEach((item) => item.classList.remove("active")); button.classList.add("active"); $("#category").value = button.dataset.category; loadProducts(); }));
  $("#profile-button").addEventListener("click", () => { if (state.user) { if (window.confirm("退出当前账号吗？")) { clearSession(); showToast("已退出登录"); } } else openModal("auth-modal"); });
  $("#sell-button").addEventListener("click", openSell); $("#cta-sell").addEventListener("click", openSell); $("#auth-form").addEventListener("submit", submitAuth); $("#sell-form").addEventListener("submit", submitSell); $("#detail-reserve").addEventListener("click", reserveDetail);
  $$("[data-auth-mode]").forEach((tab) => tab.addEventListener("click", () => setAuthMode(tab.dataset.authMode))); $$("[data-close]").forEach((button) => button.addEventListener("click", () => closeModal(button.dataset.close)));
  $$(".modal-backdrop").forEach((backdrop) => backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeModal(backdrop.id); })); document.addEventListener("keydown", (event) => { if (event.key === "Escape") $$(".modal-backdrop:not(.hidden)").forEach((modal) => closeModal(modal.id)); });
}

setAuthMode("login"); wireEvents(); loadProducts();
