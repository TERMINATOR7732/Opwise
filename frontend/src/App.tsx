import React from 'react';
import { RouterProvider, useRouter } from './router/RouterContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { AppShell } from './components/layout/AppShell';
import { OverviewView } from './views/OverviewView';
import { FactoryView } from './views/FactoryView';
import { PlanningView } from './views/PlanningView';
import { SchedulesView } from './views/SchedulesView';
import { ScenariosView } from './views/ScenariosView';
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
    case 'not-found':
    default:
      return <NotFoundView />;
  }
}

export function App(): React.ReactElement {
  return (
    <RouterProvider>
      <WorkspaceProvider>
        <AppShell>
          <RouteSwitch />
        </AppShell>
      </WorkspaceProvider>
    </RouterProvider>
  );
}

export default App;
