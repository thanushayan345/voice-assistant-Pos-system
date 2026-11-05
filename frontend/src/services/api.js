/**
 * Centralized Fetch API client for Tamil Voice POS backend communication.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const TOKEN_STORAGE_KEY = "tamil_voice_pos_token";

export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export class ApiError extends Error {
  constructor(message, status, code = null, payload = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.payload = payload;
  }
}

async function request(endpoint, options = {}) {
  const token = getStoredToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (networkErr) {
    throw new ApiError(
      "Cannot connect to the backend server. Please verify the FastAPI server is running on port 8000.",
      0,
      "NETWORK_ERROR"
    );
  }

  let data = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    if (response.status === 401 && !endpoint.includes("/api/auth/login")) {
      setStoredToken(null);
      window.dispatchEvent(new CustomEvent("pos:unauthorized"));
    }

    const detail = data?.detail;
    let message = `Request failed (${response.status})`;
    let code = null;

    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object") {
      message = detail.message || JSON.stringify(detail);
      code = detail.code || null;
    }

    if (
      response.status === 503 &&
      detail &&
      typeof detail === "object" &&
      (detail.code === "MAINTENANCE_MODE" || detail.code === "FEATURE_DISABLED")
    ) {
      window.dispatchEvent(new CustomEvent("pos:system-status-changed"));
    }

    throw new ApiError(message, response.status, code, detail);
  }

  return data;
}

export const api = {
  // Configuration & System Maintenance Status
  getConfig: () => request("/api/config"),
  getSystemStatus: () => request("/api/system/status"),
  updateSystemStatus: (payload) =>
    request("/api/system/status", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  // Authentication
  register: (payload) =>
    request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  login: (payload) =>
    request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: () =>
    request("/api/auth/logout", {
      method: "POST",
    }),
  getMe: () => request("/api/auth/me"),

  // Products
  getProducts: ({ search = "", category = "", lowStockOnly = false } = {}) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (category && category !== "All") params.set("category", category);
    if (lowStockOnly) params.set("low_stock_only", "true");
    const qs = params.toString();
    return request(`/api/products${qs ? `?${qs}` : ""}`);
  },
  getProductById: (id) => request(`/api/products/${id}`),
  createProduct: (payload) =>
    request("/api/products", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateProduct: (id, payload) =>
    request(`/api/products/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteProduct: (id) =>
    request(`/api/products/${id}`, {
      method: "DELETE",
    }),

  // Inventory
  getInventory: () => request("/api/inventory"),
  getLowStock: () => request("/api/inventory/low-stock"),
  adjustInventory: (payload) =>
    request("/api/inventory/adjust", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getStockTransactions: ({ productId = "", transactionType = "", limit = 100 } = {}) => {
    const params = new URLSearchParams();
    if (productId) params.set("product_id", String(productId));
    if (transactionType && transactionType !== "ALL") {
      params.set("transaction_type", transactionType);
    }
    params.set("limit", String(limit));
    return request(`/api/inventory/transactions?${params.toString()}`);
  },

  // POS & Sales
  createSale: (payload) =>
    request("/api/sales", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getSales: ({ search = "", dateFrom = "", dateTo = "", limit = 100 } = {}) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    params.set("limit", String(limit));
    return request(`/api/sales?${params.toString()}`);
  },
  getSaleById: (id) => request(`/api/sales/${id}`),

  // Voice AI (Local Ollama)
  processVoice: (transcript, language) =>
    request("/api/voice/process", {
      method: "POST",
      body: JSON.stringify({ transcript, language }),
    }),
  confirmVoice: (confirmationToken) =>
    request("/api/voice/confirm", {
      method: "POST",
      body: JSON.stringify({ confirmation_token: confirmationToken }),
    }),
  cancelVoice: (confirmationToken) =>
    request("/api/voice/cancel", {
      method: "POST",
      body: JSON.stringify({ confirmation_token: confirmationToken }),
    }),
  getVoiceHistory: (limit = 25) => request(`/api/voice/history?limit=${limit}`),

  // Reports
  getDashboardReport: () => request("/api/reports/dashboard"),
  getDailySalesReport: (days = 7) =>
    request(`/api/reports/daily-sales?days=${days}`),
  getInventoryReport: () => request("/api/reports/inventory"),
};
