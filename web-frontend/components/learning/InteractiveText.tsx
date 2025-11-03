import React, { useState, useRef, useEffect } from 'react';

interface WordDefinition {
  word: string;
  definition: string;
  translation?: string;
  pronunciation?: string;
  difficulty?: number;
}

interface InteractiveTextProps {
  text: string;
  onWordClick?: (word: string) => void;
  onWordHover?: (word: string, definition?: WordDefinition) => void;
  className?: string;
  language?: 'french' | 'german' | 'spanish';
  enableTranslation?: boolean;
}

// Enhanced translation service for Next.js
class TranslationService {
  private static translations: Record<string, Record<string, string>> = {
    french: {
      'bonjour': 'Hallo, Guten Tag',
      'merci': 'Danke',
      'au revoir': 'Auf Wiedersehen',
      'oui': 'Ja',
      'non': 'Nein',
      'comment': 'Wie',
      'pourquoi': 'Warum',
      'quand': 'Wann',
      'où': 'Wo',
      'qui': 'Wer',
      'que': 'Was',
      'entreprise': 'Unternehmen',
      'marché': 'Markt', 
      'développement': 'Entwicklung',
      'système': 'System',
      'problème': 'Problem',
      'solution': 'Lösung',
      'projet': 'Projekt',
      'équipe': 'Team',
      'client': 'Kunde',
      'produit': 'Produkt',
      'service': 'Service, Dienstleistung',
      'qualité': 'Qualität',
      'prix': 'Preis',
      'résultat': 'Ergebnis',
      'objectif': 'Ziel',
      'stratégie': 'Strategie',
      'performance': 'Leistung',
      'innovation': 'Innovation',
      'croissance': 'Wachstum',
      'vente': 'Verkauf',
      'achat': 'Kauf',
      'budget': 'Budget',
      'investissement': 'Investition',
      'très': 'sehr',
      'nouveau': 'neu',
      'français': 'französisch',
      'important': 'wichtig',
      'possible': 'möglich',
      'différent': 'unterschiedlich',
      'grand': 'groß',
      'petit': 'klein',
      'bon': 'gut',
      'mauvais': 'schlecht',
      'travail': 'Arbeit',
      'temps': 'Zeit',
      'personne': 'Person',
      'monde': 'Welt',
      'vie': 'Leben',
      'jour': 'Tag',
      'année': 'Jahr',
      'chose': 'Sache, Ding',
      'faire': 'machen, tun',
      'aller': 'gehen',
      'voir': 'sehen',
      'savoir': 'wissen',
      'pouvoir': 'können',
      'vouloir': 'wollen',
      'dire': 'sagen',
      'venir': 'kommen',
      'prendre': 'nehmen',
      'donner': 'geben',
      'partir': 'gehen, fahren',
      'arriver': 'ankommen',
      'rester': 'bleiben',
      'devenir': 'werden',
      'mettre': 'stellen, legen',
      'avec': 'mit',
      'sans': 'ohne',
      'dans': 'in',
      'sur': 'auf',
      'sous': 'unter',
      'pour': 'für',
      'par': 'durch',
      'depuis': 'seit',
      'pendant': 'während',
      'avant': 'vor',
      'après': 'nach'
    },
    german: {
      'hallo': 'Bonjour, Salut',
      'danke': 'Merci',
      'auf wiedersehen': 'Au revoir',
      'ja': 'Oui',
      'nein': 'Non',
      'wie': 'Comment',
      'warum': 'Pourquoi',
      'wann': 'Quand',
      'wo': 'Où',
      'wer': 'Qui',
      'was': 'Que',
      'unternehmen': 'Entreprise',
      'markt': 'Marché',
      'entwicklung': 'Développement',
      'system': 'Système',
      'problem': 'Problème',
      'lösung': 'Solution',
      'projekt': 'Projet',
      'team': 'Équipe',
      'kunde': 'Client',
      'produkt': 'Produit',
      'service': 'Service',
      'qualität': 'Qualité',
      'preis': 'Prix',
      'ergebnis': 'Résultat',
      'ziel': 'Objectif',
      'strategie': 'Stratégie',
      'leistung': 'Performance',
      'innovation': 'Innovation',
      'wachstum': 'Croissance',
      'verkauf': 'Vente',
      'kauf': 'Achat',
      'budget': 'Budget',
      'investition': 'Investissement',
      'sehr': 'très',
      'neu': 'nouveau',
      'deutsch': 'allemand',
      'wichtig': 'important',
      'möglich': 'possible',
      'unterschiedlich': 'différent',
      'groß': 'grand',
      'klein': 'petit',
      'gut': 'bon',
      'schlecht': 'mauvais',
      'arbeit': 'travail',
      'zeit': 'temps',
      'person': 'personne',
      'welt': 'monde',
      'leben': 'vie',
      'tag': 'jour',
      'jahr': 'année',
      'sache': 'chose'
    },
    spanish: {
      'hola': 'Bonjour, Salut',
      'gracias': 'Merci',
      'adiós': 'Au revoir',
      'sí': 'Oui',
      'no': 'Non',
      'cómo': 'Comment',
      'por qué': 'Pourquoi',
      'cuándo': 'Quand',
      'dónde': 'Où',
      'quién': 'Qui',
      'qué': 'Que',
      'empresa': 'Entreprise',
      'mercado': 'Marché',
      'desarrollo': 'Développement',
      'sistema': 'Système',
      'problema': 'Problème',
      'solución': 'Solution',
      'proyecto': 'Projet',
      'equipo': 'Équipe',
      'cliente': 'Client',
      'producto': 'Produit',
      'servicio': 'Service',
      'calidad': 'Qualité',
      'precio': 'Prix'
    }
  };

