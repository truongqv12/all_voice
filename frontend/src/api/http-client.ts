const BASE_URL = import.meta.env.VITE_API_BASE || '/v1';

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, init);
  if (!res.ok) {
    let code = 'unknown_error';
    let message = `HTTP error! status: ${res.status}`;
    try {
      const data = await res.json();
      if (data && data.error) {
        code = data.error.code || code;
        message = data.error.message || message;
      } else if (data && data.detail) {
        message = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        code = 'fastapi_error';
      }
    } catch (e) {
      try {
        const text = await res.text();
        if (text) message = text;
      } catch (e2) {}
    }
    throw new ApiError(res.status, code, message);
  }
  return res;
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    }
  });
  return res.json();
}

export async function apiBlob(path: string, init?: RequestInit): Promise<Blob> {
  const res = await apiFetch(path, init);
  return res.blob();
}
