/**
 * Production Factory & Shop Floor Management View
 * Governed by DATA_AND_API.md Section 3.2, SPECIFICATION.md, and PROJECT_RULES.md.
 */

import React, { useState } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { useRouter } from '../router/RouterContext';
import { useWorkspace } from '../context/WorkspaceContext';
import { FactoryProvider, useFactory, FactoryContextValue } from '../context/FactoryContext';
import { MachinesTab } from './factory/MachinesTab';
import { OrdersTab } from './factory/OrdersTab';
import { FactoryValidationCard } from './factory/FactoryValidationCard';

type FactoryTab = 'machines' | 'orders' | 'validation';

function FactoryTabBar({
  activeTab, onSelectTab, machineCount, orderCount,
}: {
  activeTab: FactoryTab; onSelectTab: (tab: FactoryTab) => void; machineCount: number; orderCount: number;
}): React.ReactElement {
  return (
    <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-subtle)', marginBottom: '1.5rem', overflowX: 'auto' }}>
      <button type="button" className={`btn btn-sm ${activeTab === 'machines' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => onSelectTab('machines')} style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}>
        Machines & Maintenance ({machineCount})
      </button>
      <button type="button" className={`btn btn-sm ${activeTab === 'orders' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => onSelectTab('orders')} style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}>
        Production Orders & Routings ({orderCount})
      </button>
      <button type="button" className={`btn btn-sm ${activeTab === 'validation' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => onSelectTab('validation')} style={{ borderRadius: 'var(--radius-md) var(--radius-md) 0 0' }}>
        Capacity & Pre-Solve Validation
      </button>
    </div>
  );
}

function FactoryTabPanels({
  tab, ctx,
}: {
  tab: FactoryTab; ctx: FactoryContextValue;
}): React.ReactElement | null {
  const { factory, status, validationResult, isValidating, validateCurrentFactory } = ctx;
  if (!factory) return null;
  if (tab === 'machines') {
    return (
      <MachinesTab
        machines={factory.machines}
        downtimes={factory.downtimes}
        orders={factory.orders}
        onAddMachine={ctx.addMachine}
        onUpdateMachine={ctx.updateMachine}
        onDeleteMachine={ctx.deleteMachine}
        onAddDowntime={ctx.addDowntime}
        onDeleteDowntime={ctx.deleteDowntime}
        isLoading={status === 'loading'}
      />
    );
  }
  if (tab === 'orders') {
    return <OrdersTab orders={factory.orders} machines={factory.machines} onAddOrder={ctx.addOrder} onUpdateOrder={ctx.updateOrder} onDeleteOrder={ctx.deleteOrder} />;
  }
  return (
    <FactoryValidationCard
      validationResult={validationResult}
      isValidating={isValidating}
      onValidate={async () => { await validateCurrentFactory(); }}
      machineCount={factory.machines.length}
      orderCount={factory.orders.length}
    />
  );
}

function FactoryInnerView(): React.ReactElement {
  const { activeWorkspace } = useWorkspace();
  const { navigate } = useRouter();
  const [tab, setTab] = useState<FactoryTab>('machines');
  const ctx = useFactory();

  if (!activeWorkspace) {
    return (
      <EmptyState
        title="No Workspace Selected"
        description="Select or create a planning workspace to manage shop floor assets and production orders."
        action={<Button variant="primary" onClick={() => navigate('overview')}>Go to Overview</Button>}
      />
    );
  }

  return (
    <div>
      <PageHeader
        title="Factory & Shop Floor Management"
        description={`Workspace: ${activeWorkspace.name} — Real-time persistence backed by local SQLite WAL and Google OR-Tools CP-SAT domain model.`}
        badge={<Badge variant="optimal">Milestone 09A Active</Badge>}
        actions={
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button variant="secondary" size="sm" onClick={() => ctx.loadFactory()} disabled={ctx.status === 'loading'}>Refresh Data</Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('overview')}>← Overview</Button>
          </div>
        }
      />
      {ctx.error && <div style={{ marginBottom: '1.5rem' }}><ErrorBanner message={ctx.error} onRetry={ctx.loadFactory} /></div>}
      {ctx.status === 'loading' && !ctx.factory ? (
        <LoadingState message="Loading factory configuration from SQLite database..." />
      ) : ctx.factory ? (
        <>
          <FactoryTabBar activeTab={tab} onSelectTab={setTab} machineCount={ctx.factory.machines.length} orderCount={ctx.factory.orders.length} />
          <FactoryTabPanels tab={tab} ctx={ctx} />
        </>
      ) : null}
    </div>
  );
}

export function FactoryView(): React.ReactElement {
  return (
    <FactoryProvider>
      <FactoryInnerView />
    </FactoryProvider>
  );
}
