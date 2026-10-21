/**
 * Two-Phase Factory Data Import Modal (CSV & Excel)
 * Governed by DATA_AND_API.md Section 3.2, Section 4, and PROJECT_RULES.md.
 */

import React, { useState, useRef } from 'react';
import { apiEndpoints } from '../../api/endpoints';
import { ApiClientError } from '../../api/client';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { ImportPreviewResponse, ImportRowError, ImportSummary } from '../../types/api';
import { isDemoMode } from '../../demo/demoService';

export interface ImportModalProps {
  isOpen: boolean;
  workspaceId: string;
  onClose: () => void;
  onSuccess: () => Promise<void>;
}

function TemplateDownloadBar(): React.ReactElement {
  const [downloading, setDownloading] = useState<'csv' | 'xlsx' | null>(null);
  const demoActive = isDemoMode();

  const handleDownload = async (format: 'csv' | 'xlsx'): Promise<void> => {
    setDownloading(format);
    try {
      await apiEndpoints.downloadTemplate(format);
    } catch (err: unknown) {
      console.error('Failed to download template:', err);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
      <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
        {demoActive ? 'Demo Mode: Download schema-compliant starter CSV:' : 'Need schema-compliant sample files?'}
      </div>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleDownload('csv')} disabled={downloading !== null}>
          {downloading === 'csv' ? 'Downloading...' : demoActive ? '📥 Starter CSV (.csv)' : '📥 Starter CSV (.zip)'}
        </button>
        {!demoActive && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => handleDownload('xlsx')} disabled={downloading !== null}>
            {downloading === 'xlsx' ? 'Downloading...' : '📥 Starter Excel (.xlsx)'}
          </button>
        )}
      </div>
    </div>
  );
}

