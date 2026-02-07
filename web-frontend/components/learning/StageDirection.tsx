import React from 'react';
import { Film } from 'lucide-react';

interface StageDirectionProps {
    content: string;
    className?: string;
}

/**
 * Displays scene/stage directions in a distinct styled box
 * Used to separate situational context from spoken dialogue
 * 
 * Example input: "The baker smiles and points to the fresh croissants"
 */
export default function StageDirection({ content, className }: StageDirectionProps) {
    if (!content.trim()) return null;

    return (
        <div
            className={`
        flex items-start gap-2 px-3 py-2 
        bg-slate-100 border-l-4 border-slate-400 
        rounded-r-lg mb-2
        text-sm text-slate-600 italic
        ${className || ''}
      `}
        >
            <Film className="h-4 w-4 mt-0.5 flex-shrink-0 text-slate-400" />
            <span>{content}</span>
        </div>
    );
}

/**
 * Utility to parse message content and extract [SCENE: ...] blocks
 * Returns { sceneContent: string | null, dialogueContent: string }
 */
export function parseMessageContent(content: string): {
    sceneContent: string | null;
    dialogueContent: string;
} {
    const sceneMatch = content.match(/\[SCENE:\s*([^\]]+)\]/i);

    if (sceneMatch) {
        const sceneContent = sceneMatch[1].trim();
        const dialogueContent = content.replace(sceneMatch[0], '').trim();
        return { sceneContent, dialogueContent };
    }

    return { sceneContent: null, dialogueContent: content };
}
