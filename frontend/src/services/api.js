// In dev Vite proxies /api → FastAPI (strips /api prefix).
// In production same origin, no prefix needed.
const API_BASE = import.meta.env.VITE_API_BASE ?? "";

function getToken() {
  return localStorage.getItem("br_token");
}

function authHeaders() {
  const t = getToken();
  return t
    ? { Authorization: `Bearer ${t}`, "Content-Type": "application/json" }
    : { "Content-Type": "application/json" };
}

async function request(path, options = {}, { noRedirectOn401 = false } = {}) {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders(), ...options });
  if (res.status === 401 && !noRedirectOn401) {
    localStorage.removeItem("br_token");
    window.location.href = "/login";
    return;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Erro desconhecido");
  }
  if (res.status === 204) return null;
  return res.json();
}

// Auth
export const apiLogin = (email, password) =>
  request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, { noRedirectOn401: true });

// Stats
export const fetchStats = () => request("/stats");

// Licitações
export const fetchBids = () => request("/licitacoes");
export const fetchBid = (id) => request(`/licitacoes/${id}`);

// Logs
export const fetchLogs = (limit = 50) => request(`/logs?limit=${limit}`);

// Filters
export const fetchFilters = () => request("/filters");
export const saveFilters = (data) =>
  request("/filters", { method: "PUT", body: JSON.stringify(data) });

// Products
export const fetchProducts = () => request("/products");
export const createProduct = (data) =>
  request("/products", { method: "POST", body: JSON.stringify(data) });
export const updateProduct = (id, data) =>
  request(`/products/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteProduct = (id) => request(`/products/${id}`, { method: "DELETE" });

// Admin users
export const fetchUsers = () => request("/admin/users");
export const createUser = (data) =>
  request("/admin/users", { method: "POST", body: JSON.stringify(data) });
export const updateUser = (id, data) =>
  request(`/admin/users/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteUser = (id) => request(`/admin/users/${id}`, { method: "DELETE" });

// Agent
export const runAgentOnce = () => request("/agent/run-once", { method: "POST" });

// Company profile documents (DB-backed)
export const fetchDocuments = () => request("/company-profile/documents");
export const createDocument = (data) =>
  request("/company-profile/documents", { method: "POST", body: JSON.stringify(data) });
export const updateDocument = (id, data) =>
  request(`/company-profile/documents/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteDocument = (id) =>
  request(`/company-profile/documents/${id}`, { method: "DELETE" });
