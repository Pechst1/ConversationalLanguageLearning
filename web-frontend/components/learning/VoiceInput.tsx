import React, { useState, useRef } from 'react';
import { Mic, Square, Loader2 } from 'lucide-react';

interface VoiceInputProps {
    onTranscript: (text: string) => void;
    disabled?: boolean;
}

export default function VoiceInput({ onTranscript, disabled }: VoiceInputProps) {
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            chunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunksRef.current.push(e.data);
                }
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
                await processAudio(audioBlob);

                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            setIsRecording(true);
        } catch (err) {
            console.error("Error accessing microphone:", err);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    const processAudio = async (blob: Blob) => {
        setIsProcessing(true);
        try {
            const formData = new FormData();
            formData.append('file', blob, 'recording.webm');

            // Get session from NextAuth for authentication
            const { getSession } = await import('next-auth/react');
            const session = await getSession();
            const token = (session as any)?.accessToken;

            const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
            const response = await fetch(`${baseUrl}/audio/transcribe`, {
                method: 'POST',
                headers: token ? {
                    'Authorization': `Bearer ${token}`,
                } : {},
                body: formData,
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Transcription response error:', response.status, errorText);
                throw new Error('Transcription failed');
            }

            const data = await response.json();
            if (data.text) {
                onTranscript(data.text);
            }
        } catch (err) {
            console.error("Transcription error:", err);
        } finally {
            setIsProcessing(false);
        }
    };


    const toggleRecording = () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    };

    return (
        <button
            type="button"
            onClick={toggleRecording}
            disabled={disabled || isProcessing}
            className={`inline-flex h-11 w-11 items-center justify-center rounded-full border transition-colors ${
                isRecording
                    ? 'animate-pulse border-rose-300 bg-rose-50 text-rose-700'
                    : 'border-stone-200 bg-white text-stone-600 hover:border-stone-300 hover:bg-stone-50'
            } disabled:cursor-not-allowed disabled:opacity-50`}
            title={isRecording ? "Stop recording" : "Start voice input"}
        >
            {isProcessing ? (
                <Loader2 className="h-5 w-5 animate-spin" />
            ) : isRecording ? (
                <Square className="h-5 w-5" />
            ) : (
                <Mic className="h-5 w-5" />
            )}
        </button>
    );
}
