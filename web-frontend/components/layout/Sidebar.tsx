import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  BookOpen,
  BarChart3,
  Trophy,
  Settings,
  MessageCircle,
  Zap,
  X,
  Sparkles,
  MapPinned,
  Compass,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { PHONE_PRODUCT_TABS } from '@/lib/product-shell';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const productIcon = {
  atelier: Compass,
  notebook: BookOpen,
  missions: MapPinned,
  feuilleton: Sparkles,
};

const primaryNavigation = PHONE_PRODUCT_TABS.map((item) => ({
  name: item.label,
  href: item.href,
  icon: productIcon[item.id],
  activeRoutes: item.activeRoutes,
}));

const secondaryNavigation = [
  {
    name: 'Conversation practice',
    href: '/learn',
    icon: MessageCircle,
    activeRoutes: ['/learn', '/learn/new', '/learn/session/[id]'],
  },
  {
    name: 'Sessions',
    href: '/sessions',
    icon: MessageCircle,
    activeRoutes: ['/sessions'],
  },
  {
    name: 'Audio Mode',
    href: '/audio-session',
    icon: MessageCircle,
    activeRoutes: ['/audio-session'],
  },
  {
    name: '5000 Review',
    href: '/practice',
    icon: Zap,
    activeRoutes: ['/practice'],
  },
  {
    name: 'Progress',
    href: '/progress',
    icon: BarChart3,
    activeRoutes: ['/progress'],
  },
  {
    name: 'Achievements',
    href: '/achievements',
    icon: Trophy,
    activeRoutes: ['/achievements'],
  },
  {
    name: 'Settings',
    href: '/settings',
    icon: Settings,
    activeRoutes: ['/settings'],
  },
];

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const router = useRouter();
  const renderItem = (item: (typeof primaryNavigation)[number] | (typeof secondaryNavigation)[number]) => {
    const isActive = item.activeRoutes.includes(router.pathname);
    return (
      <Link
        key={item.name}
        href={item.href}
        className={cn(
          'group flex items-center px-3 py-3 text-sm font-bold border-2 transition-all duration-150',
          isActive
            ? 'bg-bauhaus-blue text-white border-black shadow-[4px_4px_0px_0px_#000]'
            : 'text-gray-600 border-transparent hover:border-black hover:bg-bauhaus-yellow hover:text-black hover:shadow-[4px_4px_0px_0px_#000]'
        )}
        onClick={() => {
          // Close sidebar on mobile when navigating.
          if (window.innerWidth < 1024) {
            onClose();
          }
        }}
      >
        <item.icon
          className={cn(
            'mr-3 h-5 w-5 transition-colors',
            isActive ? 'text-white' : 'text-gray-500 group-hover:text-black'
          )}
        />
        {item.name}
      </Link>
    );
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black bg-opacity-50 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div
        className={cn(
          'fixed top-16 left-0 z-50 h-[calc(100vh-4rem)] w-64 transform bg-white border-r-4 border-black transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-full flex-col">
          {/* Close button for mobile */}
          <div className="flex items-center justify-between p-4 lg:hidden border-b-4 border-black">
            <h2 className="text-lg font-extrabold text-black uppercase tracking-tight">Menu</h2>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-6 w-6 text-black" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-2 px-4 py-6">
            {primaryNavigation.map(renderItem)}
            <div className="my-4 border-t-2 border-black pt-4">
              <p className="mb-2 px-3 text-[10px] font-black uppercase tracking-[0.16em] text-gray-500">
                Desktop tools
              </p>
              <div className="space-y-2">
                {secondaryNavigation.map(renderItem)}
              </div>
            </div>
          </nav>
        </div>
      </div>
    </>
  );
}
