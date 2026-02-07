import React, { useState, useEffect, useRef } from 'react';
import { getSession, useSession } from 'next-auth/react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import {
    ArrowLeft,
    ArrowRight,
    Send,
    Mic,
    Volume2,
    Heart,
    MessageCircle,
    Star,
    Sparkles,
    ChevronRight,
    Info,
    Maximize2,
    Minimize2
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import ImmersiveStoryView from '@/components/story/ImmersiveStoryView';

// Types
interface Scene {
    id: string;
    chapter_id: string;
    location: string | null;
    atmosphere: string | null;
    narration: string;
    objectives: Objective[];
    npcs_present: NPCInScene[];
    estimated_duration_minutes: number;
    interaction_type?: 'free_input' | 'choice' | 'drawing';
    choices?: ChoiceOption[];
}

interface ChoiceOption {
    id: string;
    text: string;
}

interface Objective {
    id: string;
    description: string;
    type: string;
    optional: boolean;
    completed: boolean;
}

interface NPCInScene {
    id: string;
    name: string;
    display_name: string | null;
    role: string | null;
    avatar_url: string | null;
    relationship_level: number;
    trust: number;
    mood: string;
}

interface Chapter {
    id: string;
    story_id: string;
    order_index: number;
    title: string;
    target_level: string | null;
}

interface StoryProgress {
    story_id: string;
    current_chapter_id: string | null;
    current_scene_id: string | null;
    completion_percentage: number;
    status: string;
    story_flags: Record<string, any>;
    philosophical_learnings: string[];
    book_quotes_unlocked: string[];
}

interface StoryStartResponse {
    progress: StoryProgress;
    scene: Scene;
    chapter: Chapter;
}

interface StoryPageProps {
    storyData: StoryStartResponse | null;
    storyId: string;
    error: string | null;
}

