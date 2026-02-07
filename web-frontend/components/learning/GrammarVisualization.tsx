import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface GrammarVisualizationProps {
  type: 'conjugation_table' | 'timeline' | 'agreement_flow' | 'sentence_structure' | null;
  conceptName: string;
  data?: any;
}

export default function GrammarVisualization({
  type,
  conceptName,
  data,
}: GrammarVisualizationProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!type) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl border border-indigo-200 dark:border-indigo-800 overflow-hidden"
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-indigo-100/50 dark:hover:bg-indigo-800/20 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xl">{getVisualizationIcon(type)}</span>
          <span className="font-medium text-indigo-900 dark:text-indigo-100">
            {getVisualizationTitle(type)}
          </span>
        </div>
        <motion.span
          animate={{ rotate: isExpanded ? 180 : 0 }}
          className="text-indigo-500"
        >
          ▼
        </motion.span>
      </button>

      {/* Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="px-4 pb-4"
          >
            {type === 'conjugation_table' && (
              <ConjugationTable data={data} conceptName={conceptName} />
            )}
            {type === 'timeline' && (
              <TenseTimeline data={data} conceptName={conceptName} />
            )}
            {type === 'agreement_flow' && (
              <AgreementFlowChart data={data} conceptName={conceptName} />
            )}
            {type === 'sentence_structure' && (
              <SentenceStructure data={data} conceptName={conceptName} />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// Conjugation Table Component
function ConjugationTable({ data, conceptName }: { data?: any; conceptName: string }) {
  // Default data for demonstration
  const defaultConjugations = {
    'Présent': {
      je: 'parle',
      tu: 'parles',
      'il/elle': 'parle',
      nous: 'parlons',
      vous: 'parlez',
      'ils/elles': 'parlent',
    },
    'Passé Composé': {
      je: 'ai parlé',
      tu: 'as parlé',
      'il/elle': 'a parlé',
      nous: 'avons parlé',
      vous: 'avez parlé',
      'ils/elles': 'ont parlé',
    },
    'Imparfait': {
      je: 'parlais',
      tu: 'parlais',
      'il/elle': 'parlait',
      nous: 'parlions',
      vous: 'parliez',
      'ils/elles': 'parlaient',
    },
  };

  const conjugations = data?.conjugations || defaultConjugations;
  const tenses = Object.keys(conjugations);
  const pronouns = ['je', 'tu', 'il/elle', 'nous', 'vous', 'ils/elles'];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-indigo-200 dark:border-indigo-700">
            <th className="text-left py-2 pr-4 font-medium text-indigo-700 dark:text-indigo-300">
              Pronomen
            </th>
            {tenses.map(tense => (
              <th
                key={tense}
                className="text-left py-2 px-4 font-medium text-indigo-700 dark:text-indigo-300"
              >
                {tense}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pronouns.map((pronoun, i) => (
            <motion.tr
              key={pronoun}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="border-b border-indigo-100 dark:border-indigo-800 last:border-0"
            >
              <td className="py-2 pr-4 font-medium text-gray-700 dark:text-gray-300">
                {pronoun}
              </td>
              {tenses.map(tense => (
                <td
                  key={tense}
                  className="py-2 px-4 text-indigo-600 dark:text-indigo-400 font-mono"
                >
                  {conjugations[tense]?.[pronoun] || '-'}
                </td>
              ))}
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Tense Timeline Component
function TenseTimeline({ data, conceptName }: { data?: any; conceptName: string }) {
  const events = data?.events || [
    { label: 'Passé', position: 20, color: 'bg-blue-500' },
    { label: 'Présent', position: 50, color: 'bg-green-500' },
    { label: 'Futur', position: 80, color: 'bg-purple-500' },
  ];

  return (
    <div className="py-4">
      <div className="relative h-24">
        {/* Timeline line */}
        <div className="absolute left-4 right-4 top-1/2 h-1 bg-gradient-to-r from-blue-300 via-green-300 to-purple-300 rounded-full" />

        {/* Now marker */}
        <motion.div
          initial={{ opacity: 0, scale: 0 }}
          animate={{ opacity: 1, scale: 1 }}
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-4 h-4 bg-green-500 rounded-full border-4 border-white shadow-lg z-10"
        />

        {/* Event markers */}
        {events.map((event: any, i: number) => (
          <motion.div
            key={event.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="absolute top-0"
            style={{ left: `${event.position}%`, transform: 'translateX(-50%)' }}
          >
            <div
              className={`w-3 h-3 ${event.color} rounded-full mx-auto mb-1 mt-8`}
            />
            <span className="text-xs font-medium text-gray-600 dark:text-gray-300 whitespace-nowrap">
              {event.label}
            </span>
          </motion.div>
        ))}

        {/* Labels */}
        <div className="absolute left-4 bottom-0 text-xs text-gray-400">Vergangenheit</div>
        <div className="absolute left-1/2 bottom-0 -translate-x-1/2 text-xs text-gray-400">Jetzt</div>
        <div className="absolute right-4 bottom-0 text-xs text-gray-400">Zukunft</div>
      </div>

      <p className="text-sm text-gray-600 dark:text-gray-400 mt-4 text-center">
        Die Zeitlinie zeigt, wann verschiedene Zeitformen verwendet werden.
      </p>
    </div>
  );
}

