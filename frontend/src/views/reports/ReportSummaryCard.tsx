import React from 'react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { SummaryKPIs, VerificationAuditSummary } from '../../types/reports';

export interface ReportSummaryCardProps {
  scheduleName: string;
  solverStatus: string;
  verificationStatus: string;
  objectiveType: string;
  summary: SummaryKPIs;
  audit: VerificationAuditSummary;
}

function formatMinutes(minutes: number): string {
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  const remMinutes = minutes % 60;
  return remMinutes > 0 ? `${hours}h ${remMinutes}m` : `${hours}h`;
}

export function ReportSummaryCard({
  scheduleName,
  solverStatus,
  verificationStatus,
  objectiveType,
  summary,
  audit,
}: ReportSummaryCardProps): React.ReactElement {
  const isOptimal = solverStatus === 'OPTIMAL';
  const isVerified = (verificationStatus === 'VERIFIED' || audit.is_valid) && audit.checks_passed >= 8;

  return (
    <Card className="report-summary-card mb-6 border border-slate-700 bg-slate-900/60 p-5">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-700/60 pb-4">
        <div>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Production Plan</span>
          <h2 className="text-xl font-bold text-slate-100">{scheduleName}</h2>
          <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
            <span>Objective:</span>
            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-300 font-mono">{objectiveType}</code>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={isOptimal ? 'optimal' : 'warning'} className="px-3 py-1 font-mono text-xs">
            {solverStatus}
          </Badge>
          <Badge variant={isVerified ? 'optimal' : 'critical'} className="px-3 py-1 font-mono text-xs">
            {isVerified ? `VERIFIED: ${audit.checks_passed}/${audit.checks_run} PASS` : 'VERIFICATION FAILED'}
          </Badge>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded border border-slate-800 bg-slate-800/40 p-3">
          <div className="text-xs font-medium text-slate-400">Makespan (Cmax)</div>
          <div className="mt-1 text-2xl font-bold text-slate-100 font-mono">
            {summary.makespan_minutes}m
          </div>
          <div className="text-xs text-slate-500 font-mono">{formatMinutes(summary.makespan_minutes)}</div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-800/40 p-3">
          <div className="text-xs font-medium text-slate-400">Weighted Tardiness</div>
          <div className="mt-1 text-2xl font-bold text-slate-100 font-mono">
            {summary.total_weighted_tardiness.toLocaleString()}
          </div>
          <div className="text-xs text-slate-500">penalty points</div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-800/40 p-3">
          <div className="text-xs font-medium text-slate-400">On-Time Delivery</div>
          <div className={`mt-1 text-2xl font-bold font-mono ${summary.on_time_rate_pct === 100 ? 'text-emerald-400' : 'text-amber-400'}`}>
            {summary.on_time_rate_pct.toFixed(1)}%
          </div>
          <div className="text-xs text-slate-500">
            {summary.on_time_order_count} of {summary.total_order_count} orders
          </div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-800/40 p-3">
          <div className="text-xs font-medium text-slate-400">Late Orders</div>
          <div className={`mt-1 text-2xl font-bold font-mono ${summary.late_order_count > 0 ? 'text-rose-400' : 'text-slate-200'}`}>
            {summary.late_order_count}
          </div>
          <div className="text-xs text-slate-500">
            {summary.late_order_count === 0 ? 'zero late deliveries' : 'breached due dates'}
          </div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-800/40 p-3">
          <div className="text-xs font-medium text-slate-400">Solver Wall Clock</div>
          <div className="mt-1 text-2xl font-bold text-slate-200 font-mono">
            {summary.solver_wall_clock_seconds.toFixed(3)}s
          </div>
          <div className="text-xs text-slate-500">elapsed runtime</div>
        </div>

        <div className="rounded border border-slate-800 bg-slate-800/40 p-3">
          <div className="text-xs font-medium text-slate-400">Deterministic Time</div>
          <div className="mt-1 text-2xl font-bold text-slate-200 font-mono">
            {summary.solver_deterministic_time != null ? summary.solver_deterministic_time.toFixed(4) : 'N/A'}
          </div>
          <div className="text-xs text-slate-500">solver ticks</div>
        </div>
      </div>
    </Card>
  );
}
