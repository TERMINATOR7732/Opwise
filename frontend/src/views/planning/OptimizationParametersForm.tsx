/**
 * Solver Parameter & Objective Configuration Form
 * Governed by DATA_AND_API.md Section 3.3 and SOLVER_MODEL.md Section 2.
 */

import React, { useState } from 'react';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { OptimizeRequest } from '../../types/api';

export interface OptimizationParametersFormProps {
  onOptimize: (req: OptimizeRequest) => Promise<void>;
  isSolving: boolean;
  isDisabled: boolean;
}

const OBJECTIVE_INFO: Record<string, { title: string; desc: string }> = {
  PURE_MAKESPAN: {
    title: 'Pure Makespan (C_max)',
    desc: 'Minimizes the completion time of the final operation across all machines.',
  },
  PURE_WEIGHTED_TARDINESS: {
    title: 'Pure Weighted Tardiness (Σ w_j · T_j)',
    desc: 'Minimizes tardiness penalties, prioritizing high-weight customer orders.',
  },
  HIERARCHICAL: {
    title: 'Hierarchical Lexicographic (Tardiness → Makespan)',
    desc: 'Two-stage solve: Stage 1 finds optimal tardiness; Stage 2 minimizes makespan bounded by Stage 1.',
  },
};

function ObjectiveOption({
  keyId, info, isSelected, onSelect,
}: {
  keyId: string; info: { title: string; desc: string }; isSelected: boolean; onSelect: () => void;
}): React.ReactElement {
  return (
    <label
      style={{
        display: 'flex', alignItems: 'flex-start', gap: '0.625rem', padding: '0.625rem 0.75rem',
        borderRadius: 'var(--radius-sm)', border: `1px solid ${isSelected ? 'var(--color-primary)' : 'var(--border-subtle)'}`,
        backgroundColor: isSelected ? 'var(--color-primary-subtle, rgba(59, 130, 246, 0.08))' : 'var(--bg-app)', cursor: 'pointer',
      }}
    >
      <input type="radio" name="objectiveMode" value={keyId} checked={isSelected} onChange={onSelect} style={{ marginTop: '0.2rem' }} />
      <div style={{ fontSize: '0.8125rem' }}>
        <strong style={{ color: 'var(--text-primary)', display: 'block' }}>{info.title}</strong>
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>{info.desc}</span>
      </div>
    </label>
  );
}

function ObjectiveSelector({ value, onChange }: { value: string; onChange: (v: string) => void }): React.ReactElement {
  return (
    <div className="form-group">
      <label className="form-label">Optimization Objective Mode *</label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {Object.entries(OBJECTIVE_INFO).map(([key, info]) => (
          <ObjectiveOption key={key} keyId={key} info={info} isSelected={value === key} onSelect={() => onChange(key)} />
        ))}
      </div>
    </div>
  );
}

function AdvancedSolverControls({
  isHierarchical, primaryBudget, setPrimaryBudget, secondaryBudget, setSecondaryBudget,
  workers, setWorkers, seed, setSeed,
}: {
  isHierarchical: boolean; primaryBudget: string; setPrimaryBudget: (v: string) => void;
  secondaryBudget: string; setSecondaryBudget: (v: string) => void;
  workers: string; setWorkers: (v: string) => void; seed: string; setSeed: (v: string) => void;
}): React.ReactElement {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', marginTop: '0.5rem' }}>
      <div className="form-group">
        <label htmlFor="primary-budget" className="form-label">{isHierarchical ? 'Stage 1 Budget (s)' : 'Time Limit (s)'}</label>
        <input id="primary-budget" type="number" min="1" max="300" step="1" required value={primaryBudget} onChange={(e) => setPrimaryBudget(e.target.value)} className="form-input font-mono" />
      </div>
      {isHierarchical && (
        <div className="form-group">
          <label htmlFor="secondary-budget" className="form-label">Stage 2 Budget (s)</label>
          <input id="secondary-budget" type="number" min="1" max="300" step="1" required value={secondaryBudget} onChange={(e) => setSecondaryBudget(e.target.value)} className="form-input font-mono" />
        </div>
      )}
      <div className="form-group">
        <label htmlFor="solver-workers" className="form-label">Worker Threads</label>
        <input id="solver-workers" type="number" min="1" max="16" required value={workers} onChange={(e) => setWorkers(e.target.value)} className="form-input font-mono" />
      </div>
      <div className="form-group">
        <label htmlFor="solver-seed" className="form-label">Random Seed</label>
        <input id="solver-seed" type="number" required value={seed} onChange={(e) => setSeed(e.target.value)} className="form-input font-mono" />
      </div>
    </div>
  );
}

