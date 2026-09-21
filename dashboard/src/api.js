const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Erreur API (${status})`);
    this.status = status;
  }
}

async function request(path, { method = "GET", token, body, form } = {}) {
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let payload;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form).toString();
  } else if (body) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, { method, headers, body: payload });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (username, password) =>
    request("/auth/login", { method: "POST", form: { username, password } }),
  createUser: (token, user) => request("/auth/users", { method: "POST", token, body: user }),
  listUsers: (token) => request("/auth/users", { token }),
  deleteUser: (token, username) => request(`/auth/users/${username}`, { method: "DELETE", token }),

  overview: (token) => request("/analytics/overview", { token }),
  adminOverview: (token) => request("/admin/overview", { token }),
  rfmSummary: (token) => request("/analytics/rfm/summary", { token }),
  rfmList: (token, { segment, limit = 50, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (segment) params.set("segment", segment);
    return request(`/analytics/rfm?${params}`, { token });
  },
  churnSummary: (token) => request("/analytics/churn/summary", { token }),
  churnList: (token, { risk_level, limit = 50, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (risk_level) params.set("risk_level", risk_level);
    return request(`/analytics/churn?${params}`, { token });
  },
  churnFeatureImportance: (token) => request("/analytics/churn/feature-importance", { token }),
  returnsByRisk: (token) => request("/analytics/churn/returns-by-risk", { token }),
  geoDistribution: (token) => request("/analytics/olist/geo-distribution", { token }),
  funnel: (token) => request("/analytics/funnel", { token }),
  recommendations: (token, itemId, limit = 10) =>
    request(`/analytics/recommendations/${itemId}?limit=${limit}`, { token }),
  associationRules: (token, { min_lift, limit = 50 } = {}) => {
    const params = new URLSearchParams({ limit });
    if (min_lift !== undefined) params.set("min_lift", min_lift);
    return request(`/analytics/association-rules?${params}`, { token });
  },
  sentimentSummary: (token) => request("/analytics/sentiment/summary", { token }),
  sentimentTrend: (token) => request("/analytics/sentiment/trend", { token }),
  sentimentList: (token, { sentiment, limit = 50, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (sentiment) params.set("sentiment", sentiment);
    return request(`/analytics/sentiment?${params}`, { token });
  },
  retentionEstimate: (token, { top_n = 500, success_rate = 0.3 } = {}) =>
    request(`/analytics/churn/retention-estimate?top_n=${top_n}&success_rate=${success_rate}`, { token }),
  marketingActions: (token, { risk_level = "high", limit = 20 } = {}) =>
    request(`/analytics/churn/marketing-actions?risk_level=${risk_level}&limit=${limit}`, { token }),
  anomalies: (token) => request("/analytics/anomalies", { token }),
  deliveryKpi: (token) => request("/analytics/olist/delivery", { token }),
  topItems: (token, limit = 10) => request(`/analytics/retailrocket/top-items?limit=${limit}`, { token }),
  paymentMethods: (token) => request("/analytics/olist/payment-methods", { token }),
  customer360Summary: (token) => request("/analytics/customer-360/summary", { token }),
  customer360List: (token, { risk_level, segment, limit = 50, offset = 0 } = {}) => {
    const params = new URLSearchParams({ limit, offset });
    if (risk_level) params.set("risk_level", risk_level);
    if (segment) params.set("segment", segment);
    return request(`/analytics/customer-360?${params}`, { token });
  },

  rgpdExport: (token, customerId) => request(`/rgpd/churn/${customerId}/export`, { token }),
  rgpdErase: (token, customerId) => request(`/rgpd/churn/${customerId}`, { method: "DELETE", token }),

  recomputeStatus: (token) => request("/admin/recompute/status", { token }),
  triggerRecompute: (token, module) => request(`/admin/recompute/${module}`, { method: "POST", token }),

  listModelRegistry: (token) => request("/admin/models", { token }),
  rollbackModel: (token, modelName) => request(`/admin/models/${modelName}/rollback`, { method: "POST", token }),
};

export { ApiError };
