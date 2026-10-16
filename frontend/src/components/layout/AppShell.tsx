import React, { useState } from 'react';
import { AppHeader } from './AppHeader';
import { AppNav } from './AppNav';

export interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps): React.ReactElement {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const toggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  const closeSidebar = () => {
    setIsSidebarOpen(false);
  };

  return (
    <div className="app-layout">
      <AppHeader onToggleSidebar={toggleSidebar} isSidebarOpen={isSidebarOpen} />
      <div className="app-body">
        <aside
          className={`app-sidebar ${isSidebarOpen ? 'open' : ''}`}
          aria-label="Sidebar Navigation"
        >
          <div style={{ padding: '0 1rem 0.75rem', borderBottom: '1px solid var(--border-subtle)', marginBottom: '0.75rem' }}>
            <span style={{ fontSize: '0.6875rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>
              Workplace Navigation
            </span>
          </div>
          <AppNav onNavClick={closeSidebar} />
        </aside>

        <main className="main-content" id="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
