import React from 'react';
import { useSession } from 'next-auth/react';
import { Toaster } from 'react-hot-toast';
import Navbar from './Navbar';
import Sidebar from './Sidebar';
import { cn } from '@/lib/utils';

interface LayoutProps {
  children: React.ReactNode;
  showSidebar?: boolean;
  className?: string;
}

export default function Layout({ children, showSidebar = true, className }: LayoutProps) {
  const { data: session, status } = useSession();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);

  const isAuthenticated = status === 'authenticated';

  return (
    <div className="min-h-screen bg-gray-50">
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: '#363636',
            color: '#fff',
          },
          success: {
            style: {
              background: '#10b981',
            },
          },
          error: {
            style: {
              background: '#ef4444',
            },
          },
        }}
      />
      
      {isAuthenticated && (
        <Navbar
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          showMenuButton={showSidebar}
        />
      )}
      
      <div className={cn('flex', isAuthenticated && 'pt-16')}>
        {isAuthenticated && showSidebar && (
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        )}
        
        <main
          className={cn(
            'flex-1 transition-all duration-300',
            isAuthenticated && showSidebar && 'lg:ml-64',
            className
          )}
        >
          <div className="container mx-auto px-4 py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}