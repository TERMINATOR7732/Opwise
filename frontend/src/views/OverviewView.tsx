import React, { useState } from 'react';
import { useWorkspace } from '../context/WorkspaceContext';
import { useRouter } from '../router/RouterContext';
import { AppRoute } from '../router/types';
import { PageHeader } from '../components/layout/PageHeader';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { LoadingState } from '../components/common/LoadingState';
import { DemoScenariosCard } from './overview/DemoScenariosCard';

function ActiveWorkspaceCard({
  activeWorkspace,
  onNewWorkspace,
}: {
  activeWorkspace: ReturnType<typeof useWorkspace>['activeWorkspace'];
  onNewWorkspace: () => void;
}): React.ReactElement {
  return (
    <Card
      title={activeWorkspace ? activeWorkspace.name : 'Select a Workspace'}
      subtitle={activeWorkspace ? `ID: ${activeWorkspace.id}` : undefined}
      actions={
        <Button variant="secondary" size="sm" onClick={onNewWorkspace}>
          + New Workspace
        </Button>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <div>
          <span className="form-label">Description</span>
          <p style={{ color: 'var(--text-primary)', fontSize: '0.875rem' }}>
            {activeWorkspace?.description || 'No description provided.'}
          </p>
        </div>
        <div>
          <span className="form-label">Created At</span>
          <p className="font-mono" style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            {activeWorkspace?.created_at ? new Date(activeWorkspace.created_at).toLocaleString() : '—'}
          </p>
        </div>
        <div>
          <span className="form-label">System Mode</span>
          <p style={{ fontSize: '0.875rem' }}>
            <Badge variant="optimal">Local-First SQLite WAL</Badge>
          </p>
        </div>
      </div>
    </Card>
  );
}

function WorkflowSteps({ onNavigate }: { onNavigate: (route: AppRoute) => void }): React.ReactElement {
  return (
    <div>
      <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '1rem' }}>
        Production Planning Workflow
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
        <Card title="1. Shop Floor & Routings" subtitle="Machines, maintenance windows, and production orders">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
            Define machine capacities, planned downtime windows, and multi-operation job sequences with deterministic durations and release times.
          </p>
          <Button variant="secondary" size="sm" onClick={() => onNavigate('factory')}>
            View Factory (M09) →
          </Button>
        </Card>
        <Card title="2. CP-SAT Optimization" subtitle="Pure Makespan, Weighted Tardiness, or Lexicographic">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
            Run discrete constraint optimization via Google OR-Tools CP-SAT. Bounded solver envelopes with mathematical optimality gap reporting.
          </p>
          <Button variant="secondary" size="sm" onClick={() => onNavigate('planning')}>
            View Planning (M09) →
          </Button>
        </Card>
        <Card title="3. Verification & Gantt" subtitle="Clean-room invariant auditing and interactive schedule">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
            Validate every schedule against all 8 operational invariants. Inspect machine allocations, downtime exclusions, and bottlenecks.
          </p>
          <Button variant="secondary" size="sm" onClick={() => onNavigate('schedules')}>
            View Schedules (M09) →
          </Button>
        </Card>
      </div>
    </div>
  );
}

function ArchitectureStatusCard(): React.ReactElement {
  return (
    <Card title="System Architectural Status" subtitle="Verified Milestones & Capability Roadmap">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Milestone 01–07: Core CP-SAT Solver, Verifier, Metrics & SQLite REST API</span>
          <Badge variant="optimal">VERIFIED (100% PASS)</Badge>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Milestone 08–09: Factory Management Grid & Interactive Gantt Canvas</span>
          <Badge variant="optimal">VERIFIED (100% PASS)</Badge>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Milestone 10: Disruption Lab & Scenario Comparator</span>
          <Badge variant="optimal">VERIFIED (100% PASS)</Badge>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Milestone 11: Production Reports, KPI Recalculation & Data Export</span>
          <Badge variant="optimal">VERIFIED (100% PASS)</Badge>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Milestone 12: Safe Two-Phase CSV/XLSX Import Engine & Validation</span>
          <Badge variant="optimal">VERIFIED (100% PASS)</Badge>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Milestone 13: Standalone Client-Side Demo Mode & In-Browser Verifier</span>
          <Badge variant="optimal">ACTIVE (CURRENT)</Badge>
        </div>
      </div>
    </Card>
  );
}

