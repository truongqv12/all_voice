const BASE_URL = import.meta.env.VITE_API_BASE || '/v1';
export const DEFAULT_TIMEOUT_MS = 150_000;

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

export type HttpClientOptions = RequestInit & { timeoutMs?: number };

export function createRequestAbort(options?: Pick<HttpClientOptions, 'signal' | 'timeoutMs'>) {
  const controller = new AbortController();
  let timedOut = false;
  const timeout = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options?.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const abort = () => controller.abort();
  if (options?.signal?.aborted) controller.abort();
  else options?.signal?.addEventListener('abort', abort, { once: true });
  return {
    signal: controller.signal,
    timedOut: () => timedOut,
    dispose: () => {
      globalThis.clearTimeout(timeout);
      options?.signal?.removeEventListener('abort', abort);
    },
  };
}

export function isAbortError(error: unknown) {
  return error instanceof ApiError && error.code === 'aborted';
}

export async function apiFetch(path: string, init?: HttpClientOptions, preserveSignal = false): Promise<Response> {
  const url = `${BASE_URL}${path}`;
  const headers = new Headers(init?.headers);
  const token = localStorage.getItem('agy_token');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  // Callers that consume a response body create one controller around the
  // entire operation. Passing that signal through unchanged is essential:
  // replacing it here would detach cancellation after response headers arrive.
  const abort = preserveSignal ? null : createRequestAbort(init);
  if (preserveSignal && !init?.signal) throw new TypeError('A preserved request signal is required.');
  const signal: AbortSignal = preserveSignal ? init!.signal! : abort!.signal;

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers, signal });
  } catch (error) {
    if (signal.aborted) {
      const timedOut = abort?.timedOut() ?? false;
      throw new ApiError(0, timedOut ? 'timeout' : 'aborted', timedOut ? 'The request timed out.' : 'The request was cancelled.');
    }
    throw error;
  } finally {
    abort?.dispose();
  }
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

export async function apiJson<T>(path: string, init?: HttpClientOptions): Promise<T> {
  const abort = createRequestAbort(init);
  try {
    const res = await apiFetch(path, {
      ...init,
      signal: abort.signal,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    }, true);
    return await res.json() as T;
  } catch (error) {
    if (abort.signal.aborted) {
      throw new ApiError(0, abort.timedOut() ? 'timeout' : 'aborted', abort.timedOut() ? 'The request timed out.' : 'The request was cancelled.');
    }
    throw error;
  } finally {
    abort.dispose();
  }
}

export async function apiBlob(path: string, init?: HttpClientOptions): Promise<Blob> {
  const abort = createRequestAbort(init);
  try {
    const res = await apiFetch(path, { ...init, signal: abort.signal }, true);
    return await res.blob();
  } catch (error) {
    if (abort.signal.aborted) {
      throw new ApiError(0, abort.timedOut() ? 'timeout' : 'aborted', abort.timedOut() ? 'The request timed out.' : 'The request was cancelled.');
    }
    throw error;
  } finally {
    abort.dispose();
  }
}
