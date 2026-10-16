import React from 'react';

export interface LoadingStateProps {
  message?: string;
  className?: string;
}

export function LoadingState({ message = 'Loading operational data...', className = '' }: LoadingStateProps): React.ReactElement {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`card ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.75rem',
        padding: '2.5rem 1.5rem',
        color: 'var(--text-secondary)',
      }}
    >
      <span className="status-dot status-dot-loading" aria-hidden="true" />
      <span style={{ fontSize: '0.875rem' }}>{message}</span>
    </div>
  );
}
