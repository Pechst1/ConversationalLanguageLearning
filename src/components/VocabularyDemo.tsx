import React, { useState, useEffect } from 'react';
import { VocabularyService, LearningPreferences } from '../services/vocabulary/VocabularyService';
import { VocabularyChip } from './VocabularyChip';
import { InteractiveText } from './InteractiveText';

export interface VocabularyDemoProps {
  language?: string;
}

export const VocabularyDemo: React.FC<VocabularyDemoProps> = ({ language = 'french' }) => {
  const [vocabularyService] = useState(() => {
    const preferences: LearningPreferences = {
      targetLanguage: language,
      difficultyRange: [2, 4],
      categories: ['common', 'business', 'casual'],
      wordsPerSession: 8,
      repetitionMode: 'mixed',
    };
    return new VocabularyService(preferences);
  });
  
  const [proposals, setProposals] = useState<string[]>([]);
  const [stats, setStats] = useState({ total: 0, practiced: 0, mastered: 0, remaining: 0 });
  const [testMessage, setTestMessage] = useState('');
  const [extractedWords, setExtractedWords] = useState<string[]>([]);

  useEffect(() => {
    // Generate initial proposals
    const initialProposals = vocabularyService.generateWordProposals();
    setProposals(initialProposals);
    setStats(vocabularyService.getVocabularyStats());
  }, [vocabularyService]);

  const handleExtractWords = () => {
    if (testMessage) {
      const words = vocabularyService.extractVocabularyFromMessage(testMessage, true);
      setExtractedWords(words.map(w => w.word));
      
      // Generate new proposals
      const newProposals = vocabularyService.generateWordProposals();
      setProposals(newProposals);
      setStats(vocabularyService.getVocabularyStats());
    }
  };

  const handleWordClick = (word: string) => {
    vocabularyService.markWordsAsUsed([word], true);
    setStats(vocabularyService.getVocabularyStats());
    console.log('Word clicked:', word);
  };

  const handleRefresh = () => {
    const newProposals = vocabularyService.generateWordProposals();
    setProposals(newProposals);
  };

  const sampleMessages = {
    french: "Bonjour! Pour développer votre entreprise, il est important de comprendre les besoins de vos clients. Notre équipe peut vous aider à créer une stratégie marketing efficace et à améliorer la qualité de vos produits.",
    german: "Guten Tag! Um Ihr Unternehmen zu entwickeln, ist es wichtig, die Bedürfnisse Ihrer Kunden zu verstehen. Unser Team kann Ihnen helfen, eine effektive Marketingstrategie zu erstellen und die Qualität Ihrer Produkte zu verbessern.",
    spanish: "¡Hola! Para desarrollar su empresa, es importante entender las necesidades de sus clientes. Nuestro equipo puede ayudarle a crear una estrategia de marketing efectiva y mejorar la calidad de sus productos."
  };

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
      <h2>Vocabulary Service Demo ({language})</h2>
      
      <div style={{ marginBottom: '20px' }}>
        <h3>Current Vocabulary Proposals</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '10px' }}>
          {proposals.length === 0 && <p>No proposals generated yet.</p>}
          {proposals.map(word => (
            <VocabularyChip 
              key={word} 
              word={word} 
              onClick={handleWordClick}
            />
          ))}
        </div>
        <button onClick={handleRefresh}>Refresh Proposals</button>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h3>Vocabulary Stats</h3>
        <p>Total words: {stats.total}</p>
        <p>Practiced: {stats.practiced}</p>
        <p>Mastered: {stats.mastered}</p>
        <p>Remaining: {stats.remaining}</p>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h3>Test Word Extraction</h3>
        <textarea
          value={testMessage}
          onChange={e => setTestMessage(e.target.value)}
          placeholder={`Enter a message in ${language} to extract vocabulary...`}
          style={{ width: '100%', height: '100px', marginBottom: '10px' }}
        />
        <div style={{ marginBottom: '10px' }}>
          <button onClick={handleExtractWords}>Extract Words</button>
          <button onClick={() => setTestMessage(sampleMessages[language as keyof typeof sampleMessages] || sampleMessages.french)} style={{ marginLeft: '10px' }}>
            Use Sample Message
          </button>
        </div>
        {extractedWords.length > 0 && (
          <div>
            <p><strong>Extracted words:</strong> {extractedWords.join(', ')}</p>
          </div>
        )}
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h3>Interactive Text Demo</h3>
        <div style={{ border: '1px solid #ddd', padding: '15px', borderRadius: '8px' }}>
          <InteractiveText 
            text={testMessage || sampleMessages[language as keyof typeof sampleMessages] || sampleMessages.french}
            onWordClick={handleWordClick}
            onWordHover={(word) => console.log('Hovered:', word)}
          />
        </div>
      </div>
    </div>
  );
};

export default VocabularyDemo;