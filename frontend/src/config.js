// VITE_API_BASE_URL is set per deployment (for example, in .env.production).
// An empty value intentionally means "same origin", which works behind a
// reverse proxy without baking an environment-specific host into the bundle.
const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '';

export const API_BASE_URL = configuredBaseUrl.replace(/\/$/, '');

export function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}
