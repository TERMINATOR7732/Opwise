/**
 * Machines & Maintenance Management View
 * Governed by DATA_AND_API.md Section 1.1 Tables 2 & 3.
 */

import React, { useState } from 'react';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { EmptyState } from '../../components/common/EmptyState';
import { MachineResponse, DowntimeResponse, MachineCreate, DowntimeCreate, OrderResponse } from '../../types/api';
import { MachineModal } from './MachineModal';
import { DowntimeModal } from './DowntimeModal';
import { DeleteConfirmModal } from './DeleteConfirmModal';

export interface MachinesTabProps {
  machines: MachineResponse[];
  downtimes: DowntimeResponse[];
  orders: OrderResponse[];
  onAddMachine: (m: MachineCreate) => Promise<void>;
  onUpdateMachine: (id: string, m: MachineCreate) => Promise<void>;
  onDeleteMachine: (id: string) => Promise<void>;
  onAddDowntime: (dt: DowntimeCreate) => Promise<void>;
  onDeleteDowntime: (id: string) => Promise<void>;
  isLoading?: boolean;
}

function MachineCard({
  machine, downtimeCount, operationCount, onEdit, onScheduleDowntime, onDelete,
}: {
  machine: MachineResponse; downtimeCount: number; operationCount: number;
  onEdit: () => void; onScheduleDowntime: () => void; onDelete: () => void;
}): React.ReactElement {
  return (
    <Card
      title={machine.external_id}
      subtitle={machine.name}
      actions={
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          <Button variant="secondary" size="sm" onClick={onEdit}>Edit</Button>
          <Button variant="danger" size="sm" onClick={onDelete}>Delete</Button>
        </div>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.8125rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
          <span>Assigned Downtimes:</span>
          <span className="font-mono" style={{ color: downtimeCount > 0 ? 'var(--color-warning)' : 'var(--text-primary)' }}>
            {downtimeCount} {downtimeCount === 1 ? 'window' : 'windows'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
          <span>Routed Operations:</span>
          <span className="font-mono" style={{ color: 'var(--text-primary)' }}>
            {operationCount} {operationCount === 1 ? 'step' : 'steps'}
          </span>
        </div>
        <div style={{ paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end' }}>
          <Button variant="secondary" size="sm" onClick={onScheduleDowntime}>+ Add Maintenance</Button>
        </div>
      </div>
    </Card>
  );
}

function DowntimeRows({
  downtimes, machineMap, onDeleteDowntime,
}: {
  downtimes: DowntimeResponse[]; machineMap: Map<string, MachineResponse>;
  onDeleteDowntime: (dt: DowntimeResponse) => void;
}): React.ReactElement {
  return (
    <tbody>
      {downtimes.map((dt) => {
        const m = machineMap.get(dt.machine_id);
        return (
          <tr key={dt.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
            <td style={{ padding: '0.625rem 0.75rem', fontWeight: 600 }}>
              <span className="font-mono">{m ? m.external_id : dt.machine_id}</span>
              {m && <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem', fontWeight: 400 }}>({m.name})</span>}
            </td>
            <td style={{ padding: '0.625rem 0.75rem' }} className="font-mono">[{dt.start_minute}, {dt.end_minute})</td>
            <td style={{ padding: '0.625rem 0.75rem' }}><Badge variant="warning">{dt.end_minute - dt.start_minute}m</Badge></td>
            <td style={{ padding: '0.625rem 0.75rem', color: dt.reason ? 'var(--text-primary)' : 'var(--text-muted)' }}>{dt.reason || '—'}</td>
            <td style={{ padding: '0.625rem 0.75rem', textAlign: 'right' }}>
              <Button variant="danger" size="sm" onClick={() => onDeleteDowntime(dt)}>Delete</Button>
            </td>
          </tr>
        );
      })}
    </tbody>
  );
}

function DowntimeTable({
  downtimes, machines, onDeleteDowntime,
}: {
  downtimes: DowntimeResponse[]; machines: MachineResponse[]; onDeleteDowntime: (dt: DowntimeResponse) => void;
}): React.ReactElement {
  const machineMap = new Map(machines.map((m) => [m.id, m]));
  if (downtimes.length === 0) {
    return (
      <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
        No planned maintenance windows scheduled. All workstations are available at 100% capacity.
      </div>
    );
  }
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8125rem' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border-strong)', color: 'var(--text-secondary)' }}>
            <th style={{ padding: '0.625rem 0.75rem' }}>Machine</th>
            <th style={{ padding: '0.625rem 0.75rem' }}>Window [Start, End)</th>
            <th style={{ padding: '0.625rem 0.75rem' }}>Duration</th>
            <th style={{ padding: '0.625rem 0.75rem' }}>Reason</th>
            <th style={{ padding: '0.625rem 0.75rem', textAlign: 'right' }}>Action</th>
          </tr>
        </thead>
        <DowntimeRows downtimes={downtimes} machineMap={machineMap} onDeleteDowntime={onDeleteDowntime} />
      </table>
    </div>
  );
}

function MachineGrid({
  machines, downtimes, orders, onEdit, onScheduleDowntime, onDelete,
}: {
  machines: MachineResponse[]; downtimes: DowntimeResponse[]; orders: OrderResponse[];
  onEdit: (m: MachineResponse) => void; onScheduleDowntime: (mId: string) => void; onDelete: (m: MachineResponse) => void;
}): React.ReactElement {
  const getDtCount = (id: string) => downtimes.filter((d) => d.machine_id === id).length;
  const getOpCount = (id: string) => orders.flatMap((o) => o.operations).filter((op) => op.machine_id === id).length;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
      {machines.map((m) => (
        <MachineCard
          key={m.id}
          machine={m}
          downtimeCount={getDtCount(m.id)}
          operationCount={getOpCount(m.id)}
          onEdit={() => onEdit(m)}
          onScheduleDowntime={() => onScheduleDowntime(m.id)}
          onDelete={() => onDelete(m)}
        />
      ))}
    </div>
  );
}

export function MachinesTab({
  machines, downtimes, orders, onAddMachine, onUpdateMachine, onDeleteMachine, onAddDowntime, onDeleteDowntime,
}: MachinesTabProps): React.ReactElement {
  const [machineModalOpen, setMachineModalOpen] = useState(false);
  const [editingMachine, setEditingMachine] = useState<MachineResponse | null>(null);
  const [downtimeModalOpen, setDowntimeModalOpen] = useState(false);
  const [selectedMachineForDowntime, setSelectedMachineForDowntime] = useState<string | undefined>(undefined);
  const [deleteTarget, setDeleteTarget] = useState<{ type: 'machine' | 'downtime'; id: string; name: string } | null>(null);

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    if (deleteTarget.type === 'machine') await onDeleteMachine(deleteTarget.id);
    else await onDeleteDowntime(deleteTarget.id);
    setDeleteTarget(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)' }}>Machine Workstations ({machines.length})</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>Exclusive discrete processing resources with non-overlapping capacity.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Button variant="secondary" size="sm" onClick={() => { setSelectedMachineForDowntime(undefined); setDowntimeModalOpen(true); }} disabled={machines.length === 0}>+ Schedule Maintenance</Button>
          <Button variant="primary" size="sm" onClick={() => { setEditingMachine(null); setMachineModalOpen(true); }}>+ Add Machine</Button>
        </div>
      </div>

      {machines.length === 0 ? (
        <EmptyState title="No Machines Configured" description="A factory requires at least one machine workstation to process production orders." action={<Button variant="primary" onClick={() => { setEditingMachine(null); setMachineModalOpen(true); }}>+ Add First Machine</Button>} />
      ) : (
        <MachineGrid machines={machines} downtimes={downtimes} orders={orders} onEdit={(m) => { setEditingMachine(m); setMachineModalOpen(true); }} onScheduleDowntime={(mId) => { setSelectedMachineForDowntime(mId); setDowntimeModalOpen(true); }} onDelete={(m) => setDeleteTarget({ type: 'machine', id: m.id, name: `${m.external_id} (${m.name})` })} />
      )}

      {machines.length > 0 && (
        <Card title="Planned Maintenance Windows" subtitle="Half-open [start, end) intervals during which machine processing is strictly prohibited">
          <DowntimeTable downtimes={downtimes} machines={machines} onDeleteDowntime={(dt) => setDeleteTarget({ type: 'downtime', id: dt.id, name: `Window [${dt.start_minute}, ${dt.end_minute}) on ${dt.machine_id}` })} />
        </Card>
      )}

      <MachineModal isOpen={machineModalOpen} initialMachine={editingMachine} onSave={async (d) => { if (editingMachine) await onUpdateMachine(editingMachine.id, d); else await onAddMachine(d); }} onClose={() => setMachineModalOpen(false)} existingCodes={machines.map((m) => m.external_id)} />
      <DowntimeModal isOpen={downtimeModalOpen} machines={machines} initialMachineId={selectedMachineForDowntime} onSave={async (d) => { await onAddDowntime(d); }} onClose={() => setDowntimeModalOpen(false)} />
      <DeleteConfirmModal isOpen={Boolean(deleteTarget)} title={deleteTarget?.type === 'machine' ? 'Delete Machine Workstation' : 'Delete Maintenance Window'} message={deleteTarget?.type === 'machine' ? 'Deleting this machine will also remove maintenance windows and cascaded routing operations assigned to it.' : 'Are you sure you want to remove this maintenance window?'} itemName={deleteTarget?.name} onConfirm={confirmDelete} onCancel={() => setDeleteTarget(null)} />
    </div>
  );
}