export default function StoryPage({ storyData, storyId, error }: StoryPageProps) {
    const router = useRouter();
    const { data: session } = useSession();
    const [scene, setScene] = useState<Scene | null>(storyData?.scene || null);
    const [chapter, setChapter] = useState<Chapter | null>(storyData?.chapter || null);
    const [progress, setProgress] = useState<StoryProgress | null>(storyData?.progress || null);
    const [messages, setMessages] = useState<Message[]>([]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [showNarration, setShowNarration] = useState(true);
    const [activeNPC, setActiveNPC] = useState<NPCInScene | null>(null);
    const [pendingTransition, setPendingTransition] = useState<any>(null);
    const [isImmersiveMode, setIsImmersiveMode] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Initialize with narration
    useEffect(() => {
        if (scene && showNarration) {
            const narrationMessage: Message = {
                id: 'narration-' + Date.now(),
                type: 'narration',
                content: scene.narration,
                timestamp: new Date().toISOString(),
            };
            setMessages([narrationMessage]);
            setShowNarration(false);

            // Set first NPC as active
            if (scene.npcs_present.length > 0) {
                setActiveNPC(scene.npcs_present.find(n => n.id !== 'narrator') || scene.npcs_present[0]);
            }
        }
    }, [scene, showNarration]);

    // Auto-scroll to bottom
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSendMessage = async (choiceId?: string, choiceText?: string) => {
        const contentToSend = choiceText || inputValue;
        if (!contentToSend.trim() || isLoading || !session) return;

        // Add user message to UI
        const userMessage: Message = {
            id: 'user-' + Date.now(),
            type: 'user',
            content: contentToSend,
            timestamp: new Date().toISOString(),
        };

        setMessages(prev => [...prev, userMessage]);
        if (!choiceId) setInputValue(''); // Only clear input if typing
        setIsLoading(true);

        try {
            // Build conversation history for context
            const conversationHistory = messages
                .filter(m => m.type === 'user' || m.type === 'npc')
                .map(m => ({
                    role: m.type === 'user' ? 'user' : 'assistant',
                    content: m.content,
                }));

            // Call the story input endpoint
            const response = await fetch(`/api/proxy/stories/${storyId}/input`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: contentToSend,
                    choice_id: choiceId,
                    target_npc_id: activeNPC?.id !== 'narrator' ? activeNPC?.id : null,
                    conversation_history: conversationHistory,
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Failed to get response');
            }

            const data = await response.json();

            // Create NPC response message if available
            if (data.npc_response) {
                const npcResponse: Message = {
                    id: 'npc-' + Date.now(),
                    type: 'npc',
                    content: data.npc_response.content,
                    npcId: data.npc_response.npc_id,
                    npcName: data.npc_response.npc_name,
                    emotion: data.npc_response.emotion,
                    timestamp: new Date().toISOString(),
                };
                setMessages(prev => [...prev, npcResponse]);

                // Update NPC relationship level if changed
                if (data.npc_response.relationship_delta !== 0 && activeNPC) {
                    setActiveNPC({
                        ...activeNPC,
                        relationship_level: data.npc_response.new_relationship_level,
                    });
                }
            } else if (data.response) {
                // Generic response / narration from choice
                const sysResponse: Message = {
                    id: 'sys-' + Date.now(),
                    type: 'narration',
                    content: data.response,
                    timestamp: new Date().toISOString(),
                };
                setMessages(prev => [...prev, sysResponse]);
            }

            // Update story flags in progress
            if (data.updated_flags?.length > 0 && progress) {
                const newFlags = { ...progress.story_flags };
                data.updated_flags.forEach((flag: string) => {
                    newFlags[flag] = true;
                });
                setProgress({ ...progress, story_flags: newFlags });
            }

            // Handle objective completion
            if (data.consequences?.length > 0 && scene) {
                const completedObjectiveConsequences = data.consequences
                    .filter((c: any) => c.type === 'objective_complete');

                const completedObjectiveIds = completedObjectiveConsequences.map((c: any) => c.target);

                if (completedObjectiveIds.length > 0) {
                    const updatedObjectives = scene.objectives.map(obj => ({
                        ...obj,
                        completed: completedObjectiveIds.includes(obj.id) || obj.completed,
                    }));
                    setScene({ ...scene, objectives: updatedObjectives });

                    // Show achievement message with description from consequence or fallback to scene
                    for (const consequence of completedObjectiveConsequences) {
                        const description = consequence.description ||
                            scene.objectives.find((o: any) => o.id === consequence.target)?.description ||
                            consequence.target;

                        const achievementMessage: Message = {
                            id: 'achievement-' + Date.now() + Math.random(),
                            type: 'system',
                            content: `🎯 Ziel erreicht: ${description}`,
                            timestamp: new Date().toISOString(),
                        };
                        setMessages(prev => [...prev, achievementMessage]);
                    }
                }
            }

            // Show XP earned with breakdown
            if (data.xp_earned > 0) {
                // Build breakdown string
                let xpContent = `✨ +${data.xp_earned} XP`;

                if (data.xp_breakdown?.length > 0) {
                    const breakdownParts = data.xp_breakdown
                        .map((b: any) => `${b.reason}: ${b.amount > 0 ? '+' : ''}${b.amount}`)
                        .join(' | ');
                    xpContent = `✨ +${data.xp_earned} XP (${breakdownParts})`;
                }

                const xpMessage: Message = {
                    id: 'xp-' + Date.now(),
                    type: 'system',
                    content: xpContent,
                    timestamp: new Date().toISOString(),
                };
                setMessages(prev => [...prev, xpMessage]);
            }

            // Handle scene transition
            if (data.scene_transition) {
                const transitionMessage: Message = {
                    id: 'transition-' + Date.now(),
                    type: 'narration',
                    content: data.scene_transition.transition_narration || 'Die Geschichte entwickelt sich weiter...',
                    timestamp: new Date().toISOString(),
                };
                setMessages(prev => [...prev, transitionMessage]);

                // Store transition data to show Continue button
                setPendingTransition(data.scene_transition);
            }

            // Handle error feedback if there are language errors
            if (data.errors_detected?.length > 0) {
                // Show ALL errors, not just the first one
                data.errors_detected.forEach((error: any, index: number) => {
                    const errorExplanation = error.message || error.correction || 'Grammatikfehler erkannt';
                    const prefix = data.errors_detected.length > 1 ? `(${index + 1}/${data.errors_detected.length}) ` : '';

                    const errorMessage: Message = {
                        id: 'error-' + Date.now() + '-' + index,
                        type: 'system',
                        content: `💡 ${prefix}${errorExplanation} (Gespeichert für dein Lern-Deck)`,
                        timestamp: new Date().toISOString(),
                    };
                    setMessages(prev => [...prev, errorMessage]);
                });
            }

        } catch (error: any) {
            console.error('Story input error:', error);
            console.error('Error details:', {
                message: error?.message,
                status: error?.response?.status,
                data: error?.response?.data,
            });

            // Show error message to user if it's a specific error
            const errorDetail = error?.message || 'Ein Fehler ist aufgetreten';

            // Fallback response
            const fallbackResponse: Message = {
                id: 'npc-' + Date.now(),
                type: 'npc',
                content: activeNPC?.id === 'petit_prince'
                    ? "S'il te plaît... répète ça."
                    : `[Fehler: ${errorDetail}]`,
                npcId: activeNPC?.id,
                npcName: activeNPC?.name,
                timestamp: new Date().toISOString(),
            };
            setMessages(prev => [...prev, fallbackResponse]);
        } finally {
            setIsLoading(false);
        }
    };

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <Card className="border-4 border-black shadow-[8px_8px_0px_0px_#000] max-w-md">
                    <CardContent className="p-8 text-center">
                        <div className="text-6xl mb-4">😔</div>
                        <h2 className="text-2xl font-bold mb-2">Fehler</h2>
                        <p className="text-gray-600 mb-6">{error}</p>
                        <Link href="/stories">
                            <Button leftIcon={<ArrowLeft className="h-4 w-4" />}>
                                Zurück zu Stories
                            </Button>
                        </Link>
                    </CardContent>
                </Card>
            </div>
        );
    }

    if (!scene || !chapter) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-pulse text-xl font-bold">Lade Story...</div>
            </div>
        );
    }

    // Immersive fullscreen mode with AI visualizations
    if (isImmersiveMode) {
        return (
            <>
                <ImmersiveStoryView
                    storyId={storyId}
                    scene={scene}
                    chapter={chapter}
                    onSendMessage={async (msg: string) => {
                        // Pass message directly as choiceText to avoid async state race condition
                        await handleSendMessage(undefined, msg);
                    }}
                    isLoading={isLoading}
                    conversationHistory={messages
                        .filter(m => m.type === 'user' || m.type === 'npc')
                        .map(m => ({ role: m.type, content: m.content }))}
                />
                <button
                    onClick={() => setIsImmersiveMode(false)}
                    className="fixed bottom-4 left-4 z-50 p-3 bg-black/60 backdrop-blur-sm rounded-full text-white hover:bg-black/80"
                >
                    <Minimize2 className="w-5 h-5" />
                </button>
            </>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-gray-50 to-slate-100 flex flex-col">
            {/* Header */}
            <header className="bg-white border-b-4 border-black p-4 shadow-[0_4px_0px_0px_#000]">
                <div className="max-w-7xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Link href="/stories">
                            <Button variant="ghost" size="sm" leftIcon={<ArrowLeft className="h-4 w-4" />}>
                                Zurück
                            </Button>
                        </Link>
                        <div className="border-l-4 border-bauhaus-blue pl-4">
                            <p className="text-xs text-gray-500 font-bold uppercase tracking-wider">Kapitel {chapter.order_index + 1}</p>
                            <h1 className="text-xl font-black uppercase">{chapter.title}</h1>
                            {scene.location && (
                                <p className="text-sm text-gray-500 flex items-center gap-1">
                                    <Sparkles className="h-3 w-3" /> {scene.location}
                                </p>
                            )}
                        </div>
                    </div>

                    {/* Progress & Actions */}
                    <div className="flex items-center gap-4">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setIsImmersiveMode(true)}
                            leftIcon={<Maximize2 className="h-4 w-4" />}
                            className="border-2 border-black shadow-[2px_2px_0px_0px_#000] bg-gradient-to-r from-purple-500 to-indigo-600 text-white hover:from-purple-600 hover:to-indigo-700"
                        >
                            ✨ Immersive Mode
                        </Button>
                        <div className="text-right bg-gray-100 p-3 border-2 border-black shadow-[2px_2px_0px_0px_#000]">
                            <p className="text-xs font-bold text-gray-500 uppercase">Fortschritt</p>
                            <p className="text-2xl font-black text-bauhaus-blue">{progress?.completion_percentage || 0}%</p>
                            <div className="w-28 h-2 bg-gray-200 border border-black mt-1">
                                <div
                                    className="h-full bg-bauhaus-blue transition-all"
                                    style={{ width: `${progress?.completion_percentage || 0}%` }}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <div className="flex-1 flex max-w-7xl mx-auto w-full">
                {/* Chat Area */}
                <div className="flex-1 flex flex-col bg-white border-r-2 border-gray-200">
                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gradient-to-b from-indigo-50/30 to-white">
                        {messages.map((message) => (
                            <MessageBubble key={message.id} message={message} activeNPC={activeNPC} />
                        ))}

                        {isLoading && (
                            <div className="flex items-center gap-2 text-gray-500 p-4">
                                <div className="animate-bounce" style={{ animationDelay: '0ms' }}>●</div>
                                <div className="animate-bounce" style={{ animationDelay: '150ms' }}>●</div>
                                <div className="animate-bounce" style={{ animationDelay: '300ms' }}>●</div>
                            </div>
                        )}

                        <div ref={messagesEndRef} />
                    </div>

                    {/* Input Area */}
                    <div className="p-4 bg-white border-t-4 border-black">
                        {pendingTransition ? (
                            <button
                                onClick={() => window.location.reload()}
                                className="w-full p-4 bg-bauhaus-yellow border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] hover:translate-x-[-1px] hover:translate-y-[-1px] transition-all font-black text-xl active:shadow-none active:translate-x-[2px] active:translate-y-[2px] flex items-center justify-center gap-3"
                            >
                                <span>Weiter zur nächsten Szene</span>
                                <ArrowRight className="h-6 w-6" />
                            </button>
                        ) : scene.interaction_type === 'choice' && scene.choices && scene.choices.length > 0 ? (
                            <div className="flex flex-col gap-3">
                                {scene.choices.map((choice) => (
                                    <button
                                        key={choice.id}
                                        onClick={() => handleSendMessage(choice.id, choice.text)}
                                        disabled={isLoading}
                                        className="w-full text-left p-4 bg-white border-2 border-black shadow-[4px_4px_0px_0px_#000] hover:shadow-[6px_6px_0px_0px_#000] hover:translate-x-[-1px] hover:translate-y-[-1px] transition-all font-bold text-lg active:shadow-none active:translate-x-[2px] active:translate-y-[2px]"
                                    >
                                        {choice.text}
                                    </button>
                                ))}
                            </div>
                        ) : (
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={inputValue}
                                    onChange={(e) => setInputValue(e.target.value)}
                                    onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                                    placeholder="Schreibe deine Antwort auf Französisch..."
                                    className="flex-1 px-4 py-3 border-2 border-black shadow-[4px_4px_0px_0px_#000] focus:outline-none focus:shadow-[6px_6px_0px_0px_#000] transition-shadow"
                                    disabled={isLoading}
                                />
                                <Button
                                    onClick={() => handleSendMessage()}
                                    disabled={isLoading || !inputValue.trim()}
                                    className="shadow-[4px_4px_0px_0px_#000] border-2 border-black"
                                >
                                    <Send className="h-5 w-5" />
                                </Button>
                                <Button
                                    variant="outline"
                                    className="shadow-[4px_4px_0px_0px_#000] border-2 border-black"
                                >
                                    <Mic className="h-5 w-5" />
                                </Button>
                            </div>
                        )}
                    </div>
                </div>

                {/* Sidebar - NPC & Objectives */}
                <aside className="w-80 border-l-4 border-black bg-white p-4 hidden lg:block">
                    {/* Active NPC */}
                    {activeNPC && (
                        <div className="mb-6">
                            <NPCCard npc={activeNPC} />
                        </div>
                    )}

                    {/* Objectives */}
                    <div>
                        <h3 className="text-lg font-black uppercase mb-3 flex items-center gap-2">
                            <Star className="h-5 w-5 text-bauhaus-yellow" />
                            Ziele
                        </h3>
                        <div className="space-y-2">
                            {scene.objectives.map((obj) => (
                                <ObjectiveItem key={obj.id} objective={obj} />
                            ))}
                        </div>
                    </div>
                </aside>
            </div>
        </div>
    );
}

