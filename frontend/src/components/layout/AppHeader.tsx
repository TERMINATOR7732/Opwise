import React, { useState, useEffect, useMemo } from 'react';
import { useWorkspace } from '../../context/WorkspaceContext';
import { useOptionalFactory } from '../../context/FactoryContext';
import { useTour } from '../../context/TourContext';
import { apiEndpoints } from '../../api/endpoints';
import { Button } from '../common/Button';
import { ClockAdvanceModal, InProgressOpInfo } from '../execution/ClockAdvanceModal';

export interface AppHeaderProps {
  onToggleSidebar?: () => void;
  isSidebarOpen?: boolean;
}

interface WorkspaceModalProps {
  onClose: () => void;
  onSubmit: (name: string, desc: string) => Promise<void>;
}

function WorkspaceFormFields({
  name,
  setName,
  desc,
  setDesc,
  formError,
}: {
  name: string;
  setName: (v: string) => void;
  desc: string;
  setDesc: (v: string) => void;
  formError: string | null;
}): React.ReactElement {
  return (
    <div className="card-body">
      {formError && (
        <p style={{ color: 'var(--color-critical)', fontSize: '0.8125rem', marginBottom: '0.75rem' }}>{formError}</p>
      )}
      <div className="form-group">
        <label htmlFor="ws-name" className="form-label">Workspace Name *</label>
        <input
          id="ws-name"
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Machine Shop Beta"
          className="form-input"
          autoFocus
        />
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label htmlFor="ws-desc" className="form-label">Description (Optional)</label>
        <input
          id="ws-desc"
          type="text"
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          placeholder="e.g. 5 CNC Mills & 2 Turning Lathes"
          className="form-input"
        />
      </div>
    </div>
  );
}

function ModalOverlay({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <div
      role="dialog"
      aria-labelledby="modal-title"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        padding: '1rem',
      }}
    >
      <div className="card" style={{ width: '100%', maxWidth: '440px', boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }}>
        <div className="card-header">
          <h2 id="modal-title" className="card-title">{title}</h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose} aria-label="Close modal">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function WorkspaceModal({ onClose, onSubmit }: WorkspaceModalProps): React.ReactElement {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setFormError('Workspace name is required');
      return;
    }
    setIsSubmitting(true);
    setFormError(null);
    try {
      await onSubmit(name, desc);
      onClose();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create workspace');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ModalOverlay title="Create Workspace" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <WorkspaceFormFields name={name} setName={setName} desc={desc} setDesc={setDesc} formError={formError} />
        <div style={{ padding: '0.875rem 1.25rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" size="sm" isLoading={isSubmitting}>Create Workspace</Button>
        </div>
      </form>
    </ModalOverlay>
  );
}

function BackendStatusIndicator({ isOnline }: { isOnline: boolean | null }): React.ReactElement {
  const dotClass = isOnline === true ? 'status-dot-online' : isOnline === false ? 'status-dot-offline' : 'status-dot-loading';
  const label = isOnline === true ? 'Backend: Online' : isOnline === false ? 'Backend: Offline' : 'Connecting...';
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.25rem 0.6rem',
        backgroundColor: 'var(--bg-app)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-subtle)',
        fontSize: '0.75rem',
      }}
      title={isOnline ? 'Connected to local FastAPI + SQLite WAL backend' : 'Backend offline at http://127.0.0.1:8000'}
    >
      <span className={`status-dot ${dotClass}`} aria-hidden="true" />
      <span style={{ color: isOnline ? 'var(--text-secondary)' : 'var(--color-critical)' }}>{label}</span>
    </div>
  );
}

function WorkspaceSelector({
  workspaces,
  activeWorkspaceId,
  onSelect,
  disabled,
  onNewClick,
}: {
  workspaces: Array<{ id: string; name: string }>;
  activeWorkspaceId: string | null;
  onSelect: (id: string) => void;
  disabled: boolean;
  onNewClick: () => void;
}): React.ReactElement {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <label htmlFor="workspace-select" className="sr-only">Active Workspace</label>
      <select
        id="workspace-select"
        value={activeWorkspaceId || ''}
        onChange={(e) => onSelect(e.target.value)}
        disabled={disabled}
        className="form-input font-mono"
        style={{ minWidth: '180px', padding: '0.35rem 0.6rem', fontSize: '0.8125rem' }}
      >
        {workspaces.length === 0 ? (
          <option value="">No workspaces available</option>
        ) : (
          workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)
        )}
      </select>
      <Button variant="secondary" size="sm" onClick={onNewClick}>+ New</Button>
    </div>
  );
}

