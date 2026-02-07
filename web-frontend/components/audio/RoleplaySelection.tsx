
import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, MapPin, Briefcase, Coffee, Stethoscope, Compass, MessageCircle } from 'lucide-react';
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
        <div className="w-full max-w-4xl mx-auto p-6">
            <div className="text-center mb-8">
                <h2 className="text-3xl font-black text-white mb-2">Choose Your Adventure</h2>
                <p className="text-purple-200">Select a real-world scenario or chat freely.</p>
            </div>

            {loading ? (
                <div className="flex justify-center p-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-white border-t-transparent" />
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Free Talk Card */}
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => onSelect(null)}
                        className="group relative overflow-hidden bg-gradient-to-br from-purple-600 to-indigo-600 rounded-2xl p-6 text-left shadow-xl border-2 border-transparent hover:border-white/50 transition-all"
                    >
                        <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <Sparkles className="w-24 h-24" />
                        </div>
                        <div className="relative z-10 flex items-start gap-4">
                            <div className="p-3 bg-white/20 rounded-xl backdrop-blur-sm">
                                <Sparkles className="w-8 h-8 text-white" />
                            </div>
                            <div>
                                <h3 className="text-xl font-bold text-white mb-1">Free Talk</h3>
                                <p className="text-indigo-100 text-sm mb-4">
                                    Casual conversation about any topic. The AI adapts to your interests.
                                </p>
                                <span className="inline-block px-3 py-1 bg-white/20 rounded-full text-xs font-bold text-white uppercase tracking-wider">
                                    Adaptive
                                </span>
                            </div>
                        </div>
                    </motion.button>

                    {/* Scenario Cards */}
                    {scenarios.map((scenario) => (
                        <motion.button
                            key={scenario.id}
                            whileHover={{ scale: 1.02 }}
                            whileTap={{ scale: 0.98 }}
                            onClick={() => onSelect(scenario.id)}
                            className="group relative overflow-hidden bg-white/10 hover:bg-white/20 backdrop-blur-sm rounded-2xl p-6 text-left shadow-xl border-2 border-transparent hover:border-purple-400/50 transition-all"
                        >
                            <div className="relative z-10 flex items-start gap-4">
                                <div className={`p-3 rounded-xl backdrop-blur-sm ${scenario.id === 'bakery' ? 'bg-orange-500/30 text-orange-200' :
                                        scenario.id === 'doctor' ? 'bg-blue-500/30 text-blue-200' :
                                            scenario.id === 'directions' ? 'bg-green-500/30 text-green-200' :
                                                'bg-purple-500/30 text-purple-200'
                                    }`}>
                                    {iconMap[scenario.id] || iconMap.default}
                                </div>
                                <div className="flex-1">
                                    <div className="flex items-center justify-between mb-1">
                                        <h3 className="text-xl font-bold text-white">{scenario.title}</h3>
                                        <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase ${scenario.difficulty === 'A1' ? 'bg-green-500/20 text-green-300' :
                                                scenario.difficulty === 'A2' ? 'bg-blue-500/20 text-blue-300' :
                                                    'bg-orange-500/20 text-orange-300'
                                            }`}>
                                            {scenario.difficulty}
                                        </span>
                                    </div>
                                    <p className="text-gray-300 text-sm mb-4 line-clamp-2">
                                        {scenario.description}
                                    </p>

                                    {/* Mini objectives preview */}
                                    <div className="flex gap-2">
                                        {scenario.objectives.slice(0, 2).map((obj, i) => (
                                            <span key={i} className="px-2 py-0.5 bg-black/30 rounded text-xs text-gray-400 truncate max-w-[120px]">
                                                {obj}
                                            </span>
                                        ))}
                                        {scenario.objectives.length > 2 && (
                                            <span className="px-2 py-0.5 bg-black/30 rounded text-xs text-gray-400">
                                                +{scenario.objectives.length - 2}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </motion.button>
                    ))}
                </div>
            )}

            <div className="mt-8 text-center">
                <button
                    onClick={onCancel}
                    className="text-purple-300 hover:text-white transition-colors text-sm font-medium"
                >
                    Cancel
                </button>
            </div>
        </div>
    );
}
