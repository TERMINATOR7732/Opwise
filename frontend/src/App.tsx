import React from 'react';
import { RouterProvider, useRouter } from './router/RouterContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { FactoryProvider } from './context/FactoryContext';
import { TourProvider } from './context/TourContext';
import { AppShell } from './components/layout/AppShell';
import { GuidedTour } from './components/tour/GuidedTour';
import { OverviewView } from './views/OverviewView';
import { FactoryView } from './views/FactoryView';
import { PlanningView } from './views/PlanningView';
import { SchedulesView } from './views/SchedulesView';
import { ScenariosView } from './views/ScenariosView';
import { ReportsView } from './views/ReportsView';
import { NotFoundView } from './views/NotFoundView';

function RouteSwitch(): React.ReactElement {
  const { currentRoute } = useRouter();

  switch (currentRoute) {
    case 'overview':
      return <OverviewView />;
    case 'factory':
      return <FactoryView />;
    case 'planning':
      return <PlanningView />;
    case 'schedules':
      return <SchedulesView />;
    case 'scenarios':
      return <ScenariosView />;
    case 'reports':
      return <ReportsView />;
    case 'not-found':
    default:
      return <NotFoundView />;
  }
}

export function App(): React.ReactElement {
  return (
    <RouterProvider>
      <TourProvider>
        <WorkspaceProvider>
          <FactoryProvider>
            <AppShell>
              <RouteSwitch />
              <GuidedTour />
            </AppShell>
          </FactoryProvider>
        </WorkspaceProvider>
      </TourProvider>
    </RouterProvider>
  );
}

export default App;
