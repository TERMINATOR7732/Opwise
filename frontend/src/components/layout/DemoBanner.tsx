/**
 * Unmissable Top Disclaimer Banner for Standalone Demo Mode & Offline Fallback
 * Governed by SPECIFICATION.md Section 1.1 (Tier 2), Section 8.4 State 13, and DECISIONS.md ADR-011.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { apiEndpoints } from '../../api/endpoints';
import { isDemoMode, setDemoMode } from '../../demo/demoService';

export function useBackendStatus(): boolean | null {
  const [isOnline, setIsOnline] = useState<boolean | null>(null);

  const checkHealth = useCallback(() => {
    apiEndpoints
      .getHealth()
      .then((res) => setIsOnline(res.status === 'healthy'))
      .catch(() => setIsOnline(false));
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  return isOnline;
}

export function DemoBanner(): React.ReactElement | null {
  const isBackendOnline = useBackendStatus();
  const [inDemo, setInDemo] = useState<boolean>(() => isDemoMode());
  const [showCopyNotice, setShowCopyNotice] = useState(false);

  const handleToggleDemo = (enabled: boolean) => {
    setDemoMode(enabled);
    setInDemo(enabled);
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  const handleCopyClone = () => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText('git clone https://github.com/TERMINATOR7732/Opwise.git');
      setShowCopyNotice(true);
      setTimeout(() => setShowCopyNotice(false), 2500);
    }
  };

  if (!inDemo && isBackendOnline !== false) {
    return null;
  }

  if (!inDemo && isBackendOnline === false) {
    return (
      <div
        role="alert"
        aria-label="Backend Disconnected Warning"
        style={{
          backgroundColor: 'rgba(239, 68, 68, 0.15)',
          borderBottom: '1px solid var(--color-critical)',
          padding: '0.5rem 1rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
          fontSize: '0.8125rem',
          color: 'var(--text-primary)',
          zIndex: 60,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ color: 'var(--color-critical)', fontWeight: 700 }}>● Disconnected:</span>
          <span>Local Backend is offline (http://127.0.0.1:8000). Switch to Standalone Demo Mode to explore pre-solved CP-SAT fixtures.</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => handleToggleDemo(true)}
            style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}
          >
            Switch to Demo Mode
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      role="region"
      aria-label="Demo mode disclaimer"
      style={{
        backgroundColor: 'rgba(59, 130, 246, 0.12)',
        borderBottom: '1px solid var(--color-primary, #3b82f6)',
        padding: '0.5rem 1rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        fontSize: '0.8125rem',
        color: 'var(--text-primary)',
        zIndex: 60,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
        <span
          style={{
            backgroundColor: 'var(--color-primary, #3b82f6)',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: '0.6875rem',
            padding: '0.15rem 0.45rem',
            borderRadius: 'var(--radius-sm)',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}
        >
          Portfolio Demo
        </span>
        <span>
          <strong>Interactive Static Demo:</strong> Pre-solved synthetic scenarios loaded in client-side simulation with 8-invariant verifier. Run locally for custom CP-SAT solving and disruption re-optimization.
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={handleCopyClone}
          style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
          title="Copy git clone command to run locally"
        >
          {showCopyNotice ? '✓ Command Copied!' : 'Run Locally (git clone)'}
        </button>
        {isBackendOnline && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => handleToggleDemo(false)}
            style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
          >
            Exit Demo Mode
          </button>
        )}
      </div>
    </div>
  );
}
