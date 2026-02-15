// API configuration - auto-detects base path from current URL
const getBasePath = () => {
  // Check if we're running at a subpath (e.g., /cfd)
  const pathname = window.location.pathname;
  if (pathname.startsWith('/cfd/')) {
    return '/cfd';
  }
  return '';
};

export const API_BASE = getBasePath();

export const apiUrl = (path: string): string => {
  // Remove leading slash if present
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `${API_BASE}/api/${cleanPath}`;
};