// Message type
interface Message {
    id: string;
    type: 'user' | 'npc' | 'narration' | 'system';
    content: string;
    npcId?: string;
    npcName?: string;
    timestamp: string;
    emotion?: string;
    infobox?: {
        title: string;
        content: string;
        type: string;
    };
}

function MessageBubble({ message, activeNPC }: { message: Message; activeNPC: NPCInScene | null }) {
    if (message.type === 'narration') {
        return (
            <div className="bg-gradient-to-r from-indigo-100 to-purple-100 border-2 border-indigo-300 p-4 rounded-lg italic text-gray-700 whitespace-pre-line">
                {message.content}
            </div>
        );
    }

    if (message.type === 'user') {
        return (
            <div className="flex justify-end">
                <div className="bg-bauhaus-blue text-white px-4 py-3 border-2 border-black shadow-[4px_4px_0px_0px_#000] max-w-[80%]">
                    {message.content}
                </div>
            </div>
        );
    }

    if (message.type === 'npc') {
        return (
            <div className="flex gap-3">
                {/* NPC Avatar */}
                <div className="w-10 h-10 bg-bauhaus-yellow border-2 border-black flex items-center justify-center flex-shrink-0 shadow-[2px_2px_0px_0px_#000]">
                    <span className="text-lg">👑</span>
                </div>
                <div className="flex-1">
                    <p className="text-xs font-bold text-gray-500 mb-1">{message.npcName}</p>
                    <div className="bg-white px-4 py-3 border-2 border-black shadow-[4px_4px_0px_0px_#000]">
                        {message.content}
                    </div>
                </div>
            </div>
        );


    }

    if (message.type === 'system') {
        return (
            <div className="flex justify-center my-2">
                <div className="bg-gray-100 border border-gray-300 text-gray-600 px-3 py-1 rounded-full text-xs font-medium flex items-center gap-2 shadow-sm">
                    {message.content}
                </div>
            </div>
        );
    }

    return null;
}

