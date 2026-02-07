import React from 'react';
import { Heart } from 'lucide-react';

interface RelationshipMeterProps {
    level: number;
    maxLevel?: number;
    trust?: number;
    showLabel?: boolean;
    size?: 'sm' | 'md' | 'lg';
}

const levelDescriptions: Record<number, string> = {
    1: 'Neugieriger Fremder',
    2: 'Neugieriger Fremder',
    3: 'Interessierter Gesprächspartner',
    4: 'Interessierter Gesprächspartner',
    5: 'Freund',
    6: 'Freund',
    7: 'Vertrauter',
    8: 'Vertrauter',
    9: 'Seelenverwandter',
    10: 'Seelenverwandter',
};

export function RelationshipMeter({
    level,
    maxLevel = 10,
    trust = 0,
    showLabel = true,
    size = 'md'
}: RelationshipMeterProps) {
    const hearts = Array.from({ length: maxLevel }, (_, i) => i < level);

    const sizeClasses = {
        sm: 'h-3 w-3',
        md: 'h-4 w-4',
        lg: 'h-5 w-5',
    };

    const description = levelDescriptions[level] || 'Unbekannt';

    return (
        <div>
            {/* Hearts */}
            <div className="flex gap-0.5">
                {hearts.map((filled, i) => (
                    <Heart
                        key={i}
                        className={`${sizeClasses[size]} transition-all duration-300 ${filled
                                ? 'text-red-500 fill-red-500 animate-heart-beat'
                                : 'text-gray-300'
                            }`}
                        style={{ animationDelay: filled ? `${i * 50}ms` : '0ms' }}
                    />
                ))}
            </div>

            {/* Label */}
            {showLabel && (
                <p className="text-xs text-gray-500 mt-1">
                    {description}
                    {trust !== 0 && (
                        <span className={trust > 0 ? 'text-green-500' : 'text-red-500'}>
                            {' '}({trust > 0 ? '+' : ''}{trust} Vertrauen)
                        </span>
                    )}
                </p>
            )}
        </div>
    );
}

// Add animation styles
const styles = `
@keyframes heart-beat {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.2); }
}

.animate-heart-beat {
  animation: heart-beat 0.3s ease-out;
}
`;

// Inject styles
if (typeof document !== 'undefined') {
    const styleSheet = document.createElement('style');
    styleSheet.textContent = styles;
    document.head.appendChild(styleSheet);
}
