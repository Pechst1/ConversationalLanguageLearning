import React from 'react';
import { Info, BookOpen, Languages, Sparkles, Quote } from 'lucide-react';

interface StoryInfoboxProps {
    title: string;
    content: string;
    type: 'grammar' | 'vocabulary' | 'culture' | 'story';
    grammarNote?: string;
    bookQuote?: string;
    onClose?: () => void;
}

const typeConfig = {
    grammar: {
        icon: Languages,
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-400',
        iconBg: 'bg-blue-500',
        label: 'Grammatik',
    },
    vocabulary: {
        icon: BookOpen,
        bgColor: 'bg-green-50',
        borderColor: 'border-green-400',
        iconBg: 'bg-green-500',
        label: 'Vokabular',
    },
    culture: {
        icon: Sparkles,
        bgColor: 'bg-purple-50',
        borderColor: 'border-purple-400',
        iconBg: 'bg-purple-500',
        label: 'Kultur',
    },
    story: {
        icon: Quote,
        bgColor: 'bg-amber-50',
        borderColor: 'border-amber-400',
        iconBg: 'bg-amber-500',
        label: 'Story-Kontext',
    },
};

export function StoryInfobox({
    title,
    content,
    type,
    grammarNote,
    bookQuote,
    onClose
}: StoryInfoboxProps) {
    const config = typeConfig[type] || typeConfig.story;
    const Icon = config.icon;

    return (
        <div className={`${config.bgColor} border-2 ${config.borderColor} p-4 rounded-lg shadow-lg animate-slide-up`}>
            {/* Header */}
            <div className="flex items-center gap-3 mb-3">
                <div className={`${config.iconBg} p-2 rounded-full`}>
                    <Icon className="h-4 w-4 text-white" />
                </div>
                <div className="flex-1">
                    <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                        {config.label}
                    </span>
                    <h4 className="font-bold text-gray-900">{title}</h4>
                </div>
                {onClose && (
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                    >
                        ×
                    </button>
                )}
            </div>

            {/* Content */}
            <div className="text-sm text-gray-700 whitespace-pre-line mb-3">
                {content}
            </div>

            {/* Grammar Note */}
            {grammarNote && (
                <div className="bg-white/50 border border-gray-200 p-3 rounded mt-3">
                    <p className="text-xs font-bold text-gray-500 mb-1">📝 Grammatik</p>
                    <p className="text-sm text-gray-800 whitespace-pre-line">{grammarNote}</p>
                </div>
            )}

            {/* Book Quote */}
            {bookQuote && (
                <div className="bg-white/50 border border-amber-200 p-3 rounded mt-3">
                    <p className="text-xs font-bold text-amber-600 mb-1">📖 Original-Zitat</p>
                    <p className="text-sm italic text-gray-800">&ldquo;{bookQuote}&rdquo;</p>
                </div>
            )}
        </div>
    );
}
