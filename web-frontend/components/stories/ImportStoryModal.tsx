
import React, { useState } from 'react';
import { useRouter } from 'next/router';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Link as LinkIcon, Youtube, FileText, Loader2, Sparkles } from 'lucide-react';
import apiService from '@/services/api';
import { Button } from '@/components/ui/Button';

interface ImportStoryModalProps {
    onClose: () => void;
}

export function ImportStoryModal({ onClose }: ImportStoryModalProps) {
    const router = useRouter();
    const [url, setUrl] = useState('');
    const [status, setStatus] = useState<'idle' | 'importing' | 'success' | 'error'>('idle');
    const [errorMsg, setErrorMsg] = useState('');

    const handleImport = async () => {
        if (!url) return;

        setStatus('importing');
        setErrorMsg('');

        try {
            const result = await apiService.importContent(url);

            // Create a discussion session for the imported content
            const discussion = await apiService.startStoryDiscussion(result.story_id);

            setStatus('success');
            // Delay to show success animation
            setTimeout(() => {
                router.push(`/learn/session/${discussion.session_id}`);
            }, 1000);
        } catch (err: any) {
            console.error(err);
            setStatus('error');
            setErrorMsg(err.response?.data?.detail || 'Failed to import content. Please check the URL.');
        }
    };

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
            onClick={onClose}
        >
            <motion.div
                initial={{ scale: 0.9, y: 20 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.9, y: 20 }}
                onClick={(e) => e.stopPropagation()}
                className="relative w-full max-w-lg overflow-hidden bg-gray-900 border border-purple-500/30 rounded-2xl shadow-2xl"
            >
                {/* Background Gradients */}
                <div className="absolute top-0 right-0 w-64 h-64 bg-purple-600/20 rounded-full blur-[100px] pointer-events-none" />
                <div className="absolute bottom-0 left-0 w-64 h-64 bg-blue-600/20 rounded-full blur-[100px] pointer-events-none" />

                <div className="p-6">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                            <Sparkles className="text-yellow-400" />
                            Import Content
                        </h2>
                        <button
                            onClick={onClose}
                            className="p-2 text-gray-400 hover:text-white transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    <div className="mb-6 space-y-4">
                        <p className="text-gray-300">
                            Paste a URL to create an interactive lesson instantly.
                        </p>

                        <div className="flex gap-4 text-sm text-gray-400 mb-4">
                            <div className="flex items-center gap-2">
                                <Youtube className="w-4 h-4 text-red-400" />
                                <span>YouTube Videos</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <FileText className="w-4 h-4 text-blue-400" />
                                <span>Web Articles</span>
                            </div>
                        </div>

                        <div className="relative">
                            <LinkIcon className="absolute left-3 top-3.5 w-5 h-5 text-gray-500" />
                            <input
                                type="url"
                                placeholder="https://youtube.com/... or https://lemonde.fr/..."
                                value={url}
                                onChange={(e) => setUrl(e.target.value)}
                                disabled={status === 'importing'}
                                className="w-full pl-10 pr-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all"
                            />
                        </div>

                        {status === 'error' && (
                            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-300 text-sm">
                                {errorMsg}
                            </div>
                        )}
                    </div>

                    <div className="flex justify-end gap-3">
                        <Button variant="ghost" onClick={onClose} disabled={status === 'importing'}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleImport}
                            disabled={!url || status === 'importing'}
                            className="bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white min-w-[120px]"
                        >
                            {status === 'importing' ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Analyzing...
                                </>
                            ) : status === 'success' ? (
                                'Success!'
                            ) : (
                                'Generate Lesson'
                            )}
                        </Button>
                    </div>
                </div>

                {/* Progress Bar for Importing */}
                {status === 'importing' && (
                    <div className="absolute bottom-0 left-0 h-1 bg-gradient-to-r from-purple-500 to-pink-500 animate-pulse w-full" />
                )}
            </motion.div>
        </motion.div>
    );
}
