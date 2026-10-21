import React from 'react';

export interface PageHeaderProps {
  title: string;
  description?: string;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
}

export function PageHeader({ title, description, badge, actions }: PageHeaderProps): React.ReactElement {
  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
        marginBottom: '1.75rem',
        paddingBottom: '1rem',
        borderBottom: '1px solid var(--border-subtle)',
      }}
    >
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.375rem' }}>
          <h1 style={{ fontSize: 'var(--font-size-h1)', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
            {title}
          </h1>
          {badge}
        </div>
        {description && (
          <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-size-body)', maxWidth: '720px', lineHeight: 'var(--line-height-body)' }}>{description}</p>
        )}
      </div>

      {actions && <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>{actions}</div>}
    </header>
  );
}
