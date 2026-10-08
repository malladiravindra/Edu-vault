/**
 * API configuration.
 *
 * NEXT_PUBLIC_API_BASE_URL  Base URL of the REST backend (no trailing slash).
 *
 * In development:  /api  (Next.js rewrites proxy this to http://localhost:8000/api)
 * In production:   https://your-api.example.com/api  (direct, set CORS on backend)
 *
 * Never put secrets in NEXT_PUBLIC_* variables — they are shipped to the browser.
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
