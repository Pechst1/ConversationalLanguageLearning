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
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white border-b-4 border-black">
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
                <Menu className="h-6 w-6 text-black" />
              </Button>
            )}

            <Link href="/dashboard" className="flex items-center group">
              <div className="flex-shrink-0 transition-transform group-hover:scale-110">
                <div className="w-10 h-10 bg-bauhaus-blue border-2 border-black shadow-[3px_3px_0px_0px_#000] flex items-center justify-center">
                  <span className="text-white font-black text-lg">CL</span>
                </div>
              </div>
              <div className="ml-3">
                <h1 className="text-xl font-extrabold text-black uppercase tracking-tight">
                  Language Learning
                </h1>
              </div>
            </Link>
          </div>

          <div className="flex items-center space-x-4">
            {/* Notifications */}
            <Button variant="ghost" size="icon" className="relative hover:bg-transparent">
              <Bell className="h-6 w-6 text-black hover:text-bauhaus-blue transition-colors" />
              <span className="absolute top-1 right-1 h-3 w-3 bg-bauhaus-red border border-black rounded-full"></span>
            </Button>

            {/* User Menu */}
            <div className="relative">
              <Button
                variant="ghost"
                className="flex items-center space-x-2 hovered:bg-transparent"
                onClick={() => setDropdownOpen(!dropdownOpen)}
              >
                <div className="w-9 h-9 bg-bauhaus-yellow border-2 border-black flex items-center justify-center shadow-[2px_2px_0px_0px_#000]">
                  <span className="text-black text-sm font-bold">
                    {getInitials(session?.user?.name || session?.user?.email || 'U')}
                  </span>
                </div>
                <span className="hidden md:block text-sm font-bold text-black group-hover:underline">
                  {session?.user?.name || session?.user?.email}
                </span>
              </Button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white border-4 border-black shadow-[8px_8px_0px_0px_#000] py-0 z-50">
                  <div className="bg-bauhaus-yellow p-3 border-b-4 border-black">
                    <p className="text-xs font-bold uppercase text-black">User Menu</p>
                  </div>
                  <Link
                    href="/profile"
                    className="flex items-center px-4 py-3 text-sm font-bold text-black hover:bg-bauhaus-blue hover:text-white transition-colors border-b-2 border-black"
                    onClick={() => setDropdownOpen(false)}
                  >
                    <User className="mr-3 h-4 w-4" />
                    Profile
                  </Link>
                  <Link
                    href="/settings"
                    className="flex items-center px-4 py-3 text-sm font-bold text-black hover:bg-bauhaus-blue hover:text-white transition-colors border-b-2 border-black"
                    onClick={() => setDropdownOpen(false)}
                  >
                    <Settings className="mr-3 h-4 w-4" />
                    Settings
                  </Link>
                  <button
                    onClick={handleSignOut}
                    className="flex items-center w-full px-4 py-3 text-sm font-bold text-black hover:bg-bauhaus-red hover:text-white transition-colors"
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