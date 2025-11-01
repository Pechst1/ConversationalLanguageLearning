import React from 'react';

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

  return (
    <div className={className}>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Vokabelvorschläge</h3>
      <p className="mb-2 text-xs text-gray-500">
        Tippe auf ein Wort, um es in deine Antwort einzufügen. Versuche, mindestens drei Vorschläge in deiner Antwort zu verwenden, um XP zu verdienen.
      </p>
      <div className="flex flex-wrap gap-2">
        {words && words.length > 0 ? (
          words.map((w) => {
            const palette =
              w.familiarity === 'familiar'
                ? 'bg-[#8ecae6] border-[#023047] text-[#023047]'
                : w.familiarity === 'learning'
                ? 'bg-[#ffd60a] border-[#0b3954] text-[#0b3954]'
                : 'bg-[#e63946] border-[#7f1d1d] text-white';
            const selected = selectedIds.has(w.id) ? 'shadow-[0_0_0_3px_rgba(0,53,102,0.35)]' : '';
            return (
              <button
                key={w.id}
                type="button"
                className={`vocabulary-word ${palette} ${selected}`}
                onClick={() => toggleSelect(w)}
                title={w.translation ?? undefined}
              >
                {w.word}
              </button>
            );
          })
        ) : (
          <p className="text-sm text-gray-500">Keine Vorschläge</p>
        )}
      </div>
    </div>
  );
}
