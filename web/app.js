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
  if (!response.ok) {
    if (response.status === 401 && state.token) clearSession();
    throw new Error(payload.error || "请求没有成功");
  }
  return payload;
}

function saveSession(data) {
  state.token = data.token || "";
  state.user = data.user || null;
  if (state.token) localStorage.setItem("campus_token", state.token);
  if (state.user) localStorage.setItem("campus_user", JSON.stringify(state.user));
  updateProfileButton();
  updateDetailAction();
}

function clearSession() {
  state.token = "";
  state.user = null;
  localStorage.removeItem("campus_token");
  localStorage.removeItem("campus_user");
  updateProfileButton();
  updateDetailAction();
}

function updateDetailAction() {
  if (!state.detail) return;
  const button = $("#detail-reserve");
  button.textContent = state.detail.status === "PUBLISHED" ? (state.user ? "立即预约 →" : "登录后预约 →") : "商品已被预约";
}

function updateProfileButton() {
  const button = $("#profile-button");
  const adminButton = $("#admin-button");
  if (!state.user) {
    button.textContent = "登录 / 注册";
    adminButton.classList.add("hidden");
    return;
  }
  const name = state.user.display_name || state.user.email.split("@")[0];
  button.textContent = name.length > 8 ? `${name.slice(0, 8)}…` : name;
  button.title = `${state.user.email} · ${state.user.role}`;
  adminButton.classList.toggle("hidden", state.user.role !== "ADMIN");
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
  updateDetailAction();
  $("#detail-reserve").disabled = product.status !== "PUBLISHED";
  openModal("detail-modal");
}

async function reserveDetail() {
  if (!state.detail) return;
  requireLogin(async () => {
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
    openModal("sell-modal");
  });
}

async function submitAuth(event) {
  event.preventDefault();
  const body = { email: $("#auth-email").value.trim(), password: $("#auth-password").value, display_name: $("#auth-name").value.trim(), phone: $("#auth-phone").value.trim() };
  try {
    const data = await request(state.authMode === "register" ? "/api/auth/register" : "/api/auth/login", { method: "POST", body: JSON.stringify(body) });
    saveSession(data); closeModal("auth-modal"); showToast(state.authMode === "register" ? "注册成功，欢迎加入拾光集市" : "登录成功，欢迎回来");
  } catch (error) { showToast(error.message, true); }
}

async function submitSell(event) {
  event.preventDefault();
  if (!state.user) return;
  const body = { title: $("#sell-title-input").value.trim(), description: $("#sell-description").value.trim(), category: $("#sell-category").value, price: $("#sell-price").value, condition: $("#sell-condition").value.trim(), city: $("#sell-city").value.trim(), contact: $("#sell-contact").value.trim() };
  try {
    const product = await request("/api/products", { method: "POST", body: JSON.stringify(body) });
    await request(`/api/products/${product.item.product_id}/submit`, { method: "POST" });
    closeModal("sell-modal"); $("#sell-form").reset(); showToast("商品已提交审核，审核通过后会出现在集市");
  } catch (error) { showToast(error.message, true); }
}

function profileStatus(status) {
  return ({ DRAFT: "草稿", PENDING_REVIEW: "待审核", PUBLISHED: "在售", RESERVED: "已预约", IN_TRANSACTION: "交易中", COMPLETED: "已完成", REJECTED: "已驳回", UNLISTED: "已下架", VIOLATION: "违规下架", ACTIVE: "进行中", CANCELLED: "已取消", CONFIRMED: "已确认" }[status] || status || "—");
}

function renderProfileProducts(items) {
  const list = $("#profile-products");
  if (!items.length) {
    list.innerHTML = '<p class="profile-empty">还没有发布商品，去发布一件闲置吧。</p>';
    return;
  }
  list.innerHTML = items.map((item) => `<article class="profile-list-item"><div><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.category)} · ¥${escapeHtml(item.price)}</small></div><span class="profile-status">${escapeHtml(profileStatus(item.status))}</span></article>`).join("");
}

async function renderProfileReservations(items) {
  const list = $("#profile-reservations");
  if (!items.length) {
    list.innerHTML = '<p class="profile-empty">还没有预约记录，去逛逛喜欢的商品吧。</p>';
    return;
  }
  const enriched = await Promise.all(items.map(async (item) => {
    try {
      const result = await request(`/api/products/${item.product_id}`);
      return { ...item, product: result.item };
    } catch (_) {
      return item;
    }
  }));
  list.innerHTML = enriched.map((item) => `<article class="profile-list-item"><div><strong>${escapeHtml(item.product?.title || item.product_id)}</strong><small>预约于 ${escapeHtml(item.created_at || "—")}</small></div><span class="profile-status">${escapeHtml(profileStatus(item.status))}</span></article>`).join("");
}

async function loadProfile() {
  if (!state.user) return;
  $("#profile-products").innerHTML = '<p class="profile-empty">正在加载商品</p>';
  $("#profile-reservations").innerHTML = '<p class="profile-empty">正在加载预约</p>';
  try {
    const [me, products, reservations] = await Promise.all([request("/api/me"), request("/api/seller/products"), request("/api/my/reservations")]);
    const user = me.user || state.user;
    state.user = user;
    localStorage.setItem("campus_user", JSON.stringify(user));
    $("#profile-avatar").textContent = (user.display_name || user.email || "拾").slice(0, 1).toUpperCase();
    $("#profile-title").textContent = user.display_name || user.email.split("@")[0];
    $("#profile-email").textContent = user.email;
    $("#profile-role").textContent = user.role === "ADMIN" ? "管理员 · 可买可卖与管理" : "普通用户 · 可买可卖";
    $("#profile-summary").innerHTML = `<div><small>我的商品</small><strong>${products.items?.length || 0}</strong></div><div><small>我的预约</small><strong>${reservations.items?.length || 0}</strong></div><div><small>账号状态</small><strong>正常</strong></div>`;
    renderProfileProducts(products.items || []);
    await renderProfileReservations(reservations.items || []);
  } catch (error) {
    $("#profile-products").innerHTML = `<p class="profile-empty">${escapeHtml(error.message)}</p>`;
    $("#profile-reservations").innerHTML = '<p class="profile-empty">暂时无法读取</p>';
  }
}

