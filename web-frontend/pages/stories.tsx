import React from 'react';
import { getSession } from 'next-auth/react';
import Image from 'next/image';
import Link from 'next/link';
import { BookOpen, Clock, Lock, Play, ChevronRight, Upload } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import EditorialMasthead from '@/components/layout/EditorialMasthead';

interface Story {
    id: string;
    title: string;
    subtitle: string | null;
    source_book: string | null;
    source_author: string | null;
    target_levels: string[];
    themes: string[];
    estimated_duration_minutes: number;
    cover_image_url: string | null;
    is_unlocked: boolean;
    progress: {
        current_chapter_title: string | null;
        completion_percentage: number;
        status: string;
        last_played_at: string | null;
    } | null;
}

interface StoriesPageProps {
    stories: Story[];
}

import { useState } from 'react';
import { useRouter } from 'next/router';
import UploadBookModal from '@/components/story/UploadBookModal';

export default function StoriesPage({ stories }: StoriesPageProps) {
    const router = useRouter();
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

    const handleUploadSuccess = () => {
        router.replace(router.asPath); // Refresh props
    };

    return (
        <div className="min-h-screen bg-[var(--app-paper)] text-[var(--app-ink)]">
            <EditorialMasthead />
            <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8 space-y-8">
                {/* Header */}
                <header className="border-b border-black pb-6">
                    <div className="text-xs font-mono font-black uppercase tracking-widest text-[var(--app-ink-3)]">
                        LITERARY EXPERIENCE
                    </div>
                    <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mt-2">
                        <div>
                            <h1 className="font-serif text-5xl italic text-black leading-none">
                                Story Adventures
                            </h1>
                            <p className="text-[var(--app-ink-2)] font-medium mt-3">
                                Learn French through immersive interactive stories.
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            <Button
                                onClick={() => setIsUploadModalOpen(true)}
                                variant="outline"
                                className="font-bold border-2 border-black rounded-none shadow-[4px_4px_0px_0px_#000] bg-white text-black hover:bg-stone-50 hover:-translate-y-0.5 transition-all"
                                leftIcon={<Upload className="h-4 w-4" />}
                            >
                                Upload Book
                            </Button>
                            <div className="flex items-center gap-2 px-4 py-2 bg-bauhaus-yellow border-2 border-black rounded-none shadow-[4px_4px_0px_0px_#000] text-black">
                                <BookOpen className="h-5 w-5" />
                                <span className="font-bold">{stories.length} Stories</span>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Featured Story */}
                {stories.length > 0 && (
                    <div className="relative">
                        <FeaturedStoryCard story={stories[0]} />
                    </div>
                )}

                {/* All Stories Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {stories.map((story) => (
                        <StoryCard key={story.id} story={story} />
                    ))}
                </div>

                {/* Empty State */}
                {stories.length === 0 && (
                    <Card className="border-4 border-black rounded-none shadow-[8px_8px_0px_0px_#000] bg-[var(--app-sheet)]">
                        <CardContent className="p-12 text-center">
                            <BookOpen className="h-16 w-16 mx-auto mb-4 text-stone-450" />
                            <h3 className="text-2xl font-bold mb-2">No Stories Available</h3>
                            <p className="text-[var(--app-ink-2)]">
                                Story content will be available soon.
                            </p>
                            <Button
                                onClick={() => setIsUploadModalOpen(true)}
                                variant="outline"
                                className="mt-4 font-bold border-2 border-black rounded-none shadow-[4px_4px_0px_0px_#000] text-black bg-white hover:bg-stone-50"
                            >
                                Upload First Book
                            </Button>
                        </CardContent>
                    </Card>
                )}

                <UploadBookModal
                    isOpen={isUploadModalOpen}
                    onClose={() => setIsUploadModalOpen(false)}
                    onSuccess={handleUploadSuccess}
                />
            </div>
        </div>
    );
}

