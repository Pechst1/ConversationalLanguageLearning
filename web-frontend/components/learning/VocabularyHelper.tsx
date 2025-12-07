import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

type Word = {
  id: number;
  word: string;
  translation?: string;
  is_new?: boolean;
  familiarity?: 'new' | 'learning' | 'familiar';
};

type Props = {
  words: Word[];
  className?: string;
  onInsertWord?: (word: string) => void;
  onToggleWord?: (word: Word, selected: boolean) => void;
};

export default function VocabularyHelper({ words, className, onInsertWord, onToggleWord }: Props) {
  const [selectedIds, setSelectedIds] = React.useState<Set<number>>(new Set());

  // Reset selection whenever the suggestion list changes
  React.useEffect(() => {
    setSelectedIds(new Set());
  }, [words]);

  const toggleSelect = React.useCallback(
    (w: Word) => {
      setSelectedIds((prev) => {
        const next = new Set(prev);
        let isSelected: boolean;
        if (next.has(w.id)) {
          next.delete(w.id);
          isSelected = false;
        } else {
          next.add(w.id);
          isSelected = true;
        }
        onToggleWord?.(w, isSelected);
        return next;
      });
      if (onInsertWord) {
        onInsertWord(w.word);
      }
    },
    [onInsertWord, onToggleWord]
  );

  const completedCount = selectedIds.size;
  const totalCount = words.length;
  const progress = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  return (
    <div className={`${className} overflow-hidden`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-gray-800 uppercase tracking-wider flex items-center gap-2">
          <span className="text-lg">🎯</span> Mission Objectives
        </h3>
        <div className="text-xs font-mono bg-gray-100 px-2 py-1 rounded text-gray-600">
          {completedCount}/{totalCount} COMPLETED
        </div>
      </div>

      <div className="relative h-1 bg-gray-100 rounded-full mb-4 overflow-hidden">
        <motion.div
          className="absolute top-0 left-0 h-full bg-gradient-to-r from-blue-500 to-purple-500"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>

      <p className="mb-3 text-xs text-gray-500">
        Use these words in your response to complete the mission and earn a Combo Bonus!
      </p>

      <div className="flex flex-wrap gap-2">
        <AnimatePresence>
          {words && words.length > 0 ? (
            words.map((w) => {
              const isSelected = selectedIds.has(w.id);
              const isNew = w.is_new;

              let baseClasses = "relative px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-200 border-2";
              let colorClasses = "";

              if (isSelected) {
                colorClasses = "bg-green-100 border-green-500 text-green-800 shadow-sm scale-105";
              } else if (isNew) {
                colorClasses = "bg-red-50 border-red-200 text-red-800 hover:border-red-300 hover:bg-red-100";
              } else {
                colorClasses = "bg-white border-gray-200 text-gray-700 hover:border-blue-300 hover:bg-blue-50";
              }

              return (
                <motion.button
                  key={w.id}
                  layout
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  type="button"
                  className={`${baseClasses} ${colorClasses}`}
                  onClick={() => toggleSelect(w)}
                  title={w.translation ?? undefined}
                >
                  {w.word}
                  {isSelected && (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute -top-2 -right-2 bg-green-500 text-white rounded-full p-0.5 w-4 h-4 flex items-center justify-center text-[10px]"
                    >
                      ✓
                    </motion.span>
                  )}
                  {isNew && !isSelected && (
                    <span className="absolute -top-1.5 -right-1.5 flex h-2.5 w-2.5">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
                    </span>
                  )}
                </motion.button>
              );
            })
          ) : (
            <p className="text-sm text-gray-400 italic">Mission complete. Awaiting new orders...</p>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
