import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, MapPin, Briefcase, Coffee, Stethoscope, MessageCircle } from 'lucide-react';
import apiService from '@/services/api';

interface Scenario {
    id: string;
    title: string;
    description: string;
    difficulty: string;
    objectives: string[];
}

interface RoleplaySelectionProps {
    onSelect: (scenarioId: string | null) => void;
    onCancel: () => void;
}

const iconMap: Record<string, React.ReactNode> = {
    bakery: <Coffee className="w-8 h-8" />,
    doctor: <Stethoscope className="w-8 h-8" />,
    directions: <MapPin className="w-8 h-8" />,
    restaurant_order: <Coffee className="w-8 h-8" />,
    job_interview: <Briefcase className="w-8 h-8" />,
    default: <MessageCircle className="w-8 h-8" />,
};

export function RoleplaySelection({ onSelect, onCancel }: RoleplaySelectionProps) {
    const [scenarios, setScenarios] = useState<Scenario[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchScenarios = async () => {
            try {
                const data = await apiService.getAudioScenarios();
                setScenarios(data);
            } catch (error) {
                console.error('Failed to load scenarios', error);
            } finally {
                setLoading(false);
            }
        };
        fetchScenarios();
    }, []);

    return (
        <div className="w-full max-w-4xl mx-auto p-6 text-[var(--app-ink)]">
            <div className="text-center mb-8">
                <h2 className="font-serif text-5xl italic text-black mb-2">Choose Your Adventure</h2>
                <p className="text-[var(--app-ink-2)] font-medium">Select a real-world scenario or chat freely.</p>
            </div>

            {loading ? (
                <div className="flex justify-center p-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-black border-t-transparent" />
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Free Talk Card */}
                    <button
                        onClick={() => onSelect(null)}
                        className="group relative overflow-hidden bg-bauhaus-yellow border-4 border-black rounded-none p-6 text-left shadow-[6px_6px_0px_0px_#000] hover:shadow-[8px_8px_0px_0px_#000] hover:-translate-y-0.5 transition-all text-black"
                    >
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <Sparkles className="w-24 h-24 text-black" />
                        </div>
                        <div className="relative z-10 flex items-start gap-4">
                            <div className="p-3 bg-white border-2 border-black rounded-none">
                                <Sparkles className="w-8 h-8 text-black" />
                            </div>
                            <div>
                                <h3 className="text-xl font-black mb-1">Free Talk</h3>
                                <p className="text-stone-800 text-sm mb-4">
                                    Casual conversation about any topic. The AI adapts to your interests.
                                </p>
                                <span className="inline-block px-3 py-1 bg-white border border-black rounded-none text-xs font-bold uppercase tracking-wider">
                                    Adaptive
                                </span>
                            </div>
                        </div>
                    </button>

                    {/* Scenario Cards */}
                    {scenarios.map((scenario) => (
                        <button
                            key={scenario.id}
                            onClick={() => onSelect(scenario.id)}
                            className="group relative overflow-hidden bg-white hover:bg-stone-50 border-4 border-black rounded-none p-6 text-left shadow-[6px_6px_0px_0px_#000] hover:shadow-[8px_8px_0px_0px_#000] hover:-translate-y-0.5 transition-all text-black"
                        >
                            <div className="relative z-10 flex items-start gap-4">
                                <div className={`p-3 rounded-none border-2 border-black ${scenario.id === 'bakery' ? 'bg-amber-100 text-amber-800' :
                                        scenario.id === 'doctor' ? 'bg-rose-100 text-rose-800' :
                                            scenario.id === 'directions' ? 'bg-emerald-100 text-emerald-800' :
                                                'bg-indigo-100 text-indigo-800'
                                    }`}>
                                    {iconMap[scenario.id] || iconMap.default}
                                </div>
                                <div className="flex-1">
                                    <div className="flex items-center justify-between mb-1">
                                        <h3 className="text-xl font-black">{scenario.title}</h3>
                                        <span className={`px-2 py-0.5 border border-black rounded-none text-xs font-bold uppercase ${scenario.difficulty === 'A1' ? 'bg-emerald-100 text-emerald-800' :
                                                scenario.difficulty === 'A2' ? 'bg-blue-100 text-blue-800' :
                                                    'bg-orange-100 text-orange-800'
                                            }`}>
                                            {scenario.difficulty}
                                        </span>
                                    </div>
                                    <p className="text-stone-600 text-sm mb-4 line-clamp-2">
                                        {scenario.description}
                                    </p>

                                    {/* Mini objectives preview */}
                                    <div className="flex gap-2 flex-wrap">
                                        {scenario.objectives.slice(0, 2).map((obj, i) => (
                                            <span key={i} className="px-2 py-0.5 bg-stone-100 border border-black rounded-none text-xs text-stone-700 truncate max-w-[120px] font-medium">
                                                {obj}
                                            </span>
                                        ))}
                                        {scenario.objectives.length > 2 && (
                                            <span className="px-2 py-0.5 bg-stone-100 border border-black rounded-none text-xs text-stone-700 font-bold">
                                                +{scenario.objectives.length - 2}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            )}

            <div className="mt-12 text-center">
                <button
                    onClick={onCancel}
                    className="text-[var(--app-ink-2)] hover:text-black font-bold uppercase tracking-wider text-xs transition-colors"
                >
                    Cancel
                </button>
            </div>
        </div>
    );
}
