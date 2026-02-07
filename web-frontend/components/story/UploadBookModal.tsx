
import React, { useState } from 'react';
import { Upload, X, FileText, Check, AlertCircle, Loader2, Clock, BookOpen } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';

interface UploadBookModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

export default function UploadBookModal({ isOpen, onClose, onSuccess }: UploadBookModalProps) {
    const [file, setFile] = useState<File | null>(null);
    const [title, setTitle] = useState('');
    const [author, setAuthor] = useState('');
    const [levels, setLevels] = useState('A1,A2,B1');
    const [maxChapters, setMaxChapters] = useState(5);
    const [loading, setLoading] = useState(false);
    const [progressMessage, setProgressMessage] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    if (!isOpen) return null;

    // Estimate ~30 seconds per chapter for LLM processing
    const estimatedMinutes = Math.ceil((maxChapters * 30) / 60);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError(null);

            // Auto-fill title from filename if empty
            if (!title) {
                const name = e.target.files[0].name.replace(/\.[^/.]+$/, "");
                setTitle(name.split('-').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' '));
            }
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            setFile(e.dataTransfer.files[0]);
            setError(null);
            if (!title) {
                const name = e.dataTransfer.files[0].name.replace(/\.[^/.]+$/, "");
                setTitle(name.split('-').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' '));
            }
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file) {
            setError('Bitte wähle eine Datei aus.');
            return;
        }

        setLoading(true);
        setProgressMessage('Starte Upload...');
        setError(null);
        setSuccess(null);

        try {
            const formData = new FormData();
            formData.append('file', file);
            if (title) formData.append('title', title);
            if (author) formData.append('author', author);
            formData.append('target_levels', levels);
            formData.append('max_chapters', String(maxChapters));

            // Start upload
            const response = await fetch('/api/proxy/stories/upload-book', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || 'Upload failed');
            }

            const { task_id } = await response.json();

            // Poll for status
            let attempts = 0;
            const maxAttempts = 300; // 10 minutes timeout (2s * 300)

            const interval = setInterval(async () => {
                try {
                    attempts++;
                    const statusRes = await fetch(`/api/proxy/stories/upload-status/${task_id}`);

                    if (!statusRes.ok) throw new Error('Failed to check status');

                    const statusData = await statusRes.json();

                    if (statusData.status === 'completed') {
                        clearInterval(interval);
                        setSuccess(`Buch erfolgreich verarbeitet!`);
                        setLoading(false);
                        setProgressMessage('');
                        setTimeout(() => {
                            onSuccess();
                            onClose();
                        }, 1500);
                    } else if (statusData.status === 'failed') {
                        clearInterval(interval);
                        setLoading(false);
                        setProgressMessage('');
                        setError(statusData.error || 'Verarbeitung fehlgeschlagen');
                    } else {
                        // processing
                        setProgressMessage(`${statusData.message} (${statusData.progress}%)`);
                    }

                    if (attempts >= maxAttempts) {
                        clearInterval(interval);
                        setLoading(false);
                        setError('Zeitüberschreitung bei der Verarbeitung.');
                    }
                } catch (err) {
                    // Ignore transient errors but stop on fatal
                    console.error(err);
                }
            }, 2000);

        } catch (err: any) {
            console.error(err);
            setLoading(false);
            setError(err.message || 'Ein Fehler ist aufgetreten.');
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <Card className="w-full max-w-lg border-4 border-black shadow-[8px_8px_0px_0px_#000] bg-white max-h-[90vh] overflow-y-auto">
                <div className="flex justify-between items-center p-6 border-b-2 border-gray-100">
                    <h2 className="text-2xl font-black uppercase">Buch hochladen</h2>
                    <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full">
                        <X className="h-6 w-6" />
                    </button>
                </div>

                <form onSubmit={handleSubmit} className="p-6 space-y-6">
                    {/* File Drop Zone */}
                    <div
                        className={`border-4 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${file ? 'border-bauhaus-blue bg-blue-50' : 'border-gray-300 hover:border-gray-400'}`}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                        onClick={() => document.getElementById('file-upload')?.click()}
                    >
                        <input
                            id="file-upload"
                            type="file"
                            accept=".txt,.pdf,.epub,.html,.htm"
                            className="hidden"
                            onChange={handleFileChange}
                        />

                        {file ? (
                            <div className="flex flex-col items-center">
                                <FileText className="h-12 w-12 text-bauhaus-blue mb-2" />
                                <p className="font-bold text-lg">{file.name}</p>
                                <p className="text-sm text-gray-500">
                                    {(file.size / 1024 / 1024).toFixed(2)} MB
                                </p>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center">
                                <Upload className="h-12 w-12 text-gray-400 mb-2" />
                                <p className="font-bold text-lg">Datei hier ablegen</p>
                                <p className="text-sm text-gray-500">oder klicken zum Auswählen</p>
                                <p className="text-xs text-gray-400 mt-2">TXT, PDF, EPUB, HTML (max 10MB)</p>
                            </div>
                        )}
                    </div>

                    <div className="space-y-4">
                        <div>
                            <label className="block font-bold mb-1">Titel (Optional)</label>
                            <input
                                type="text"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                className="w-full p-3 border-2 border-black font-medium focus:ring-2 focus:ring-bauhaus-yellow outline-none"
                                placeholder="z.B. Moby Dick"
                            />
                        </div>

                        <div>
                            <label className="block font-bold mb-1">Autor (Optional)</label>
                            <input
                                type="text"
                                value={author}
                                onChange={(e) => setAuthor(e.target.value)}
                                className="w-full p-3 border-2 border-black font-medium focus:ring-2 focus:ring-bauhaus-yellow outline-none"
                                placeholder="z.B. Herman Melville"
                            />
                        </div>

                        <div>
                            <label className="block font-bold mb-1">Ziel-Niveaus</label>
                            <input
                                type="text"
                                value={levels}
                                onChange={(e) => setLevels(e.target.value)}
                                className="w-full p-3 border-2 border-black font-medium focus:ring-2 focus:ring-bauhaus-yellow outline-none"
                                placeholder="z.B. A1,A2,B1"
                            />
                            <p className="text-xs text-gray-500 mt-1">Kommagetrennt (A1, A2, B1, B2, C1, C2)</p>
                        </div>

                        {/* Chapter Limit Slider */}
                        <div className="p-4 bg-gray-50 border-2 border-gray-200 rounded-lg">
                            <div className="flex items-center justify-between mb-2">
                                <label className="font-bold flex items-center gap-2">
                                    <BookOpen className="h-4 w-4" />
                                    Kapitelanzahl
                                </label>
                                <span className="text-lg font-black text-bauhaus-blue">{maxChapters}</span>
                            </div>
                            <input
                                type="range"
                                min="1"
                                max="20"
                                value={maxChapters}
                                onChange={(e) => setMaxChapters(Number(e.target.value))}
                                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-bauhaus-blue"
                            />
                            <div className="flex justify-between text-xs text-gray-500 mt-1">
                                <span>1</span>
                                <span>20</span>
                            </div>

                            {/* Estimated Time */}
                            <div className="mt-3 flex items-center gap-2 text-sm text-gray-600">
                                <Clock className="h-4 w-4" />
                                <span>Geschätzte Zeit: <strong>~{estimatedMinutes} Min.</strong></span>
                            </div>
                            <p className="text-xs text-gray-400 mt-1">
                                Du kannst später weitere Kapitel hinzufügen.
                            </p>
                        </div>
                    </div>

                    {error && (
                        <div className="p-4 bg-red-50 border-2 border-red-500 flex items-center gap-2 text-red-700 font-bold">
                            <AlertCircle className="h-5 w-5" />
                            {error}
                        </div>
                    )}

                    {success && (
                        <div className="p-4 bg-green-50 border-2 border-green-500 flex items-center gap-2 text-green-700 font-bold">
                            <Check className="h-5 w-5" />
                            {success}
                        </div>
                    )}

                    <div className="flex justify-end gap-3 pt-2">
                        <Button
                            type="button"
                            variant="ghost"
                            onClick={onClose}
                            className="font-bold"
                            disabled={loading}
                        >
                            Abbrechen
                        </Button>
                        <Button
                            type="submit"
                            className="font-bold shadow-[4px_4px_0px_0px_#000] border-2 border-black bg-bauhaus-yellow text-black hover:translate-y-[-2px] hover:shadow-[6px_6px_0px_0px_#000]"
                            disabled={loading || !file}
                            leftIcon={loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                        >
                            {loading ? (progressMessage || 'Wird hochgeladen...') : 'Buch hochladen'}
                        </Button>
                    </div>
                </form>
            </Card>
        </div>
    );
}
