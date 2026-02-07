import React, { useState, useEffect, useCallback } from 'react';
import {
    ChevronLeft,
    ChevronRight,
    Maximize2,
    Minimize2,
    Volume2,
    VolumeX,
    MessageCircle,
    BookOpen,
    Sparkles,
    Loader2
} from 'lucide-react';

interface Scene {
    id: string;
    chapter_id: string;
    location?: string | null;
    atmosphere?: string | null;
    narration: string;
    objectives: Array<{ id: string; description: string; type: string }>;
    npcs_present: Array<{
        id: string;
        name: string;
        display_name?: string | null;
        mood?: string | null;
    }>;
}

interface Chapter {
    id: string;
    title: string;
    order_index: number;
}

interface ImmersiveStoryViewProps {
    storyId: string;
    scene: Scene;
    chapter: Chapter;
    onSendMessage: (message: string) => void;
    onNextScene?: () => void;
    onPreviousScene?: () => void;
    isLoading?: boolean;
    conversationHistory?: Array<{ role: string; content: string }>;
}

export default function ImmersiveStoryView({
    storyId,
    scene,
    chapter,
    onSendMessage,
    onNextScene,
    onPreviousScene,
    isLoading,
    conversationHistory = [],
}: ImmersiveStoryViewProps) {
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [imageUrl, setImageUrl] = useState<string | null>(null);
    const [imageLoading, setImageLoading] = useState(true);
    const [showNarration, setShowNarration] = useState(true);
    const [inputValue, setInputValue] = useState('');
    const [artStyle, setArtStyle] = useState<string>('auto');

    // Fetch scene visualization
    useEffect(() => {
        const fetchVisualization = async () => {
            setImageLoading(true);
            try {
                const styleParam = artStyle !== 'auto' ? `&style=${artStyle}` : '';
                // Use proxy route to reach backend
                const response = await fetch(
                    `/api/proxy/stories/${storyId}/scene/${scene.id}/visualization?${styleParam}`,
                    { credentials: 'include' }
                );

                if (response.ok) {
                    const data = await response.json();
                    setImageUrl(data.image_url);
                }
            } catch (error) {
                console.error('Failed to fetch visualization:', error);
            } finally {
                setImageLoading(false);
            }
        };

        if (scene?.id) {
            fetchVisualization();
        }
    }, [storyId, scene?.id, artStyle]);

    // Handle fullscreen toggle
    const toggleFullscreen = useCallback(() => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            setIsFullscreen(true);
        } else {
            document.exitFullscreen();
            setIsFullscreen(false);
        }
    }, []);

    // Handle message send
    const handleSend = () => {
        if (inputValue.trim()) {
            onSendMessage(inputValue.trim());
            setInputValue('');
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className={`relative w-full h-screen bg-black overflow-hidden ${isFullscreen ? 'fixed inset-0 z-50' : ''}`}>
            {/* Background Image */}
            <div className="absolute inset-0">
                {imageLoading ? (
                    <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-black">
                        <div className="text-center text-white">
                            <Loader2 className="w-12 h-12 animate-spin mx-auto mb-4 text-purple-400" />
                            <p className="text-lg font-medium">Generating scene visualization...</p>
                            <p className="text-sm text-gray-400 mt-2">Powered by AI</p>
                        </div>
                    </div>
                ) : imageUrl ? (
                    <img
                        src={imageUrl}
                        alt={`Scene: ${scene.location || 'Story scene'}`}
                        className="w-full h-full object-cover"
                    />
                ) : (
                    <div className="w-full h-full bg-gradient-to-br from-slate-800 via-slate-900 to-black" />
                )}

                {/* Gradient overlays for text readability */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/40" />
                <div className="absolute inset-0 bg-gradient-to-r from-black/50 via-transparent to-transparent" />
            </div>

            {/* Top Bar */}
            <div className="absolute top-0 left-0 right-0 p-4 flex items-center justify-between z-10">
                <div className="flex items-center gap-3">
                    <button
                        onClick={onPreviousScene}
                        disabled={!onPreviousScene}
                        className="p-2 bg-black/40 backdrop-blur-sm rounded-full text-white hover:bg-black/60 transition-colors disabled:opacity-30"
                    >
                        <ChevronLeft className="w-5 h-5" />
                    </button>

                    <div className="bg-black/40 backdrop-blur-sm rounded-lg px-4 py-2">
                        <p className="text-white/70 text-xs uppercase tracking-wider">
                            Chapter {chapter.order_index + 1}
                        </p>
                        <p className="text-white font-bold">{chapter.title}</p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Art Style Selector */}
                    <select
                        value={artStyle}
                        onChange={(e) => setArtStyle(e.target.value)}
                        className="p-2 bg-black/40 backdrop-blur-sm rounded-lg text-white text-sm border-0 cursor-pointer"
                    >
                        <option value="auto">Auto Style</option>
                        <option value="whimsical">Whimsical</option>
                        <option value="dramatic">Dramatic</option>
                        <option value="classic">Classic</option>
                        <option value="fantasy">Fantasy</option>
                        <option value="minimal">Minimal</option>
                    </select>

                    <button
                        onClick={() => setShowNarration(!showNarration)}
                        className="p-2 bg-black/40 backdrop-blur-sm rounded-full text-white hover:bg-black/60"
                    >
                        <BookOpen className="w-5 h-5" />
                    </button>

                    <button
                        onClick={toggleFullscreen}
                        className="p-2 bg-black/40 backdrop-blur-sm rounded-full text-white hover:bg-black/60"
                    >
                        {isFullscreen ? <Minimize2 className="w-5 h-5" /> : <Maximize2 className="w-5 h-5" />}
                    </button>

                    <button
                        onClick={onNextScene}
                        disabled={!onNextScene}
                        className="p-2 bg-black/40 backdrop-blur-sm rounded-full text-white hover:bg-black/60 disabled:opacity-30"
                    >
                        <ChevronRight className="w-5 h-5" />
                    </button>
                </div>
            </div>

            {/* Main Content Area */}
            <div className="absolute inset-0 flex">
                {/* Left: Narration Panel */}
                {showNarration && (
                    <div className="w-1/3 min-w-[300px] max-w-[400px] h-full flex flex-col p-6 pt-20">
                        {/* Location Badge */}
                        {scene.location && (
                            <div className="flex items-center gap-2 mb-4">
                                <Sparkles className="w-4 h-4 text-amber-400" />
                                <span className="text-amber-300 text-sm font-medium">{scene.location}</span>
                            </div>
                        )}

                        {/* Narration Text */}
                        <div className="bg-black/60 backdrop-blur-md rounded-2xl p-6 border border-white/10 flex-1 overflow-y-auto">
                            <p className="text-white text-lg leading-relaxed font-serif">
                                {scene.narration}
                            </p>

                            {/* NPCs Present */}
                            {scene.npcs_present.length > 0 && (
                                <div className="mt-6 pt-4 border-t border-white/20">
                                    <p className="text-white/60 text-xs uppercase tracking-wider mb-3">
                                        Characters Present
                                    </p>
                                    <div className="flex flex-wrap gap-2">
                                        {scene.npcs_present.map((npc) => (
                                            <span
                                                key={npc.id}
                                                className="px-3 py-1 bg-white/10 rounded-full text-white text-sm"
                                            >
                                                {npc.display_name || npc.name}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Objectives */}
                            {scene.objectives.length > 0 && (
                                <div className="mt-6 pt-4 border-t border-white/20">
                                    <p className="text-white/60 text-xs uppercase tracking-wider mb-3">
                                        Objectives
                                    </p>
                                    <ul className="space-y-2">
                                        {scene.objectives.map((obj) => (
                                            <li key={obj.id} className="flex items-start gap-2 text-white/80 text-sm">
                                                <span className="w-2 h-2 bg-amber-400 rounded-full mt-1.5 flex-shrink-0" />
                                                {obj.description}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Right: Conversation Area */}
                <div className="flex-1 flex flex-col justify-end p-6">
                    {/* Conversation History */}
                    <div className="flex-1 overflow-y-auto mb-4 space-y-4 max-h-[40vh]">
                        {conversationHistory.map((msg, idx) => (
                            <div
                                key={idx}
                                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                            >
                                <div
                                    className={`max-w-[80%] px-4 py-3 rounded-2xl ${msg.role === 'user'
                                        ? 'bg-indigo-600 text-white rounded-br-sm'
                                        : 'bg-white/10 backdrop-blur-md text-white rounded-bl-sm border border-white/20'
                                        }`}
                                >
                                    <p className="text-sm leading-relaxed">{msg.content}</p>
                                </div>
                            </div>
                        ))}

                        {isLoading && (
                            <div className="flex justify-start">
                                <div className="bg-white/10 backdrop-blur-md px-4 py-3 rounded-2xl rounded-bl-sm border border-white/20">
                                    <div className="flex items-center gap-2 text-white/60">
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        <span className="text-sm">Thinking...</span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Input Area */}
                    <div className="relative">
                        <div className="absolute inset-0 bg-black/40 backdrop-blur-md rounded-2xl border border-white/20" />
                        <div className="relative flex items-center gap-3 p-3">
                            <input
                                type="text"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyPress={handleKeyPress}
                                placeholder="Speak to the characters in French..."
                                className="flex-1 bg-transparent text-white placeholder-white/40 text-lg px-4 py-2 outline-none"
                                disabled={isLoading}
                            />
                            <button
                                onClick={handleSend}
                                disabled={!inputValue.trim() || isLoading}
                                className="p-3 bg-indigo-600 rounded-xl text-white hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <MessageCircle className="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