function buildSolvePayload(
  name: string, objectiveType: string, prim: string, sec: string, workers: string, seed: string
): OptimizeRequest {
  const primSec = Math.min(300, Math.max(1, parseFloat(prim) || 10.0));
  const secSec = Math.min(300, Math.max(1, parseFloat(sec) || 5.0));
  const numWork = Math.min(16, Math.max(1, parseInt(workers, 10) || 1));
  const rndSeed = parseInt(seed, 10) || 42;
  return {
    name: name.trim() || 'Optimization Run',
    objective_type: objectiveType,
    parameters: {
      primary_objective: objectiveType === 'HIERARCHICAL' ? 'PURE_WEIGHTED_TARDINESS' : objectiveType,
      secondary_objective: objectiveType === 'HIERARCHICAL' ? 'PURE_MAKESPAN' : null,
      primary_time_budget_seconds: primSec,
      secondary_time_budget_seconds: secSec,
      num_workers: numWork,
      random_seed: rndSeed,
    },
  };
}

export function OptimizationParametersForm({
  onOptimize, isSolving, isDisabled,
}: OptimizationParametersFormProps): React.ReactElement {
  const [name, setName] = useState('Production Schedule Run');
  const [objectiveType, setObjectiveType] = useState('PURE_MAKESPAN');
  const [primaryBudget, setPrimaryBudget] = useState('10');
  const [secondaryBudget, setSecondaryBudget] = useState('5');
  const [workers, setWorkers] = useState('1');
  const [seed, setSeed] = useState('42');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSolving || isDisabled) return;
    await onOptimize(buildSolvePayload(name, objectiveType, primaryBudget, secondaryBudget, workers, seed));
  };

  return (
    <Card title="CP-SAT Solver Parameters & Controls" subtitle="Deterministic OR-Tools constraint integer programming engine configuration.">
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
        <div className="form-group">
          <label htmlFor="run-name" className="form-label">Run Label / Schedule Identifier *</label>
          <input id="run-name" type="text" required maxLength={128} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Peak Shift Batch #1" className="form-input" disabled={isSolving} />
        </div>
        <ObjectiveSelector value={objectiveType} onChange={setObjectiveType} />
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setShowAdvanced(!showAdvanced)} style={{ fontSize: '0.75rem' }}>
            {showAdvanced ? '▲ Hide Solver Tuning Parameters' : '▼ Advanced Tuning (Time Limits, Worker Threads, Seed)'}
          </button>
          {showAdvanced && (
            <AdvancedSolverControls
              isHierarchical={objectiveType === 'HIERARCHICAL'}
              primaryBudget={primaryBudget} setPrimaryBudget={setPrimaryBudget}
              secondaryBudget={secondaryBudget} setSecondaryBudget={setSecondaryBudget}
              workers={workers} setWorkers={setWorkers}
              seed={seed} setSeed={setSeed}
            />
          )}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '0.5rem', borderTop: '1px solid var(--border-subtle)' }}>
          <Button type="submit" variant="primary" isLoading={isSolving} disabled={isDisabled || isSolving}>
            {isSolving ? 'Solving CP-SAT Model...' : 'Run CP-SAT Optimization'}
          </Button>
        </div>
      </form>
    </Card>
  );
}