function BrandLogo({ onToggleSidebar, isSidebarOpen }: AppHeaderProps): React.ReactElement {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
      <button
        type="button"
        className="btn btn-secondary btn-sm mobile-nav-toggle"
        onClick={onToggleSidebar}
        aria-label={isSidebarOpen ? 'Close Navigation Menu' : 'Open Navigation Menu'}
        aria-expanded={isSidebarOpen}
      >
        {isSidebarOpen ? '✕' : '☰'}
      </button>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--color-optimal)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="3" width="7" height="7" />
          <rect x="14" y="3" width="7" height="7" />
          <rect x="14" y="14" width="7" height="7" />
          <rect x="3" y="14" width="7" height="7" />
        </svg>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
          <span style={{ fontSize: '1.125rem', fontWeight: 800, letterSpacing: '0.04em', color: 'var(--text-primary)' }}>OPWISE</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }} className="font-mono">v0.1.0</span>
        </div>
      </div>
    </div>
  );
}

function useBackendStatus(): boolean | null {
  const [isOnline, setIsOnline] = useState<boolean | null>(null);
  useEffect(() => {
    let isMounted = true;
    apiEndpoints.getHealth()
      .then((res) => { if (isMounted) setIsOnline(res.status === 'healthy'); })
      .catch(() => { if (isMounted) setIsOnline(false); });
    return () => { isMounted = false; };
  }, []);
  return isOnline;
}

function PlantClockWidget({
  currentTime,
  onOpenAdvance,
  disabled,
}: {
  currentTime: number;
  onOpenAdvance: () => void;
  disabled?: boolean;
}): React.ReactElement {
  return (
    <div
      data-tour="plant-clock"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        padding: '0.25rem 0.6rem',
        backgroundColor: 'var(--bg-app)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-subtle)',
        fontSize: 'var(--font-size-small)',
      }}
      title="Plant Clock represents current operational simulated shop floor minute"
    >
      <span style={{ fontSize: 'var(--font-size-body)' }} aria-hidden="true">⏱️</span>
      <span className="plant-clock-label" style={{ color: 'var(--text-secondary)' }}>Plant Clock:</span>
      <strong className="font-mono" style={{ color: 'var(--color-primary)' }}>t₀ = {currentTime}m</strong>
      <Button
        variant="secondary"
        size="sm"
        onClick={onOpenAdvance}
        disabled={disabled}
        style={{ padding: '0.15rem 0.5rem', fontSize: 'var(--font-size-small)', marginLeft: '0.25rem' }}
      >
        Advance
      </Button>
    </div>
  );
}

export function AppHeader({ onToggleSidebar, isSidebarOpen }: AppHeaderProps): React.ReactElement {
  const { workspaces, activeWorkspaceId, selectWorkspace, createWorkspace, status } = useWorkspace();
  const factoryCtx = useOptionalFactory();
  const { startTour } = useTour();
  const isOnline = useBackendStatus();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAdvanceModal, setShowAdvanceModal] = useState(false);

  const inProgressOps = useMemo(() => {
    if (!factoryCtx?.factory) return [];
    const ops: InProgressOpInfo[] = [];
    for (const o of factoryCtx.factory.orders) {
      for (const op of o.operations) {
        if (
          op.status === 'IN_PROGRESS' &&
          typeof op.actual_start_minute === 'number' &&
          typeof op.remaining_duration_minutes === 'number'
        ) {
          ops.push({
            id: op.id,
            orderExternalId: o.external_id,
            orderName: o.name,
            sequenceIndex: op.sequence_index,
            machineId: op.machine_id,
            actualStartMinute: op.actual_start_minute,
            remainingDurationMinutes: op.remaining_duration_minutes,
          });
        }
      }
    }
    return ops;
  }, [factoryCtx?.factory]);

  const currentClock = factoryCtx?.factory?.current_time_minute ?? 0;

  return (
    <header className="app-header">
      <BrandLogo onToggleSidebar={onToggleSidebar} isSidebarOpen={isSidebarOpen} />
      <div className="app-header-actions" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <Button
          variant="secondary"
          size="sm"
          onClick={startTour}
          aria-label="Start Guided Product Tour"
          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
        >
          <span aria-hidden="true">🧭</span>
          <span className="tour-button-label">Guided Tour</span>
        </Button>
        {factoryCtx && (
          <PlantClockWidget
            currentTime={currentClock}
            onOpenAdvance={() => setShowAdvanceModal(true)}
            disabled={!activeWorkspaceId || !factoryCtx.factory}
          />
        )}
        <WorkspaceSelector
          workspaces={workspaces}
          activeWorkspaceId={activeWorkspaceId}
          onSelect={selectWorkspace}
          disabled={workspaces.length === 0 || status === 'loading'}
          onNewClick={() => setShowCreateModal(true)}
        />
        <BackendStatusIndicator isOnline={isOnline} />
      </div>

      {showCreateModal && (
        <WorkspaceModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={async (name, desc) => { await createWorkspace(name, desc); }}
        />
      )}

      {showAdvanceModal && factoryCtx && (
        <ClockAdvanceModal
          isOpen={showAdvanceModal}
          onClose={() => setShowAdvanceModal(false)}
          currentClock={currentClock}
          inProgressOps={inProgressOps}
          onAdvance={async (payload) => {
            await factoryCtx.advanceClock(payload);
          }}
        />
      )}
    </header>
  );
}
