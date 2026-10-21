/**
 * Guided Product Tour Context and State Manager
 * Governed by PROJECT_RULES.md (Zero external dependencies).
 */

import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import { useRouter } from '../router/RouterContext';
import { TOUR_STEPS, TourStep } from '../components/tour/tourSteps';

const TOUR_STORAGE_KEY = 'opwise_tour_dismissed';

export interface TourContextValue {
  isTourOpen: boolean;
  currentStepIndex: number;
  currentStep: TourStep;
  totalSteps: number;
  hasDismissedTour: boolean;
  startTour: () => void;
  closeTour: () => void;
  nextStep: () => void;
  prevStep: () => void;
  skipTour: () => void;
  finishTour: () => void;
  resetTourState: () => void;
}

export const defaultTourContext: TourContextValue = {
  isTourOpen: false,
  currentStepIndex: 0,
  currentStep: TOUR_STEPS[0],
  totalSteps: TOUR_STEPS.length,
  hasDismissedTour: false,
  startTour: () => {},
  closeTour: () => {},
  nextStep: () => {},
  prevStep: () => {},
  skipTour: () => {},
  finishTour: () => {},
  resetTourState: () => {},
};

export const TourContext = createContext<TourContextValue | null>(null);

function getInitialDismissedState(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return localStorage.getItem(TOUR_STORAGE_KEY) === 'true';
  } catch {
    return false;
  }
}

function persistDismissedState(dismissed: boolean): void {
  if (typeof window === 'undefined') return;
  try {
    if (dismissed) {
      localStorage.setItem(TOUR_STORAGE_KEY, 'true');
    } else {
      localStorage.removeItem(TOUR_STORAGE_KEY);
    }
  } catch {
    // Graceful fallback when storage is restricted
  }
}

export function TourProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const { navigate } = useRouter();
  const [isTourOpen, setIsTourOpen] = useState(false);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [hasDismissedTour, setHasDismissedTour] = useState<boolean>(getInitialDismissedState);

  const currentStep = TOUR_STEPS[currentStepIndex] || TOUR_STEPS[0];
  const totalSteps = TOUR_STEPS.length;

  const startTour = useCallback(() => {
    setCurrentStepIndex(0);
    setIsTourOpen(true);
    navigate(TOUR_STEPS[0].route);
  }, [navigate]);

  const closeTour = useCallback(() => {
    setIsTourOpen(false);
    setHasDismissedTour(true);
    persistDismissedState(true);
  }, []);

  const skipTour = useCallback(() => {
    closeTour();
  }, [closeTour]);

  const finishTour = useCallback(() => {
    closeTour();
  }, [closeTour]);

  const nextStep = useCallback(() => {
    if (currentStepIndex < totalSteps - 1) {
      const nextIdx = currentStepIndex + 1;
      setCurrentStepIndex(nextIdx);
      navigate(TOUR_STEPS[nextIdx].route);
    } else {
      finishTour();
    }
  }, [currentStepIndex, totalSteps, navigate, finishTour]);

  const prevStep = useCallback(() => {
    if (currentStepIndex > 0) {
      const prevIdx = currentStepIndex - 1;
      setCurrentStepIndex(prevIdx);
      navigate(TOUR_STEPS[prevIdx].route);
    }
  }, [currentStepIndex, navigate]);

  const resetTourState = useCallback(() => {
    setIsTourOpen(false);
    setCurrentStepIndex(0);
    setHasDismissedTour(false);
    persistDismissedState(false);
  }, []);

  const value = useMemo(
    () => ({
      isTourOpen,
      currentStepIndex,
      currentStep,
      totalSteps,
      hasDismissedTour,
      startTour,
      closeTour,
      nextStep,
      prevStep,
      skipTour,
      finishTour,
      resetTourState,
    }),
    [
      isTourOpen,
      currentStepIndex,
      currentStep,
      totalSteps,
      hasDismissedTour,
      startTour,
      closeTour,
      nextStep,
      prevStep,
      skipTour,
      finishTour,
      resetTourState,
    ]
  );

  return <TourContext.Provider value={value}>{children}</TourContext.Provider>;
}

export function useTour(): TourContextValue {
  const context = useContext(TourContext);
  if (!context) {
    return defaultTourContext;
  }
  return context;
}
