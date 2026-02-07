import React, { useState, useEffect } from 'react';

interface SceneNarrationProps {
    text: string;
    atmosphere?: string;
    onComplete?: () => void;
    typingSpeed?: number;
}

const atmosphereStyles: Record<string, string> = {
    lonely: 'bg-gradient-to-r from-indigo-900/10 to-purple-900/10 border-indigo-300',
    contemplative: 'bg-gradient-to-r from-blue-100 to-indigo-100 border-blue-300',
    excited: 'bg-gradient-to-r from-amber-100 to-orange-100 border-amber-300',
    tender: 'bg-gradient-to-r from-pink-100 to-rose-100 border-pink-300',
    philosophical: 'bg-gradient-to-r from-purple-100 to-violet-100 border-purple-300',
    bittersweet: 'bg-gradient-to-r from-amber-100 to-red-100 border-amber-300',
    default: 'bg-gradient-to-r from-gray-100 to-slate-100 border-gray-300',
};

export function SceneNarration({
    text,
    atmosphere = 'default',
    onComplete,
    typingSpeed = 30
}: SceneNarrationProps) {
    const [displayedText, setDisplayedText] = useState('');
    const [isComplete, setIsComplete] = useState(false);

    useEffect(() => {
        if (!text) return;

        let index = 0;
        const timer = setInterval(() => {
            if (index < text.length) {
                setDisplayedText(text.slice(0, index + 1));
                index++;
            } else {
                clearInterval(timer);
                setIsComplete(true);
                onComplete?.();
            }
        }, typingSpeed);

        return () => clearInterval(timer);
    }, [text, typingSpeed, onComplete]);

    const handleClick = () => {
        if (!isComplete) {
            setDisplayedText(text);
            setIsComplete(true);
            onComplete?.();
        }
    };

    const styleClass = atmosphereStyles[atmosphere] || atmosphereStyles.default;

    return (
        <div
            className={`${styleClass} border-2 p-6 rounded-lg cursor-pointer transition-all hover:shadow-lg`}
            onClick={handleClick}
        >
            <p className="text-gray-700 whitespace-pre-line leading-relaxed font-serif text-lg italic">
                {displayedText}
                {!isComplete && (
                    <span className="animate-pulse">▌</span>
                )}
            </p>

            {!isComplete && (
                <p className="text-xs text-gray-400 mt-4 text-center">
                    Klicke, um fortzufahren...
                </p>
            )}
        </div>
    );
}
