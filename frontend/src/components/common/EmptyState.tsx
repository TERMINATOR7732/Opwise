import React from 'react';

export interface EmptyStateProps {
  title: string;
  description: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title,
  description,
  action,
  icon,
  className = '',
}: EmptyStateProps): React.ReactElement {
  return (
    <div
      className={`card ${className}`}
      style={{
        textAlign: 'center',
        padding: '3rem 1.5rem',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {icon && <div style={{ marginBottom: '1rem', color: 'var(--text-muted)' }}>{icon}</div>}
      <h3 style={{ fontSize: 'var(--font-size-h3)', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
        {title}
      </h3>
      <p style={{ maxWidth: '480px', color: 'var(--text-secondary)', fontSize: 'var(--font-size-body)', marginBottom: action ? '1.5rem' : 0 }}>
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
}
