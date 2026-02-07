import React from 'react';
import { BookOpen } from 'lucide-react';

interface NarrativeCardProps {
  narrative: string | null;
}

export default function NarrativeCard({ narrative }: NarrativeCardProps) {
  if (!narrative) return null;

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-300 rounded-xl p-6 shadow-lg">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
            <BookOpen className="h-5 w-5 text-white" />
          </div>
        </div>
        <div className="flex-1">
          <h3 className="font-bold text-lg text-blue-900 mb-2">Story Opening</h3>
          <div className="prose prose-sm max-w-none">
            <p className="text-gray-700 leading-relaxed whitespace-pre-line">{narrative}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
