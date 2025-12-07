import React from 'react';
import { motion } from 'framer-motion';

export type Scenario = {
    id: string;
    title: string;
    description: string;
    icon: string;
};

const SCENARIOS: Scenario[] = [
    { id: 'bakery', title: 'The Bakery', description: 'Order croissants and baguettes.', icon: '🥐' },
    { id: 'cafe', title: 'Parisian Café', description: 'Order coffee and people watch.', icon: '☕' },
    { id: 'train', title: 'Train Station', description: 'Buy tickets and ask for directions.', icon: '🚆' },
    { id: 'market', title: 'Street Market', description: 'Buy fresh vegetables and fruits.', icon: '🍎' },
    { id: 'pharmacy', title: 'Pharmacy', description: 'Explain your symptoms and get medicine.', icon: '💊' },
    { id: 'hotel', title: 'Hotel Check-in', description: 'Check into your room and ask about amenities.', icon: '🏨' },
];

type Props = {
    selectedId: string | null;
    onSelect: (id: string | null) => void;
};

export default function ScenarioSelector({ selectedId, onSelect }: Props) {
    return (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {SCENARIOS.map((scenario) => {
                const isSelected = selectedId === scenario.id;
                return (
                    <motion.button
                        key={scenario.id}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => onSelect(isSelected ? null : scenario.id)}
                        className={`
              relative p-4 rounded-xl border-2 text-left transition-all duration-200
              ${isSelected
                                ? 'border-blue-500 bg-blue-50 shadow-md'
                                : 'border-gray-200 bg-white hover:border-blue-200 hover:bg-gray-50'
                            }
            `}
                    >
                        <div className="text-2xl mb-2">{scenario.icon}</div>
                        <div className="font-bold text-gray-800 text-sm">{scenario.title}</div>
                        <div className="text-xs text-gray-500 mt-1 leading-tight">{scenario.description}</div>

                        {isSelected && (
                            <div className="absolute top-2 right-2 text-blue-500">
                                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                </svg>
                            </div>
                        )}
                    </motion.button>
                );
            })}
        </div>
    );
}
