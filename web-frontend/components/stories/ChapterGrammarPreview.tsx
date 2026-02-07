import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChapterGrammarConcept } from '@/types/grammar';

interface ChapterGrammarPreviewProps {
  concepts: ChapterGrammarConcept[];
  onReviewClick?: (conceptId: number) => void;
  loading?: boolean;
}

const stateColors: Record<string, { bg: string; text: string; border: string }> = {
  neu: {
    bg: 'bg-gray-50 dark:bg-gray-800',
    text: 'text-gray-600 dark:text-gray-400',
    border: 'border-gray-200 dark:border-gray-700',
  },
  'ausbaufähig': {
    bg: 'bg-orange-50 dark:bg-orange-900/20',
    text: 'text-orange-600 dark:text-orange-400',
    border: 'border-orange-200 dark:border-orange-800',
  },
  in_arbeit: {
    bg: 'bg-yellow-50 dark:bg-yellow-900/20',
    text: 'text-yellow-600 dark:text-yellow-400',
    border: 'border-yellow-200 dark:border-yellow-800',
  },
  gefestigt: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    text: 'text-blue-600 dark:text-blue-400',
    border: 'border-blue-200 dark:border-blue-800',
  },
  gemeistert: {
    bg: 'bg-green-50 dark:bg-green-900/20',
    text: 'text-green-600 dark:text-green-400',
    border: 'border-green-200 dark:border-green-800',
  },
};

export default function ChapterGrammarPreview({
  concepts,
  onReviewClick,
  loading = false,
}: ChapterGrammarPreviewProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (loading) {
    return (
      <div className="animate-pulse bg-indigo-50 dark:bg-indigo-900/20 rounded-xl p-4">
        <div className="h-5 bg-indigo-200 dark:bg-indigo-800 rounded w-1/3 mb-3" />
        <div className="space-y-2">
          <div className="h-12 bg-indigo-200 dark:bg-indigo-800 rounded" />
          <div className="h-12 bg-indigo-200 dark:bg-indigo-800 rounded" />
        </div>
      </div>
    );
  }

  if (concepts.length === 0) return null;

  const dueCount = concepts.filter(c => c.is_due).length;
  const masteredCount = concepts.filter(c => c.state === 'gemeistert').length;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl border border-indigo-200 dark:border-indigo-800 overflow-hidden"
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-indigo-100/50 dark:hover:bg-indigo-800/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">📚</span>
          <div className="text-left">
            <h3 className="font-semibold text-indigo-900 dark:text-indigo-100">
              Grammatik-Fokus
            </h3>
            <p className="text-sm text-indigo-600 dark:text-indigo-400">
              {concepts.length} Konzept{concepts.length !== 1 ? 'e' : ''} in diesem Kapitel
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Status badges */}
          {dueCount > 0 && (
            <span className="px-2 py-1 bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 text-xs rounded-full">
              {dueCount} fällig
            </span>
          )}
          {masteredCount > 0 && (
            <span className="px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 text-xs rounded-full">
              {masteredCount} gemeistert
            </span>
          )}

          <motion.span
            animate={{ rotate: isExpanded ? 180 : 0 }}
            className="text-indigo-500"
          >
            ▼
          </motion.span>
        </div>
      </button>

      {/* Concept List */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="px-4 pb-4"
          >
            <div className="space-y-2">
              {concepts.map((concept, i) => {
                const colors = stateColors[concept.state] || stateColors.neu;

                return (
                  <motion.div
                    key={concept.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className={`rounded-lg p-3 border ${colors.border} ${colors.bg} flex items-center justify-between`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-gray-900 dark:text-white truncate">
                          {concept.name}
                        </h4>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors.text} ${colors.bg}`}>
                          {concept.level}
                        </span>
                      </div>

                      {concept.description && (
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 line-clamp-1">
                          {concept.description}
                        </p>
                      )}

                      {/* Progress bar */}
                      {concept.reps > 0 && (
                        <div className="flex items-center gap-2 mt-2">
                          <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                concept.score >= 7
                                  ? 'bg-green-500'
                                  : concept.score >= 5
                                  ? 'bg-yellow-500'
                                  : 'bg-orange-500'
                              }`}
                              style={{ width: `${concept.score * 10}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {concept.score.toFixed(1)}/10
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Action button */}
                    {onReviewClick && (
                      <button
                        onClick={() => onReviewClick(concept.id)}
                        className={`ml-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                          concept.is_due
                            ? 'bg-indigo-500 text-white hover:bg-indigo-600'
                            : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                        }`}
                      >
                        {concept.state === 'neu'
                          ? 'Lernen'
                          : concept.is_due
                          ? 'Wiederholen'
                          : 'Üben'}
                      </button>
                    )}
                  </motion.div>
                );
              })}
            </div>

            {/* Review All Button */}
            {dueCount > 0 && onReviewClick && (
              <motion.button
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.3 }}
                onClick={() => concepts.filter(c => c.is_due).forEach(c => onReviewClick(c.id))}
                className="mt-4 w-full py-2 bg-indigo-500 text-white rounded-lg font-medium hover:bg-indigo-600 transition-colors flex items-center justify-center gap-2"
              >
                <span>📝</span>
                Alle fälligen Konzepte wiederholen ({dueCount})
              </motion.button>
            )}

            {/* Tip */}
            <div className="mt-4 p-3 bg-indigo-100/50 dark:bg-indigo-900/30 rounded-lg">
              <p className="text-sm text-indigo-700 dark:text-indigo-300">
                💡 <strong>Tipp:</strong> Wiederhole die Grammatik vor dem Kapitel, um sie im Kontext der Geschichte besser zu verstehen!
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
