import React from 'react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { OrderPerformanceItem } from '../../types/reports';

export interface OrderPerformanceTableProps {
  orders: OrderPerformanceItem[];
}

export function OrderPerformanceTable({ orders }: OrderPerformanceTableProps): React.ReactElement {
  return (
    <Card className="order-performance-table mb-6 border border-slate-700 bg-slate-900/60 p-5">
      <div className="border-b border-slate-700/60 pb-3">
        <h3 className="text-base font-bold text-slate-100">Production Order Due Date & Tardiness Audit</h3>
        <p className="mt-0.5 text-xs text-slate-400">
          Per-order release windows, completion timestamps, tardiness penalties, and delivery slack.
        </p>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="border-b border-slate-700 bg-slate-800/60 text-slate-400 font-semibold uppercase tracking-wider">
            <tr>
              <th scope="col" className="px-3 py-2.5">Order</th>
              <th scope="col" className="px-3 py-2.5 text-center font-mono">Status</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Release</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Due Date</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Completion</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Tardiness</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Weight</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Weighted Tard.</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Slack</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Ops</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {orders.map((o) => (
              <tr key={o.order_id} className="hover:bg-slate-800/30 transition-colors">
                <td className="px-3 py-2.5 font-medium text-slate-200">
                  <div className="font-mono text-slate-100">{o.order_code}</div>
                  <div className="text-[10px] text-slate-500 font-mono">{o.order_id}</div>
                </td>
                <td className="px-3 py-2.5 text-center">
                  <Badge
                    variant={o.is_on_time ? 'optimal' : 'critical'}
                    className="font-mono text-[10px] px-2 py-0.5"
                  >
                    {o.is_on_time ? 'ON TIME' : 'LATE'}
                  </Badge>
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-slate-400">
                  {o.release_minute}m
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-slate-300">
                  {o.due_date_minute}m
                </td>
                <td className="px-3 py-2.5 text-right font-mono font-bold text-slate-100">
                  {o.completion_minute}m
                </td>
                <td className="px-3 py-2.5 text-right font-mono">
                  <span className={o.tardiness_minutes > 0 ? 'text-rose-400 font-bold' : 'text-slate-500'}>
                    {o.tardiness_minutes > 0 ? `+${o.tardiness_minutes}m` : '0m'}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-slate-400">
                  w={o.tardiness_weight}
                </td>
                <td className="px-3 py-2.5 text-right font-mono">
                  <span className={o.weighted_tardiness > 0 ? 'text-rose-400 font-bold' : 'text-slate-500'}>
                    {o.weighted_tardiness}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-right font-mono">
                  <span className={o.slack_minutes > 0 ? 'text-emerald-400' : 'text-slate-500'}>
                    {o.slack_minutes > 0 ? `${o.slack_minutes}m` : '0m'}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-slate-300">
                  {o.operation_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
