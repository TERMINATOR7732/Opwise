import React from 'react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { BottleneckReportItem } from '../../types/reports';

export interface BottleneckCardProps {
  bottleneck: BottleneckReportItem;
}

export function BottleneckCard({ bottleneck }: BottleneckCardProps): React.ReactElement {
  const hasBottleneck = bottleneck.primary_bottleneck_machine_id != null;

  return (
    <Card className="bottleneck-card mb-6 border border-amber-900/40 bg-amber-950/20 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-amber-800/30 pb-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-amber-500" aria-hidden="true" />
          <h3 className="text-base font-bold text-slate-100">Primary Bottleneck Diagnosis</h3>
        </div>
        {hasBottleneck ? (
          <Badge variant="warning" className="font-mono text-xs">
            {bottleneck.primary_bottleneck_machine_name || bottleneck.primary_bottleneck_machine_id}
          </Badge>
        ) : (
          <Badge variant="neutral" className="font-mono text-xs">
            NO CONTENTION
          </Badge>
        )}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded border border-slate-800 bg-slate-900/60 p-3">
          <div className="text-xs text-slate-400">Bottleneck Workstation</div>
          <div className="mt-1 text-lg font-bold text-amber-300 font-mono">
            {bottleneck.primary_bottleneck_machine_name || bottleneck.primary_bottleneck_machine_id || 'None'}
          </div>
          <div className="text-xs text-slate-500 font-mono">
            ID: {bottleneck.primary_bottleneck_machine_id || 'N/A'}
          </div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-900/60 p-3">
          <div className="text-xs text-slate-400">Peak Machine Workload</div>
          <div className="mt-1 text-lg font-bold text-slate-100 font-mono">
            {bottleneck.highest_workload_minutes} min
          </div>
          <div className="text-xs text-slate-500">cumulative processing duration</div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-900/60 p-3">
          <div className="text-xs text-slate-400">Peak Net Utilization</div>
          <div className="mt-1 text-lg font-bold text-slate-100 font-mono">
            {bottleneck.highest_net_utilization_pct.toFixed(2)}%
          </div>
          <div className="text-xs text-slate-500">of available non-downtime capacity</div>
        </div>
      </div>

      {bottleneck.ranked_machines.length > 0 && (
        <div className="mt-4 rounded border border-slate-800 bg-slate-900/40 p-3 text-xs">
          <span className="font-semibold text-slate-400">Machine Load Hierarchy: </span>
          <span className="font-mono text-slate-300">
            {bottleneck.ranked_machines.join('  ➔  ')}
          </span>
        </div>
      )}

      <div className="mt-4 rounded border border-amber-900/30 bg-amber-950/30 p-3 text-xs leading-relaxed text-amber-200/80">
        <strong className="text-amber-300">Disclaimer: </strong>
        {bottleneck.disclaimer}
      </div>
    </Card>
  );
}
