/**
 * CP-SAT Optimization Planning Workspace
 * Governed by SPECIFICATION.md Section 4, DATA_AND_API.md Section 3.3, and PROJECT_RULES.md.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Button } from '../components/common/Button';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { useRouter } from '../router/RouterContext';
import { AppRoute } from '../router/types';
import { useWorkspace } from '../context/WorkspaceContext';
import { apiEndpoints } from '../api/endpoints';
import { ApiClientError } from '../api/client';
import {
  FactoryConfigResponse,
  FactoryValidationResponse,
  OptimizeRequest,
  OptimizeResponseData,
  ScheduleSummaryResponse,
} from '../types/api';
import { FactoryReadinessCard } from './planning/FactoryReadinessCard';
import { OptimizationParametersForm } from './planning/OptimizationParametersForm';
import { OptimizationResultCard } from './planning/OptimizationResultCard';
import { RecentSchedulesCard } from './planning/RecentSchedulesCard';

function usePlanningState(workspaceId: string | null) {
  const [factory, setFactory] = useState<FactoryConfigResponse | null>(null);
  const [schedules, setSchedules] = useState<ScheduleSummaryResponse[]>([]);
  const [valResult, setValResult] = useState<FactoryValidationResponse | null>(null);
  const [optResult, setOptResult] = useState<OptimizeResponseData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSolving, setIsSolving] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!workspaceId) return;
    setIsLoading(true);
    setError(null);
    try {
      const [fData, sData] = await Promise.all([
        apiEndpoints.getFactory(workspaceId),
        apiEndpoints.listSchedules(workspaceId),
      ]);
      setFactory(fData);
      setSchedules(sData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load workspace data');
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { loadData(); }, [loadData]);

  return {
    factory, schedules, setSchedules, valResult, setValResult, optResult, setOptResult,
    isLoading, isSolving, setIsSolving, isValidating, setIsValidating, error, setError, loadData,
  };
}

function PlanningWorkspaceContent({
  state, workspaceId, onNavigate,
}: {
  state: ReturnType<typeof usePlanningState>; workspaceId: string; onNavigate: (route: AppRoute) => void;
}): React.ReactElement {
  const { factory, valResult, setValResult, optResult, setOptResult, isSolving, setIsSolving, isValidating, setIsValidating, setError, setSchedules, loadData } = state;

  const handleValidate = async () => {
    if (!factory) return;
    setIsValidating(true);
    try {
      const res = await apiEndpoints.validateFactory(workspaceId, {
        machines: factory.machines.map((m) => ({ external_id: m.external_id, name: m.name })),
        downtimes: factory.downtimes.map((d) => ({ machine_id: d.machine_id, start_minute: d.start_minute, end_minute: d.end_minute, reason: d.reason })),
        orders: factory.orders.map((o) => ({
          external_id: o.external_id, name: o.name, release_minute: o.release_minute, due_minute: o.due_minute, tardiness_weight: o.tardiness_weight,
          operations: o.operations.map((op) => ({ sequence_index: op.sequence_index, machine_id: op.machine_id, processing_minutes: op.processing_minutes })),
        })),
      });
      setValResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Validation request failed');
    } finally {
      setIsValidating(false);
    }
  };

  const handleOptimize = async (req: OptimizeRequest) => {
    setIsSolving(true);
    setError(null);
    try {
      const data = await apiEndpoints.optimizeSchedule(workspaceId, req);
      setOptResult(data);
      const updatedSchedules = await apiEndpoints.listSchedules(workspaceId);
      setSchedules(updatedSchedules);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setError(`Optimization Rejected (${err.code}): ${err.message}`);
      } else {
        setError(err instanceof Error ? err.message : 'CP-SAT optimization request failed');
      }
    } finally {
      setIsSolving(false);
    }
  };

  const isBlocked = !factory || factory.machines.length === 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      <FactoryReadinessCard
        factory={factory} validationResult={valResult} isValidating={isValidating}
        onValidate={handleValidate} onNavigateToFactory={() => onNavigate('factory')}
      />
      <div data-tour="planning-controls">
        <OptimizationParametersForm onOptimize={handleOptimize} isSolving={isSolving} isDisabled={isBlocked} />
      </div>
      {optResult && <OptimizationResultCard result={optResult} onViewSchedules={() => onNavigate('schedules')} />}
      <RecentSchedulesCard schedules={state.schedules} isLoading={state.isLoading} onRefresh={loadData} onSelectSchedule={() => onNavigate('schedules')} />
    </div>
  );
}

export function PlanningView(): React.ReactElement {
  const { activeWorkspace } = useWorkspace();
  const { navigate } = useRouter();
  const state = usePlanningState(activeWorkspace?.id || null);

  if (!activeWorkspace) {
    return (
      <EmptyState
        title="No Workspace Selected"
        description="Select or create a production workspace to configure optimization objectives and execute CP-SAT solves."
        action={<Button variant="primary" onClick={() => navigate('overview')}>Go to Overview</Button>}
      />
    );
  }

  return (
    <div>
      <PageHeader
        title="Optimization Planning Engine"
        description={`Workspace: ${activeWorkspace.name} — CP-SAT mathematical optimization and clean-room independent schedule verification.`}
        actions={
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button variant="secondary" size="sm" onClick={state.loadData} disabled={state.isLoading || state.isSolving}>Refresh State</Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('overview')}>← Overview</Button>
          </div>
        }
      />
      {state.error && <div style={{ marginBottom: '1.25rem' }}><ErrorBanner message={state.error} onRetry={state.loadData} /></div>}
      {state.isLoading && !state.factory ? (
        <LoadingState message="Loading workspace factory configuration..." />
      ) : (
        <PlanningWorkspaceContent state={state} workspaceId={activeWorkspace.id} onNavigate={navigate} />
      )}
    </div>
  );
}
