import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiError(e, fallback = "Ocorreu um erro. Tente novamente.") {
  const detail = e?.response?.data?.detail;
  if (detail == null) return e?.message || fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((d) => (d && d.msg) || JSON.stringify(d)).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;
