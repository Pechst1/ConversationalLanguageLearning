import React from 'react';
import { useSession, signOut } from 'next-auth/react';
import Link from 'next/link';
import { Menu, Bell, User, LogOut, Settings } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { getInitials } from '@/lib/utils';

interface NavbarProps {
  onToggleSidebar: () => void;
  showMenuButton?: boolean;
}

export default function Navbar({ onToggleSidebar, showMenuButton = true }: NavbarProps) {
  const { data: session } = useSession();
  const [dropdownOpen, setDropdownOpen] = React.useState(false);

  const handleSignOut = () => {
    signOut({ callbackUrl: '/' });
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-200 shadow-sm">
      <div className="px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center">
            {showMenuButton && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleSidebar}
                className="mr-4 lg:hidden"
              >
                <Menu className="h-5 w-5" />
              </Button>
            )}
            
            <Link href="/dashboard" className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-sm">CL</span>
                </div>
              </div>
              <div className="ml-3">
                <h1 className="text-xl font-bold text-gray-900">
                  Language Learning
                </h1>
              </div>
            </Link>
          </div>

          <div className="flex items-center space-x-4">
            {/* Notifications */}
            <Button variant="ghost" size="icon" className="relative">
              <Bell className="h-5 w-5" />
              <span className="absolute top-0 right-0 h-2 w-2 bg-red-500 rounded-full"></span>
            </Button>

            {/* User Menu */}
            <div className="relative">
              <Button
                variant="ghost"
                className="flex items-center space-x-2"
                onClick={() => setDropdownOpen(!dropdownOpen)}
              >
                <div className="w-8 h-8 bg-primary-600 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-medium">
                    {getInitials(session?.user?.name || session?.user?.email || 'U')}
                  </span>
                </div>
                <span className="hidden md:block text-sm font-medium text-gray-700">
                  {session?.user?.name || session?.user?.email}
                </span>
              </Button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50">
                  <Link
                    href="/profile"
                    className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    onClick={() => setDropdownOpen(false)}
                  >
                    <User className="mr-3 h-4 w-4" />
                    Profile
                  </Link>
                  <Link
                    href="/settings"
                    className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                    onClick={() => setDropdownOpen(false)}
                  >
                    <Settings className="mr-3 h-4 w-4" />
                    Settings
                  </Link>
                  <hr className="my-1" />
                  <button
                    onClick={handleSignOut}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  >
                    <LogOut className="mr-3 h-4 w-4" />
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Backdrop for dropdown */}
      {dropdownOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setDropdownOpen(false)}
        />
      )}
    </nav>
  );
}