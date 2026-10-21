import React from 'react';
import { useRouter } from '../../router/RouterContext';
import { APP_ROUTES, AppRoute } from '../../router/types';

export interface AppNavProps {
  onNavClick?: () => void;
  className?: string;
}

export function AppNav({ onNavClick, className = '' }: AppNavProps): React.ReactElement {
  const { currentRoute, navigate } = useRouter();

  const handleLinkClick = (e: React.MouseEvent, routeId: AppRoute) => {
    e.preventDefault();
    navigate(routeId);
    if (onNavClick) {
      onNavClick();
    }
  };

  const navRoutes = Object.values(APP_ROUTES);

  return (
    <nav className={`app-sidebar-nav ${className}`} aria-label="Primary Navigation">
      <ul className="nav-list">
        {navRoutes.map((meta) => {
          const isActive = currentRoute === meta.id;
          return (
            <li key={meta.id}>
              <a
                href={meta.hash}
                onClick={(e) => handleLinkClick(e, meta.id)}
                className={`nav-item-link ${isActive ? 'active' : ''}`}
                aria-current={isActive ? 'page' : undefined}
                title={meta.description}
              >
                <span>{meta.label}</span>
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
