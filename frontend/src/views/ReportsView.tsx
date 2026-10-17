/**
 * Reports & Analytics View (Pillar 5)
 * Governed by SPECIFICATION.md Section 8.1 View 5, Section 8.4 State 14, and DATA_AND_API.md Section 4.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { Button } from '../components/common/Button';
import { useRouter } from '../router/RouterContext';
import { useWorkspace } from '../context/WorkspaceContext';
import { apiEndpoints } from '../api/endpoints';
import { ScheduleSummaryResponse } from '../types/api';
import { ScheduleReportResponse } from '../types/reports';
import { ReportSummaryCard } from './reports/ReportSummaryCard';
import { BottleneckCard } from './reports/BottleneckCard';
import { MachineUtilizationTable } from './reports/MachineUtilizationTable';
import { OrderPerformanceTable } from './reports/OrderPerformanceTable';
import { ScheduleExplanationsCard } from './reports/ScheduleExplanationsCard';
import { ExportActionButtons } from './reports/ExportActionButtons';

export function ReportsView(): React.ReactElement {
  const { navigate } = useRouter();
  const { activeWorkspace, status } = useWorkspace();
  const wsLoading = status === 'loading';

  const [schedules, setSchedules] = useState<ScheduleSummaryResponse[]>([]);
  const [selectedScheduleId, setSelectedScheduleId] = useState<string | null>(null);
  const [report, setReport] = useState<ScheduleReportResponse | null>(null);
  const [isLoadingSchedules, setIsLoadingSchedules] = useState<boolean>(false);
  const [isLoadingReport, setIsLoadingReport] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchSchedules = useCallback(async () => {
    if (!activeWorkspace) return;
    try {
      setIsLoadingSchedules(true);
      setErrorMessage(null);
      const list = await apiEndpoints.listSchedules(activeWorkspace.id);
      setSchedules(list);
      if (list.length > 0) {
        setSelectedScheduleId((prev) => (prev && list.some((s) => s.id === prev) ? prev : list[0].id));
      } else {
        setSelectedScheduleId(null);
        setReport(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch schedules';
      setErrorMessage(msg);
    } finally {
      setIsLoadingSchedules(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    fetchSchedules();
  }, [fetchSchedules]);

  const fetchReport = useCallback(async (scheduleId: string) => {
    if (!activeWorkspace) return;
    try {
      setIsLoadingReport(true);
      setErrorMessage(null);
      const res = await apiEndpoints.getScheduleReport(activeWorkspace.id, scheduleId);
      setReport(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch schedule analytics report';
      setErrorMessage(msg);
    } finally {
      setIsLoadingReport(false);
    }
  }, [activeWorkspace]);

  useEffect(() => {
    if (selectedScheduleId) {
      fetchReport(selectedScheduleId);
    }
  }, [selectedScheduleId, fetchReport]);

  if (wsLoading || (isLoadingSchedules && schedules.length === 0)) {
    return <LoadingState message="Loading production performance analytics..." />;
  }

  if (!activeWorkspace) {
    return (
      <EmptyState
        title="No Active Workspace"
        description="Select or create a workspace to view production performance reports."
        action={
          <Button variant="primary" onClick={() => navigate('overview')}>
            Go to Overview
          </Button>
        }
      />
    );
  }

  if (schedules.length === 0 && !isLoadingSchedules) {
    return (
      <div className="reports-view-container">
        <PageHeader
          title="Reports & Analytics"
          description="In-depth tabular analytics: order tardiness breakdown, machine utilization and idle logs, bottleneck reports, and sanitized CSV/JSON exports."
        />
        <EmptyState
          title="No Schedule Generated"
          description="No schedule generated yet. Solve a scenario to generate analytics."
          action={
            <Button variant="primary" onClick={() => navigate('planning')}>
              Go to Planning
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="reports-view-container">
      <PageHeader
        title="Reports & Analytics"
        description="In-depth tabular analytics: order tardiness breakdown, machine utilization and idle logs, bottleneck reports, and sanitized CSV/JSON exports."
      />

      {errorMessage && (
        <ErrorBanner
          message={errorMessage}
          onRetry={() => {
            if (selectedScheduleId) {
              fetchReport(selectedScheduleId);
            } else {
              fetchSchedules();
            }
          }}
          className="mb-6"
        />
      )}

      {/* Control bar: schedule switcher & export actions */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4 rounded border border-slate-700 bg-slate-800/40 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <label htmlFor="schedule-select" className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Select Schedule:
          </label>
          <select
            id="schedule-select"
            value={selectedScheduleId || ''}
            onChange={(e) => setSelectedScheduleId(e.target.value)}
            disabled={isLoadingReport}
            className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 font-mono text-xs text-slate-200 focus:border-cyan-500 focus:outline-none"
          >
            {schedules.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.solver_status} — {s.makespan_minutes}m, Cmax — {new Date(s.created_at).toLocaleDateString()})
              </option>
            ))}
          </select>

          <Button
            variant="ghost"
            size="sm"
            onClick={fetchSchedules}
            disabled={isLoadingSchedules}
            className="text-xs text-slate-400 hover:text-slate-200"
          >
            Refresh
          </Button>
        </div>

        {selectedScheduleId && (
          <ExportActionButtons workspaceId={activeWorkspace.id} scheduleId={selectedScheduleId} />
        )}
      </div>

      {isLoadingReport && (
        <div className="py-12">
          <LoadingState message="Compiling verified report..." />
        </div>
      )}

      {!isLoadingReport && report && (
        <div className="report-canvas">
          <ReportSummaryCard
            scheduleName={report.schedule_name}
            solverStatus={report.solver_status}
            verificationStatus={report.verification_status}
            objectiveType={report.objective_type}
            summary={report.summary}
            audit={report.verification_audit}
          />

          <BottleneckCard bottleneck={report.bottleneck} />

          <MachineUtilizationTable machines={report.machine_utilization} />

          <OrderPerformanceTable orders={report.order_performance} />

          <ScheduleExplanationsCard explanations={report.explanations} />
        </div>
      )}
    </div>
  );
}
export default ReportsView;
