/**
 * Demo Scenario Explorer & Quickstart Loaders (Demos 1-6)
 * Governed by SPECIFICATION.md Section 8.1 View 1 and Section 10.
 */

import React from 'react';
import { Card } from '../../components/common/Card';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { DEMO_SCENARIO_LIST, DemoFixture } from '../../demo/fixtures';
import { setActiveDemoId, setDemoMode } from '../../demo/demoService';
import { useRouter } from '../../router/RouterContext';
import { useWorkspace } from '../../context/WorkspaceContext';

function ScenarioBadge({ fixture }: { fixture: DemoFixture }): React.ReactElement {
  if (fixture.id === 'demo-6') {
    return <Badge variant="critical">INVALID (REJECTED)</Badge>;
  }
  return <Badge variant="optimal">VERIFIED (8/8)</Badge>;
}

function ScenarioCardItem({
  fixture,
  onLoad,
}: {
  fixture: DemoFixture;
  onLoad: (fixture: DemoFixture) => void;
}): React.ReactElement {
  return (
    <div
      style={{
        padding: '1rem',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-subtle)',
        backgroundColor: 'var(--bg-card)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        gap: '0.75rem',
      }}
    >
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.375rem' }}>
          <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            {fixture.category}
          </span>
          <ScenarioBadge fixture={fixture} />
        </div>
        <h3 style={{ fontSize: 'var(--font-size-h3)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.375rem' }}>
          {fixture.name}
        </h3>
        <p style={{ fontSize: 'var(--font-size-body)', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {fixture.description}
        </p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.625rem' }}>
        <div style={{ fontSize: 'var(--font-size-small)', color: 'var(--text-muted)' }} className="font-mono">
          {fixture.factory.machines.length} Machines · {fixture.factory.orders.length} Orders
        </div>
        <Button variant="secondary" size="sm" onClick={() => onLoad(fixture)}>
          Inspect Schedule →
        </Button>
      </div>
    </div>
  );
}

export function DemoScenariosCard(): React.ReactElement {
  const { navigate } = useRouter();
  const { selectWorkspace, refreshWorkspaces } = useWorkspace();

  const handleLoadScenario = async (fixture: DemoFixture) => {
    setActiveDemoId(fixture.id);
    setDemoMode(true);
    await refreshWorkspaces();
    selectWorkspace(fixture.factory.workspace_id);
    navigate('schedules');
  };

  return (
    <Card
      title="Interactive Synthetic Demo Scenarios (Demos 1–6)"
      subtitle="Clean-room benchmark fixtures pre-solved by CP-SAT and audited by the in-browser 8-invariant verifier."
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))',
          gap: '1rem',
          marginTop: '0.5rem',
        }}
      >
        {DEMO_SCENARIO_LIST.map((fixture) => (
          <ScenarioCardItem key={fixture.id} fixture={fixture} onLoad={handleLoadScenario} />
        ))}
      </div>
    </Card>
  );
}