function NPCCard({ npc }: { npc: NPCInScene }) {
    // Relationship hearts
    const hearts = Array.from({ length: 10 }, (_, i) => i < npc.relationship_level);

    return (
        <Card className="border-2 border-black shadow-[4px_4px_0px_0px_#000]">
            <CardContent className="p-4">
                <div className="flex items-center gap-3 mb-3">
                    <div className="w-12 h-12 bg-bauhaus-yellow border-2 border-black flex items-center justify-center shadow-[2px_2px_0px_0px_#000]">
                        <span className="text-2xl">👑</span>
                    </div>
                    <div>
                        <h4 className="font-black">{npc.name}</h4>
                        {npc.role && (
                            <p className="text-xs text-gray-500">{npc.role}</p>
                        )}
                    </div>
                </div>

                {/* Relationship */}
                <div className="mb-3">
                    <p className="text-xs font-bold text-gray-500 mb-1">Beziehung</p>
                    <div className="flex gap-0.5">
                        {hearts.map((filled, i) => (
                            <Heart
                                key={i}
                                className={`h-4 w-4 ${filled ? 'text-red-500 fill-red-500' : 'text-gray-300'}`}
                            />
                        ))}
                    </div>
                </div>

                {/* Mood */}
                <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-gray-500">Stimmung:</span>
                    <span className="px-2 py-0.5 bg-gray-100 text-xs font-medium rounded">
                        {npc.mood === 'neutral' ? '😐' : npc.mood === 'happy' ? '😊' : '😔'} {npc.mood}
                    </span>
                </div>
            </CardContent>
        </Card>
    );
}

