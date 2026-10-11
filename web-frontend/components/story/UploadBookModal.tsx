/* Importing a book into the Bibliothèque, on the Claude design (Atelier V2).
 *
 * The upload contract is untouched: one multipart POST to `/stories/upload-book`,
 * then a poll of `/stories/upload-status/{task_id}` until the server says the
 * book is cut into episodes. What changed is the chrome — the design's bottom
 * sheet, its fields and its one 3D press — and the copy, which follows the one
 * language rule (`bibliotheque-copy.ts`): the learner's language up to A2,
 * French from B1.
 */

import React, { useState } from 'react';

import { Action, BottomSheet, ProgressRule } from '@/components/atelier-v2/ui';
import { bibliothequeCopy, fill } from '@/components/stories/bibliotheque-copy';
import { getAppAccessToken } from '@/lib/app-auth';
import { useChromeLanguage } from '@/lib/learner-language';
import { resolveBrowserApiBaseUrl } from '@/services/api';

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
    const [loading, setLoading] = useState(false);
    const [progressMessage, setProgressMessage] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const language = useChromeLanguage();
    const t = bibliothequeCopy(language);

    if (!isOpen) return null;

    const titleFromFileName = (name: string) =>
        name
            .replace(/\.[^/.]+$/, '')
            .split('-')
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(' ');

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError(null);

            // Auto-fill title from filename if empty
            if (!title) setTitle(titleFromFileName(e.target.files[0].name));
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
            if (!title) setTitle(titleFromFileName(e.dataTransfer.files[0].name));
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file) {
            setError(t.choose_file_first);
            return;
        }

        setLoading(true);
        setProgressMessage(t.sending);
        setError(null);
        setSuccess(null);

        try {
            const formData = new FormData();
            formData.append('file', file);
            if (title) formData.append('title', title);
            if (author) formData.append('author', author);
            formData.append('target_levels', levels);
            formData.append('max_chapters', '0');

            const token = await getAppAccessToken();
            const authHeaders = token ? { Authorization: `Bearer ${token}` } : undefined;

            // Start upload
            const response = await fetch(`${resolveBrowserApiBaseUrl()}/stories/upload-book`, {
                method: 'POST',
                headers: authHeaders,
                body: formData,
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.detail || t.generic_error);
            }

            const { task_id } = await response.json();

            // Poll for status
            let attempts = 0;
            const maxAttempts = 300; // 10 minutes timeout (2s * 300)

            const interval = setInterval(async () => {
                try {
                    attempts++;
                    const statusRes = await fetch(`${resolveBrowserApiBaseUrl()}/stories/upload-status/${task_id}`, {
                        headers: authHeaders,
                    });

                    if (!statusRes.ok) throw new Error('Failed to check status');

                    const statusData = await statusRes.json();

                    if (statusData.status === 'completed') {
                        clearInterval(interval);
                        setSuccess(t.upload_done);
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
                        setError(statusData.error || t.upload_failed);
                    } else {
                        // processing
                        setProgressMessage(`${statusData.message} (${statusData.progress} %)`);
                    }

                    if (attempts >= maxAttempts) {
                        clearInterval(interval);
                        setLoading(false);
                        setError(t.upload_too_long);
                    }
                } catch (err) {
                    // Ignore transient errors but stop on fatal
                    console.error(err);
                }
            }, 2000);

        } catch (err: any) {
            console.error(err);
            setLoading(false);
            setError(err.message || t.generic_error);
        }
    };

    return (
        <BottomSheet
            open={isOpen}
            onClose={onClose}
            eyebrow="La bibliothèque"
            title={t.import_book}
            dismissible={!loading}
        >
            <form className="bib-upload" onSubmit={handleSubmit}>
                <button
                    type="button"
                    className="bib-upload__drop"
                    data-filled={file ? 'true' : undefined}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    onClick={() => document.getElementById('file-upload')?.click()}
                >
                    <input
                        id="file-upload"
                        type="file"
                        accept=".txt,.pdf,.epub,.html,.htm"
                        className="bib-upload__input"
                        onChange={handleFileChange}
                    />
                    {file ? (
                        <>
                            <span className="av2-headline av2-headline--rule">{file.name}</span>
                            <span className="av2-label">{fill(t.file_size, { size: (file.size / 1024 / 1024).toFixed(2) })}</span>
                        </>
                    ) : (
                        <>
                            <span className="av2-headline av2-headline--rule">{t.drop_here}</span>
                            <span className="av2-label">{t.drop_hint}</span>
                        </>
                    )}
                </button>

                <label className="av2-field">
                    <span className="av2-field__label">{t.title_label}</span>
                    <input
                        className="av2-field__control"
                        type="text"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder={t.title_placeholder}
                    />
                </label>

                <label className="av2-field">
                    <span className="av2-field__label">{t.author_label}</span>
                    <input
                        className="av2-field__control"
                        type="text"
                        value={author}
                        onChange={(e) => setAuthor(e.target.value)}
                        placeholder={t.author_placeholder}
                    />
                </label>

                <label className="av2-field">
                    <span className="av2-field__label">{t.levels_label}</span>
                    <input
                        className="av2-field__control"
                        type="text"
                        value={levels}
                        onChange={(e) => setLevels(e.target.value)}
                        placeholder={t.levels_placeholder}
                    />
                    <span className="av2-label">{t.levels_hint}</span>
                </label>

                <p className="av2-label">{t.whole_book}</p>

                {loading && progressMessage && (
                    <div aria-live="polite">
                        <p className="av2-label">{progressMessage}</p>
                        <ProgressRule value={0} max={0} label={t.processing} />
                    </div>
                )}

                {error && (
                    <p className="av2-label av2-label--action" role="alert">
                        {error}
                    </p>
                )}

                {success && (
                    <p className="av2-label" role="status">
                        {success}
                    </p>
                )}

                <div className="bib-upload__actions">
                    {/* the one tactile 3D press of this sheet */}
                    <Action
                        type="submit"
                        tone="primary"
                        disabled={!file}
                        pending={loading}
                        pendingLabel={progressMessage || t.sending}
                    >
                        {t.import_the_book}
                    </Action>
                    <Action tone="quiet" onClick={onClose} disabled={loading}>
                        {t.cancel}
                    </Action>
                </div>
            </form>

            <style jsx global>{`
                .av2 .bib-upload { display: flex; flex-direction: column; gap: 12px; margin-top: 4px; }
                .av2 .bib-upload__drop {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 4px;
                    text-align: center;
                    padding: 22px 16px;
                    border: 2px dashed var(--av2-line-2);
                    border-radius: var(--av2-r-card);
                    background: var(--av2-card);
                    cursor: pointer;
                }
                .av2 .bib-upload__drop[data-filled='true'] { border-style: solid; border-color: var(--av2-blue); }
                .av2 .bib-upload__input { display: none; }
                .av2 .bib-upload__actions { display: flex; flex-direction: column; gap: 8px; }
            `}</style>
        </BottomSheet>
    );
}
