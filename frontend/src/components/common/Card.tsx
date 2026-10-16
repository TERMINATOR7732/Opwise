import React from 'react';

export interface CardProps {
  children: React.ReactNode;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}

export function Card({ children, title, subtitle, actions, className = '' }: CardProps): React.ReactElement {
  return (
    <div className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-header">
          <div>
            {title && <h2 className="card-title">{title}</h2>}
            {subtitle && <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>{subtitle}</p>}
          </div>
          {actions && <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>{actions}</div>}
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  );
}