function ObjectiveItem({ objective }: { objective: Objective }) {
    return (
        <div className={`p-3 border-2 border-black ${objective.completed ? 'bg-green-100' : 'bg-white'} shadow-[2px_2px_0px_0px_#000]`}>
            <div className="flex items-start gap-2">
                <div className={`w-5 h-5 border-2 border-black flex items-center justify-center flex-shrink-0 ${objective.completed ? 'bg-green-500' : 'bg-white'}`}>
                    {objective.completed && <span className="text-white text-xs">✓</span>}
                </div>
                <div>
                    <p className={`text-sm font-medium ${objective.completed ? 'line-through text-gray-500' : ''}`}>
                        {objective.description}
                    </p>
                    {objective.optional && (
                        <span className="text-xs text-gray-400">Optional</span>
                    )}
                </div>
            </div>
        </div>
    );
}

export async function getServerSideProps(context: any) {
    const session = await getSession(context);
    const { id } = context.params;

    if (!session) {
        return {
            redirect: {
                destination: '/auth/signin',
                permanent: false,
            },
        };
    }

    try {
        const baseUrl = process.env.API_URL || 'http://localhost:8000';
        const headers = {
            'Authorization': `Bearer ${session.accessToken}`,
            'Content-Type': 'application/json',
        };

        // Start or resume the story
        const res = await fetch(`${baseUrl}/api/v1/stories/${id}/start`, {
            method: 'POST',
            headers,
        });

        if (!res.ok) {
            const errorData = await res.json().catch(() => ({}));
            return {
                props: {
                    storyData: null,
                    storyId: id,
                    error: errorData.detail || 'Story konnte nicht geladen werden.',
                }
            };
        }

        const storyData = await res.json();

        return {
            props: {
                storyData,
                storyId: id,
                error: null,
            },
        };
    } catch (error) {
        console.error('Failed to start story:', error);
        return {
            props: {
                storyData: null,
                storyId: id,
                error: 'Verbindungsfehler. Bitte versuche es später erneut.',
            },
        };
    }
}
