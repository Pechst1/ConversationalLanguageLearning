// The walks run a headless browser; a bare one reads the machine's clock, which is UTC, and the
// Courrier then shows server hours («02 h 57» at 03:57 in Berlin) that look like #316 again (#397).
// The learner the walks play lives in Berlin; set WALK_TIMEZONE to walk from elsewhere.
export const WALK_TIMEZONE = process.env.WALK_TIMEZONE || 'Europe/Berlin';
