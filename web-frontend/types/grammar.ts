export interface GrammarConcept {
    id: number;
    name: string;
    level: string;
    category?: string;
    description?: string;
    examples?: string;
    difficulty_order: number;
}

export interface GrammarProgress {
    concept_id: number;
    concept_name: string;
    concept_level: string;
    score: number;
    reps: number;
    state: string;
    state_label: string;
    notes?: string;
    last_review?: string;
    next_review?: string;
}

export interface GrammarSummary {
    total_concepts: number;
    started: number;
    due_today: number;
    new_available: number;
    state_counts: Record<string, number>;
    level_counts: Record<string, number>;
}

export interface DueConcept {
    id: number;
    name: string;
    level: string;
    category?: string;
    description?: string;
    current_score?: number;
    current_state: string;
    reps: number;
}

export interface GrammarLevelGroup {
    [level: string]: {
        id: number;
        name: string;
        category?: string;
        description?: string;
        score?: number;
        state: string;
        reps: number;
        next_review?: string;
    }[];
}

// Exercise types
export interface GrammarExercise {
    type: 'fill_blank' | 'translation' | 'error_correction' | 'sentence_build' | 'context' | 'open';
    instruction: string;
    prompt: string;
    hint?: string;
    correct_answer?: string;
    explanation?: string;
}

export interface ExerciseResult {
    exercise_index: number;
    is_correct: boolean;
    user_answer: string;
    correct_answer: string;
    feedback: string;
    points: number;
}

export interface ExerciseSession {
    concept_id: number;
    concept_name: string;
    level: string;
    exercises: GrammarExercise[];
}

export interface CheckAnswersResponse {
    results: ExerciseResult[];
    total_score: number;
    overall_feedback: string;
    tips: string[];
}

// Achievement types
export interface GrammarAchievement {
    id: number;
    key: string;
    name: string;
    description?: string;
    icon_url?: string;
    xp_reward: number;
    tier: 'bronze' | 'silver' | 'gold' | 'platinum';
    category?: string;
    is_unlocked: boolean;
    unlocked_at?: string;
    progress: number;
}

export interface StreakInfo {
    current_streak: number;
    longest_streak: number;
    last_review_date?: string;
    is_active_today: boolean;
}

export interface AchievementUnlock {
    id: number;
    key: string;
    name: string;
    description?: string;
    xp_reward: number;
    tier: string;
}

export interface ReviewWithAchievementsResponse {
    progress: GrammarProgress;
    streak: {
        streak_days: number;
        is_new_day: boolean;
        milestone_reached?: number;
    };
    achievements_unlocked: AchievementUnlock[];
}

// Concept Graph types
export interface ConceptGraphNode {
    id: number;
    name: string;
    level: string;
    category?: string;
    description?: string;
    visualization_type?: string;
    prerequisites: number[];
    is_locked: boolean;
    state: string;
    score: number;
    reps: number;
}

export interface ConceptGraphEdge {
    source: number;
    target: number;
}

export interface ConceptGraph {
    nodes: ConceptGraphNode[];
    edges: ConceptGraphEdge[];
    levels: Record<string, number[]>;
}

// Chapter Grammar Integration types
export interface ChapterGrammarConcept {
    id: number;
    name: string;
    level: string;
    category?: string;
    description?: string;
    visualization_type?: string;
    state: string;
    score: number;
    reps: number;
    is_due: boolean;
}
