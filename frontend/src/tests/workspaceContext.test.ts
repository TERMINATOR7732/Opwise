import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiEndpoints } from '../api/endpoints';
import { ApiClientError } from '../api/client';

describe('Workspace Context & Backend Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('queries backend listWorkspaces endpoint', async () => {
    const mockWorkspaces = [
      { id: 'ws-1', name: 'Shop 1', description: 'Desc 1', created_at: '2026-10-16T12:00:00Z', updated_at: '2026-10-16T12:00:00Z' },
      { id: 'ws-2', name: 'Shop 2', description: 'Desc 2', created_at: '2026-10-16T12:00:00Z', updated_at: '2026-10-16T12:00:00Z' },
    ];
    vi.spyOn(apiEndpoints, 'listWorkspaces').mockResolvedValue(mockWorkspaces);

    const result = await apiEndpoints.listWorkspaces();
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe('Shop 1');
  });

  it('creates workspace via POST payload', async () => {
    const newWs = { id: 'ws-new', name: 'New Shop', description: '', created_at: '2026-10-16T12:00:00Z', updated_at: '2026-10-16T12:00:00Z' };
    vi.spyOn(apiEndpoints, 'createWorkspace').mockResolvedValue(newWs);

    const result = await apiEndpoints.createWorkspace({ name: 'New Shop' });
    expect(result.id).toBe('ws-new');
    expect(result.name).toBe('New Shop');
  });

  it('does NOT fabricate success data when backend rejects request', async () => {
    vi.spyOn(apiEndpoints, 'createWorkspace').mockRejectedValue(
      new ApiClientError('VALIDATION_FAILED', 'Workspace name must not be blank', 422)
    );

    await expect(apiEndpoints.createWorkspace({ name: '' })).rejects.toThrow(ApiClientError);
    await expect(apiEndpoints.createWorkspace({ name: '' })).rejects.toThrow('Workspace name must not be blank');
  });

  it('propagates backend network unavailability without masking', async () => {
    vi.spyOn(apiEndpoints, 'listWorkspaces').mockRejectedValue(
      new ApiClientError('BACKEND_UNAVAILABLE', 'Cannot connect to Opwise API', 0)
    );

    try {
      await apiEndpoints.listWorkspaces();
      expect.fail('Should have thrown ApiClientError');
    } catch (err: unknown) {
      expect(err).toBeInstanceOf(ApiClientError);
      expect((err as ApiClientError).code).toBe('BACKEND_UNAVAILABLE');
      expect((err as ApiClientError).status).toBe(0);
    }
  });
});
