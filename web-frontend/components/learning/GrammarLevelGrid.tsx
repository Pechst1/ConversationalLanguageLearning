import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Clock, Play, Star } from 'lucide-react';
import { GrammarLevelGroup } from '@/types/grammar';

interface GrammarLevelGridProps {
    levels: GrammarLevelGroup;
    loading?: boolean;
    onConceptClick?: (concept: any, level: string) => void;
}

export default function GrammarLevelGrid({ levels, loading = false, onConceptClick }: GrammarLevelGridProps) {
    const [expandedLevels, setExpandedLevels] = useState<string[]>(
        Object.keys(levels).sort() // Expand all by default
    );

    const toggleLevel = (level: string) => {
        setExpandedLevels(prev =>
            prev.includes(level)
                ? prev.filter(l => l !== level)
                : [...prev, level]
        );
    };

    const getStateColor = (state: string) => {
        switch (state) {
            case 'gemeistert': return 'bg-green-400 text-black border-black';
            case 'gefestigt': return 'bg-blue-400 text-black border-black';
            case 'in_arbeit': return 'bg-yellow-400 text-black border-black';
            case 'ausbaufähig': return 'bg-orange-400 text-black border-black';
            default: return 'bg-gray-200 text-black border-black';
        }
    };

    const getStateLabel = (state: string) => {
        switch (state) {
            case 'gemeistert': return 'MEISTER';
            case 'gefestigt': return 'FEST';
            case 'in_arbeit': return 'LÄUFT';
            case 'ausbaufähig': return 'ÜBEN';
            default: return 'NEU';
        }
    };

    if (loading) {
        return (
            <div className="border-2 border-black p-8 text-center bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
                <span className="font-bold text-xl uppercase tracking-widest">Lade Daten...</span>
            </div>
        );
    }

    const sortedLevels = Object.keys(levels).sort();

    return (
        <div className="space-y-6">
            {sortedLevels.map(level => (
                <div key={level} className="border-2 border-black bg-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] transition-transform hover:-translate-y-1 hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)]">
                    <button
                        onClick={() => toggleLevel(level)}
                        className="w-full flex items-center justify-between p-4 bg-white hover:bg-gray-50 transition-colors"
                    >
                        <div className="flex items-center gap-4">
                            <div className={`w-12 h-12 border-2 border-black flex items-center justify-center font-black text-xl ${level.startsWith('A') ? 'bg-green-400' :
                                    level.startsWith('B') ? 'bg-blue-400' :
                                        'bg-purple-400'
                                }`}>
                                {level}
                            </div>
                            <div className="text-left">
                                <span className="block font-black text-xl uppercase tracking-tighter">Niveau {level}</span>
                                <span className="text-xs font-bold bg-black text-white px-2 py-0.5 inline-block mt-1">
                                    {levels[level].length} KONZEPTE
                                </span>
                            </div>
                        </div>
                        {expandedLevels.includes(level) ? (
                            <ChevronDown className="w-8 h-8 text-black" strokeWidth={3} />
                        ) : (
                            <ChevronRight className="w-8 h-8 text-black" strokeWidth={3} />
                        )}
                    </button>

                    <AnimatePresence>
                        {expandedLevels.includes(level) && (
                            <motion.div
                                initial={{ height: 0 }}
                                animate={{ height: 'auto' }}
                                exit={{ height: 0 }}
                                className="overflow-hidden border-t-2 border-black"
                            >
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-6 bg-gray-50">
                                    {levels[level].map(concept => (
                                        <button
                                            key={concept.id}
                                            onClick={() => onConceptClick && onConceptClick(concept, level)}
                                            className="group flex flex-col h-full text-left bg-white border-2 border-black p-0 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] hover:shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-1 transition-all active:translate-y-0 active:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]"
                                        >
                                            {/* Header */}
                                            <div className="flex justify-between items-stretch border-b-2 border-black">
                                                <div className="px-3 py-2 bg-gray-100 font-bold text-xs uppercase tracking-wider border-r-2 border-black flex-1 truncate">
                                                    {concept.category || 'Allgemein'}
                                                </div>
                                                <div className={`px-3 py-2 text-xs font-bold border-l-0 ${getStateColor(concept.state)}`}>
                                                    {getStateLabel(concept.state)}
                                                </div>
                                            </div>

                                            {/* Content */}
                                            <div className="p-4 flex-1 flex flex-col gap-2">
                                                <h4 className="font-black text-lg leading-tight uppercase tracking-tight">{concept.name}</h4>

                                                {concept.description && (
                                                    <p className="text-sm font-medium text-gray-600 line-clamp-2 border-l-4 border-gray-300 pl-2">
                                                        {concept.description}
                                                    </p>
                                                )}
                                            </div>

                                            {/* Footer */}
                                            <div className="mt-auto border-t-2 border-black flex divide-x-2 divide-black bg-gray-50">
                                                {/* Stats */}
                                                <div className="flex-1 p-2 flex items-center justify-center gap-2 text-xs font-bold">
                                                    <Clock className="w-4 h-4" />
                                                    <span>{concept.reps} REPS</span>
                                                </div>

                                                {/* Score / Stars */}
                                                <div className="flex-1 p-2 flex items-center justify-center gap-0.5">
                                                    {[1, 2, 3, 4, 5].map(star => (
                                                        <Star
                                                            key={star}
                                                            className={`w-3 h-3 ${(concept.score! / 2) >= star
                                                                    ? 'fill-black text-black'
                                                                    : 'text-gray-300'
                                                                }`}
                                                        />
                                                    ))}
                                                </div>

                                                {/* Action */}
                                                <div className="p-2 bg-primary-600 group-hover:bg-primary-500 text-white flex items-center justify-center transition-colors">
                                                    <Play className="w-5 h-5 fill-current" />
                                                </div>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            ))}
        </div>
    );
}