  static getTranslation(word: string, fromLanguage: string): string {
    const normalizedWord = word.toLowerCase().trim();
    const langTranslations = this.translations[fromLanguage];
    return langTranslations?.[normalizedWord] || `[Übersetzung für "${word}" nicht gefunden]`;
  }

  static calculateDifficulty(word: string, language: string): number {
    let difficulty = 3; // Base difficulty
    
    // Length-based difficulty
    if (word.length > 8) difficulty += 1;
    if (word.length < 4) difficulty -= 1;
    
    // Language-specific patterns
    if (language === 'french') {
      if (/[àâäéèêëïîôùûüÿç]/.test(word)) difficulty += 0.5;
      if (word.endsWith('tion') || word.endsWith('ment')) difficulty += 0.5;
    } else if (language === 'german') {
      if (/[äöüß]/.test(word)) difficulty += 0.5;
      if (word[0] === word[0].toUpperCase()) difficulty += 0.3; // Nouns
    }
    
    return Math.max(1, Math.min(5, Math.round(difficulty)));
  }
}

export const InteractiveText: React.FC<InteractiveTextProps> = ({
  text,
  onWordClick,
  onWordHover,
  className = '',
  language = 'french',
  enableTranslation = true,
}) => {
  const [hoveredWord, setHoveredWord] = useState<string | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<{ x: number; y: number } | null>(null);
  const [wordDefinition, setWordDefinition] = useState<WordDefinition | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Extract meaningful words (3+ characters, alphabetic including accented characters)
  const extractWords = (text: string): string[] => {
    return text.match(/\b[a-zA-ZàâäéèêëïîôùûüÿçÀÂÄÉÈÊËÏÎÔÙÛÜŸÇäöüßÄÖÜñáéíóúÑÁÉÍÓÚ]{3,}\b/g) || [];
  };

  const handleWordClick = (word: string, event: React.MouseEvent) => {
    event.preventDefault();
    console.log('🎯 InteractiveText word clicked:', word);
    onWordClick?.(word);
    
    // Hide tooltip when clicking
    handleWordLeave();
  };

  const handleWordHover = async (word: string, event: React.MouseEvent) => {
    if (!enableTranslation) return;
    
    const rect = event.currentTarget.getBoundingClientRect();
    const containerRect = containerRef.current?.getBoundingClientRect();
    
    if (!containerRect) return;
    
    // Calculate position relative to container
    const tooltipX = rect.left + (rect.width / 2) - containerRect.left;
    const tooltipY = rect.top - containerRect.top - 10;
    
    setTooltipPosition({ x: tooltipX, y: tooltipY });
    setHoveredWord(word);
    
    // Get translation and definition
    const translation = TranslationService.getTranslation(word, language);
    const difficulty = TranslationService.calculateDifficulty(word, language);
    
    const definition: WordDefinition = {
      word,
      definition: `${word} - Schwierigkeitsgrad: ${difficulty}/5`,
      translation,
      difficulty
    };
    
    setWordDefinition(definition);
    onWordHover?.(word, definition);
    
    console.log('🔍 Word hovered:', word, 'Translation:', translation);
  };

  const handleWordLeave = () => {
    setHoveredWord(null);
    setTooltipPosition(null);
    setWordDefinition(null);
  };

  // Adjust tooltip position to stay within bounds
  useEffect(() => {
    if (tooltipRef.current && tooltipPosition && containerRef.current) {
      const tooltip = tooltipRef.current;
      const container = containerRef.current;
      const containerRect = container.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();
      
      let adjustedX = tooltipPosition.x;
      let adjustedY = tooltipPosition.y;
      
      // Adjust horizontal position
      if (adjustedX + tooltipRect.width / 2 > containerRect.width) {
        adjustedX = containerRect.width - tooltipRect.width / 2 - 10;
      }
      if (adjustedX - tooltipRect.width / 2 < 0) {
        adjustedX = tooltipRect.width / 2 + 10;
      }
      
      // Adjust vertical position 
      if (adjustedY < tooltipRect.height + 10) {
        adjustedY = tooltipPosition.y + 30; // Show below word instead
      }
      
      if (adjustedX !== tooltipPosition.x || adjustedY !== tooltipPosition.y) {
        setTooltipPosition({ x: adjustedX, y: adjustedY });
      }
    }
  }, [tooltipPosition]);

  const renderInteractiveText = () => {
    const words = extractWords(text);
    const parts = text.split(/(\b[a-zA-ZàâäéèêëïîôùûüÿçÀÂÄÉÈÊËÏÎÔÙÛÜŸÇäöüßÄÖÜñáéíóúÑÁÉÍÓÚ]{3,}\b)/);
    
    return parts.map((part, index) => {
      const isWord = words.includes(part);
      
      if (isWord) {
        return (
          <span
            key={index}
            className={`interactive-word cursor-pointer px-1 py-0.5 rounded transition-all duration-200 hover:bg-blue-100 hover:text-blue-800 border-b border-dotted border-transparent hover:border-blue-400 ${hoveredWord === part ? 'bg-blue-100 text-blue-800 border-blue-400' : ''}`}
            onClick={(e) => handleWordClick(part, e)}
            onMouseEnter={(e) => handleWordHover(part, e)}
            onMouseLeave={handleWordLeave}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleWordClick(part, e as any);
              }
            }}
            title={`Klicke um "${part}" hinzuzufügen`}
          >
            {part}
          </span>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      <span>{renderInteractiveText()}</span>
      
      {hoveredWord && tooltipPosition && wordDefinition && (
        <div
          ref={tooltipRef}
          className="absolute z-50 bg-gray-800 text-white px-3 py-2 rounded-lg shadow-lg text-sm max-w-xs pointer-events-none"
          style={{
            left: tooltipPosition.x,
            top: tooltipPosition.y,
            transform: 'translateX(-50%) translateY(-100%)',
          }}
        >
          <div className="text-center">
            <div className="font-semibold text-white mb-1">{wordDefinition.word}</div>
            {wordDefinition.translation && (
              <div className="text-green-300">
                <strong>Deutsch:</strong> {wordDefinition.translation}
              </div>
            )}
            {wordDefinition.difficulty && (
              <div className="text-yellow-300 text-xs mt-1">
                <strong>Schwierigkeit:</strong> {wordDefinition.difficulty}/5
              </div>
            )}
          </div>
          {/* Tooltip arrow */}
          <div 
            className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-800"
          ></div>
        </div>
      )}
    </div>
  );
};

export default InteractiveText;