import React, { useState } from 'react';
import axios from 'axios';
import { RefreshCw, Check, AlertCircle } from 'lucide-react';

interface AnkiSyncProps {
    onSyncComplete?: () => void;
}

import { useSession } from 'next-auth/react';

export const AnkiSync: React.FC<AnkiSyncProps> = ({ onSyncComplete }) => {
    const { data: session } = useSession();
    const [syncing, setSyncing] = useState(false);
    const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [message, setMessage] = useState('');
    const [decks, setDecks] = useState<string[]>([]);
    const [selectedDeck, setSelectedDeck] = useState<string>('');
    const [showDeckSelect, setShowDeckSelect] = useState(false);

    const invokeAnkiConnect = async (action: string, params: any = {}) => {
        try {
            // Use our custom API proxy which handles headers correctly
            const response = await axios.post('/api/anki', {
                action,
                version: 6,
                params,
            });
            if (response.data.error) {
                throw new Error(response.data.error);
            }
            return response.data.result;
        } catch (error) {
            console.error('AnkiConnect error:', error);
            throw error;
        }
    };

    const fetchDecks = async () => {
        setSyncing(true);
        setMessage('Fetching decks...');
        try {
            const deckNames = await invokeAnkiConnect('deckNames');
            setDecks(deckNames);
            if (deckNames.length > 0) {
                setSelectedDeck(deckNames[0]);
                setShowDeckSelect(true);
                setMessage('Select a deck to sync');
            } else {
                setMessage('No decks found in Anki');
            }
            setStatus('idle');
        } catch (error: any) {
            console.error('Failed to fetch decks:', error);
            setStatus('error');
            setMessage('Could not connect to Anki. Is it running?');
        } finally {
            setSyncing(false);
        }
    };

    const handleSync = async () => {
        if (!selectedDeck) return;

        setSyncing(true);
        setStatus('idle');
        setMessage(`Syncing deck: ${selectedDeck}...`);

        try {
            // 2. Find cards in the selected deck
            const cardIds = await invokeAnkiConnect('findCards', { query: `deck:"${selectedDeck}"` });

            if (cardIds.length === 0) {
                setStatus('success');
                setMessage(`No cards found in deck "${selectedDeck}".`);
                setSyncing(false);
                return;
            }

            // 3. Get card info
            const batchSize = 200; // Increased to speed up sync
            let processed = 0;

            for (let i = 0; i < cardIds.length; i += batchSize) {
                const batch = cardIds.slice(i, i + batchSize);
                setMessage(`Processing cards ${i + 1} to ${Math.min(i + batchSize, cardIds.length)}...`);

                const cardsInfo = await invokeAnkiConnect('cardsInfo', { cards: batch });

                // 4. Send to backend
                const updates = cardsInfo.map((info: any) => ({
                    note_id: info.note,
                    card_id: info.cardId,
                    deck_name: info.deckName,
                    model_name: info.modelName,
                    fields: info.fields,
                    due: info.due,
                    interval: info.interval,
                    ease: info.factor,
                    reps: info.reps,
                    lapses: info.lapses,
                    ord: info.ord,
                }));

                // Flatten fields
                const flattenedUpdates = updates.map((u: any) => ({
                    ...u,
                    fields: Object.fromEntries(
                        Object.entries(u.fields).map(([k, v]: [string, any]) => [k, v.value])
                    )
                }));

                if (!session?.accessToken) {
                    throw new Error("Not authenticated");
                }

                await axios.post('http://localhost:8000/api/v1/progress/anki/sync',
                    { cards: flattenedUpdates },
                    {
                        headers: {
                            Authorization: `Bearer ${session.accessToken}`
                        }
                    }
                );
                processed += batch.length;
            }

            setStatus('success');
            setMessage(`Synced ${processed} cards from "${selectedDeck}".`);
            if (onSyncComplete) onSyncComplete();
            setShowDeckSelect(false); // Hide selection after success

        } catch (error: any) {
            console.error('Sync failed:', error);
            setStatus('error');

            if (error.message === "Not authenticated" || error.response?.status === 401) {
                setMessage("Session expired. Please sign out and sign in again.");
            } else if (error.code === 'ERR_NETWORK' && error.config?.url?.includes('8765')) {
                setMessage('Could not connect to Anki. Is it running with AnkiConnect?');
            } else {
                setMessage(`Sync failed: ${error.response?.data?.detail || error.message || "Unknown error"}`);
            }
        } finally {
            setSyncing(false);
        }
    };

    return (
        <div className="flex flex-col gap-4 p-4 bg-zinc-900 border border-zinc-800 rounded-lg shadow-lg">
            <div className="flex items-center justify-between">
                <div className="flex-1">
                    <h3 className="text-lg font-bold text-zinc-100 font-display">Anki Sync</h3>
                    <p className="text-sm text-zinc-400">
                        {message || "Connect to local Anki instance"}
                    </p>
                </div>

                {!showDeckSelect ? (
                    <button
                        onClick={fetchDecks}
                        disabled={syncing}
                        className={`
                            flex items-center justify-center w-12 h-12 rounded-full 
                            transition-all duration-300
                            ${syncing ? 'bg-amber-500 animate-pulse' : 'bg-zinc-800 hover:bg-amber-500 hover:text-black text-white'}
                            ${status === 'success' ? 'bg-green-500 text-black' : ''}
                            ${status === 'error' ? 'bg-red-500 text-white' : ''}
                        `}
                        title="Connect to Anki"
                    >
                        {syncing ? (
                            <RefreshCw className="w-6 h-6 animate-spin" />
                        ) : status === 'success' ? (
                            <Check className="w-6 h-6" />
                        ) : status === 'error' ? (
                            <AlertCircle className="w-6 h-6" />
                        ) : (
                            <RefreshCw className="w-6 h-6" />
                        )}
                    </button>
                ) : null}
            </div>

            {showDeckSelect && (
                <div className="flex gap-2 animate-in fade-in slide-in-from-top-2">
                    <select
                        value={selectedDeck}
                        onChange={(e) => setSelectedDeck(e.target.value)}
                        className="flex-1 bg-zinc-800 text-white border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-amber-500"
                        disabled={syncing}
                    >
                        {decks.map((deck) => (
                            <option key={deck} value={deck}>
                                {deck}
                            </option>
                        ))}
                    </select>
                    <button
                        onClick={handleSync}
                        disabled={syncing}
                        className="bg-amber-500 text-black font-bold px-4 py-2 rounded hover:bg-amber-400 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {syncing ? 'Syncing...' : 'Sync'}
                    </button>
                </div>
            )}
        </div>
    );
};
