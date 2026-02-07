import React from 'react';
import { Filter } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface StoryFiltersProps {
  difficulty: string | undefined;
  theme: string | undefined;
  onDifficultyChange: (difficulty: string | undefined) => void;
  onThemeChange: (theme: string | undefined) => void;
}

const difficultyLevels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

const themeOptions = [
  { value: 'mystery', label: 'Mystery' },
  { value: 'adventure', label: 'Adventure' },
  { value: 'romance', label: 'Romance' },
  { value: 'detective', label: 'Detective' },
  { value: 'paris', label: 'Paris' },
  { value: 'cafe', label: 'Café' },
  { value: 'travel', label: 'Travel' },
];

export default function StoryFilters({
  difficulty,
  theme,
  onDifficultyChange,
  onThemeChange,
}: StoryFiltersProps) {
  const hasActiveFilters = difficulty !== undefined || theme !== undefined;

  const clearFilters = () => {
    onDifficultyChange(undefined);
    onThemeChange(undefined);
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-600" />
          <h3 className="font-medium text-gray-900">Filters</h3>
        </div>
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            Clear all
          </Button>
        )}
      </div>

      {/* Difficulty Filter */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Difficulty Level (CEFR)</label>
        <div className="flex flex-wrap gap-2">
          {difficultyLevels.map((level) => (
            <button
              key={level}
              onClick={() => onDifficultyChange(difficulty === level ? undefined : level)}
              className={`px-3 py-1.5 text-sm font-medium rounded border transition-colors ${
                difficulty === level
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-primary-500'
              }`}
            >
              {level}
            </button>
          ))}
        </div>
      </div>

      {/* Theme Filter */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Theme</label>
        <div className="flex flex-wrap gap-2">
          {themeOptions.map((option) => (
            <button
              key={option.value}
              onClick={() => onThemeChange(theme === option.value ? undefined : option.value)}
              className={`px-3 py-1.5 text-sm font-medium rounded border transition-colors ${
                theme === option.value
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-primary-500'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
