/**
 * Router Context and Provider for Lightweight Deterministic Client Routing
 * Governed by PROJECT_RULES.md (Zero external dependencies).
 */

import React, { createContext, useContext, useEffect, useState, useMemo } from 'react';
import { APP_ROUTES, AppRoute, RouteMeta } from './types';

export interface RouterContextValue {
  currentRoute: AppRoute;
  currentMeta: RouteMeta | null;
  navigate: (route: AppRoute) => void;
  rawHash: string;
}

export const RouterContext = createContext<RouterContextValue | null>(null);

export function parseRouteFromHash(hash: string): AppRoute {
  const cleanHash = hash.replace(/^#\/?/, '').trim().toLowerCase();
  if (!cleanHash || cleanHash === 'overview') {
    return 'overview';
  }
  if (cleanHash === 'factory') {
    return 'factory';
  }
  if (cleanHash === 'planning') {
    return 'planning';
  }
  if (cleanHash === 'schedules' || cleanHash === 'schedule') {
    return 'schedules';
  }
  if (cleanHash === 'scenarios' || cleanHash === 'scenario') {
    return 'scenarios';
  }
  return 'not-found';
}

export interface RouterProviderProps {
  children: React.ReactNode;
  initialHash?: string;
}

export function RouterProvider({ children, initialHash }: RouterProviderProps): React.ReactElement {
  const [hash, setHash] = useState<string>(() => {
    if (initialHash !== undefined) return initialHash;
    if (typeof window !== 'undefined') return window.location.hash;
    return '#overview';
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleHashChange = () => {
      setHash(window.location.hash);
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, []);

  const currentRoute = useMemo(() => parseRouteFromHash(hash), [hash]);

  const currentMeta = useMemo(() => {
    if (currentRoute === 'not-found') return null;
    return APP_ROUTES[currentRoute] || null;
  }, [currentRoute]);

  const navigate = (route: AppRoute) => {
    if (typeof window !== 'undefined') {
      const targetHash = route === 'overview' ? '#overview' : `#${route}`;
      window.location.hash = targetHash;
    }
  };

  const value = useMemo(
    () => ({
      currentRoute,
      currentMeta,
      navigate,
      rawHash: hash,
    }),
    [currentRoute, currentMeta, hash]
  );

  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter(): RouterContextValue {
  const context = useContext(RouterContext);
  if (!context) {
    throw new Error('useRouter must be used within a RouterProvider');
  }
  return context;
}
