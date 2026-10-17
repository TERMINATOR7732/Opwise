/**
 * Tests for Safe CSV/XLSX Import (Milestone 12B)
 * Governed by DATA_AND_API.md Section 3.2, Section 4, and PROJECT_RULES.md.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { apiEndpoints } from '../api/endpoints';
import { ImportModal } from '../views/factory/ImportModal';
import { ImportPreviewResponse } from '../types/api';

describe('Import API Endpoints', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('previewImport uploads form data to preview endpoint', async () => {
    const mockPreview: ImportPreviewResponse = {
      job_id: 'job-uuid-1',
      filename: 'factory.zip',
      status: 'PENDING_CONFIRMATION',
      is_valid: true,
      summary: {
        machine_count: 3,
        order_count: 2,
        operation_count: 4,
        downtime_count: 1,
      },
      warnings: [],
      errors: [],
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: mockPreview,
        metadata: { timestamp: '2026-10-17T12:00:00Z', requestId: 'req-1' },
      }),
    });

    const file = new File(['dummy-content'], 'factory.zip', { type: 'application/zip' });
    const res = await apiEndpoints.previewImport('ws-1', file);
    expect(res.job_id).toBe('job-uuid-1');
    expect(res.is_valid).toBe(true);
    expect(res.summary?.machine_count).toBe(3);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/import/preview',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('confirmImport sends staged job_id to confirm endpoint', async () => {
    const mockConfirm = {
      job_id: 'job-uuid-1',
      status: 'COMMITTED',
      message: 'Factory configuration imported successfully.',
      factory: { machines: [], orders: [], downtimes: [] },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: mockConfirm,
        metadata: { timestamp: '2026-10-17T12:00:00Z', requestId: 'req-2' },
      }),
    });

    const res = await apiEndpoints.confirmImport('ws-1', 'job-uuid-1');
    expect(res.job_id).toBe('job-uuid-1');
    expect(res.status).toBe('COMMITTED');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/workspaces/ws-1/import/confirm',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ job_id: 'job-uuid-1' }),
      })
    );
  });
});

describe('ImportModal Component Rendering', () => {
  it('returns null when isOpen is false', () => {
    const html = renderToStaticMarkup(
      <ImportModal isOpen={false} workspaceId="ws-1" onClose={() => {}} onSuccess={async () => {}} />
    );
    expect(html).toBe('');
  });

  it('renders modal dialog with header and template buttons when isOpen is true', () => {
    const html = renderToStaticMarkup(
      <ImportModal isOpen={true} workspaceId="ws-1" onClose={() => {}} onSuccess={async () => {}} />
    );
    expect(html).toContain('Import Factory Configuration');
    expect(html).toContain('Starter CSV (.zip)');
    expect(html).toContain('Starter Excel (.xlsx)');
    expect(html).toContain('Preview &amp; Validate');
    expect(html).toContain('Confirm &amp; Replace Factory');
  });
});
