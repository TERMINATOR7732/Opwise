/**
 * Reusable Confirmation Dialog for Destructive Actions
 * Governed by PROJECT_RULES.md
 */

import React from 'react';
import { Button } from '../../components/common/Button';

export interface DeleteConfirmModalProps {
  isOpen: boolean;
  title: string;
  message: string;
  itemName?: string;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

export function DeleteConfirmModal({
  isOpen,
  title,
  message,
  itemName,
  onConfirm,
  onCancel,
  isLoading = false,
}: DeleteConfirmModalProps): React.ReactElement | null {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-labelledby="delete-confirm-title"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 60,
        padding: '1rem',
      }}
    >
      <div className="card" style={{ width: '100%', maxWidth: '440px', boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }}>
        <div className="card-header" style={{ borderColor: 'var(--color-critical-border)' }}>
          <h2 id="delete-confirm-title" className="card-title" style={{ color: 'var(--color-critical)' }}>
            {title}
          </h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onCancel} aria-label="Close dialog">
            ✕
          </button>
        </div>
        <div className="card-body">
          <p style={{ color: 'var(--text-primary)', fontSize: '0.875rem', marginBottom: '0.75rem', lineHeight: 1.5 }}>
            {message}
          </p>
          {itemName && (
            <div
              style={{
                padding: '0.5rem 0.75rem',
                backgroundColor: 'var(--bg-app)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.8125rem',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-secondary)',
              }}
            >
              Target: <strong style={{ color: 'var(--text-primary)' }}>{itemName}</strong>
            </div>
          )}
        </div>
        <div
          style={{
            padding: '0.875rem 1.25rem',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '0.5rem',
          }}
        >
          <Button type="button" variant="secondary" size="sm" onClick={onCancel} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="button" variant="danger" size="sm" onClick={onConfirm} isLoading={isLoading}>
            Delete Permanently
          </Button>
        </div>
      </div>
    </div>
  );
}