function openProfile() {
  requireLogin(() => {
    openModal("profile-modal");
    loadProfile();
  });
}

function renderAdminStats(stats) {
  const labels = [
    ["products", "商品总数"],
    ["published_products", "在售商品"],
    ["reservations", "预约次数"],
    ["completed_transactions", "已完成交易"],
    ["violations", "违规下架"],
  ];
  $("#admin-stats").innerHTML = labels.map(([key, label]) => `<div class="admin-stat"><small>${label}</small><strong>${escapeHtml(stats[key] ?? 0)}</strong></div>`).join("");
}

async function renderAdminReviews(tasks) {
  const list = $("#admin-review-list");
  if (!tasks.length) {
    list.innerHTML = '<p class="admin-empty">当前没有待审核商品</p>';
    return;
  }
  const enriched = await Promise.all(tasks.map(async (task) => {
    try {
      const product = await request(`/api/products/${task.product_id}`);
      return { ...task, product: product.item };
    } catch (_) {
      return task;
    }
  }));
  list.innerHTML = enriched.map((task) => {
    const product = task.product || {};
    return `<article class="admin-review-card"><div><span class="detail-tag">${escapeHtml(product.category || "待审核")}</span><h4>${escapeHtml(product.title || task.product_id)}</h4><p>${escapeHtml(product.description || "商品详情暂时无法读取")}</p><small>提交时间 ${escapeHtml(task.created_at || "—")}</small></div><div class="admin-review-actions"><button class="full-button admin-approve" type="button" data-product-id="${escapeHtml(task.product_id)}" data-version="${escapeHtml(product.version ?? "")}">通过</button><button class="ghost-button admin-reject" type="button" data-product-id="${escapeHtml(task.product_id)}" data-version="${escapeHtml(product.version ?? "")}">驳回</button></div></article>`;
  }).join("");
  $$(".admin-approve").forEach((button) => button.addEventListener("click", () => decideReview(button.dataset.productId, "APPROVE", button.dataset.version)));
  $$(".admin-reject").forEach((button) => button.addEventListener("click", () => {
    const reason = window.prompt("请输入驳回原因");
    if (reason && reason.trim()) decideReview(button.dataset.productId, "REJECT", button.dataset.version, reason.trim());
  }));
}

async function loadAdminCenter() {
  if (!state.user || state.user.role !== "ADMIN") return;
  $("#admin-stats").innerHTML = '<p class="admin-empty">正在加载统计数据</p>';
  $("#admin-review-list").innerHTML = '<p class="admin-empty">正在加载审核队列</p>';
  try {
    const [stats, reviews] = await Promise.all([request("/api/admin/stats"), request("/api/admin/reviews")]);
    renderAdminStats(stats);
    await renderAdminReviews(reviews.items || []);
  } catch (error) {
    $("#admin-stats").innerHTML = "";
    $("#admin-review-list").innerHTML = `<p class="admin-empty">${escapeHtml(error.message)}</p>`;
  }
}

function openAdminCenter() {
  if (!state.user || state.user.role !== "ADMIN") {
    showToast("只有管理员可以打开管理中心", true);
    return;
  }
  openModal("admin-modal");
  loadAdminCenter();
}

async function decideReview(productId, decision, version, reason = "") {
  try {
    await request(`/api/reviews/${productId}/decision`, { method: "POST", body: JSON.stringify({ decision, reason, expected_version: version ? Number(version) : undefined }) });
    showToast(decision === "APPROVE" ? "商品已通过审核" : "商品已驳回");
    await loadAdminCenter();
    await loadProducts();
  } catch (error) {
    showToast(error.message, true);
  }
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
  $("#profile-button").addEventListener("click", openProfile);
  $("#profile-logout").addEventListener("click", () => { clearSession(); closeModal("profile-modal"); showToast("已退出登录"); });
  $("#profile-products-refresh").addEventListener("click", loadProfile); $("#profile-reservations-refresh").addEventListener("click", loadProfile);
  $("#admin-button").addEventListener("click", openAdminCenter); $("#admin-refresh").addEventListener("click", loadAdminCenter); $("#sell-button").addEventListener("click", openSell); $("#cta-sell").addEventListener("click", openSell); $("#auth-form").addEventListener("submit", submitAuth); $("#sell-form").addEventListener("submit", submitSell); $("#detail-reserve").addEventListener("click", reserveDetail);
  $$("[data-auth-mode]").forEach((tab) => tab.addEventListener("click", () => setAuthMode(tab.dataset.authMode))); $$("[data-close]").forEach((button) => button.addEventListener("click", () => closeModal(button.dataset.close)));
  $$(".modal-backdrop").forEach((backdrop) => backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeModal(backdrop.id); })); document.addEventListener("keydown", (event) => { if (event.key === "Escape") $$(".modal-backdrop:not(.hidden)").forEach((modal) => closeModal(modal.id)); });
}

setAuthMode("login"); wireEvents(); loadProducts();
