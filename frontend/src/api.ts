// API configuration - points to backend on port 8001
const getBasePath = () => {
  // Check if we're running at a subpath (e.g., /cfd)
  const pathname = window.location.pathname;
  if (pathname.startsWith("/cfd/")) {
    return "http://localhost:8001/cfd";
  }
  // For local development, use backend on port 8001
  return "http://localhost:8001";
};

export const API_BASE = getBasePath();

export const apiUrl = (path: string): string => {
  // Remove leading slash if present
  const cleanPath = path.startsWith("/") ? path.slice(1) : path;
  return `${API_BASE}/api/${cleanPath}`;
};
