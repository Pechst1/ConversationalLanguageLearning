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
    iconBgColor = 'bg-[var(--accent-info)]',
    defaultOpen = true,
    children,
    badge,
}: CollapsibleSectionProps) {
    const [isOpen, setIsOpen] = useState(defaultOpen);

    return (
        <div className="border border-[var(--app-ink)] bg-[var(--app-sheet)] text-[var(--app-ink)]">
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="w-full flex items-center justify-between p-4 bg-[var(--app-sheet)] border-b border-[var(--app-ink)] hover:bg-[var(--app-paper-2)] transition-colors"
            >
                <div className="flex items-center gap-3">
                    {icon && (
                        <div className={`${iconBgColor} border border-[var(--app-ink)] p-1`}>
                            {icon}
                        </div>
                    )}
                    <h2 className="text-lg font-medium uppercase tracking-[0.08em]">{title}</h2>
                    {badge !== undefined && (
                        <span className="bg-[var(--accent-reward)] text-[var(--app-ink)] text-sm font-bold px-2 py-0.5 border border-[var(--app-ink)]">
                            {badge}
                        </span>
                    )}
                </div>
                <div className="border border-[var(--app-ink)] p-1 bg-[var(--app-paper)]">
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
