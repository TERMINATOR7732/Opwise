import React from 'react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { ScheduleExplanationItem } from '../../types/reports';

export interface ScheduleExplanationsCardProps {
  explanations: ScheduleExplanationItem[];
}

export function ScheduleExplanationsCard({ explanations }: ScheduleExplanationsCardProps): React.ReactElement {
  if (explanations.length === 0) {
    return <></>;
  }

  return (
    <Card className="schedule-explanations-card mb-6 border border-slate-700 bg-slate-900/60 p-5">
      <div className="border-b border-slate-700/60 pb-3">
        <h3 className="text-base font-bold text-slate-100">Deterministic Mathematical Explanations</h3>
        <p className="mt-0.5 text-xs text-slate-400">
          Traceable evidence and mathematical formulations for calculated schedule properties.
        </p>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        {explanations.map((e, idx) => (
          <div
            key={`${e.entity_type}-${e.entity_id}-${idx}`}
            className="rounded border border-slate-800 bg-slate-800/30 p-3.5 text-xs"
          >
            <div className="flex items-center justify-between gap-2">
              <Badge variant="neutral" className="font-mono text-[10px]">
                {e.category}
              </Badge>
              <span className="font-mono text-[10px] text-slate-500">
                {e.entity_type}: {e.entity_id}
              </span>
            </div>

            <div className="mt-2 font-medium text-slate-200">{e.summary}</div>

            <div className="mt-2 rounded bg-slate-900/80 px-2 py-1 font-mono text-[11px] text-cyan-300">
              {e.mathematical_formula}
            </div>

            <div className="mt-2 text-slate-400 leading-relaxed">{e.reason}</div>

            <div className="mt-2 flex items-center gap-3 text-[11px] font-mono text-slate-400">
              <span>
                Measured: <strong className="text-slate-200">{e.measured_value}</strong>
              </span>
              {e.threshold_or_target && (
                <span>
                  Target: <strong className="text-slate-300">{e.threshold_or_target}</strong>
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
