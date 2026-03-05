import React from 'react';
import { Link, useLocation } from 'react-router-dom';

const TABS = [
  { path: '/', label: 'Upload' },
  { path: '/results', label: 'Results' },
  { path: '/summary', label: 'Summary' },
];

export function NavBar() {
  const location = useLocation();

  return (
    <nav className="border-b border-gray-200 bg-white">
      <div className="max-w-5xl mx-auto px-6 py-4 flex gap-8">
        {TABS.map(({ path, label }) => {
          const isActive = path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);
          return (
            <Link
              key={path}
              to={path}
              className={`font-medium ${isActive ? 'text-gray-900 border-b-2 border-gray-900 pb-1' : 'text-gray-500 hover:text-gray-700'}`}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
