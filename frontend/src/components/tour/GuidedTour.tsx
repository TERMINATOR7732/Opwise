/**
 * Opwise Interactive Guided Product Tour Component
 * Governed by PROJECT_RULES.md, SPECIFICATION.md, and UI Refinement Requirements.
 */

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useTour } from '../../context/TourContext';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';

interface TargetRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export function GuidedTour(): React.ReactElement | null {
  const {
    isTourOpen,
    currentStep,
    currentStepIndex,
    totalSteps,
    nextStep,
    prevStep,
    skipTour,
    finishTour,
    closeTour,
  } = useTour();

  const [targetRect, setTargetRect] = useState<TargetRect | null>(null);
  const [viewportSize, setViewportSize] = useState(() => ({
    width: typeof window !== 'undefined' ? window.innerWidth : 1024,
    height: typeof window !== 'undefined' ? window.innerHeight : 768,
  }));
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  // Focus management: capture prior focus and focus tour dialog
  useEffect(() => {
    if (isTourOpen) {
      if (typeof document !== 'undefined' && document.activeElement instanceof HTMLElement) {
        if (!previousActiveElementRef.current) {
          previousActiveElementRef.current = document.activeElement;
        }
      }
      popoverRef.current?.focus();
    } else if (previousActiveElementRef.current) {
      previousActiveElementRef.current.focus();
      previousActiveElementRef.current = null;
    }
  }, [isTourOpen, currentStepIndex]);

  const updateTargetRect = useCallback(() => {
    if (!isTourOpen || !currentStep.targetSelector) {
      setTargetRect(null);
      return;
    }

    try {
      const el = document.querySelector(currentStep.targetSelector);
      if (el) {
        const rect = el.getBoundingClientRect();
        // Check for positive dimensions
        if (rect.width > 0 && rect.height > 0) {
          // Scroll into view if out of viewport
          if (
            rect.top < 60 ||
            rect.bottom > window.innerHeight - 20 ||
            rect.left < 0 ||
            rect.right > window.innerWidth
          ) {
            el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }

          setTargetRect({
            top: Math.max(0, rect.top),
            left: Math.max(0, rect.left),
            width: rect.width,
            height: rect.height,
          });
          return;
        }
      }
    } catch {
      // Graceful fallback if querySelector or getBoundingClientRect fails
    }

    setTargetRect(null);
  }, [isTourOpen, currentStep.targetSelector]);