function ErrorDiagnosticsTable({ errors }: { errors: ImportRowError[] }): React.ReactElement {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ color: 'var(--color-critical)', fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.5rem' }}>
        Validation Failed: {errors.length} issue{errors.length !== 1 ? 's' : ''} detected. No data committed.
      </div>
      <div style={{ maxHeight: '180px', overflowY: 'auto', border: '1px solid var(--color-critical-border)', borderRadius: 'var(--radius-sm)' }}>
        <table className="table table-sm" style={{ margin: 0, fontSize: '0.75rem' }}>
          <thead>
            <tr>
              <th>File / Sheet</th>
              <th>Row</th>
              <th>Field</th>
              <th>Value</th>
              <th>Diagnostic Issue</th>
            </tr>
          </thead>
          <tbody>
            {errors.map((err, idx) => (
              <tr key={idx}>
                <td><code>{err.sheet}</code></td>
                <td>{err.row > 0 ? err.row : '—'}</td>
                <td><code>{err.column}</code></td>
                <td><span style={{ color: 'var(--text-muted)' }}>{err.value || '—'}</span></td>
                <td style={{ color: 'var(--color-critical)' }}>{err.issue}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StagedSummaryGrid({ summary, warnings }: { summary: ImportSummary; warnings?: string[] }): React.ReactElement {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <Badge variant="optimal">Validation Passed</Badge>
        <span style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>Staged entities ready for atomic confirmation:</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <div className="card" style={{ padding: '0.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>{summary.machine_count}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Machines</div>
        </div>
        <div className="card" style={{ padding: '0.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>{summary.order_count}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Orders</div>
        </div>
        <div className="card" style={{ padding: '0.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>{summary.operation_count}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Operations</div>
        </div>
        <div className="card" style={{ padding: '0.5rem', textAlign: 'center' }}>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)' }}>{summary.downtime_count}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Downtimes</div>
        </div>
      </div>
      {warnings && warnings.length > 0 && (
        <div style={{ padding: '0.5rem 0.75rem', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.75rem', color: 'var(--color-warning)' }}>
          <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Advisory Normalization Notes:</div>
          <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
            {warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

interface FileInputProps {
  inputRef: React.RefObject<HTMLInputElement | null>;
  selectedFile: File | null;
  isPreviewing: boolean;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onPreview: () => Promise<void>;
}

function FileInputSection({ inputRef, selectedFile, isPreviewing, onFileChange, onPreview }: FileInputProps): React.ReactElement {
  const demoActive = isDemoMode();
  return (
    <div style={{ marginBottom: '1.25rem' }}>
      <label htmlFor="import-file-input" style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.375rem' }}>
        {demoActive ? 'Select Factory CSV (.csv) File:' : 'Select CSV Bundle (.zip) or Excel (.xlsx) File:'}
      </label>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <input
          id="import-file-input"
          ref={inputRef}
          type="file"
          accept={demoActive ? '.csv,text/csv' : '.zip,.xlsx,application/zip,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
          onChange={onFileChange}
          style={{ flex: 1, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}
        />
        <Button variant="primary" size="sm" onClick={onPreview} disabled={!selectedFile || isPreviewing}>
          {isPreviewing ? 'Validating...' : 'Preview & Validate'}
        </Button>
      </div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
        {demoActive
          ? 'Demo schema: multi-section CSV with Machines, Orders, Operations, and optional Downtimes sections. (Binary .xlsx and .zip bundles require the Python backend).'
          : 'Expected sheets/files: machines, orders, operations, optional downtimes.'}
      </div>
    </div>
  );
}

interface ModalFooterProps {
  onCancel: () => void;
  onConfirm: () => Promise<void>;
  isConfirming: boolean;
  canConfirm: boolean;
}

function ImportModalFooter({ onCancel, onConfirm, isConfirming, canConfirm }: ModalFooterProps): React.ReactElement {
  return (
    <div style={{ padding: '1rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
      <Button variant="secondary" onClick={onCancel} disabled={isConfirming}>Cancel</Button>
      <Button variant="primary" onClick={onConfirm} disabled={!canConfirm || isConfirming}>
        {isConfirming ? 'Committing...' : 'Confirm & Replace Factory'}
      </Button>
    </div>
  );
}

export function ImportModal({ isOpen, workspaceId, onClose, onSuccess }: ImportModalProps): React.ReactElement | null {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isPreviewing, setIsPreviewing] = useState<boolean>(false);
  const [isConfirming, setIsConfirming] = useState<boolean>(false);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [genericError, setGenericError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  if (!isOpen) return null;

  const handleClose = (): void => {
    setSelectedFile(null);
    setPreview(null);
    setGenericError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    onClose();
  };

  const handlePreview = async (): Promise<void> => {
    if (!selectedFile) return;
    setIsPreviewing(true);
    setGenericError(null);
    setPreview(null);
    try {
      const resp = await apiEndpoints.previewImport(workspaceId, selectedFile);
      setPreview(resp);
    } catch (err: unknown) {
      if (err instanceof ApiClientError && err.data && typeof err.data === 'object' && 'errors' in (err.data as object)) {
        setPreview(err.data as ImportPreviewResponse);
      } else {
        setGenericError(err instanceof Error ? err.message : 'Failed to parse import file.');
      }
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleConfirm = async (): Promise<void> => {
    if (!preview?.job_id) return;
    setIsConfirming(true);
    setGenericError(null);
    try {
      await apiEndpoints.confirmImport(workspaceId, preview.job_id);
      await onSuccess();
      handleClose();
    } catch (err: unknown) {
      setGenericError(err instanceof Error ? err.message : 'Confirmation failed.');
    } finally {
      setIsConfirming(false);
    }
  };

  return (
    <div role="dialog" aria-labelledby="import-modal-title" aria-modal="true" style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60, padding: '1rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: '640px', maxHeight: '90vh', display: 'flex', flexDirection: 'column', boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }}>
        <div className="card-header">
          <h2 id="import-modal-title" className="card-title">Import Factory Configuration</h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={handleClose} aria-label="Close dialog">✕</button>
        </div>
        <div className="card-body" style={{ overflowY: 'auto' }}>
          <TemplateDownloadBar />
          <FileInputSection inputRef={fileInputRef} selectedFile={selectedFile} isPreviewing={isPreviewing} onFileChange={(e) => setSelectedFile(e.target.files?.[0] || null)} onPreview={handlePreview} />
          {genericError && <div style={{ padding: '0.75rem', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--color-critical-border)', borderRadius: 'var(--radius-sm)', color: 'var(--color-critical)', fontSize: '0.8125rem', marginBottom: '1rem' }}>{genericError}</div>}
          {preview?.errors && preview.errors.length > 0 && <ErrorDiagnosticsTable errors={preview.errors} />}
          {preview?.is_valid && preview.summary && (
            <>
              <StagedSummaryGrid summary={preview.summary} warnings={preview.warnings} />
              <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-app)', border: '1px solid var(--color-warning-border)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                ⚠️ <strong>Destructive Action:</strong> Confirming this import will atomically replace all current machines, maintenance downtimes, production orders, and routings for this workspace.
              </div>
            </>
          )}
        </div>
        <ImportModalFooter onCancel={handleClose} onConfirm={handleConfirm} isConfirming={isConfirming} canConfirm={Boolean(preview?.is_valid && preview?.job_id)} />
      </div>
    </div>
  );
}
