/**
 * Comprehensive Tests for Guided Product Tour & Typography Refinement
 * Governed by PROJECT_RULES.md, SPECIFICATION.md, and UI Refinement Requirements.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { TOUR_STEPS } from '../components/tour/tourSteps';
import { TourProvider, TourContext, useTour, defaultTourContext, TourContextValue } from '../context/TourContext';
import { GuidedTour } from '../components/tour/GuidedTour';
import { RouterProvider } from '../router/RouterContext';
import { AppHeader } from '../components/layout/AppHeader';
import { OverviewView } from '../views/OverviewView';
import { WorkspaceProvider } from '../context/WorkspaceContext';
import { FactoryProvider } from '../context/FactoryContext';

describe('Guided Tour Steps Specification', () => {
  it('defines exactly 8 sequential steps', () => {
    expect(TOUR_STEPS).toHaveLength(8);
    TOUR_STEPS.forEach((step, index) => {
      expect(step.stepNumber).toBe(index + 1);
      expect(step.id).toBeDefined();
      expect(typeof step.title).toBe('string');
      expect(step.title.length).toBeGreaterThan(0);
      expect(typeof step.description).toBe('string');
      expect(step.description.length).toBeGreaterThan(0);
      expect(typeof step.route).toBe('string');
      expect(typeof step.targetSelector).toBe('string');
      expect(step.targetSelector.length).toBeGreaterThan(0);
    });
  });

  it('routes through the end-to-end manufacturing planning workflow', () => {
    const routes = TOUR_STEPS.map((s) => s.route);
    expect(routes).toEqual([
      'overview',   // Step 1: Welcome
      'factory',    // Step 2: Machines & Routings
      'planning',   // Step 3: CP-SAT Optimization
      'schedules',  // Step 4: Gantt Timeline
      'factory',    // Step 5: Plant Clock Execution
      'scenarios',  // Step 6: Disruption Lab
      'reports',    // Step 7: Analytical Verification
      'overview',   // Step 8: Ready to Plan
    ]);
  });

  it('targets expected data-tour DOM attributes', () => {
    const targets = TOUR_STEPS.map((s) => s.targetSelector);
    expect(targets).toEqual([
      '[data-tour="overview-welcome"]',
      '[data-tour="factory-tabs"]',
      '[data-tour="planning-controls"]',
      '[data-tour="gantt-chart"]',
      '[data-tour="plant-clock"]',
      '[data-tour="scenarios-view"]',
      '[data-tour="reports-summary"]',
      '[data-tour="overview-welcome"]',
    ]);
  });
});

describe('GuidedTour Component Rendering', () => {
  const store: Record<string, string> = {};

  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k]);
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => { store[k] = v; },
      removeItem: (k: string) => { delete store[k]; },
      clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders nothing when isTourOpen is false', () => {
    const TestConsumer = () => <GuidedTour />;
    const markup = renderToStaticMarkup(
      <RouterProvider>
        <TourProvider initialOpen={false}>
          <TestConsumer />
        </TourProvider>
      </RouterProvider>
    );
    expect(markup).toBe('');
  });

  it('renders tour modal dialog when open with step 1 content', () => {
    const OpenTourWrapper = () => {
      const mockValue = {
        isTourOpen: true,
        currentStepIndex: 0,
        currentStep: TOUR_STEPS[0],
        totalSteps: 8,
        hasDismissedTour: false,
        startTour: vi.fn(),
        closeTour: vi.fn(),
        nextStep: vi.fn(),
        prevStep: vi.fn(),
        skipTour: vi.fn(),
        finishTour: vi.fn(),
        resetTourState: vi.fn(),
      };

      return (
        <TourContext.Provider value={mockValue}>
          <GuidedTour />
        </TourContext.Provider>
      );
    };

    const markup = renderToStaticMarkup(<OpenTourWrapper />);
    expect(markup).toContain('tour-backdrop');
    expect(markup).toContain('tour-popover');
    expect(markup).toContain('Step 1 of 8');
    expect(markup).toContain('Welcome to Opwise');
    expect(markup).toContain('Next Step →');
    expect(markup).toContain('Skip Tour');
    expect(markup).toContain('Exit Tour');
  });

  it('renders Finish Tour button on step 8 and Back button on intermediate steps', () => {
    const Step8Wrapper = () => {
      const mockValue = {
        isTourOpen: true,
        currentStepIndex: 7,
        currentStep: TOUR_STEPS[7],
        totalSteps: 8,
        hasDismissedTour: false,
        startTour: vi.fn(),
        closeTour: vi.fn(),
        nextStep: vi.fn(),
        prevStep: vi.fn(),
        skipTour: vi.fn(),
        finishTour: vi.fn(),
        resetTourState: vi.fn(),
      };

      return (
        <TourContext.Provider value={mockValue}>
          <GuidedTour />
        </TourContext.Provider>
      );
    };

    const markup = renderToStaticMarkup(<Step8Wrapper />);
    expect(markup).toContain('Step 8 of 8');
    expect(markup).toContain('Ready to Plan');
    expect(markup).toContain('Finish Tour ✓');
    expect(markup).toContain('← Back');
  });

  it('returns default fallback context when used outside TourProvider', () => {
    let result: TourContextValue = defaultTourContext;
    const TestConsumer = () => {
      result = useTour();
      return <div>Fallback: {result.isTourOpen ? 'OPEN' : 'CLOSED'}</div>;
    };

    const markup = renderToStaticMarkup(<TestConsumer />);
    expect(markup).toContain('Fallback: CLOSED');
    expect(result.totalSteps).toBe(8);
    expect(result.hasDismissedTour).toBe(false);
  });
});

describe('TourContext Initialization & Persistence', () => {
  const store: Record<string, string> = {};

  beforeEach(() => {
    Object.keys(store).forEach((k) => delete store[k]);
    vi.stubGlobal('localStorage', {
      getItem: (k: string) => store[k] ?? null,
      setItem: (k: string, v: string) => { store[k] = v; },
      removeItem: (k: string) => { delete store[k]; },
      clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
    });
    vi.stubGlobal('window', {
      localStorage: globalThis.localStorage,
      location: { hash: '' },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('automatically launches tour on fresh demo visit by default', () => {
    let contextValue: TourContextValue = defaultTourContext;
    const Reader = () => {
      contextValue = useTour();
      return <div>Tour: {contextValue.isTourOpen ? 'OPEN' : 'CLOSED'}</div>;
    };

    const markup = renderToStaticMarkup(
      <RouterProvider>
        <TourProvider>
          <Reader />
          <GuidedTour />
        </TourProvider>
      </RouterProvider>
    );

    expect(contextValue.isTourOpen).toBe(true);
    expect(contextValue.hasDismissedTour).toBe(false);
    expect(contextValue.currentStepIndex).toBe(0);
    expect(markup).toContain('Tour: OPEN');
    expect(markup).toContain('tour-popover');
    expect(markup).toContain('Step 1 of 8');
    expect(markup).toContain('Exit Tour');
    expect(markup).toContain('Skip Tour');
  });

  it('maintains dismissal strictly in memory without persisting to localStorage across visits', () => {
    // Even if legacy localStorage had a flag, it should be cleared/ignored
    store['opwise_tour_dismissed'] = 'true';

    let contextValue: TourContextValue = defaultTourContext;
    const Reader = () => {
      contextValue = useTour();
      return <div>State: {contextValue.hasDismissedTour ? 'DISMISSED' : 'ACTIVE'}</div>;
    };

    const markup = renderToStaticMarkup(
      <RouterProvider>
        <TourProvider>
          <Reader />
        </TourProvider>
      </RouterProvider>
    );

    // Fresh visit must not be silenced by localStorage
    expect(markup).toContain('State: ACTIVE');
    expect(contextValue.hasDismissedTour).toBe(false);
    expect(contextValue.isTourOpen).toBe(true);
  });

  it('respects initialOpen={false} when explicitly configured', () => {
    let contextValue: TourContextValue = defaultTourContext;
    const Reader = () => {
      contextValue = useTour();
      return <div>Tour: {contextValue.isTourOpen ? 'OPEN' : 'CLOSED'}</div>;
    };

    const markup = renderToStaticMarkup(
      <RouterProvider>
        <TourProvider initialOpen={false}>
          <Reader />
          <GuidedTour />
        </TourProvider>
      </RouterProvider>
    );

    expect(contextValue.isTourOpen).toBe(false);
    expect(contextValue.hasDismissedTour).toBe(false);
    expect(markup).toContain('Tour: CLOSED');
    expect(markup).not.toContain('tour-popover');
  });

  it('provides callable controls for dismiss, skip, next, prev, and manual start without localStorage mutation', () => {
    let captured: TourContextValue = defaultTourContext;
    const Capture = () => {
      captured = useTour();
      return null;
    };

    renderToStaticMarkup(
      <RouterProvider>
        <TourProvider>
          <Capture />
        </TourProvider>
      </RouterProvider>
    );

    expect(typeof captured.startTour).toBe('function');
    expect(typeof captured.closeTour).toBe('function');
    expect(typeof captured.skipTour).toBe('function');
    expect(typeof captured.finishTour).toBe('function');
    expect(typeof captured.nextStep).toBe('function');
    expect(typeof captured.prevStep).toBe('function');
    expect(typeof captured.resetTourState).toBe('function');

    // Executing closeTour or skipTour does NOT write to localStorage
    captured.closeTour();
    expect(store['opwise_tour_dismissed']).toBeUndefined();
    captured.skipTour();
    expect(store['opwise_tour_dismissed']).toBeUndefined();
  });
});

describe('Typography Scale and Inter Font Integration', () => {
  it('verifies that index.css establishes the 15px body standard and typography tokens', () => {
    const cssPath = resolve(process.cwd(), 'src/index.css');
    const css = readFileSync(cssPath, 'utf-8');

    // Font family includes Inter
    expect(css).toContain("--font-sans: 'Inter'");

    // Consistent 15px body font size
    expect(css).toContain('--font-size-body: 15px;');

    // Heading hierarchy preserved
    expect(css).toContain('--font-size-h1: 28px;');
    expect(css).toContain('--font-size-h2: 22px;');
    expect(css).toContain('--font-size-h3: 18px;');
    expect(css).toContain('--font-size-small: 13px;');
    expect(css).toContain('--font-size-caption: 12px;');

    // html and body font size set to --font-size-body
    expect(css).toContain('font-size: var(--font-size-body);');

    // Font weights
    expect(css).toContain('--font-weight-normal: 400;');
    expect(css).toContain('--font-weight-medium: 500;');
    expect(css).toContain('--font-weight-semibold: 600;');
    expect(css).toContain('--font-weight-bold: 700;');

    // Self-hosted @fontsource/inter imports
    expect(css).toContain('@fontsource/inter/400.css');
    expect(css).toContain('@fontsource/inter/500.css');
    expect(css).toContain('@fontsource/inter/600.css');
    expect(css).toContain('@fontsource/inter/700.css');
  });

  it('renders persistent Guided Tour button and Plant Clock tour hook in AppHeader', () => {
    const markup = renderToStaticMarkup(
      <RouterProvider>
        <WorkspaceProvider>
          <FactoryProvider>
            <TourProvider>
              <AppHeader />
            </TourProvider>
          </FactoryProvider>
        </WorkspaceProvider>
      </RouterProvider>
    );

    expect(markup).toContain('Guided Tour');
    expect(markup).toContain('data-tour="plant-clock"');
  });

  it('renders Tour onboarding card and target in OverviewView', () => {
    const markup = renderToStaticMarkup(
      <RouterProvider>
        <WorkspaceProvider>
          <TourProvider>
            <OverviewView />
          </TourProvider>
        </WorkspaceProvider>
      </RouterProvider>
    );

    expect(markup).toContain('data-tour="overview-welcome"');
    expect(markup).toContain('New to Opwise? Explore the Production Planning Walkthrough');
    expect(markup).toContain('Start Guided Tour →');
  });
});
