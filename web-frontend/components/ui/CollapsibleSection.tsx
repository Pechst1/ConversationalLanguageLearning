import React, { useState, ReactNode } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface CollapsibleSectionProps {
    title: string;
    icon?: ReactNode;
    iconBgColor?: string;
    defaultOpen?: boolean;
    children: ReactNode;
    badge?: string | number;
}

export function CollapsibleSection({
    title,
    icon,
    iconBgColor = 'bg-bauhaus-blue',
    defaultOpen = true,
    children,
    badge,
}: CollapsibleSectionProps) {
    const [isOpen, setIsOpen] = useState(defaultOpen);

    return (
        <div className="border-4 border-black bg-white shadow-[8px_8px_0px_0px_#000]">
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between p-4 bg-gray-50 border-b-4 border-black hover:bg-gray-100 transition-colors"
            >
                <div className="flex items-center gap-3">
                    {icon && (
                        <div className={`${iconBgColor} border-2 border-black p-1 shadow-[4px_4px_0px_0px_#000]`}>
                            {icon}
                        </div>
                    )}
                    <h2 className="text-xl font-black uppercase tracking-tight">{title}</h2>
                    {badge !== undefined && (
                        <span className="bg-bauhaus-yellow text-black text-sm font-bold px-2 py-0.5 border-2 border-black">
                            {badge}
                        </span>
                    )}
                </div>
                <div className="border-2 border-black p-1 bg-white shadow-[2px_2px_0px_0px_#000]">
                    {isOpen ? (
                        <ChevronDown className="w-5 h-5" />
                    ) : (
                        <ChevronRight className="w-5 h-5" />
                    )}
                </div>
            </button>
            <div
                className={`transition-all duration-300 overflow-hidden ${isOpen ? 'max-h-[5000px] opacity-100' : 'max-h-0 opacity-0'
                    }`}
            >
                <div className="p-6">{children}</div>
            </div>
        </div>
    );
}
