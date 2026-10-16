import React from 'react';
import { Button } from './Button';
import { ValidationErrorDetail } from '../../types/api';

export interface ErrorBannerProps {
  message: string;
  code?: string | null;
  details?: ValidationErrorDetail[] | Record<string, unknown> | null;
  onRetry?: () => void;
  className?: string;
}

function ErrorDetailList({ details }: { details: ValidationErrorDetail[] }): React.ReactElement {
  return (
    <ul style={{ marginTop: '0.75rem', paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
      {details.map((detail, idx) => (
        <li key={idx}>
          <code className="font-mono" style={{ color: 'var(--color-critical)' }}>{detail.field}</code>: {detail.issue}
        </li>
      ))}
    </ul>
  );
}

export function ErrorBanner({
  message,
  code,
  details,
  onRetry,
  className = '',
}: ErrorBannerProps): React.ReactElement {
  const isDetailsArray = Array.isArray(details) && details.length > 0;

  return (
    <div
      role="alert"
      className={`card ${className}`}
      style={{
        backgroundColor: 'var(--color-critical-bg)',
        borderColor: 'var(--color-critical-border)',
        padding: '1.25rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: 'var(--color-critical)',
                display: 'inline-block',
              }}
              aria-hidden="true"
            />
            <strong style={{ color: 'var(--color-critical)', fontSize: '0.875rem' }}>
              {code ? `[${code}] Operational Error` : 'Operational Error'}
            </strong>
          </div>
          <p style={{ color: 'var(--text-primary)', fontSize: '0.875rem', lineHeight: 1.4 }}>{message}</p>
          {isDetailsArray && <ErrorDetailList details={details as ValidationErrorDetail[]} />}
        </div>

        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry Request
          </Button>
        )}
      </div>
    </div>
  );
}
