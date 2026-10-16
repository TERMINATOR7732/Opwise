import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { api, ApiClientError, getApiBaseUrl } from '../api/client';

describe('API Client Foundation', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('resolves default API base URL cleanly without trailing slash', () => {
    const url = getApiBaseUrl();
    expect(url).toBe('/api/v1');
    expect(url.endsWith('/')).toBe(false);
  });

  it('unwraps SuccessEnvelope and returns data payload', async () => {
    const mockData = { id: 'ws-123', name: 'Precision Shop' };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: mockData,
        metadata: { timestamp: '2026-10-16T12:00:00Z', requestId: 'req-1' },
      }),
    });

    const result = await api.get('/workspaces/ws-123');
    expect(result).toEqual(mockData);
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/workspaces/ws-123', expect.any(Object));
  });

  it('unwraps ErrorEnvelope and throws ApiClientError with code and details', async () => {
    const errorPayload = {
      code: 'VALIDATION_FAILED',
      message: 'Referenced machine does not exist in workspace.',
      details: [{ field: 'operations[0].machine_id', issue: 'Missing M99' }],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        success: false,
        error: errorPayload,
        metadata: { timestamp: '2026-10-16T12:00:00Z', requestId: 'req-2' },
      }),
    });

    await expect(api.post('/workspaces/ws-1/factory', {})).rejects.toThrow(ApiClientError);

    try {
      await api.post('/workspaces/ws-1/factory', {});
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiClientError);
      const apiErr = err as ApiClientError;
      expect(apiErr.code).toBe('VALIDATION_FAILED');
      expect(apiErr.status).toBe(422);
      expect(apiErr.message).toBe('Referenced machine does not exist in workspace.');
      expect(apiErr.details).toEqual(errorPayload.details);
    }
  });

  it('throws BACKEND_UNAVAILABLE on fetch network disconnection', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    await expect(api.get('/health')).rejects.toThrow(ApiClientError);

    try {
      await api.get('/health');
    } catch (err: unknown) {
      const apiErr = err as ApiClientError;
      expect(apiErr.code).toBe('BACKEND_UNAVAILABLE');
      expect(apiErr.status).toBe(0);
      expect(apiErr.message).toContain('Cannot connect to Opwise API');
    }
  });

  it('handles HTTP 204 No Content without error', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => {
        throw new Error('No body');
      },
    });

    const result = await api.delete('/workspaces/ws-delete-1');
    expect(result).toBeUndefined();
  });
});
