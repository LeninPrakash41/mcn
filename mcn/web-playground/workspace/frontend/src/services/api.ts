/**
 * MCN API service - auto-generated.
 * All endpoint calls go through this module so components stay clean.
 */

const BASE = (import.meta as any).env?.VITE_API_URL ?? "http://localhost:8080"

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method:  body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body:    body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const api = {
  get:  <T = any>(path: string)              => request<T>(path),
  post: <T = any>(path: string, body: unknown) => request<T>(path, body),
}