// Agreement Flow Chart Component
function AgreementFlowChart({ data, conceptName }: { data?: any; conceptName: string }) {
  const steps = data?.steps || [
    { label: 'Nomen', example: 'la maison', arrow: true },
    { label: 'Adjektiv', example: 'blanche', arrow: true },
    { label: 'Verb', example: 'est', arrow: false },
  ];

  return (
    <div className="py-4">
      <div className="flex items-center justify-center gap-2 flex-wrap">
        {steps.map((step: any, i: number) => (
          <motion.div
            key={step.label}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.15 }}
            className="flex items-center"
          >
            <div className="bg-white dark:bg-gray-800 rounded-lg p-3 shadow-sm border border-indigo-200 dark:border-indigo-700">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                {step.label}
              </div>
              <div className="font-medium text-indigo-600 dark:text-indigo-400">
                {step.example}
              </div>
            </div>
            {step.arrow && (
              <span className="mx-2 text-indigo-400 text-xl">→</span>
            )}
          </motion.div>
        ))}
      </div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="mt-4 p-3 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg text-center"
      >
        <span className="text-sm text-indigo-700 dark:text-indigo-300">
          💡 Tipp: Genus und Numerus müssen übereinstimmen!
        </span>
      </motion.div>
    </div>
  );
}

// Sentence Structure Component
function SentenceStructure({ data, conceptName }: { data?: any; conceptName: string }) {
  const [hoveredPart, setHoveredPart] = useState<string | null>(null);

  const parts = data?.parts || [
    { type: 'subject', text: 'Je', color: 'bg-blue-200 border-blue-400', label: 'Subjekt' },
    { type: 'negation1', text: 'ne', color: 'bg-red-200 border-red-400', label: 'Verneinung' },
    { type: 'verb', text: 'parle', color: 'bg-green-200 border-green-400', label: 'Verb' },
    { type: 'negation2', text: 'pas', color: 'bg-red-200 border-red-400', label: 'Verneinung' },
    { type: 'object', text: 'français', color: 'bg-purple-200 border-purple-400', label: 'Objekt' },
  ];

  return (
    <div className="py-4">
      <div className="flex items-center justify-center gap-1 flex-wrap mb-4">
        {parts.map((part: any, i: number) => (
          <motion.div
            key={`${part.type}-${i}`}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            onMouseEnter={() => setHoveredPart(part.type)}
            onMouseLeave={() => setHoveredPart(null)}
            className={`relative px-3 py-2 rounded border-2 ${part.color} cursor-pointer transition-transform ${
              hoveredPart === part.type ? 'scale-110 z-10' : ''
            }`}
          >
            <span className="font-medium text-gray-800">{part.text}</span>
            {hoveredPart === part.type && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-gray-800 text-white text-xs rounded whitespace-nowrap"
              >
                {part.label}
              </motion.div>
            )}
          </motion.div>
        ))}
      </div>

      <div className="flex justify-center gap-4 text-xs">
        {[
          { color: 'bg-blue-200 border-blue-400', label: 'Subjekt' },
          { color: 'bg-green-200 border-green-400', label: 'Verb' },
          { color: 'bg-red-200 border-red-400', label: 'Verneinung' },
          { color: 'bg-purple-200 border-purple-400', label: 'Objekt' },
        ].map(item => (
          <div key={item.label} className="flex items-center gap-1">
            <div className={`w-3 h-3 rounded border ${item.color}`} />
            <span className="text-gray-600 dark:text-gray-400">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function getVisualizationIcon(type: string): string {
  const icons: Record<string, string> = {
    conjugation_table: '📊',
    timeline: '⏱️',
    agreement_flow: '🔗',
    sentence_structure: '📝',
  };
  return icons[type] || '📈';
}

function getVisualizationTitle(type: string): string {
  const titles: Record<string, string> = {
    conjugation_table: 'Konjugationstabelle',
    timeline: 'Zeitstrahl',
    agreement_flow: 'Kongruenz-Diagramm',
    sentence_structure: 'Satzstruktur',
  };
  return titles[type] || 'Visualisierung';
}