function FeaturedStoryCard({ story }: { story: Story }) {
    const hasProgress = story.progress && story.progress.status !== 'not_started';

    return (
        <Card className="border-4 border-black rounded-none shadow-[8px_8px_0px_0px_#000] overflow-hidden bg-[var(--app-sheet)]">
            <div className="grid grid-cols-1 lg:grid-cols-2">
                {/* Left: Cover Image or Placeholder */}
                <div className="bg-gradient-to-br from-bauhaus-blue via-indigo-650 to-purple-800 p-8 flex items-center justify-center min-h-[300px]">
                    {story.cover_image_url ? (
                        <div className="relative h-[280px] w-full max-w-[220px] border-2 border-black shadow-[4px_4px_0px_0px_#000] bg-black/10">
                            <Image
                                src={story.cover_image_url}
                                alt={story.title}
                                fill
                                unoptimized
                                sizes="(max-width: 1024px) 70vw, 220px"
                                className="object-contain"
                            />
                        </div>
                    ) : (
                        <div className="text-center text-white">
                            <div className="text-8xl mb-4">🌹</div>
                            <p className="text-lg font-bold opacity-80">{story.source_book}</p>
                        </div>
                    )}
                </div>

                {/* Right: Details */}
                <div className="p-8 flex flex-col justify-between text-black">
                    <div>
                        {/* Badges */}
                        <div className="flex flex-wrap gap-2 mb-4">
                            {story.target_levels.map((level) => (
                                <span
                                    key={level}
                                    className="px-3 py-1 bg-bauhaus-yellow border-2 border-black font-bold text-sm rounded-none shadow-[2px_2px_0px_0px_#000]"
                                >
                                    {level}
                                </span>
                            ))}
                            <span className="px-3 py-1 bg-white border-2 border-black font-bold text-sm rounded-none shadow-[2px_2px_0px_0px_#000] flex items-center gap-1">
                                <Clock className="h-4 w-4" />
                                {story.estimated_duration_minutes} min
                            </span>
                        </div>

                        <h2 className="text-3xl font-black uppercase mb-2">{story.title}</h2>
                        {story.subtitle && (
                            <p className="text-lg text-[var(--app-ink-2)] font-medium mb-4">{story.subtitle}</p>
                        )}

                        {story.source_author && (
                            <p className="text-sm text-[var(--app-ink-3)] font-bold mb-4">
                                By {story.source_author}
                            </p>
                        )}

                        {/* Themes */}
                        <div className="flex flex-wrap gap-2 mb-6">
                            {story.themes.slice(0, 4).map((theme) => (
                                <span
                                    key={theme}
                                    className="px-2 py-1 bg-stone-100 border border-black/10 text-stone-700 text-sm font-semibold rounded-none"
                                >
                                    {theme}
                                </span>
                            ))}
                        </div>

                        {/* Progress */}
                        {hasProgress && story.progress && (
                            <div className="mb-6">
                                <div className="flex justify-between text-sm font-bold mb-2">
                                    <span>Progress</span>
                                    <span>{story.progress.completion_percentage}%</span>
                                </div>
                                <div className="w-full h-4 bg-stone-100 border-2 border-black rounded-none">
                                    <div
                                        className="h-full bg-bauhaus-blue transition-all"
                                        style={{ width: `${story.progress.completion_percentage}%` }}
                                    />
                                </div>
                                {story.progress.current_chapter_title && (
                                    <p className="text-sm text-[var(--app-ink-2)] mt-2">
                                        Current: {story.progress.current_chapter_title}
                                    </p>
                                )}
                            </div>
                        )}
                    </div>

                    {/* CTA */}
                    <Link href={`/story/${story.id}`}>
                        <Button
                            className="w-full h-14 text-lg font-bold shadow-[4px_4px_0px_0px_#000] border-2 border-black rounded-none bg-black text-white hover:bg-stone-900 transition-all"
                            leftIcon={<Play className="h-5 w-5" />}
                        >
                            {hasProgress ? 'Continue' : 'Start Story'}
                        </Button>
                    </Link>
                </div>
            </div>
        </Card>
    );
}

