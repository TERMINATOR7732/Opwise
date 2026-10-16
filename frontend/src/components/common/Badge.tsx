import React from 'react';

export type BadgeVariant = 'optimal' | 'warning' | 'critical' | 'neutral';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

export function Badge({ children, variant = 'neutral', className = '' }: BadgeProps): React.ReactElement {
  return <span className={`badge badge-${variant} ${className}`}>{children}</span>;
}
