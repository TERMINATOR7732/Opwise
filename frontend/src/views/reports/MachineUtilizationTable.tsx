import React from 'react';
import { Card } from '../../components/common/Card';
import { MachineUtilizationItem } from '../../types/reports';

export interface MachineUtilizationTableProps {
  machines: MachineUtilizationItem[];
}

function getUtilizationColor(pct: number): string {
  if (pct >= 90) return 'text-rose-400 bg-rose-500';
  if (pct >= 70) return 'text-amber-400 bg-amber-500';
  return 'text-emerald-400 bg-emerald-500';
}

export function MachineUtilizationTable({ machines }: MachineUtilizationTableProps): React.ReactElement {
  return (
    <Card className="machine-utilization-table mb-6 border border-slate-700 bg-slate-900/60 p-5">
      <div className="border-b border-slate-700/60 pb-3">
        <h3 className="text-base font-bold text-slate-100">Machine Capacity & Utilization Audit</h3>
        <p className="mt-0.5 text-xs text-slate-400">
          Workload, planned maintenance, and net utilization computed using true available window: Wm / (Cmax - Dm).
        </p>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="border-b border-slate-700 bg-slate-800/60 text-slate-400 font-semibold uppercase tracking-wider">
            <tr>
              <th scope="col" className="px-3 py-2.5">Machine</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Workload</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Downtime</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Available</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Idle</th>
              <th scope="col" className="px-3 py-2.5 text-center font-mono">Net Util %</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Gross Util %</th>
              <th scope="col" className="px-3 py-2.5 text-right font-mono">Ops</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {machines.map((m) => {
              const colorClasses = getUtilizationColor(m.net_utilization_pct);
              const [textColor, bgColor] = colorClasses.split(' ');

              return (
                <tr key={m.machine_id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="px-3 py-2.5 font-medium text-slate-200">
                    <div>{m.machine_name}</div>
                    <div className="text-[10px] text-slate-500 font-mono">{m.machine_id}</div>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-slate-100">
                    {m.workload_minutes}m
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-slate-400">
                    {m.downtime_minutes}m
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-slate-300">
                    {m.available_capacity_minutes}m
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-slate-400">
                    {m.idle_minutes}m
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${bgColor}`}
                          style={{ width: `${Math.min(100, m.net_utilization_pct)}%` }}
                        />
                      </div>
                      <span className={`font-mono font-bold text-xs ${textColor}`}>
                        {m.net_utilization_pct.toFixed(1)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-slate-400">
                    {m.gross_utilization_pct.toFixed(1)}%
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-slate-300">
                    {m.assigned_operation_count}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