  // Track target on mount, step change, resize, and scroll
  useEffect(() => {
    if (!isTourOpen) return;

    updateTargetRect();

    // Check again after a short delay to accommodate route view rendering
    const timer = setTimeout(updateTargetRect, 100);

    const handleResize = () => {
      setViewportSize({
        width: typeof window !== 'undefined' ? window.innerWidth : 1024,
        height: typeof window !== 'undefined' ? window.innerHeight : 768,
      });
      updateTargetRect();
    };
    const handleScroll = () => updateTargetRect();

    window.addEventListener('resize', handleResize);
    window.addEventListener('scroll', handleScroll, true);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('scroll', handleScroll, true);
    };
  }, [isTourOpen, currentStepIndex, updateTargetRect]);

  // Keyboard navigation
  useEffect(() => {
    if (!isTourOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isInputActive =
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable);

      if (e.key === 'Escape') {
        closeTour();
      } else if (!isInputActive) {
        if (e.key === 'ArrowRight' && currentStepIndex < totalSteps - 1) {
          nextStep();
        } else if (e.key === 'ArrowLeft' && currentStepIndex > 0) {
          prevStep();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isTourOpen, currentStepIndex, totalSteps, nextStep, prevStep, closeTour]);

  if (!isTourOpen) return null;

  const isLastStep = currentStepIndex === totalSteps - 1;

  // Calculate popover coordinates
  const viewportWidth = viewportSize.width;
  const viewportHeight = viewportSize.height;
  const margin = 14;
  const isNarrowScreen = viewportWidth < 640;
  const popoverWidth = Math.min(440, viewportWidth - margin * 2);
  const popoverHeight = 270; // Estimated height

  let popoverStyle: React.CSSProperties = {
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: `${popoverWidth}px`,
    maxWidth: 'calc(100vw - 28px)',
    maxHeight: 'calc(100vh - 28px)',
    overflowY: 'auto',
  };

  if (targetRect && currentStep.placement !== 'center') {
    if (isNarrowScreen) {
      // On narrow/mobile screens, anchor cleanly to viewport bottom as a responsive card
      popoverStyle = {
        bottom: `${margin}px`,
        left: `${margin}px`,
        right: `${margin}px`,
        top: 'auto',
        width: 'auto',
        maxWidth: `min(440px, calc(100vw - ${margin * 2}px))`,
        maxHeight: `calc(100vh - ${margin * 2}px)`,
        margin: '0 auto',
        transform: 'none',
        overflowY: 'auto',
      };
    } else {
      const spaceBelow = viewportHeight - (targetRect.top + targetRect.height + margin);
      const spaceAbove = targetRect.top - margin;

      let computedTop: number;
      if (spaceBelow >= popoverHeight || spaceBelow >= spaceAbove) {
        computedTop = targetRect.top + targetRect.height + margin;
      } else {
        computedTop = Math.max(margin, targetRect.top - popoverHeight - margin);
      }

      // Keep clamped inside viewport
      computedTop = Math.max(margin, Math.min(computedTop, viewportHeight - popoverHeight - margin));

      let computedLeft = targetRect.left;
      if (computedLeft + popoverWidth > viewportWidth - margin) {
        computedLeft = viewportWidth - popoverWidth - margin;
      }
      computedLeft = Math.max(margin, computedLeft);

      popoverStyle = {
        top: `${computedTop}px`,
        left: `${computedLeft}px`,
        width: `${popoverWidth}px`,
        maxWidth: 'calc(100vw - 28px)',
        maxHeight: 'calc(100vh - 28px)',
        transform: 'none',
        overflowY: 'auto',
      };
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="tour-backdrop"
        onClick={closeTour}
        aria-hidden="true"
      />

      {/* Target Spotlight Highlight */}
      {targetRect && (
        <div
          className="tour-spotlight"
          style={{
            top: `${Math.max(0, targetRect.top - 6)}px`,
            left: `${Math.max(0, targetRect.left - 6)}px`,
            width: `${targetRect.width + 12}px`,
            height: `${targetRect.height + 12}px`,
          }}
          aria-hidden="true"
        />
      )}

      {/* Floating Tour Popover Dialog */}
      <div
        ref={popoverRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-step-title"
        aria-describedby="tour-step-desc"
        className="tour-popover"
        style={{ ...popoverStyle, outline: 'none' }}
      >
        <div className="tour-popover-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <span style={{ fontSize: '1.125rem' }} aria-hidden="true">🧭</span>
            <Badge variant="optimal">
              Step {currentStep.stepNumber} of {totalSteps}
            </Badge>
          </div>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={closeTour}
            aria-label="Exit Tour"
            title="Exit Tour"
            style={{ padding: '0.2rem 0.6rem', fontSize: 'var(--font-size-small)', display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
          >
            <span aria-hidden="true">✕</span>
            <span>Exit Tour</span>
          </button>
        </div>

        <div className="tour-popover-body">
          <h3 id="tour-step-title">{currentStep.title}</h3>
          <p id="tour-step-desc">{currentStep.description}</p>
        </div>

        <div className="tour-popover-footer">
          <Button
            variant="secondary"
            size="sm"
            onClick={skipTour}
            aria-label="Skip Tour"
            style={{ color: 'var(--text-muted)' }}
          >
            Skip Tour
          </Button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {currentStepIndex > 0 && (
              <Button
                variant="secondary"
                size="sm"
                onClick={prevStep}
                aria-label="Previous Tour Step"
              >
                ← Back
              </Button>
            )}

            {!isLastStep ? (
              <Button
                variant="primary"
                size="sm"
                onClick={nextStep}
                aria-label="Next Tour Step"
              >
                Next Step →
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                onClick={finishTour}
                aria-label="Finish Tour"
              >
                Finish Tour ✓
              </Button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