function OverviewFormFields({
  name,
  setName,
  desc,
  setDesc,
  error,
}: {
  name: string;
  setName: (v: string) => void;
  desc: string;
  setDesc: (v: string) => void;
  error: string | null;
}): React.ReactElement {
  return (
    <div className="card-body">
      {error && <p style={{ color: 'var(--color-critical)', fontSize: '0.8125rem', marginBottom: '0.75rem' }}>{error}</p>}
      <div className="form-group">
        <label htmlFor="overview-ws-name" className="form-label">Workspace Name *</label>
        <input
          id="overview-ws-name"
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Primary Machine Shop"
          className="form-input"
          autoFocus
        />
      </div>
      <div className="form-group" style={{ marginBottom: 0 }}>
        <label htmlFor="overview-ws-desc" className="form-label">Description (Optional)</label>
        <input
          id="overview-ws-desc"
          type="text"
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
          placeholder="e.g. High-tolerance milling and turning cell"
          className="form-input"
        />
      </div>
    </div>
  );
}

function OverviewModalShell({
  onClose,
  children,
}: {
  onClose: () => void;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <div
      role="dialog"
      aria-labelledby="overview-modal-title"
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
          <h2 id="overview-modal-title" className="card-title">Create Workspace</h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose} aria-label="Close modal">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function WorkspaceCreateDialog({
  isOpen,
  onClose,
  onCreate,
}: {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (name: string, desc: string) => Promise<void>;
}): React.ReactElement | null {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [createErr, setCreateErr] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setIsCreating(true);
    setCreateErr(null);
    try {
      await onCreate(name, desc);
      onClose();
      setName('');
      setDesc('');
    } catch (err: unknown) {
      setCreateErr(err instanceof Error ? err.message : 'Failed to create workspace');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <OverviewModalShell onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <OverviewFormFields name={name} setName={setName} desc={desc} setDesc={setDesc} error={createErr} />
        <div style={{ padding: '0.875rem 1.25rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
          <Button type="button" variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" size="sm" isLoading={isCreating}>Create Workspace</Button>
        </div>
      </form>
    </OverviewModalShell>
  );
}

function OverviewWorkspaceContent({
  activeWorkspace,
  onNewWorkspace,
  onNavigate,
}: {
  activeWorkspace: ReturnType<typeof useWorkspace>['activeWorkspace'];
  onNewWorkspace: () => void;
  onNavigate: (route: AppRoute) => void;
}): React.ReactElement {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <ActiveWorkspaceCard activeWorkspace={activeWorkspace} onNewWorkspace={onNewWorkspace} />
      <DemoScenariosCard />
      <WorkflowSteps onNavigate={onNavigate} />
      <ArchitectureStatusCard />
    </div>
  );
}

export function OverviewView(): React.ReactElement {
  const { workspaces, activeWorkspace, status, error, refreshWorkspaces, createWorkspace } = useWorkspace();
  const { navigate } = useRouter();
  const [showCreateModal, setShowCreateModal] = useState(false);

  return (
    <div>
      <PageHeader
        title="Production Planning Overview"
        description="Deterministic discrete manufacturing optimization powered by Google OR-Tools CP-SAT and verified by clean-room invariant auditing."
        badge={<Badge variant="optimal">Milestone 13 Active</Badge>}
        actions={<Button variant="secondary" size="sm" onClick={() => refreshWorkspaces()}>Refresh State</Button>}
      />

      {error && (
        <div style={{ marginBottom: '1.5rem' }}>
          <ErrorBanner message={error} onRetry={refreshWorkspaces} />
        </div>
      )}

      {status === 'loading' && workspaces.length === 0 ? (
        <LoadingState message="Loading workspaces..." />
      ) : workspaces.length === 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <EmptyState
            title="No Workspaces Configured"
            description="Opwise organizes production planning into isolated workspaces. Create your first workspace to begin modeling shop floor capacity, or explore one of the pre-solved synthetic demo scenarios below."
            action={<Button variant="primary" onClick={() => setShowCreateModal(true)}>+ Create First Workspace</Button>}
          />
          <DemoScenariosCard />
        </div>
      ) : (
        <OverviewWorkspaceContent
          activeWorkspace={activeWorkspace}
          onNewWorkspace={() => setShowCreateModal(true)}
          onNavigate={navigate}
        />
      )}

      <WorkspaceCreateDialog
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={async (n, d) => { await createWorkspace(n, d); }}
      />
    </div>
  );
}
