/**
 * Production Orders & Routing Management View
 * Governed by DATA_AND_API.md Section 1.1 Tables 4 & 5.
 */

import React, { useState } from 'react';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { EmptyState } from '../../components/common/EmptyState';
import { MachineResponse, OrderCreate, OrderResponse } from '../../types/api';
import { OrderModal } from './OrderModal';
import { DeleteConfirmModal } from './DeleteConfirmModal';

export interface OrdersTabProps {
  orders: OrderResponse[];
  machines: MachineResponse[];
  onAddOrder: (o: OrderCreate) => Promise<void>;
  onUpdateOrder: (id: string, o: OrderCreate) => Promise<void>;
  onDeleteOrder: (id: string) => Promise<void>;
}

function RoutingBadges({ ops, machineMap }: { ops: OrderResponse['operations']; machineMap: Map<string, MachineResponse> }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.25rem' }}>
      {ops.map((op, idx) => {
        const m = machineMap.get(op.machine_id);
        const label = m ? m.external_id : op.machine_id.slice(0, 6);
        return (
          <React.Fragment key={op.id || idx}>
            {idx > 0 && <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>→</span>}
            <span className="badge badge-neutral font-mono" style={{ fontSize: '0.7rem' }}>
              {label} ({op.processing_minutes}m)
            </span>
          </React.Fragment>
        );
      })}
    </div>
  );
}

function OrderTableRow({
  order, machineMap, onEdit, onDelete,
}: {
  order: OrderResponse; machineMap: Map<string, MachineResponse>; onEdit: () => void; onDelete: () => void;
}): React.ReactElement {
  const total = order.operations.reduce((acc, op) => acc + op.processing_minutes, 0);
  return (
    <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
      <td style={{ padding: '0.625rem 0.75rem', fontWeight: 600 }}><span className="font-mono">{order.external_id}</span></td>
      <td style={{ padding: '0.625rem 0.75rem', color: 'var(--text-primary)' }}>{order.name}</td>
      <td style={{ padding: '0.625rem 0.75rem' }} className="font-mono">{order.release_minute}m</td>
      <td style={{ padding: '0.625rem 0.75rem' }} className="font-mono">{order.due_minute}m</td>
      <td style={{ padding: '0.625rem 0.75rem' }} className="font-mono">{order.tardiness_weight}</td>
      <td style={{ padding: '0.625rem 0.75rem' }}><RoutingBadges ops={order.operations} machineMap={machineMap} /></td>
      <td style={{ padding: '0.625rem 0.75rem' }} className="font-mono"><Badge variant="neutral">{total}m</Badge></td>
      <td style={{ padding: '0.625rem 0.75rem', textAlign: 'right' }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.35rem' }}>
          <Button variant="secondary" size="sm" onClick={onEdit}>Edit</Button>
          <Button variant="danger" size="sm" onClick={onDelete}>Delete</Button>
        </div>
      </td>
    </tr>
  );
}

function OrdersTable({
  orders, machineMap, onEdit, onDelete,
}: {
  orders: OrderResponse[]; machineMap: Map<string, MachineResponse>;
  onEdit: (o: OrderResponse) => void; onDelete: (o: OrderResponse) => void;
}): React.ReactElement {
  return (
    <Card title="Active Production Orders Table" subtitle="Sorted by order code. Operations sequence dictates strict processing order.">
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8125rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-strong)', color: 'var(--text-secondary)' }}>
              <th style={{ padding: '0.625rem 0.75rem' }}>Order Code</th>
              <th style={{ padding: '0.625rem 0.75rem' }}>Product / Name</th>
              <th style={{ padding: '0.625rem 0.75rem' }}>Release (r_j)</th>
              <th style={{ padding: '0.625rem 0.75rem' }}>Due (d_j)</th>
              <th style={{ padding: '0.625rem 0.75rem' }}>Weight (w_j)</th>
              <th style={{ padding: '0.625rem 0.75rem' }}>Routing Sequence</th>
              <th style={{ padding: '0.625rem 0.75rem' }}>Total Work</th>
              <th style={{ padding: '0.625rem 0.75rem', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <OrderTableRow key={o.id} order={o} machineMap={machineMap} onEdit={() => onEdit(o)} onDelete={() => onDelete(o)} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function OrdersTab({
  orders, machines, onAddOrder, onUpdateOrder, onDeleteOrder,
}: OrdersTabProps): React.ReactElement {
  const [modalOpen, setModalOpen] = useState(false);
  const [editingOrder, setEditingOrder] = useState<OrderResponse | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<OrderResponse | null>(null);
  const machineMap = new Map(machines.map((m) => [m.id, m]));

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    await onDeleteOrder(deleteTarget.id);
    setDeleteTarget(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--text-primary)' }}>Production Orders & Sequences ({orders.length})</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem' }}>Job orders with sequential machine operations, release dates, and tardiness penalty weights.</p>
        </div>
        <Button variant="primary" size="sm" onClick={() => { setEditingOrder(null); setModalOpen(true); }} disabled={machines.length === 0}>
          + Create Production Order
        </Button>
      </div>

      {machines.length === 0 ? (
        <Card title="Prerequisite: Machine Workstations Required">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Before creating production orders and routing steps, you must configure at least one machine workstation in the <strong>Machines & Maintenance</strong> tab.
          </p>
        </Card>
      ) : orders.length === 0 ? (
        <EmptyState title="No Production Orders in Workspace" description="Production orders define manufacturing jobs with release times, due dates, and operation sequences." action={<Button variant="primary" onClick={() => { setEditingOrder(null); setModalOpen(true); }}>+ Create First Order</Button>} />
      ) : (
        <OrdersTable orders={orders} machineMap={machineMap} onEdit={(o) => { setEditingOrder(o); setModalOpen(true); }} onDelete={(o) => setDeleteTarget(o)} />
      )}

      <OrderModal isOpen={modalOpen} machines={machines} initialOrder={editingOrder} onSave={async (d) => { if (editingOrder) await onUpdateOrder(editingOrder.id, d); else await onAddOrder(d); }} onClose={() => setModalOpen(false)} existingCodes={orders.map((o) => o.external_id)} />
      <DeleteConfirmModal isOpen={Boolean(deleteTarget)} title="Delete Production Order" message="Are you sure you want to permanently delete this production order and its operation sequence?" itemName={deleteTarget ? `${deleteTarget.external_id} (${deleteTarget.name})` : undefined} onConfirm={confirmDelete} onCancel={() => setDeleteTarget(null)} />
    </div>
  );
}
