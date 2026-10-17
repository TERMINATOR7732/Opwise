/**
 * Typed HTTP Client for Opwise API v1
 * Governed by DATA_AND_API.md Section 3 and PROJECT_RULES.md Rule 1.
 */

import { ErrorEnvelope, SuccessEnvelope, ValidationErrorDetail } from '../types/api';

export class ApiClientError extends Error {
  public readonly code: string;
  public readonly status: number;
  public readonly details?: ValidationErrorDetail[] | Record<string, unknown> | null;

  constructor(
    code: string,
    message: string,
    status: number,
    details?: ValidationErrorDetail[] | Record<string, unknown> | null
  ) {
    super(message);
    this.name = 'ApiClientError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function getApiBaseUrl(): string {
  const envUrl = typeof import.meta !== 'undefined' && import.meta.env ? import.meta.env.VITE_API_BASE_URL : undefined;
  return (envUrl || '/api/v1').replace(/\/+$/, '');
}

function buildHeaders(options: RequestInit): Headers {
  const headers = new Headers(options.headers);
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  return headers;
}

function handleEnvelopeResult<T>(json: unknown, status: number): T {
  if (typeof json === 'object' && json !== null && 'success' in json) {
    const envelope = json as SuccessEnvelope<T> | ErrorEnvelope;
    if (envelope.success === true) {
      return envelope.data;
    }
    throw new ApiClientError(
      envelope.error.code,
      envelope.error.message,
      status,
      envelope.error.details
    );
  }
  return json as T;
}

async function parseResponseBody<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as unknown as T;
  }
  let json: unknown;
  try {
    json = await response.json();
  } catch {
    if (!response.ok) {
      throw new ApiClientError(
        'HTTP_ERROR',
        `Server returned error HTTP ${response.status}: ${response.statusText}`,
        response.status
      );
    }
    return undefined as unknown as T;
  }
  const result = handleEnvelopeResult<T>(json, response.status);
  if (!response.ok) {
    throw new ApiClientError('HTTP_ERROR', `Request failed with status ${response.status}`, response.status);
  }
  return result;
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const fullUrl = `${baseUrl}${normalizedPath}`;
  const headers = buildHeaders(options);

  try {
    const response = await fetch(fullUrl, { ...options, headers });
    return await parseResponseBody<T>(response);
  } catch (err: unknown) {
    if (err instanceof ApiClientError) {
      throw err;
    }
    const errorMsg = err instanceof Error ? err.message : 'Network request failed';
    throw new ApiClientError(
      'BACKEND_UNAVAILABLE',
      `Cannot connect to Opwise API (${errorMsg}). Verify that the backend server is running on http://127.0.0.1:8000.`,
      0
    );
  }
}

export const api = {
  get: <T>(path: string, options?: RequestInit) => request<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestInit) =>
    request<T>(path, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),
  put: <T>(path: string, body?: unknown, options?: RequestInit) =>
    request<T>(path, {
      ...options,
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    }),
  delete: <T>(path: string, options?: RequestInit) => request<T>(path, { ...options, method: 'DELETE' }),
};

export async function downloadFile(path: string, defaultFilename: string): Promise<void> {
  const baseUrl = getApiBaseUrl();
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const fullUrl = `${baseUrl}${normalizedPath}`;
  const response = await fetch(fullUrl);
  if (!response.ok) {
    throw new ApiClientError('DOWNLOAD_FAILED', `Download failed with HTTP ${response.status}`, response.status);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition');
  let filename = defaultFilename;
  if (disposition) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}
