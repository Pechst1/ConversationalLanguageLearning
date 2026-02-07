'use client';

import React from 'react';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Legend, Tooltip } from 'chart.js';

ChartJS.register(ArcElement, Legend, Tooltip);

type Props = {
    data: { category: string; value: number }[];
};

const COLORS: Record<string, string> = {
    grammar: '#ef4444',      // red-500
    spelling: '#f97316',     // orange-500
    vocabulary: '#3b82f6',   // blue-500
    style: '#a855f7',        // purple-500
    unknown: '#9ca3af',      // gray-400
};

const categoryLabel: Record<string, string> = {
    grammar: 'Grammatik',
    spelling: 'Rechtschreibung',
    vocabulary: 'Wortschatz',
    style: 'Stil',
    unknown: 'Sonstige',
};

export default function ErrorCategoryPie({ data }: Props) {
    if (!data || data.length === 0 || data.every((entry) => entry.value === 0)) {
        return (
            <div className="flex h-full items-center justify-center text-sm text-gray-500">
                Keine Fehler für das Diagramm verfügbar.
            </div>
        );
    }

    const chartData = {
        labels: data.map((entry) => categoryLabel[entry.category] ?? entry.category),
        datasets: [
            {
                data: data.map((entry) => entry.value),
                backgroundColor: data.map((entry) => COLORS[entry.category] || COLORS.unknown),
                borderWidth: 1,
                borderColor: '#ffffff',
            },
        ],
    };

    return (
        <Pie
            data={chartData}
            options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 14,
                            usePointStyle: true,
                            padding: 16,
                            font: { size: 12 },
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const value = context.raw as number;
                                const total = data.reduce((sum, d) => sum + d.value, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : '0';
                                return `${context.label}: ${value} (${percentage}%)`;
                            },
                        },
                    },
                },
            }}
        />
    );
}
