import React from 'react';
import { PageHeader } from '../components/layout/PageHeader';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { useRouter } from '../router/RouterContext';

export function NotFoundView(): React.ReactElement {
  const { navigate, rawHash } = useRouter();

  return (
    <div>
      <PageHeader
        title="404 — Route Not Found"
        description="The requested manufacturing workbench route does not exist or has been relocated."
        badge={<Badge variant="critical">Invalid Route</Badge>}
      />

      <Card title="Unrecognized View">
        <div style={{ maxWidth: '480px', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          <p style={{ marginBottom: '1rem' }}>
            No registered route matches current fragment: <code className="font-mono" style={{ color: 'var(--color-critical)' }}>{rawHash || '(empty)'}</code>.
          </p>
          <Button variant="primary" onClick={() => navigate('overview')}>
            Return to Overview
          </Button>
        </div>
      </Card>
    </div>
  );
}