function StoryCard({ story }: { story: Story }) {
    const isLocked = !story.is_unlocked;
    const hasProgress = story.progress && story.progress.status !== 'not_started';

    return (
        <Card className={`border-4 border-black rounded-none shadow-[6px_6px_0px_0px_#000] hover:shadow-[8px_8px_0px_0px_#000] hover:-translate-y-0.5 transition-all bg-[var(--app-sheet)] text-black ${isLocked ? 'opacity-60' : ''}`}>
            {/* Cover */}
            <div className="h-40 bg-gradient-to-br from-bauhaus-blue to-purple-800 flex items-center justify-center relative">
                {story.cover_image_url ? (
                    <Image
                        src={story.cover_image_url}
                        alt={story.title}
                        fill
                        unoptimized
                        sizes="(max-width: 768px) 100vw, (max-width: 1024px) 50vw, 33vw"
                        className="h-full w-full object-cover border-b-2 border-black"
                    />
                ) : (
                    <div className="text-6xl">🌹</div>
                )}

                {isLocked && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                        <Lock className="h-12 w-12 text-white" />
                    </div>
                )}

                {/* Level Badge */}
                <div className="absolute top-3 right-3 flex gap-1">
                    {story.target_levels.slice(0, 2).map((level) => (
                        <span
                            key={level}
                            className="px-2 py-1 bg-bauhaus-yellow border-2 border-black font-bold text-xs rounded-none shadow-[2px_2px_0px_0px_#000]"
                        >
                            {level}
                        </span>
                    ))}
                </div>
            </div>

            <CardContent className="p-4">
                <h3 className="text-xl font-black uppercase mb-1 line-clamp-1">{story.title}</h3>
                {story.source_author && (
                    <p className="text-sm text-[var(--app-ink-3)] font-medium mb-3">
                        By {story.source_author}
                    </p>
                )}

                {/* Duration & Themes */}
                <div className="flex items-center gap-2 text-sm text-[var(--app-ink-2)] mb-4">
                    <Clock className="h-4 w-4" />
                    <span>{story.estimated_duration_minutes} min</span>
                </div>

                {/* Progress Bar */}
                {hasProgress && story.progress && (
                    <div className="mb-4">
                        <div className="w-full h-2 bg-stone-100 border border-black rounded-none">
                            <div
                                className="h-full bg-bauhaus-blue"
                                style={{ width: `${story.progress.completion_percentage}%` }}
                            />
                        </div>
                    </div>
                )}

                {/* Action */}
                <Link href={isLocked ? '#' : `/story/${story.id}`}>
                    <Button
                        variant="outline"
                        className="w-full border-2 border-black rounded-none shadow-[4px_4px_0px_0px_#000] font-bold bg-white text-black hover:bg-stone-50 transition-all"
                        disabled={isLocked}
                        rightIcon={<ChevronRight className="h-4 w-4" />}
                    >
                        {isLocked ? 'Locked' : hasProgress ? 'Continue' : 'Play'}
                    </Button>
                </Link>
            </CardContent>
        </Card>
    );
}

export async function getServerSideProps(context: any) {
    const session = await getSession(context);

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

        const res = await fetch(`${baseUrl}/api/v1/stories`, { headers });

        if (!res.ok) {
            console.error('Failed to fetch stories:', res.status);
            return { props: { stories: [] } };
        }

        const stories = await res.json();

        // Filter out imported stories as they belong to the Learn/Conversational framework
        const filteredStories = stories.filter((story: any) =>
            !story.themes?.includes('imported')
        );

        return {
            props: {
                stories: filteredStories,
            },
        };
    } catch (error) {
        console.error('Failed to fetch stories:', error);
        return {
            props: {
                stories: [],
            },
        };
    }
}
