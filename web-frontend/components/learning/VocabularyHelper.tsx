import React from 'react';

type Word = {
  id: number;
  text: string;
  translation?: string;
  difficulty?: number;
};

type Props = {
  words: Word[];
  onSelect?: (id: number) => void;
};

export default function VocabularyHelper({ words, onSelect }: Props) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">Vokabelvorschläge</h3>
      <div className="flex flex-wrap gap-2">
        {words?.map((w) => (
          <button
            key={w.id}
            className="vocabulary-word"
            onClick={() => onSelect?.(w.id)}
            title={w.translation}
          >
            {w.text}
          </button>
        )) || <p className="text-sm text-gray-500">Keine Vorschläge</p>}
      </div>
    </div>
  );
}
