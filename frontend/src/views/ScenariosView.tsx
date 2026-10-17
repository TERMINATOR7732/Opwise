/**
 * Scenario Branching & Disruption Lab View
 * Governed by SPECIFICATION.md Section 6 and Section 8.1.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { EmptyState } from '../components/common/EmptyState';
import { LoadingState } from '../components/common/LoadingState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { useWorkspace } from '../context/WorkspaceContext';
import { useRouter } from '../router/RouterContext';
import { apiEndpoints } from '../api/endpoints';
import {
  MachineResponse,
  ScheduleDetailResponse,
  ScheduleSummaryResponse,
} from '../types/api';
import { ScenarioComparisonResponse, ScenarioCreateRequest, ScenarioResponse } from '../types/scenarios';
import { CreateScenarioModal } from './scenarios/CreateScenarioModal';
import { ScenarioDetailCard } from './scenarios/ScenarioDetailCard';
import { ScenarioComparisonCard } from './scenarios/ScenarioComparisonCard';
import { DualGanttComparison } from './scenarios/DualGanttComparison';

export function ScenariosView(): React.ReactElement {
  const { activeWorkspace } = useWorkspace();
  const { navigate } = useRouter();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioResponse[]>([]);
  const [schedules, setSchedules] = useState<ScheduleSummaryResponse[]>([]);
  const [machines, setMachines] = useState<MachineResponse[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null);

  const [baselineSchedule, setBaselineSchedule] = useState<ScheduleDetailResponse | null>(null);
  const [recoverySchedule, setRecoverySchedule] = useState<ScheduleDetailResponse | null>(null);
  const [comparison, setComparison] = useState<ScenarioComparisonResponse | null>(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isReoptimizing, setIsReoptimizing] = useState(false);

  const activeScenario = scenarios.find((s) => s.id === selectedScenarioId) || scenarios[0] || null;

  const loadData = useCallback(async () => {
    if (!activeWorkspace) return;
    try {
      setLoading(true);
      setError(null);
      const [scenList, schedList, factoryRes] = await Promise.all([
        apiEndpoints.listScenarios(activeWorkspace.id),
        apiEndpoints.listSchedules(activeWorkspace.id),
        apiEndpoints.getFactory(activeWorkspace.id).catch(() => ({ machines: [] })),
      ]);
      setScenarios(scenList);
      setSchedules(schedList);
      setMachines(factoryRes.machines || []);
      if (scenList.length > 0 && !selectedScenarioId) {
        setSelectedScenarioId(scenList[0].id);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load scenario workspace data.');
    } finally {
      setLoading(false);
    }
  }, [activeWorkspace, selectedScenarioId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Load details for the active scenario
  const loadActiveScenarioDetails = useCallback(async () => {
    if (!activeWorkspace || !activeScenario) {
      setBaselineSchedule(null);
      setRecoverySchedule(null);
      setComparison(null);
      return;
    }

    try {
      // 1. Fetch baseline schedule
      const baseSched = await apiEndpoints.getSchedule(activeWorkspace.id, activeScenario.baseline_schedule_id);
      setBaselineSchedule(baseSched);

      // 2. Fetch recovery schedule if reoptimized
      if (activeScenario.reoptimized_schedule_id) {
        const recSched = await apiEndpoints.getSchedule(activeWorkspace.id, activeScenario.reoptimized_schedule_id);
        setRecoverySchedule(recSched);

        // Fetch latest scenario with comparison attached
        const fullScen = await apiEndpoints.getScenario(activeWorkspace.id, activeScenario.id);
        if (fullScen.comparison) {
          setComparison(fullScen.comparison);
        } else {
          // Fallback: compare directly
          const comp = await apiEndpoints.compareSchedules(activeWorkspace.id, {
            baseline_schedule_id: activeScenario.baseline_schedule_id,
            compared_schedule_id: activeScenario.reoptimized_schedule_id,
            scenario_id: activeScenario.id,
          });
          setComparison(comp);
        }
      } else {
        setRecoverySchedule(null);
        setComparison(null);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load scenario schedule details.');
    }
  }, [activeWorkspace, activeScenario]);

  useEffect(() => {
    loadActiveScenarioDetails();
  }, [loadActiveScenarioDetails]);

  const handleCreateScenario = async (req: ScenarioCreateRequest) => {
    if (!activeWorkspace) return;
    const created = await apiEndpoints.createScenario(activeWorkspace.id, req);
    setScenarios((prev) => [created, ...prev]);
    setSelectedScenarioId(created.id);
  };

  const handleReoptimize = async () => {
    if (!activeWorkspace || !activeScenario) return;
    try {
      setIsReoptimizing(true);
      setError(null);
      const compRes = await apiEndpoints.reoptimizeScenario(activeWorkspace.id, activeScenario.id);
      setComparison(compRes);
      // Reload scenario and schedules
      const updatedScen = await apiEndpoints.getScenario(activeWorkspace.id, activeScenario.id);
      setScenarios((prev) => prev.map((s) => (s.id === updatedScen.id ? updatedScen : s)));
      if (updatedScen.reoptimized_schedule_id) {
        const recSched = await apiEndpoints.getSchedule(activeWorkspace.id, updatedScen.reoptimized_schedule_id);
        setRecoverySchedule(recSched);
      }
    } catch (err: any) {
      setError(err?.message || 'Reoptimization failed.');
    } finally {
      setIsReoptimizing(false);
    }
  };

  const handleDeleteScenario = async () => {
    if (!activeWorkspace || !activeScenario) return;
    if (!window.confirm(`Delete scenario "${activeScenario.name}"?`)) return;
    try {
      await apiEndpoints.deleteScenario(activeWorkspace.id, activeScenario.id);
      const nextScens = scenarios.filter((s) => s.id !== activeScenario.id);
      setScenarios(nextScens);
      setSelectedScenarioId(nextScens[0]?.id || null);
    } catch (err: any) {
      setError(err?.message || 'Failed to delete scenario.');
    }
  };

  if (!activeWorkspace) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <PageHeader
          title="Scenario Branching & Disruption Lab"
          description="Model machine breakdowns, urgent rush orders, and delivery delays without mutating baseline solutions."
          badge={<Badge variant="neutral">Milestone 10 Implementation</Badge>}
        />
        <EmptyState
          title="No Workspace Selected"
          description="Select or create a workspace to access the Scenario Branching & Disruption Lab."
        />
      </div>
    );
  }

  if (loading) {
    return <LoadingState message="Loading scenario simulations..." />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <PageHeader
        title="Scenario Branching & Disruption Lab"
        description="Model machine breakdowns, urgent rush orders, and delivery delays without mutating baseline solutions."
        badge={<Badge variant="optimal">MILITARY SPEC SOLVER RECOVERY</Badge>}
        actions={
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsModalOpen(true)}
              disabled={schedules.length === 0}
            >
              + New Disruption Scenario
            </Button>
            <Button variant="secondary" size="sm" onClick={() => navigate('overview')}>
              ← Overview
            </Button>
          </div>
        }
      />

      {error && <ErrorBanner message={error} onRetry={() => setError(null)} />}

      {schedules.length === 0 ? (
        <EmptyState
          title="No Baseline Schedules Available"
          description="Disruption scenarios branch from locked baseline solutions. Run an optimization in the Planning canvas first."
          action={
            <Button variant="primary" size="sm" onClick={() => navigate('planning')}>
              Go to Planning Canvas
            </Button>
          }
        />
      ) : scenarios.length === 0 ? (
        <EmptyState
          title="No Disruption Scenarios Defined"
          description="Simulate what-if events like machine breakdowns or rush orders by creating an isolated scenario."
          action={
            <Button variant="primary" size="sm" onClick={() => setIsModalOpen(true)}>
              + Create First Scenario
            </Button>
          }
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Scenario selector tabs */}
          {scenarios.length > 1 && (
            <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.25rem' }}>
              {scenarios.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelectedScenarioId(s.id)}
                  style={{
                    padding: '0.5rem 0.875rem',
                    fontSize: '0.8125rem',
                    fontWeight: 500,
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid',
                    cursor: 'pointer',
                    backgroundColor: s.id === activeScenario?.id ? 'var(--bg-card)' : 'var(--bg-app)',
                    borderColor: s.id === activeScenario?.id ? 'var(--accent-primary)' : 'var(--border-subtle)',
                    color: s.id === activeScenario?.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {s.name}
                </button>
              ))}
            </div>
          )}

          {activeScenario && (
            <>
              <ScenarioDetailCard
                scenario={activeScenario}
                baselineName={schedules.find((s) => s.id === activeScenario.baseline_schedule_id)?.name}
                isReoptimizing={isReoptimizing}
                onReoptimize={handleReoptimize}
                onDelete={handleDeleteScenario}
                onSelectRecoverySchedule={() => navigate('schedules')}
              />

              {comparison && (
                <ScenarioComparisonCard comparison={comparison} />
              )}

              {baselineSchedule && (
                <DualGanttComparison
                  baselineSchedule={baselineSchedule}
                  recoverySchedule={recoverySchedule}
                />
              )}
            </>
          )}
        </div>
      )}

      <CreateScenarioModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleCreateScenario}
        schedules={schedules}
        machines={machines}
      />
    </div>
  );
}
