/** Generated from app.main.create_app().openapi(). Run npm run types:generate. */
export interface paths {
    "/api/v1/achievements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Achievements
         * @description Return all available achievement definitions.
         */
        get: operations["list_achievements_api_v1_achievements_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/achievements/check": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Check Achievements
         * @description Compatibility endpoint; normal clients unlock automatically on read.
         */
        post: operations["check_achievements_api_v1_achievements_check_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/achievements/my": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get My Achievements
         * @description Return the authenticated user's achievement progress.
         */
        get: operations["get_my_achievements_api_v1_achievements_my_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/client-error": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Record Client Error
         * @description First-party crash intake for the web/native shell.
         */
        post: operations["record_client_error_api_v1_analytics_client_error_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/client-error/anonymous": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Record Anonymous Client Error
         * @description Crash intake for the signed-out shell (onboarding, sign-in, placement).
         */
        post: operations["record_anonymous_client_error_api_v1_analytics_client_error_anonymous_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/errors": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Error Patterns
         * @description Return the most common learner errors.
         */
        get: operations["read_error_patterns_api_v1_analytics_errors_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/errors/list": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Error List
         * @description Return detailed list of all tracked errors with SRS data.
         */
        get: operations["read_error_list_api_v1_analytics_errors_list_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/errors/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Error Summary
         * @description Return Anki-like summary of user errors for progress tracking.
         */
        get: operations["read_error_summary_api_v1_analytics_errors_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/pilot-daily": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Pilot Daily
         * @description Return one learner-day ledger for pilot operations.
         */
        get: operations["read_pilot_daily_api_v1_analytics_pilot_daily_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/pilot-forge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Pilot Forge
         * @description WP-S8 «La Forge»: per-rule speed, séance health, latency — 7 and 30 days, per band.
         */
        get: operations["read_pilot_forge_api_v1_analytics_pilot_forge_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/pilot-ops": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Pilot Operations
         * @description Return the pilot's cost and generated-content health guardrails.
         */
        get: operations["read_pilot_operations_api_v1_analytics_pilot_ops_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/statistics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Statistics
         * @description Return rolling analytics windows for charts.
         */
        get: operations["read_statistics_api_v1_analytics_statistics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/streak": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Streak
         * @description Return the streak and «Vos sceaux», read from the same rows (WP-D5).
         */
        get: operations["read_streak_api_v1_analytics_streak_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Analytics Summary
         * @description Return top-line learner metrics.
         */
        get: operations["read_analytics_summary_api_v1_analytics_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/analytics/vocabulary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Vocabulary Heatmap
         * @description Return vocabulary mastery counts by state.
         */
        get: operations["read_vocabulary_heatmap_api_v1_analytics_vocabulary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/anki/due-cards": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Due Cards
         * @description Get vocabulary cards that are due for review.
         *
         *     Args:
         *         limit: Maximum number of cards to return
         *         scheduler_type: Filter by scheduler ('anki' or 'fsrs')
         *
         *     Returns cards due for review with their vocabulary information.
         */
        get: operations["get_due_cards_api_v1_anki_due_cards_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/anki/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import Anki Cards
         * @description Import Anki cards from a CSV file.
         *
         *     Upload your Anki deck export (CSV format) to import French-German vocabulary cards.
         *     The system will automatically:
         *     - Detect French and German content
         *     - Create paired cards (French↔German)
         *     - Preserve your existing review progress
         *     - Maintain synchronization with Anki
         */
        post: operations["import_anki_cards_api_v1_anki_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/anki/import/text": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import Anki Cards Text
         * @description Import Anki cards from CSV text content.
         *
         *     Alternative endpoint for importing cards by pasting CSV content directly.
         *     Useful for smaller imports or when file upload is not convenient.
         */
        post: operations["import_anki_cards_text_api_v1_anki_import_text_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/anki/rehydrate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Rehydrate From Last Import
         * @description Re-import the most recent saved Anki CSV for the current user.
         *
         *     Useful if the database was reset or vocabulary rows were lost.
         */
        post: operations["rehydrate_from_last_import_api_v1_anki_rehydrate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/anki/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Submit Anki Review
         * @description Submit a review for an imported Anki card using SM-2 scheduling.
         */
        post: operations["submit_anki_review_api_v1_anki_review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/anki/statistics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Anki Statistics
         * @description Get statistics about imported Anki cards and review progress.
         *
         *     Returns detailed statistics about:
         *     - Total imported vocabulary
         *     - French→German vs German→French cards
         *     - Paired card relationships
         *     - Review performance by scheduler type
         */
        get: operations["get_anki_statistics_api_v1_anki_statistics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/almanac": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Almanac */
        get: operations["get_almanac_api_v1_atelier_almanac_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/attempts/{attempt_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Attempt */
        get: operations["get_attempt_api_v1_atelier_attempts__attempt_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/attempts/{attempt_id}/ai-review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Request Attempt Ai Review */
        post: operations["request_attempt_ai_review_api_v1_atelier_attempts__attempt_id__ai_review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/attempts/{attempt_id}/repair": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Repair Attempt */
        post: operations["repair_attempt_api_v1_atelier_attempts__attempt_id__repair_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/errata/{error_id}/attempt": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Erratum Review Attempt */
        post: operations["submit_erratum_review_attempt_api_v1_atelier_errata__error_id__attempt_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/errata/{error_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Review Erratum */
        post: operations["review_erratum_api_v1_atelier_errata__error_id__review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/errata/{error_id}/task": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Erratum Review Task */
        get: operations["get_erratum_review_task_api_v1_atelier_errata__error_id__task_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/exercises/report": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Report Exercise */
        post: operations["report_exercise_api_v1_atelier_exercises_report_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/forge/eclair": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Eclair */
        post: operations["start_eclair_api_v1_atelier_forge_eclair_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/forge/eclair/{eclair_id}/finish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Finish Eclair */
        post: operations["finish_eclair_api_v1_atelier_forge_eclair__eclair_id__finish_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/forge/map": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Grammar Map */
        get: operations["get_grammar_map_api_v1_atelier_forge_map_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/forge/map/opened": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Record Grammar Map Opened */
        post: operations["record_grammar_map_opened_api_v1_atelier_forge_map_opened_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/forge/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Forge Session */
        get: operations["get_forge_session_api_v1_atelier_forge_sessions__session_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/forge/state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Forge State */
        get: operations["get_forge_state_api_v1_atelier_forge_state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/forge/test-out": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Test Out */
        post: operations["start_test_out_api_v1_atelier_forge_test_out_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Session */
        post: operations["start_session_api_v1_atelier_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Session */
        get: operations["get_session_api_v1_atelier_sessions__session_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/sessions/{session_id}/attempts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Attempt */
        post: operations["submit_attempt_api_v1_atelier_sessions__session_id__attempts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/sessions/{session_id}/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Complete Session */
        post: operations["complete_session_api_v1_atelier_sessions__session_id__complete_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/sessions/{session_id}/exit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Exit Session
         * @description WP-S8: the learner closed an unfinished forge séance («forge_abandoned»).
         *
         *     The séance stays open (a bare start resumes it); only the event is written,
         *     once. A completed, finished or legacy séance writes nothing.
         */
        post: operations["exit_session_api_v1_atelier_sessions__session_id__exit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/sessions/active": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Active Session */
        get: operations["get_active_session_api_v1_atelier_sessions_active_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/today": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Today */
        get: operations["get_today_api_v1_atelier_today_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/translate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Translate For Learner
         * @description On-demand French -> learner's-language translation for any learner-facing line.
         *
         *     The target is the account's ``native_language`` (German for a German
         *     learner, English as the floor), never a fixed English: the help sheet
         *     quotes this line under the French one, and a translation the learner
         *     cannot read is no help at all.
         */
        post: operations["translate_for_learner_api_v1_atelier_translate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/atelier/workshop/compose": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Compose Workshop Plate */
        post: operations["compose_workshop_plate_api_v1_atelier_workshop_compose_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audio-session/end": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * End Audio Session
         * @description End an audio session and get summary.
         */
        post: operations["end_audio_session_api_v1_audio_session_end_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audio-session/respond": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Respond To Audio
         * @description Process user's spoken response and get AI reply.
         *
         *     Flow:
         *     1. Transcribed text comes from client (via Whisper)
         *     2. AI generates natural response
         *     3. Error detection runs in background
         *     4. If errors detected, they're tracked for SRS and linked to grammar concepts
         */
        post: operations["respond_to_audio_api_v1_audio_session_respond_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audio-session/scenarios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Audio Scenarios
         * @description List available roleplay scenarios.
         */
        get: operations["list_audio_scenarios_api_v1_audio_session_scenarios_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audio-session/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Audio Session
         * @description Start a new audio-only session.
         *
         *     This is a ZERO-CONFIG endpoint. The AI automatically:
         *     - Picks a conversation topic based on time of day (default)
         *     - Or uses the requested roleplay scenario
         *     - Weaves in user's past errors for natural practice
         *     - Adjusts to user's proficiency level
         */
        post: operations["start_audio_session_api_v1_audio_session_start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audio/speak": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Text To Speech
         * @description Convert text to speech audio.
         */
        post: operations["text_to_speech_api_v1_audio_speak_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/audio/transcribe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Transcribe Audio
         * @description Transcribe an audio file to text.
         *
         *     WP-27 made speaking the daily journey's default output, so this is a paid
         *     endpoint on the learner's main path: every successful call writes one
         *     priced pilot-cost row (`app.services.transcription_cost`). Nothing here
         *     scores pronunciation — the transcript is graded as text, exactly like a
         *     typed answer.
         */
        post: operations["transcribe_audio_api_v1_audio_transcribe_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description Authenticate a user and return JWT tokens.
         */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Logout
         * @description Revoke the supplied refresh token if the client has one.
         */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/password-reset/confirm": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Confirm Password Reset
         * @description Set a new password with the emailed code (email + code) or a link token.
         */
        post: operations["confirm_password_reset_api_v1_auth_password_reset_confirm_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/password-reset/request": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Request Password Reset
         * @description Email a six-digit reset code (plus a link where a public app URL exists).
         */
        post: operations["request_password_reset_api_v1_auth_password_reset_request_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refresh Tokens
         * @description Rotate a refresh token and return a fresh token pair.
         */
        post: operations["refresh_tokens_api_v1_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Register User
         * @description Register a new user and return the created entity.
         */
        post: operations["register_user_api_v1_auth_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/can-dos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Carnet
         * @description Every sub-band's can-dos, each with its Seal once story evidence pressed it.
         */
        get: operations["get_carnet_api_v1_can_dos_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Journey
         * @description 201 for a new ready journey, 200 for an existing one, 202 while preparing.
         */
        post: operations["create_journey_api_v1_daily_journeys_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/{journey_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Journey
         * @description Owned persisted state, terminal states included. Safe to poll.
         */
        get: operations["read_journey_api_v1_daily_journeys__journey_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/{journey_id}/advance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Advance
         * @description Acknowledge the current step and activate the next eligible one.
         */
        post: operations["advance_api_v1_daily_journeys__journey_id__advance_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/{journey_id}/finish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Finish
         * @description Complete requires resolved mandatory steps; early records partial work.
         */
        post: operations["finish_api_v1_daily_journeys__journey_id__finish_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/{journey_id}/pause": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Pause
         * @description Preserve every completed step.
         */
        post: operations["pause_api_v1_daily_journeys__journey_id__pause_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/{journey_id}/resume": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Resume
         * @description Return the same step and the same pinned content, never a new plan.
         */
        post: operations["resume_api_v1_daily_journeys__journey_id__resume_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/{journey_id}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Retry
         * @description Bounded recovery for a preparing/unavailable journey, reusing its id.
         */
        post: operations["retry_api_v1_daily_journeys__journey_id__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/{journey_id}/steps/{step_id}/attempts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Submit Attempt
         * @description Canonical server evaluation. The client never supplies a score.
         */
        post: operations["submit_attempt_api_v1_daily_journeys__journey_id__steps__step_id__attempts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/{journey_id}/steps/{step_id}/help": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Use Help
         * @description Record the reveal, then return it. Assistance is never client-asserted.
         */
        post: operations["use_help_api_v1_daily_journeys__journey_id__steps__step_id__help_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/{journey_id}/steps/{step_id}/line-audio": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Speak Step Line
         * @description Speak one line of one step, or say ``disabled`` so the device reads it.
         */
        post: operations["speak_step_line_api_v1_daily_journeys__journey_id__steps__step_id__line_audio_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/capabilities/progress": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Capability Progress
         * @description Evidence-backed practical capability summary (WP-09 fills this in).
         */
        get: operations["read_capability_progress_api_v1_daily_journeys_capabilities_progress_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/line-audio/{clip_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Line Audio Clip
         * @description One spoken line: the learner's own clip, or a listening item's, spoken now.
         */
        get: operations["line_audio_clip_api_v1_daily_journeys_line_audio__clip_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/daily-journeys/today": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Today
         * @description Capability, the open journey, or today's available scenario.
         *
         *     Never creates a journey and never pays for generation.
         */
        get: operations["read_today_api_v1_daily_journeys_today_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dossier/claims": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Open Claim
         * @description Open the check behind «je connais déjà», and record that it was claimed.
         */
        post: operations["open_claim_api_v1_dossier_claims_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dossier/claims/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Verify
         * @description Grade the two items. Both right advances the schedule; anything else does not.
         */
        post: operations["verify_api_v1_dossier_claims_verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dossier/state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Dossier
         * @description What the app believes about this learner, and why. A read, start to end.
         */
        get: operations["read_dossier_api_v1_dossier_state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/feedback/reports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Feedback Reports
         * @description List feedback reports for admin triage.
         */
        get: operations["list_feedback_reports_api_v1_feedback_reports_get"];
        put?: never;
        /**
         * Create Feedback Report
         * @description Store a lightweight report from the global pilot feedback widget.
         */
        post: operations["create_feedback_report_api_v1_feedback_reports_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/achievements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Achievements
         * @description Get all grammar achievements with user unlock status.
         */
        get: operations["get_achievements_api_v1_grammar_achievements_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/by-level": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Concepts By Level
         * @description Get all concepts grouped by level with user progress.
         */
        get: operations["get_concepts_by_level_api_v1_grammar_by_level_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/concepts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Concepts
         * @description List all grammar concepts.
         */
        get: operations["list_concepts_api_v1_grammar_concepts_get"];
        put?: never;
        /**
         * Create Concept
         * @description Create a new grammar concept.
         */
        post: operations["create_concept_api_v1_grammar_concepts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/concepts/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Bulk Import Concepts
         * @description Bulk import grammar concepts.
         */
        post: operations["bulk_import_concepts_api_v1_grammar_concepts_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/due": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Due Concepts
         * @description Get grammar concepts due for review.
         */
        get: operations["get_due_concepts_api_v1_grammar_due_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/for-chapter/{chapter_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Concepts For Chapter
         * @description Get grammar concepts associated with a story chapter.
         */
        get: operations["get_concepts_for_chapter_api_v1_grammar_for_chapter__chapter_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/for-errors": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Concepts For Errors
         * @description Get grammar concepts to review based on user's error patterns.
         *
         *     This creates the Error→Grammar synergy by recommending which grammar
         *     topics to study based on recurring mistakes.
         */
        get: operations["get_concepts_for_errors_api_v1_grammar_for_errors_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/graph": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Concept Graph
         * @description Get the concept dependency graph for visualization.
         */
        get: operations["get_concept_graph_api_v1_grammar_graph_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/mark-practiced-in-context": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Mark Practiced In Context
         * @description Mark grammar concepts as practiced in story context.
         */
        post: operations["mark_practiced_in_context_api_v1_grammar_mark_practiced_in_context_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/notebook": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Grammar Notebook
         * @description List concepts for the personal grammar notebook.
         */
        get: operations["get_grammar_notebook_api_v1_grammar_notebook_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/notebook/{concept_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Grammar Notebook Concept
         * @description Get one concept as a personal grammar notebook page.
         */
        get: operations["get_grammar_notebook_concept_api_v1_grammar_notebook__concept_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/notebook/{concept_id}/notes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Grammar Notebook Notes
         * @description Update personal notes without recording a review.
         */
        patch: operations["update_grammar_notebook_notes_api_v1_grammar_notebook__concept_id__notes_patch"];
        trace?: never;
    };
    "/api/v1/grammar/progress": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get User Progress
         * @description Get user's grammar progress.
         */
        get: operations["get_user_progress_api_v1_grammar_progress_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Record Review
         * @description Record a grammar concept review with 0-10 score.
         */
        post: operations["record_review_api_v1_grammar_review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/review-with-achievements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Record Review With Achievements
         * @description Record a grammar review and check for achievement unlocks.
         *
         *     Returns the review result plus any newly unlocked achievements.
         */
        post: operations["record_review_with_achievements_api_v1_grammar_review_with_achievements_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/streak": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Streak Info
         * @description Get user's current grammar streak information.
         */
        get: operations["get_streak_info_api_v1_grammar_streak_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/grammar/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Summary
         * @description Get grammar progress summary for dashboard.
         */
        get: operations["get_summary_api_v1_grammar_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/graphic-novel/scenes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Graphic Novel Scene */
        post: operations["create_graphic_novel_scene_api_v1_graphic_novel_scenes_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/graphic-novel/scenes/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Graphic Novel Scene */
        post: operations["create_graphic_novel_scene_api_v1_graphic_novel_scenes__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/graphic-novel/scenes/{scene_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Graphic Novel Scene */
        get: operations["get_graphic_novel_scene_api_v1_graphic_novel_scenes__scene_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/graphic-novel/scenes/{scene_id}/attempts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Graphic Novel Attempt */
        post: operations["submit_graphic_novel_attempt_api_v1_graphic_novel_scenes__scene_id__attempts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/graphic-novel/scenes/{scene_id}/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Complete Graphic Novel Scene */
        post: operations["complete_graphic_novel_scene_api_v1_graphic_novel_scenes__scene_id__complete_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/graphic-novel/today": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Graphic Novel Today */
        get: operations["get_graphic_novel_today_api_v1_graphic_novel_today_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/intake": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Artefacts
         * @description Everything this learner has brought in, and how much allowance is left.
         */
        get: operations["list_artefacts_api_v1_intake_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/intake/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Artefacts
         * @description Everything this learner has brought in, and how much allowance is left.
         */
        get: operations["list_artefacts_api_v1_intake__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/intake/{artefact_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Artefact */
        get: operations["get_artefact_api_v1_intake__artefact_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Artefact
         * @description Delete the artefact and the Courrier task derived from it.
         *
         *     Answers 204 whether or not the row was there. A learner deleting a document
         *     twice must not be told which of their documents exist.
         */
        delete: operations["delete_artefact_api_v1_intake__artefact_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/intake/photo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Submit Photo
         * @description Read one photographed document.
         *
         *     The bytes are read to one byte past the ceiling and no further, so an
         *     oversized upload is refused without ever being held whole in memory, and they
         *     are never written anywhere: what survives the request is the reading.
         */
        post: operations["submit_photo_api_v1_intake_photo_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/intake/text": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Submit Text
         * @description Read one pasted document. Costs exactly one model call.
         */
        post: operations["submit_text_api_v1_intake_text_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/{entry_id}/followup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Answer Followup
         * @description One line, a week later. Its answer is the ``used_again_later`` signal.
         */
        post: operations["answer_followup_api_v1_journal__entry_id__followup_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/{entry_id}/skip": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Skip Entry
         * @description The learner declined this scene. Asked once, then let go.
         */
        post: operations["skip_entry_api_v1_journal__entry_id__skip_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/{entry_id}/write": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Write Entry
         * @description Store the recap, correct it, and reveal the scene.
         *
         *     Replaying it is a no-op: the entry already carries text, so no second paid
         *     correction is bought and the stored verdict stands.
         */
        post: operations["write_entry_api_v1_journal__entry_id__write_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/entries": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Entries
         * @description The learner's own writing, newest first. Their journal, not a report.
         */
        get: operations["list_entries_api_v1_journal_entries_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/journal/state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read State
         * @description What the journal should show today.
         *
         *     Creating the offer on a GET is deliberate and safe: it is idempotent, writes
         *     no learner content, and the alternative — a client that has to POST before
         *     it can render — turns an empty tab into a mutation.
         */
        get: operations["read_state_api_v1_journal_state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/legal/consent": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Consent */
        get: operations["read_consent_api_v1_legal_consent_get"];
        put?: never;
        /**
         * Record Consent
         * @description Record acceptance of the terms, the privacy policy and AI processing.
         *
         *     Only the version the server is currently serving can be accepted: a client
         *     holding stale text must not record consent to words it never showed.
         */
        post: operations["record_consent_api_v1_legal_consent_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/missions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Mission */
        post: operations["create_mission_api_v1_missions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/missions/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Mission */
        post: operations["create_mission_api_v1_missions__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/missions/{mission_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Mission */
        get: operations["get_mission_api_v1_missions__mission_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/missions/{mission_id}/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Complete Mission */
        post: operations["complete_mission_api_v1_missions__mission_id__complete_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/missions/{mission_id}/submit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Mission */
        post: operations["submit_mission_api_v1_missions__mission_id__submit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/missions/{mission_id}/turns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Mission Turn */
        post: operations["submit_mission_turn_api_v1_missions__mission_id__turns_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/missions/audio/transcribe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Transcribe Mission Audio
         * @description Transcribe mission voice input while keeping Atelier's demo-auth behavior.
         */
        post: operations["transcribe_mission_audio_api_v1_missions_audio_transcribe_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/missions/today": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Missions Today
         * @description Return the weekly mission, active mission, and post-session recommendation.
         */
        get: operations["get_missions_today_api_v1_missions_today_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications/native/subscribe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Subscribe Native
         * @description Register the APNs token emitted by the Capacitor iOS shell.
         */
        post: operations["subscribe_native_api_v1_notifications_native_subscribe_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications/subscribe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Subscribe */
        post: operations["subscribe_api_v1_notifications_subscribe_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications/tap": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Record Notification Tap
         * @description Record engagement before the native shell follows the deep link.
         */
        post: operations["record_notification_tap_api_v1_notifications_tap_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications/test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Test Notification */
        post: operations["test_notification_api_v1_notifications_test_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/notifications/vapid-public-key": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Vapid Public Key */
        get: operations["get_vapid_public_key_api_v1_notifications_vapid_public_key_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/npcs/{npc_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Npc
         * @description Get NPC details.
         */
        get: operations["get_npc_api_v1_npcs__npc_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/npcs/{npc_id}/memories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Npc Memories
         * @description Get NPC's memories of interactions with user.
         */
        get: operations["get_npc_memories_api_v1_npcs__npc_id__memories_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/npcs/{npc_id}/relationship": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Npc Relationship
         * @description Get user's relationship status with an NPC.
         */
        get: operations["get_npc_relationship_api_v1_npcs__npc_id__relationship_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/placement/{session_id}/finish": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Finish
         * @description End it with the evidence there is. No graded turn means no level.
         */
        post: operations["finish_api_v1_placement__session_id__finish_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/placement/{session_id}/respond": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Respond
         * @description Grade one answer and hand back the next rung, or the result.
         */
        post: operations["respond_api_v1_placement__session_id__respond_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/placement/offer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Offer
         * @description WP-126: true from the first completed ending on, before any placement was
         *     taken or declined, and only when it can tell the learner something (they
         *     declared more than «Nouveau», or their days say they are *above* their band).
         *     An open placement is offered for resuming.
         */
        get: operations["read_offer_api_v1_placement_offer_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/placement/skip": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Skip
         * @description The learner declined. Their declared level stands, exactly as before.
         */
        post: operations["skip_api_v1_placement_skip_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/placement/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start
         * @description Open a placement, or resume the one already open (idempotent).
         */
        post: operations["start_api_v1_placement_start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/placement/state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read State
         * @description What the learner should see: an open placement, a result, or the offer.
         */
        get: operations["read_state_api_v1_placement_state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/{word_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Progress Detail
         * @description Return the learner's scheduling stats for a vocabulary item.
         */
        get: operations["get_progress_detail_api_v1_progress__word_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/anki": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Anki Progress
         * @description Return all imported Anki cards with their current progress for the learner.
         */
        get: operations["list_anki_progress_api_v1_progress_anki_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/anki/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Anki Summary
         * @description Return aggregate progress metrics for imported Anki cards.
         */
        get: operations["get_anki_summary_api_v1_progress_anki_summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/anki/sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Sync Anki Progress Endpoint
         * @description Sync progress from AnkiConnect.
         */
        post: operations["sync_anki_progress_endpoint_api_v1_progress_anki_sync_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/bump/{word_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Bump Word Difficulty
         * @description Bump a word's difficulty to schedule it for earlier review.
         *     This is equivalent to marking a word as "Again" in spaced repetition.
         *     Used when a user clicks on a word during conversation to indicate they need more practice.
         */
        post: operations["bump_word_difficulty_api_v1_progress_bump__word_id__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/cefr": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Cefr Progress
         * @description Return the visible CEFR estimate and next-level forecast.
         */
        get: operations["get_cefr_progress_api_v1_progress_cefr_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/cefr/checkpoint": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Level Checkpoint
         * @description WP-L7 — the épreuve's state for the band in force, computed fresh.
         *
         *     The story engine's one question is ``checkpoint_ready``: stage the band's
         *     finale-like épreuve episode now. Read-only (no row is written).
         */
        get: operations["get_level_checkpoint_api_v1_progress_cefr_checkpoint_get"];
        put?: never;
        /**
         * Record Level Checkpoint
         * @description WP-L7 — record the épreuve's result; a pass raises the level.
         *
         *     409 when the band is not the one in force, not ready, already closed, or a
         *     failed épreuve is still inside its week of consolidation.
         */
        post: operations["record_level_checkpoint_api_v1_progress_cefr_checkpoint_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/cefr/recompute": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Recompute Cefr Progress
         * @description Recompute and persist a CEFR estimate snapshot.
         */
        post: operations["recompute_cefr_progress_api_v1_progress_cefr_recompute_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/insights/weekly": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Weekly Insights
         * @description Get AI-powered weekly learning insights and recommendations.
         *
         *     This endpoint generates personalized insights based on the user's
         *     learning analytics, including:
         *     - Progress summary for the week
         *     - Strengths and areas for improvement
         *     - Specific actionable recommendations
         *     - Motivational encouragement
         *
         *     Results are cached for 24 hours unless force_refresh is True.
         */
        get: operations["get_weekly_insights_api_v1_progress_insights_weekly_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/queue": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Review Queue
         * @description Return a mix of due and new words for the authenticated learner.
         */
        get: operations["get_review_queue_api_v1_progress_queue_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Submit Review
         * @description Register a learner review and return the next scheduled review time.
         */
        post: operations["submit_review_api_v1_progress_review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/unified-queue": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Unified Review Queue
         * @description Return one canonical SRS queue across vocabulary, grammar, and durable errata.
         */
        get: operations["get_unified_review_queue_api_v1_progress_unified_queue_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/vocabulary/map": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Vocabulary Mastery Map
         * @description Return a compact mastery map for the imported French 5000 deck.
         */
        get: operations["get_vocabulary_mastery_map_api_v1_progress_vocabulary_map_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/vocabulary/recommendations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Vocabulary Recommendations
         * @description Return SRS-ranked vocabulary cards for today's learning loop.
         */
        get: operations["get_vocabulary_recommendations_api_v1_progress_vocabulary_recommendations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/progress/weekly-dossier": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Weekly Dossier
         * @description Return a deterministic editorial digest of this learner's recent work.
         */
        get: operations["get_weekly_dossier_api_v1_progress_weekly_dossier_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rehearsals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Declare
         * @description Declare a real situation and prepare it in one round trip.
         *
         *     The response may well carry ``status: "not_prepared"``. That is a success of
         *     the transport and a failure of the provider, and it is reported as such —
         *     never as a 500, and never as an invented scene.
         */
        post: operations["declare_api_v1_rehearsals_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rehearsals/{rehearsal_id}/abandon": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Abandon
         * @description Drop a rehearsal. It still counts against the week: the scene was paid for.
         */
        post: operations["abandon_api_v1_rehearsals__rehearsal_id__abandon_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rehearsals/{rehearsal_id}/debrief": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Debrief
         * @description How the real thing went. This is the package's success metric.
         */
        post: operations["debrief_api_v1_rehearsals__rehearsal_id__debrief_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rehearsals/{rehearsal_id}/phrases": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reveal Phrases
         * @description Hand over the useful phrases — and book the assistance that costs.
         */
        post: operations["reveal_phrases_api_v1_rehearsals__rehearsal_id__phrases_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rehearsals/{rehearsal_id}/prepare": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Prepare
         * @description Try again to prepare a rehearsal the provider could not prepare.
         */
        post: operations["prepare_api_v1_rehearsals__rehearsal_id__prepare_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rehearsals/{rehearsal_id}/turns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Respond
         * @description Grade one rehearsal turn.
         */
        post: operations["respond_api_v1_rehearsals__rehearsal_id__turns_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/rehearsals/state": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read State
         * @description What the learner has open, what is owed a debrief, and what is left.
         */
        get: operations["read_state_api_v1_rehearsals_state_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/admin/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refresh Intake
         * @description Rebuild the period's dossiers from the feeds (``refresh=True``).
         */
        post: operations["refresh_intake_api_v1_revue_admin_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/carte": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Carte
         * @description The learner's pins (closed Papiers with a place), «Mon quartier», counts per level.
         */
        get: operations["read_carte_api_v1_revue_carte_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/carte/review/{place_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Carte Review
         * @description WP-121 A.3: the due words met at this place, what carried them, and the items to pose.
         */
        get: operations["read_carte_review_api_v1_revue_carte_review__place_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/carte/review/{place_id}/grade": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Grade Carte Review
         * @description WP-121 A.3: grade one item on the server and move its cards through the SRS.
         */
        post: operations["grade_carte_review_api_v1_revue_carte_review__place_id__grade_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/correcteur/{correction_id}/marks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Marks */
        post: operations["submit_marks_api_v1_revue_correcteur__correction_id__marks_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/correcteur/{dossier_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** New Draft */
        post: operations["new_draft_api_v1_revue_correcteur__dossier_id__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/correcteur/week": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Week */
        get: operations["read_week_api_v1_revue_correcteur_week_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/match": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Match Request
         * @description «Autre chose ?»: match a free request against the week's dossiers. Nothing is stored.
         */
        post: operations["match_request_api_v1_revue_match_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/radio/{dossier_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Bulletin */
        get: operations["read_bulletin_api_v1_revue_radio__dossier_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/radio/{dossier_id}/dictee": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Grade Dictee */
        post: operations["grade_dictee_api_v1_revue_radio__dossier_id__dictee_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/radio/{dossier_id}/heard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark Heard */
        post: operations["mark_heard_api_v1_revue_radio__dossier_id__heard_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/radio/week": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Radio Week */
        get: operations["read_radio_week_api_v1_revue_radio_week_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/relecture/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Pair */
        get: operations["read_pair_api_v1_revue_relecture__session_id__get"];
        put?: never;
        /** Post Answer */
        post: operations["post_answer_api_v1_revue_relecture__session_id__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/relecture/offer": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Offer */
        get: operations["read_offer_api_v1_revue_relecture_offer_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/releve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Releve
         * @description The learner's filed Papiers for Le Relevé.
         */
        get: operations["read_releve_api_v1_revue_releve_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Session */
        post: operations["start_session_api_v1_revue_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Session
         * @description Resume: a pure replay of the session's state. No model call, nothing written.
         */
        get: operations["read_session_api_v1_revue_sessions__session_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/sessions/{session_id}/close": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Close Session
         * @description Romy does something with it: the dispatch, the words and claims kept, her memory. Idempotent.
         */
        post: operations["close_session_api_v1_revue_sessions__session_id__close_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/sessions/{session_id}/make": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Make Options
         * @description The make options; the headline exercise is built once and reused, its answer never sent.
         */
        get: operations["read_make_options_api_v1_revue_sessions__session_id__make_get"];
        put?: never;
        /** Post Make */
        post: operations["post_make_api_v1_revue_sessions__session_id__make_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/sessions/{session_id}/turns": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Post Turn */
        post: operations["post_turn_api_v1_revue_sessions__session_id__turns_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/vignettes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Vignettes */
        get: operations["read_vignettes_api_v1_revue_vignettes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/revue/week": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Week
         * @description The week's recommended story, two alternatives, and any session to resume or already filed.
         */
        get: operations["read_week_api_v1_revue_week_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/serial/onboarding/seen": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark Serial Onboarding Seen */
        post: operations["mark_serial_onboarding_seen_api_v1_serial_onboarding_seen_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/serial/season": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Serial Season
         * @description The Feuilleton tab's season page (WP-44).
         *
         *     Read-only by construction: unlike `/threads/current/episodes` it does not
         *     call `get_or_create_thread`, because opening a tab is not a decision to
         *     begin a story. A learner with no thread gets the honest empty page.
         */
        get: operations["get_serial_season_api_v1_serial_season_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/serial/threads": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Serial Thread */
        post: operations["create_serial_thread_api_v1_serial_threads_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/serial/threads/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Serial Thread */
        post: operations["create_serial_thread_api_v1_serial_threads__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/serial/threads/{thread_id}/advance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Advance Serial Thread */
        post: operations["advance_serial_thread_api_v1_serial_threads__thread_id__advance_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/serial/threads/current/avatar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Set Current Serial Avatar */
        post: operations["set_current_serial_avatar_api_v1_serial_threads_current_avatar_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/serial/threads/current/cast": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Current Serial Cast */
        get: operations["get_current_serial_cast_api_v1_serial_threads_current_cast_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/serial/threads/current/episodes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Current Serial Episodes */
        get: operations["list_current_serial_episodes_api_v1_serial_threads_current_episodes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/serial/today": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Serial Today */
        get: operations["get_serial_today_api_v1_serial_today_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Sessions */
        get: operations["list_sessions_api_v1_sessions_get"];
        put?: never;
        /**
         * Create Session
         * @description Create a new learning session.
         */
        post: operations["create_session_api_v1_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/{session_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Session */
        get: operations["get_session_api_v1_sessions__session_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Update Session Status */
        patch: operations["update_session_status_api_v1_sessions__session_id__patch"];
        trace?: never;
    };
    "/api/v1/sessions/{session_id}/difficult_words": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Mark Word Difficult */
        post: operations["mark_word_difficult_api_v1_sessions__session_id__difficult_words_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/{session_id}/exposures": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Log Word Exposure */
        post: operations["log_word_exposure_api_v1_sessions__session_id__exposures_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/{session_id}/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Session Messages */
        get: operations["list_session_messages_api_v1_sessions__session_id__messages_get"];
        put?: never;
        /** Post Session Message */
        post: operations["post_session_message_api_v1_sessions__session_id__messages_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/{session_id}/moments/{moment_id}/skip": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Skip Session Moment */
        post: operations["skip_session_moment_api_v1_sessions__session_id__moments__moment_id__skip_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/{session_id}/moments/{moment_id}/submit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Submit Session Moment */
        post: operations["submit_session_moment_api_v1_sessions__session_id__moments__moment_id__submit_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/{session_id}/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Session Summary */
        get: operations["get_session_summary_api_v1_sessions__session_id__summary_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/live-stories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Live Stories
         * @description Fetch live headlines in the learner's target language for quick-start selection.
         */
        get: operations["get_live_stories_api_v1_sessions_live_stories_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sessions/quick-start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Quick Session
         * @description Create a new 'Zero Decision' learning session with auto-detected context.
         */
        post: operations["create_quick_session_api_v1_sessions_quick_start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Stories
         * @description List all available stories with user progress.
         */
        get: operations["list_stories_api_v1_stories_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Story
         * @description Get story details with user progress.
         */
        get: operations["get_story_api_v1_stories__story_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/chapter/{chapter_id}/cover": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Chapter Cover
         * @description Generate an AI cover image for a story chapter.
         */
        get: operations["get_chapter_cover_api_v1_stories__story_id__chapter__chapter_id__cover_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/chapters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Story Chapters
         * @description Get all chapters for a story with completion status.
         */
        get: operations["get_story_chapters_api_v1_stories__story_id__chapters_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/chapters/{chapter_id}/check-goals": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Check Chapter Goals
         * @description Check narrative goal completion for a chapter session using French morphological matching.
         */
        post: operations["check_chapter_goals_api_v1_stories__story_id__chapters__chapter_id__check_goals_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/chapters/{chapter_id}/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Complete Chapter
         * @description Complete a chapter and unlock the next one.
         */
        post: operations["complete_chapter_api_v1_stories__story_id__chapters__chapter_id__complete_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/discuss": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Story Discussion
         * @description Start a conversational session based on this story/article.
         */
        post: operations["start_story_discussion_api_v1_stories__story_id__discuss_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/input": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Process Story Input
         * @description Process player input in a story and get NPC response.
         */
        post: operations["process_story_input_api_v1_stories__story_id__input_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/make-choice": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Make Narrative Choice
         * @description Make a narrative branching choice and advance to the corresponding chapter.
         */
        post: operations["make_narrative_choice_api_v1_stories__story_id__make_choice_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/progress": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Story Progress
         * @description Get user's progress in a story.
         */
        get: operations["get_story_progress_api_v1_stories__story_id__progress_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/scene": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Current Scene
         * @description Get current scene for a story.
         */
        get: operations["get_current_scene_api_v1_stories__story_id__scene_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/scene/{scene_id}/visualization": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Scene Visualization
         * @description Generate an AI visualization for a story scene.
         *
         *     Returns a URL to a generated image that illustrates the scene.
         *     Results are cached for 1 week.
         *
         *     Args:
         *         style: Optional art style override (whimsical, dramatic, classic, minimal, fantasy)
         *         include_avatar: Whether to include user's avatar in the image
         */
        get: operations["get_scene_visualization_api_v1_stories__story_id__scene__scene_id__visualization_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/{story_id}/start": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Start Story
         * @description Start or resume a story.
         */
        post: operations["start_story_api_v1_stories__story_id__start_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import Content
         * @description Import content from URL (YouTube/Article).
         */
        post: operations["import_content_api_v1_stories_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/library": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Library Books
         * @description List private guided-reading books for the current learner.
         */
        get: operations["list_library_books_api_v1_stories_library_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/library/{book_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Library Book
         * @description Read one private guided-reading book plus episode summaries.
         */
        get: operations["get_library_book_api_v1_stories_library__book_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/library/{book_id}/episodes/{order_index}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Library Episode
         * @description Read a passage-grounded episode and its generated exercise payload.
         */
        get: operations["get_library_episode_api_v1_stories_library__book_id__episodes__order_index__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/library/{book_id}/episodes/{order_index}/complete": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Complete Library Episode
         * @description Mark a guided-reading episode complete and advance book progress.
         */
        post: operations["complete_library_episode_api_v1_stories_library__book_id__episodes__order_index__complete_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/library/upload": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Upload Library Book
         * @description Upload a book into the current user's private guided-reading library.
         */
        post: operations["upload_library_book_api_v1_stories_library_upload_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/upload-book": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Upload Book
         * @description Upload a book file and convert it to a private guided-reading library book.
         *     Returns a task_id to track progress.
         */
        post: operations["upload_book_api_v1_stories_upload_book_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stories/upload-status/{task_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Upload Status
         * @description Get DB-backed status for a guided-reading upload task.
         */
        get: operations["get_upload_status_api_v1_stories_upload_status__task_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/story-engine/archive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Archive
         * @description WP-96 «Archives du journal»: every day the learner lived, as seasons of
         *     chapters of planches — the authored first day and fallback days included.
         *     Newest chapter first, days oldest first; one season's days per call
         *     (``?season=N``, default the newest).
         */
        get: operations["archive_api_v1_story_engine_archive_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/story-engine/episodes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Episodes */
        get: operations["episodes_api_v1_story_engine_episodes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/story-engine/episodes/{scene_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Episode
         * @description One of the owner's pages with its panels — a day's episode, or (WP-93) the
         *     «Lecture» page a READ step names (yesterday's episode, or today's «Coulisses»).
         *     Anyone else's page, or an unknown id, is a 404.
         */
        get: operations["episode_api_v1_story_engine_episodes__scene_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/story-engine/episodes/{scene_id}/audio": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Audio Manifest
         * @description What is already spoken. Never starts a paid call.
         *
         *     A client opens with this so that a learner who has listened before — or on
         *     a second device — hears the episode without spending anything, and so that
         *     ``status: "disabled"`` reaches the page as data rather than as a 404.
         */
        get: operations["audio_manifest_api_v1_story_engine_episodes__scene_id__audio_get"];
        put?: never;
        /**
         * Synthesize Audio
         * @description Speak the episode, or say honestly that it is not spoken.
         *
         *     Idempotent by revision: the second call for the same scene text returns the
         *     stored clips and makes no request. The row lock is what keeps two devices —
         *     or a double tap — from paying twice for the same episode.
         */
        post: operations["synthesize_audio_api_v1_story_engine_episodes__scene_id__audio_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/story-engine/episodes/{scene_id}/audio/{clip_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Audio Clip
         * @description One spoken line.
         *
         *     Authorised through the scene, not through the clip's own ``user_id``: the
         *     scene is the thing the learner is allowed to read, and deriving the answer
         *     from it means a clip can never outlive that permission.
         */
        get: operations["audio_clip_api_v1_story_engine_episodes__scene_id__audio__clip_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/story-engine/episodes/{scene_id}/audio/prediction": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Prediction
         * @description Record what the learner predicted before listening.
         *
         *     Measurement, not marking: the response carries no score, nothing here
         *     reaches the capability rubric, and an ``unresolved`` scene is stored as
         *     unresolved rather than counted as a miss.
         */
        post: operations["prediction_api_v1_story_engine_episodes__scene_id__audio_prediction_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/story-engine/episodes/{scene_id}/position": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Position */
        put: operations["position_api_v1_story_engine_episodes__scene_id__position_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Users
         * @description Return a paginated list of users ordered by recency.
         */
        get: operations["list_users_api_v1_users__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read User By Id
         * @description Fetch a user profile when it is the current user or an admin request.
         */
        get: operations["read_user_by_id_api_v1_users__user_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Current User
         * @description Return the authenticated user profile.
         */
        get: operations["read_current_user_api_v1_users_me_get"];
        put?: never;
        post?: never;
        /**
         * Delete Current User
         * @description Permanently delete the authenticated user account.
         */
        delete: operations["delete_current_user_api_v1_users_me_delete"];
        options?: never;
        head?: never;
        /**
         * Update Current User
         * @description Allow the authenticated user to update their profile details.
         */
        patch: operations["update_current_user_api_v1_users_me_patch"];
        trace?: never;
    };
    "/api/v1/users/me/email": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Change Current User Email
         * @description Change the current user's email after password confirmation.
         */
        patch: operations["change_current_user_email_api_v1_users_me_email_patch"];
        trace?: never;
    };
    "/api/v1/users/me/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Export User Data
         * @description Export all user data as JSON for GDPR compliance.
         *
         *     Returns comprehensive data including:
         *     - User profile
         *     - Vocabulary progress
         *     - Grammar progress
         *     - Error tracking
         *     - Session history
         *     - Achievements
         */
        get: operations["export_user_data_api_v1_users_me_export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/users/me/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Change Current User Password
         * @description Change the current user's password and revoke existing sessions.
         */
        patch: operations["change_current_user_password_api_v1_users_me_password_patch"];
        trace?: never;
    };
    "/api/v1/users/me/settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Read Current User Settings
         * @description Return the authenticated user's editable settings bundle.
         */
        get: operations["read_current_user_settings_api_v1_users_me_settings_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Current User Settings
         * @description Update the authenticated user's account and app preferences.
         */
        patch: operations["update_current_user_settings_api_v1_users_me_settings_patch"];
        trace?: never;
    };
    "/api/v1/users/me/sign-out-all": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Sign Out All Devices
         * @description Sign out from all devices by invalidating all user sessions.
         *
         *     This forces re-authentication on all devices.
         *     Note: Actual implementation depends on session management strategy.
         *     For JWT, this would require a token blacklist or version increment.
         */
        post: operations["sign_out_all_devices_api_v1_users_me_sign_out_all_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Vocabulary
         * @description Return vocabulary items with optional pagination.
         */
        get: operations["list_vocabulary_api_v1_vocabulary__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/{word_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Vocabulary Word
         * @description Retrieve a vocabulary word by identifier.
         */
        get: operations["get_vocabulary_word_api_v1_vocabulary__word_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/{word_id}/biography": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Vocabulary Word Biography
         * @description Return a concise, user-aware memory thread for a vocabulary word.
         */
        get: operations["get_vocabulary_word_biography_api_v1_vocabulary__word_id__biography_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/band-check": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Band Checks
         * @description The sub-bands below the learner's level whose words a short check can credit.
         */
        get: operations["list_band_checks_api_v1_vocabulary_band_check_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/band-check/{sub_band}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Start Band Check
         * @description This attempt's check for one sub-band: meaning choices, no answer key.
         */
        get: operations["start_band_check_api_v1_vocabulary_band_check__sub_band__get"];
        put?: never;
        /**
         * Submit Band Check
         * @description Grade the check; a pass credits the band (sampled) and the bands below (inferred).
         */
        post: operations["submit_band_check_api_v1_vocabulary_band_check__sub_band__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/band-check/ladder": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Band Check Ladder
         * @description WP-127: the top-down check — the next band to check, or why there is none.
         */
        get: operations["band_check_ladder_api_v1_vocabulary_band_check_ladder_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/conjugation/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Conjugation Review Queue
         * @description Return due/new irregular conjugation drill prompts.
         */
        get: operations["get_conjugation_review_queue_api_v1_vocabulary_conjugation_review_get"];
        put?: never;
        /**
         * Submit Conjugation Review
         * @description Rate an irregular conjugation item.
         */
        post: operations["submit_conjugation_review_api_v1_vocabulary_conjugation_review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/coverage": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Vocabulary Coverage
         * @description Return the three-axis coverage map for the learner.
         */
        get: operations["get_vocabulary_coverage_api_v1_vocabulary_coverage_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/due-context": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Vocabulary Due Context
         * @description Return SRS and contextual vocabulary buckets for mobile practice surfaces.
         */
        get: operations["get_vocabulary_due_context_api_v1_vocabulary_due_context_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/keep": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Keep Vocabulary Word
         * @description WP-78 — keep a tapped word in the learner's Lexique, with its sentence.
         *
         *     Learner-scoped by construction (``app/services/kept_words.py``): the shared
         *     catalogue row is never written. Idempotent for the same word and sentence.
         */
        post: operations["keep_vocabulary_word_api_v1_vocabulary_keep_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/lookup": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Lookup Vocabulary Word
         * @description Lookup a vocabulary word by its surface form.
         */
        get: operations["lookup_vocabulary_word_api_v1_vocabulary_lookup_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vocabulary/words-of-the-day": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Words Of The Day
         * @description Return today's coordinated word slate, selecting it on first call.
         */
        get: operations["get_words_of_the_day_api_v1_vocabulary_words_of_the_day_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AbsenceView
         * @description WP-99 «Pendant votre absence». Present from two missed days, else ``null``.
         *
         *     ``greeting_fr`` is the scene's own line for the gap (the engine writes
         *     ``script_payload.absence``), ``null`` when there is none; ``entre_temps`` is
         *     at most five beats, oldest first, since the last finished day.
         */
        AbsenceView: {
            /** Days */
            days: number;
            /** Entre Temps */
            entre_temps: components["schemas"]["EntreTempsItem"][];
            /** Greeting Fr */
            greeting_fr: string | null;
            /** Lapsed Letters */
            lapsed_letters: components["schemas"]["LapsedLetter"][];
        };
        /**
         * AchievementProgressResponse
         * @description User achievement progress schema.
         */
        AchievementProgressResponse: {
            /** Achievement Id */
            achievement_id: number;
            /** Achievement Key */
            achievement_key: string;
            /** Completed */
            completed: boolean;
            /** Current Progress */
            current_progress: number;
            /** Description */
            description?: string | null;
            /** Icon Url */
            icon_url?: string | null;
            /** Name */
            name: string;
            /** Target Progress */
            target_progress: number;
            /** Tier */
            tier: string;
            /** Unlocked At */
            unlocked_at?: string | null;
            /** Xp Reward */
            xp_reward: number;
        };
        /**
         * AchievementUnlockResponse
         * @description Response after checking for achievement unlocks.
         */
        AchievementUnlockResponse: {
            /** Newly Unlocked */
            newly_unlocked?: components["schemas"]["app__schemas__achievement__AchievementRead"][];
            /** Total Unlocked */
            total_unlocked: number;
        };
        /**
         * AnalyticsStatisticsResponse
         * @description Rolling analytics metrics.
         */
        AnalyticsStatisticsResponse: {
            /** Accuracy */
            accuracy?: components["schemas"]["MetricPoint"][];
            /** Minutes Practiced */
            minutes_practiced?: components["schemas"]["MetricPoint"][];
            /** Reviews Completed */
            reviews_completed?: components["schemas"]["MetricPoint"][];
            /** Xp Earned */
            xp_earned?: components["schemas"]["MetricPoint"][];
        };
        /**
         * AnalyticsSummary
         * @description Headline learner statistics.
         */
        AnalyticsSummary: {
            /** Accuracy Rate */
            accuracy_rate?: number | null;
            /** Average Minutes */
            average_minutes: number;
            /** Current Streak */
            current_streak: number;
            /** Last Session At */
            last_session_at?: string | null;
            /** Longest Streak */
            longest_streak: number;
            /** Reviews Due Today */
            reviews_due_today: number;
            /** Reviews Due Week */
            reviews_due_week: number;
            /** Sessions Completed */
            sessions_completed: number;
            /** Total Minutes */
            total_minutes: number;
            /** Words Learning */
            words_learning: number;
            /** Words Mastered */
            words_mastered: number;
            /** Xp Earned */
            xp_earned: number;
        };
        /**
         * AnkiCardUpdate
         * @description Data for a single card from AnkiConnect.
         */
        AnkiCardUpdate: {
            /** Card Id */
            card_id: number;
            /** Deck Name */
            deck_name: string;
            /** Due */
            due?: number | null;
            /** Ease */
            ease?: number | null;
            /** Fields */
            fields: {
                [key: string]: string;
            };
            /** Interval */
            interval?: number | null;
            /** Lapses */
            lapses?: number | null;
            /** Model Name */
            model_name: string;
            /** Note Id */
            note_id: number;
            /** Ord */
            ord?: number | null;
            /** Reps */
            reps?: number | null;
        };
        /**
         * AnkiConnectSyncRequest
         * @description Payload for syncing data from AnkiConnect.
         */
        AnkiConnectSyncRequest: {
            /** Cards */
            cards: components["schemas"]["AnkiCardUpdate"][];
        };
        /**
         * AnkiDirectionSummary
         * @description Per-direction breakdown for Anki progress.
         */
        AnkiDirectionSummary: {
            /** Direction */
            direction: string;
            /** Due Today */
            due_today: number;
            /** Stage Counts */
            stage_counts: {
                [key: string]: number;
            };
            /** Total */
            total: number;
        };
        /**
         * AnkiDueCardsStatistics
         * @description Statistics about cards due for review.
         */
        AnkiDueCardsStatistics: {
            /**
             * Anki Scheduler
             * @description Cards due using Anki scheduler
             */
            anki_scheduler: number;
            /**
             * Fsrs Scheduler
             * @description Cards due using FSRS scheduler
             */
            fsrs_scheduler: number;
            /**
             * Total
             * @description Total cards due
             */
            total: number;
        };
        /**
         * AnkiImportRequest
         * @description Request schema for importing Anki cards from CSV text.
         */
        AnkiImportRequest: {
            /**
             * Csv Content
             * @description CSV content from Anki export
             */
            csv_content: string;
            /**
             * Deck Name
             * @description Optional deck name override
             */
            deck_name?: string | null;
            /**
             * Preserve Scheduling
             * @description Whether to preserve existing Anki scheduling data
             * @default true
             */
            preserve_scheduling?: boolean;
        };
        /**
         * AnkiImportResponse
         * @description Response schema for Anki import operations.
         */
        AnkiImportResponse: {
            /**
             * Message
             * @description Human-readable result message
             */
            message: string;
            /**
             * Statistics
             * @description Detailed import statistics
             */
            statistics: {
                [key: string]: unknown;
            };
            /**
             * Success
             * @description Whether the import was successful
             */
            success: boolean;
        };
        /**
         * AnkiProgressSummary
         * @description Aggregate Anki progress metrics.
         */
        AnkiProgressSummary: {
            /** Chart */
            chart: components["schemas"]["AnkiStageSlice"][];
            /** Directions */
            directions: {
                [key: string]: components["schemas"]["AnkiDirectionSummary"];
            };
            /** Due Today */
            due_today: number;
            /** Stage Totals */
            stage_totals: {
                [key: string]: number;
            };
            /** Total Cards */
            total_cards: number;
        };
        /**
         * AnkiReviewRequest
         * @description Payload for submitting an Anki-style review.
         */
        AnkiReviewRequest: {
            /** Answer Text */
            answer_text?: string | null;
            /** Correct */
            correct?: boolean | null;
            /** Direction */
            direction?: ("fr_to_native" | "native_to_fr") | null;
            /** Format */
            format?: ("flashcard" | "typed" | "cloze" | "audio" | "choice" | "spoken") | null;
            /**
             * Rating
             * @description Anki rating 0=Again,1=Hard,2=Good,3=Easy
             */
            rating: number;
            /** Response Time Ms */
            response_time_ms?: number | null;
            /** Word Id */
            word_id: number;
        };
        /**
         * AnkiReviewResponse
         * @description Response for an Anki review submission.
         */
        AnkiReviewResponse: {
            /** Correct */
            correct?: boolean | null;
            /** Due At */
            due_at?: string | null;
            /** Ease Factor */
            ease_factor?: number | null;
            /** Expected */
            expected?: string | null;
            /** Interval Days */
            interval_days?: number | null;
            /** Next Review */
            next_review?: string | null;
            /** Note Native */
            note_native?: string | null;
            /** Phase */
            phase?: string | null;
            /**
             * Scheduler
             * @default anki
             */
            scheduler?: string;
            /** Word Id */
            word_id: number;
        };
        /**
         * AnkiReviewStatistics
         * @description Statistics about review performance.
         */
        AnkiReviewStatistics: {
            /**
             * Anki Reviews
             * @description Reviews using Anki SM-2 scheduler
             */
            anki_reviews: number;
            /**
             * Average Rating
             * @description Average rating across all reviews
             */
            average_rating: number;
            /**
             * Fsrs Reviews
             * @description Reviews using FSRS scheduler
             */
            fsrs_reviews: number;
            /**
             * Period Days
             * @description Period covered by statistics in days
             */
            period_days: number;
            /**
             * Total Reviews
             * @description Total reviews in the period
             */
            total_reviews: number;
        };
        /**
         * AnkiStageSlice
         * @description Slice element for chart visualisation.
         */
        AnkiStageSlice: {
            /** Stage */
            stage: string;
            /** Value */
            value: number;
        };
        /**
         * AnkiStatisticsResponse
         * @description Complete statistics response for Anki integration.
         */
        AnkiStatisticsResponse: {
            due_cards: components["schemas"]["AnkiDueCardsStatistics"];
            import_statistics: components["schemas"]["AnkiVocabularyStatistics"];
            review_statistics: components["schemas"]["AnkiReviewStatistics"];
        };
        /**
         * AnkiVocabularyStatistics
         * @description Statistics about imported Anki vocabulary.
         */
        AnkiVocabularyStatistics: {
            /**
             * French To German Cards
             * @description Number of French→German cards
             */
            french_to_german_cards: number;
            /**
             * German To French Cards
             * @description Number of German→French cards
             */
            german_to_french_cards: number;
            /**
             * Paired Cards
             * @description Total cards that are part of pairs
             */
            paired_cards: number;
            /**
             * Total Vocabulary
             * @description Total vocabulary words from Anki
             */
            total_vocabulary: number;
            /**
             * Unique Pairs
             * @description Number of unique vocabulary pairs
             */
            unique_pairs: number;
            /**
             * User Progress Entries
             * @description User progress entries for Anki cards
             */
            user_progress_entries: number;
        };
        /**
         * AnkiWordProgressRead
         * @description Overview entry for an imported Anki card and its progress.
         */
        AnkiWordProgressRead: {
            /** Deck Name */
            deck_name?: string | null;
            /** Difficulty Level */
            difficulty_level?: number | null;
            /** Direction */
            direction?: string | null;
            /** Due At */
            due_at?: string | null;
            /** Ease Factor */
            ease_factor?: number | null;
            /** English Translation */
            english_translation?: string | null;
            /** French Translation */
            french_translation?: string | null;
            /** German Translation */
            german_translation?: string | null;
            /** Interval Days */
            interval_days?: number | null;
            /** Language */
            language: string;
            /**
             * Lapses
             * @default 0
             */
            lapses?: number;
            /** Last Review */
            last_review?: string | null;
            /** Learning Stage */
            learning_stage: string;
            /** Next Review */
            next_review?: string | null;
            /**
             * Proficiency Score
             * @default 0
             */
            proficiency_score?: number;
            /** Progress Difficulty */
            progress_difficulty?: number | null;
            /**
             * Reps
             * @default 0
             */
            reps?: number;
            /** Scheduler */
            scheduler?: string | null;
            /** State */
            state: string;
            /** Word */
            word: string;
            /** Word Id */
            word_id: number;
        };
        /** AnonymousClientErrorRequest */
        AnonymousClientErrorRequest: {
            /** Message */
            message: string;
            /** Release */
            release?: string | null;
            /** Route */
            route?: string | null;
            /**
             * Source
             * @default web
             */
            source?: string;
            /** Stack */
            stack?: string | null;
        };
        /**
         * AchievementRead
         * @description Achievement with unlock status.
         */
        app__api__v1__endpoints__grammar__AchievementRead: {
            /** Category */
            category: string | null;
            /** Description */
            description: string | null;
            /** Icon Url */
            icon_url: string | null;
            /** Id */
            id: number;
            /** Is Unlocked */
            is_unlocked: boolean;
            /** Key */
            key: string;
            /** Name */
            name: string;
            /** Progress */
            progress: number;
            /** Tier */
            tier: string;
            /** Unlocked At */
            unlocked_at: string | null;
            /** Xp Reward */
            xp_reward: number;
        };
        /**
         * AchievementRead
         * @description Achievement definition schema.
         */
        app__schemas__achievement__AchievementRead: {
            /** Achievement Key */
            achievement_key: string;
            /** Description */
            description?: string | null;
            /** Icon Url */
            icon_url?: string | null;
            /** Id */
            id: number;
            /** Name */
            name: string;
            /** Tier */
            tier: string;
            /** Xp Reward */
            xp_reward: number;
        };
        /** ArchiveChapter */
        ArchiveChapter: {
            /**
             * Closed
             * @default false
             */
            closed?: boolean;
            /** Days */
            days?: components["schemas"]["ArchiveDay"][];
            /** Digest Fr */
            digest_fr?: string | null;
            /**
             * Finale
             * @default false
             */
            finale?: boolean;
            /** Index */
            index: number;
            /**
             * Prologue
             * @default false
             */
            prologue?: boolean;
            /** Title Fr */
            title_fr: string;
        };
        /** ArchiveCurrent */
        ArchiveCurrent: {
            /** Chapter */
            chapter?: number | null;
            /** Season */
            season: number;
        };
        /**
         * ArchiveDay
         * @description One planche: a day the learner lived, engine-written or authored.
         */
        ArchiveDay: {
            /**
             * Authored
             * @default false
             */
            authored?: boolean;
            /** Can Do Id */
            can_do_id?: string | null;
            /** Character Id */
            character_id?: string | null;
            /** Date */
            date: string;
            /** Edition No */
            edition_no?: number | null;
            /** Ending Fr */
            ending_fr?: string | null;
            /** Image Url */
            image_url?: string | null;
            /** Journey Id */
            journey_id: string;
            /** Learner Lines */
            learner_lines?: string[];
            /** Margin Notes */
            margin_notes?: components["schemas"]["MarginNote"][];
            /** Panels */
            panels?: components["schemas"]["ArchivePanel"][] | null;
            /** Scene Id */
            scene_id?: string | null;
            /** Special */
            special?: "epreuve" | null;
            /** Title Fr */
            title_fr: string;
        };
        /**
         * ArchivePanel
         * @description One panel of an authored day's page (the first day, a fallback day).
         */
        ArchivePanel: {
            /** Dialogue */
            dialogue?: components["schemas"]["ArchivePanelLine"][];
            /** Id */
            id: string;
            /** Image Url */
            image_url?: string | null;
            /** Index */
            index: number;
            /**
             * Narration Fr
             * @default
             */
            narration_fr?: string;
        };
        /** ArchivePanelLine */
        ArchivePanelLine: {
            /** Character Id */
            character_id: string;
            /** Character Name */
            character_name?: string | null;
            /** Text Fr */
            text_fr: string;
        };
        /** ArchiveSeason */
        ArchiveSeason: {
            /** Chapters */
            chapters?: components["schemas"]["ArchiveChapter"][];
            /**
             * Day Count
             * @default 0
             */
            day_count?: number;
            /**
             * Finished
             * @default false
             */
            finished?: boolean;
            /**
             * Loaded
             * @default false
             */
            loaded?: boolean;
            /** Number */
            number: number;
            /** Title Fr */
            title_fr: string;
        };
        /**
         * AssistanceLevel
         * @description Server-recorded assistance. Never taken from a client self-report.
         * @enum {string}
         */
        AssistanceLevel: "none" | "hint" | "translation" | "solution" | "suggested_response";
        /**
         * AssistantTurnRead
         * @description Assistant message accompanied by vocabulary plan.
         */
        AssistantTurnRead: {
            /**
             * Learning Focus
             * @description Normalized list of vocabulary, grammar, and error cues for the current learning moment
             */
            learning_focus?: components["schemas"]["LearningFocusRead"][];
            message: components["schemas"]["SessionMessageRead"];
            pending_moment?: components["schemas"]["LearningMomentRead"] | null;
            /**
             * Targeted Errors
             * @description Error patterns the assistant is subtly targeting for correction
             */
            targeted_errors?: components["schemas"]["TargetedErrorRead"][];
            /** Targets */
            targets?: components["schemas"]["TargetWordRead"][];
        };
        /** AtelierActiveSessionResponse */
        AtelierActiveSessionResponse: {
            session?: components["schemas"]["AtelierSessionStartResponse"] | null;
        };
        /** AtelierAlmanacResponse */
        AtelierAlmanacResponse: {
            /** Collectibles */
            collectibles?: {
                [key: string]: components["schemas"]["AtelierCollectibleRead"][];
            };
            /** Plates */
            plates?: components["schemas"]["AtelierPlateRead"][];
            /** Progress */
            progress?: {
                [key: string]: components["schemas"]["AtelierWorkshopProgressRead"];
            };
            /** Totals */
            totals?: {
                [key: string]: number;
            };
        };
        /** AtelierAttemptRepairRequest */
        AtelierAttemptRepairRequest: {
            /**
             * Erratum Index
             * @default 0
             */
            erratum_index?: number;
            /** Text */
            text: string;
        };
        /** AtelierAttemptRequest */
        AtelierAttemptRequest: {
            /** Answer Payload */
            answer_payload?: {
                [key: string]: unknown;
            };
            /** Concept Id */
            concept_id?: number | null;
            /** Confidence */
            confidence?: ("sure" | "unsure") | null;
            /** Exercise Id */
            exercise_id: string;
            /** Mode */
            mode: string;
            /**
             * Resubmit
             * @default false
             */
            resubmit?: boolean;
            /** Retest Source Attempt Id */
            retest_source_attempt_id?: string | null;
            /** Round */
            round: string;
        };
        /** AtelierAttemptResponse */
        AtelierAttemptResponse: {
            /** Ai Review */
            ai_review?: {
                [key: string]: unknown;
            };
            /**
             * Attempt Id
             * Format: uuid
             */
            attempt_id: string;
            /** Correction */
            correction: {
                [key: string]: unknown;
            };
            /** Forge */
            forge?: {
                [key: string]: unknown;
            };
            /** Local Status */
            local_status?: string | null;
            /** Minted Collectibles */
            minted_collectibles?: components["schemas"]["AtelierCollectibleRead"][];
            /** Score 0 4 */
            score_0_4: number;
            /** Verdict */
            verdict: string;
        };
        /** AtelierCollectibleRead */
        AtelierCollectibleRead: {
            /**
             * Composed
             * @default false
             */
            composed?: boolean;
            /** Composed Into Id */
            composed_into_id?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Kind */
            kind: string;
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            };
            /** Minted At */
            minted_at?: string | null;
            /** Source Kind */
            source_kind: string;
            /** Source Ref */
            source_ref: string;
        };
        /** AtelierCompleteResponse */
        AtelierCompleteResponse: {
            /** Minted Collectibles */
            minted_collectibles?: components["schemas"]["AtelierCollectibleRead"][];
            /** Recap */
            recap: {
                [key: string]: unknown;
            };
            /**
             * Session Id
             * Format: uuid
             */
            session_id: string;
        };
        /** AtelierConceptRead */
        AtelierConceptRead: {
            /** Anchor Examples */
            anchor_examples?: string[];
            /** Atelier Blueprint */
            atelier_blueprint?: {
                [key: string]: unknown;
            };
            /** Category */
            category?: string | null;
            /** Category Label Fr */
            category_label_fr?: string | null;
            /** Coach */
            coach?: {
                [key: string]: unknown;
            } | null;
            /** Core Rule */
            core_rule?: string | null;
            /** Due Errata */
            due_errata?: {
                [key: string]: unknown;
            }[];
            /** Exercise Tags */
            exercise_tags?: string[];
            /** External Id */
            external_id?: string | null;
            /** Id */
            id: number;
            /**
             * Is Foundation
             * @default false
             */
            is_foundation?: boolean;
            /** Level */
            level: string;
            /** Main Traps */
            main_traps?: string[];
            /**
             * Mastery
             * @default 0
             */
            mastery?: number;
            /** Name */
            name: string;
            /** Next Review */
            next_review?: string | null;
            /** Role */
            role?: string | null;
            /** Rule Card */
            rule_card?: {
                [key: string]: unknown;
            } | null;
            /** Subskill */
            subskill?: string | null;
            /** Title Fr */
            title_fr?: string | null;
        };
        /**
         * AtelierErrataAttemptRequest
         * @description An empty body is not an answer.
         *
         *     `answer_text: str = ""` let a missing or blank field through, and the service
         *     graded it as a wrong attempt: rating 1, `needs_repair`, one more lapse, the
         *     erratum pushed into `relearning`. A learner's memory strength must never be
         *     moved by a request that carried no answer.
         */
        AtelierErrataAttemptRequest: {
            /** Answer Text */
            answer_text: string;
        };
        /** AtelierErrataAttemptResponse */
        AtelierErrataAttemptResponse: {
            /** Answer Text */
            answer_text: string;
            /** Closure */
            closure?: {
                [key: string]: unknown;
            } | null;
            /** Erratum */
            erratum: {
                [key: string]: unknown;
            };
            /** Feedback */
            feedback: string;
            /** Is Correct */
            is_correct: boolean;
            /** Score 0 4 */
            score_0_4: number;
            /** Target Answer */
            target_answer: string;
            /** Task */
            task: {
                [key: string]: unknown;
            };
            /** Verdict */
            verdict: string;
        };
        /** AtelierErrataReviewRequest */
        AtelierErrataReviewRequest: {
            /**
             * Rating
             * @default 4
             */
            rating?: number;
            /**
             * Repaired
             * @default true
             */
            repaired?: boolean;
        };
        /** AtelierErrataReviewResponse */
        AtelierErrataReviewResponse: {
            /** Erratum */
            erratum: {
                [key: string]: unknown;
            };
        };
        /** AtelierErrataTaskResponse */
        AtelierErrataTaskResponse: {
            /** Task */
            task: {
                [key: string]: unknown;
            };
        };
        /** AtelierExerciseReportRequest */
        AtelierExerciseReportRequest: {
            /** Concept Id */
            concept_id?: number | null;
            /** Exercise Id */
            exercise_id?: string | null;
            /** Exercise Set Id */
            exercise_set_id?: string | null;
            /** Item Id */
            item_id?: string | null;
            /** Mode */
            mode?: string | null;
            /** Reason */
            reason: string;
            /** Round */
            round?: string | null;
            /** Session Id */
            session_id?: string | null;
        };
        /** AtelierExerciseReportResponse */
        AtelierExerciseReportResponse: {
            /**
             * Event Id
             * Format: uuid
             */
            event_id: string;
            /** Ok */
            ok: boolean;
        };
        /** AtelierForgeStateResponse */
        AtelierForgeStateResponse: {
            /** Rules */
            rules?: {
                [key: string]: unknown;
            }[];
        };
        /** AtelierForgeTestOutRequest */
        AtelierForgeTestOutRequest: {
            /** Concept Id */
            concept_id: number;
            /**
             * Short
             * @default false
             */
            short?: boolean;
            /** Source */
            source?: ("journey" | "cahier" | "forge") | null;
        };
        /** AtelierPlateRead */
        AtelierPlateRead: {
            /**
             * Composed
             * @default false
             */
            composed?: boolean;
            /** Composed Into Id */
            composed_into_id?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Kind */
            kind: string;
            /** Members */
            members?: components["schemas"]["AtelierCollectibleRead"][];
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            };
            /** Minted At */
            minted_at?: string | null;
            /** Source Kind */
            source_kind: string;
            /** Source Ref */
            source_ref: string;
        };
        /** AtelierSessionStartRequest */
        AtelierSessionStartRequest: {
            /** Budget Seconds */
            budget_seconds?: number | null;
            /** Concept Ids */
            concept_ids?: number[] | null;
            /** Journey Step Id */
            journey_step_id?: string | null;
            /** Origin */
            origin?: ("journey" | "after_day" | "practice") | null;
            /** Preferred Concept Id */
            preferred_concept_id?: number | null;
            /** Preferred Vocabulary Ids */
            preferred_vocabulary_ids?: number[] | null;
        };
        /** AtelierSessionStartResponse */
        AtelierSessionStartResponse: {
            /** Attempts */
            attempts?: {
                [key: string]: unknown;
            }[];
            /** Concepts */
            concepts: components["schemas"]["AtelierConceptRead"][];
            /** Current Position */
            current_position?: {
                [key: string]: unknown;
            };
            /** Due Errata */
            due_errata?: {
                [key: string]: unknown;
            }[];
            /** Exercise Sets */
            exercise_sets: {
                [key: string]: unknown;
            }[];
            /** Forge */
            forge?: {
                [key: string]: unknown;
            };
            /** Learning Moments */
            learning_moments?: {
                [key: string]: unknown;
            };
            /** Quote */
            quote: {
                [key: string]: unknown;
            };
            /** Recap */
            recap?: {
                [key: string]: unknown;
            };
            /**
             * Session Id
             * Format: uuid
             */
            session_id: string;
            /** Status */
            status: string;
            /** Submitted Map */
            submitted_map?: {
                [key: string]: boolean;
            };
            /** Target Vocabulary */
            target_vocabulary?: {
                [key: string]: unknown;
            }[];
            /** Target Vocabulary Ids */
            target_vocabulary_ids?: number[];
        };
        /** AtelierTodayResponse */
        AtelierTodayResponse: {
            /** Atlas */
            atlas: {
                [key: string]: unknown;
            }[];
            /** Cefr */
            cefr?: {
                [key: string]: unknown;
            };
            /** Concepts */
            concepts: components["schemas"]["AtelierConceptRead"][];
            /** Due Errata */
            due_errata?: {
                [key: string]: unknown;
            }[];
            /** Intake */
            intake?: {
                [key: string]: unknown;
            } | null;
            /** Library Episode */
            library_episode?: {
                [key: string]: unknown;
            } | null;
            /** Onboarding */
            onboarding?: {
                [key: string]: unknown;
            };
            /** Phrase Of Day */
            phrase_of_day?: {
                [key: string]: unknown;
            } | null;
            /** Progress */
            progress?: {
                [key: string]: unknown;
            };
            /** Quote */
            quote: {
                [key: string]: unknown;
            };
            /** Serial */
            serial?: {
                [key: string]: unknown;
            } | null;
            /** Serial Episode */
            serial_episode?: {
                [key: string]: unknown;
            } | null;
            /** Streak */
            streak?: {
                [key: string]: unknown;
            } | null;
            /** Summary */
            summary: {
                [key: string]: unknown;
            };
        };
        /** AtelierWorkshopComposeRequest */
        AtelierWorkshopComposeRequest: {
            /**
             * Target
             * @enum {string}
             */
            target: "plate_semaine" | "plate_chapter" | "colophon";
        };
        /** AtelierWorkshopComposeResponse */
        AtelierWorkshopComposeResponse: {
            /** Members */
            members?: components["schemas"]["AtelierCollectibleRead"][];
            /** Minted Collectibles */
            minted_collectibles?: components["schemas"]["AtelierCollectibleRead"][];
            plate: components["schemas"]["AtelierCollectibleRead"];
            /** Progress */
            progress?: {
                [key: string]: components["schemas"]["AtelierWorkshopProgressRead"];
            };
        };
        /** AtelierWorkshopProgressRead */
        AtelierWorkshopProgressRead: {
            /** Available */
            available: number;
            /** Member Kind */
            member_kind: string;
            /** Progress */
            progress: number;
            /** Required */
            required: number;
            /** Shortfall */
            shortfall: number;
            /** Target */
            target: string;
        };
        /** AttemptResult */
        AttemptResult: {
            assistance_level: components["schemas"]["AssistanceLevel"];
            /** Character Lines */
            character_lines: components["schemas"]["ThreadLine"][];
            /** Character Reply Fr */
            character_reply_fr: string | null;
            /**
             * Contract Version
             * @default 1
             * @constant
             */
            contract_version: 1;
            correction: components["schemas"]["JourneyCorrection"] | null;
            /** Evidence Ref */
            evidence_ref: string;
            journey: components["schemas"]["JourneySnapshot"];
            next_turn: components["schemas"]["NextTurn"] | null;
            /**
             * Pending
             * @default false
             */
            pending: boolean;
            /**
             * Reply Source
             * @default none
             * @enum {string}
             */
            reply_source: "authored" | "model" | "none";
            /** Slip Note Native */
            slip_note_native: string | null;
            task_outcome: components["schemas"]["TaskOutcome"];
        };
        /**
         * AudioSessionEndRequest
         * @description Request to end an audio session.
         */
        AudioSessionEndRequest: {
            /** Session Id */
            session_id: string;
        };
        /**
         * AudioSessionEndResponse
         * @description Summary when ending an audio session.
         */
        AudioSessionEndResponse: {
            /** Cast Memory */
            cast_memory?: {
                [key: string]: unknown;
            } | null;
            /** Due Words Reused */
            due_words_reused?: string[];
            /** Duration Seconds */
            duration_seconds: number;
            /** Errors Practiced */
            errors_practiced: number;
            /** Longest Answer */
            longest_answer: string;
            /** Longest Answer Words */
            longest_answer_words: number;
            /** Message */
            message: string;
            /** Produced Words */
            produced_words: number;
            /** Session Id */
            session_id: string;
            /** Tomorrow Focus */
            tomorrow_focus: string;
            /** Total Xp */
            total_xp: number;
            /** Turns */
            turns: number;
        };
        /**
         * AudioSessionMessageRequest
         * @description User's transcribed speech.
         */
        AudioSessionMessageRequest: {
            /** Conversation History */
            conversation_history?: {
                [key: string]: unknown;
            }[];
            /** Session Id */
            session_id: string;
            /** User Text */
            user_text: string;
        };
        /**
         * AudioSessionMessageResponse
         * @description AI response to user's message.
         */
        AudioSessionMessageResponse: {
            /** Ai Audio Text */
            ai_audio_text: string;
            /** Ai Response */
            ai_response: string;
            /** Detected Errors */
            detected_errors?: {
                [key: string]: unknown;
            }[];
            /** Minted Collectibles */
            minted_collectibles?: {
                [key: string]: unknown;
            }[];
            /**
             * Should Show Text
             * @default false
             */
            should_show_text?: boolean;
            /** Vocabulary Credit */
            vocabulary_credit?: {
                [key: string]: unknown;
            };
            /**
             * Xp Awarded
             * @default 0
             */
            xp_awarded?: number;
        };
        /**
         * AudioSessionStartRequest
         * @description Request to start an audio session.
         */
        AudioSessionStartRequest: {
            /** Scenario Id */
            scenario_id?: string | null;
        };
        /**
         * AudioSessionStartResponse
         * @description Response when starting an audio session.
         */
        AudioSessionStartResponse: {
            /** Context */
            context: {
                [key: string]: unknown;
            };
            /** Opening Audio Text */
            opening_audio_text: string;
            /** Opening Message */
            opening_message: string;
            /** Session Id */
            session_id: string;
        };
        /** BandCheckItem */
        BandCheckItem: {
            /** Fr */
            fr: string;
            /** Id */
            id: string;
            /** Options */
            options: string[];
        };
        /**
         * BandCheckLadder
         * @description WP-127: the top-down check — where it stands and what to check next.
         */
        BandCheckLadder: {
            /** Bands */
            bands: components["schemas"]["BandCheckSubBand"][];
            /** Items Per Check */
            items_per_check: number;
            /** Max Checks Per Visit */
            max_checks_per_visit: number;
            /** Next */
            next?: string | null;
            /** Pass Correct */
            pass_correct: number;
            /** Policy Version */
            policy_version: string;
            /** Resume Band */
            resume_band?: string | null;
            /** Status */
            status: string;
            /** Visit Checks Left */
            visit_checks_left: number;
            /** Visit Checks Used */
            visit_checks_used: number;
        };
        /** BandCheckResult */
        BandCheckResult: {
            /** Attempt Id */
            attempt_id?: string | null;
            /** Correct */
            correct: number;
            /**
             * Credited Inferred
             * @default 0
             */
            credited_inferred?: number;
            /**
             * Credited Sampled
             * @default 0
             */
            credited_sampled?: number;
            /** Credited Words */
            credited_words: number;
            /** Inferred Bands */
            inferred_bands?: string[];
            /** Ladder Status */
            ladder_status?: string | null;
            /** Missed */
            missed: string[];
            /** Next */
            next?: string | null;
            /** Pass Correct */
            pass_correct?: number | null;
            /** Passed */
            passed: boolean;
            /** Policy Version */
            policy_version?: string | null;
            /**
             * Replayed
             * @default false
             */
            replayed?: boolean;
            /** Resume Band */
            resume_band?: string | null;
            /** Sub Band */
            sub_band: string;
            /** Total */
            total: number;
        };
        /** BandCheckStart */
        BandCheckStart: {
            /** Attempt Id */
            attempt_id?: string | null;
            /** Items */
            items: components["schemas"]["BandCheckItem"][];
            /** Pass Correct */
            pass_correct?: number | null;
            /** Pass Share */
            pass_share: number;
            /** Policy Version */
            policy_version?: string | null;
            /** Sub Band */
            sub_band: string;
        };
        /** BandCheckSubBand */
        BandCheckSubBand: {
            /** Credit Kind */
            credit_kind?: string | null;
            /** Credited */
            credited: boolean;
            /**
             * Missed
             * @default false
             */
            missed?: boolean;
            /** Sub Band */
            sub_band: string;
            /** Words */
            words: number;
        };
        /** BandCheckSubmit */
        BandCheckSubmit: {
            /** Answers */
            answers?: {
                [key: string]: number | null;
            };
            /** Attempt Id */
            attempt_id?: string | null;
        };
        /** Body_import_anki_cards_api_v1_anki_import_post */
        Body_import_anki_cards_api_v1_anki_import_post: {
            /**
             * Deck Name
             * @description Override deck name
             */
            deck_name?: string | null;
            /**
             * File
             * Format: binary
             * @description Anki CSV export file
             */
            file: string;
            /**
             * Preserve Scheduling
             * @description Preserve Anki scheduling data
             * @default true
             */
            preserve_scheduling?: boolean;
        };
        /** Body_submit_photo_api_v1_intake_photo_post */
        Body_submit_photo_api_v1_intake_photo_post: {
            /**
             * File
             * Format: binary
             */
            file: string;
        };
        /** Body_transcribe_audio_api_v1_audio_transcribe_post */
        Body_transcribe_audio_api_v1_audio_transcribe_post: {
            /**
             * File
             * Format: binary
             */
            file: string;
            /**
             * Surface
             * @default unknown
             */
            surface?: string;
        };
        /** Body_transcribe_mission_audio_api_v1_missions_audio_transcribe_post */
        Body_transcribe_mission_audio_api_v1_missions_audio_transcribe_post: {
            /**
             * File
             * Format: binary
             */
            file: string;
        };
        /** Body_upload_book_api_v1_stories_upload_book_post */
        Body_upload_book_api_v1_stories_upload_book_post: {
            /** Author */
            author?: string | null;
            /**
             * File
             * Format: binary
             */
            file: string;
            /**
             * Max Chapters
             * @default 0
             */
            max_chapters?: number;
            /**
             * Target Levels
             * @default A1,A2,B1
             */
            target_levels?: string | null;
            /** Title */
            title?: string | null;
        };
        /** Body_upload_library_book_api_v1_stories_library_upload_post */
        Body_upload_library_book_api_v1_stories_library_upload_post: {
            /** Author */
            author?: string | null;
            /**
             * File
             * Format: binary
             */
            file: string;
            /**
             * Target Level
             * @default A2
             */
            target_level?: string | null;
            /** Title */
            title?: string | null;
        };
        /**
         * BulkImportRequest
         * @description Request to bulk import grammar concepts.
         */
        BulkImportRequest: {
            /** Concepts */
            concepts: components["schemas"]["GrammarConceptCreate"][];
        };
        /** CapabilityEvidence */
        CapabilityEvidence: {
            capability_key: components["schemas"]["CapabilityKey"];
            /** Context Native */
            context_native: string;
            modality: components["schemas"]["InputMode"];
            /**
             * Observed On
             * Format: date
             */
            observed_on: string;
            state: components["schemas"]["CapabilityState"];
        };
        /**
         * CapabilityKey
         * @description What the rubric reports on. The first three are scenario objectives.
         *
         *     ``REGISTER`` (WP-33, wired by WP-37) is the odd one out and deliberately so:
         *     it is a *dimension* re-read from the same respond turns, scored by the same
         *     ``_summarize`` and the same ladder — one rubric, never a second one
         *     (CONTRACTS §8). It carries no scenario of its own, which is why
         *     ``journey_capabilities._SCENARIO_KEYS`` — not ``tuple(CapabilityKey)`` — is
         *     what the evidence reader groups by. It is last because the wire list is
         *     ordered by this enum and the register line belongs after the three
         *     capabilities it is read from.
         * @enum {string}
         */
        CapabilityKey: "order_at_cafe" | "arrange_meeting" | "explain_delay" | "register";
        /** CapabilityProgress */
        CapabilityProgress: {
            /** Capabilities */
            capabilities: components["schemas"]["CapabilitySummary"][];
            /**
             * Contract Version
             * @default 1
             * @constant
             */
            contract_version: 1;
            /** Rubric Version */
            rubric_version: string;
        };
        /**
         * CapabilityState
         * @enum {string}
         */
        CapabilityState: "not_tried" | "with_support" | "independent_once" | "used_again_later" | "unknown";
        /** CapabilitySummary */
        CapabilitySummary: {
            capability_key: components["schemas"]["CapabilityKey"];
            /** Evidence */
            evidence: components["schemas"]["CapabilityEvidence"][];
            /** Latest Qualifying On */
            latest_qualifying_on: string | null;
            /** Modalities */
            modalities: components["schemas"]["InputMode"][];
            state: components["schemas"]["CapabilityState"];
            /** Title Native */
            title_native: string;
        };
        /** CarnetBand */
        CarnetBand: {
            /** Band */
            band: string;
            /** Can Dos */
            can_dos?: components["schemas"]["CarnetCanDo"][];
            /** Title Native */
            title_native: string;
        };
        /** CarnetCanDo */
        CarnetCanDo: {
            /** Character Id */
            character_id?: string | null;
            /** Id */
            id: string;
            /** Quote Fr */
            quote_fr?: string | null;
            /** Scene Id */
            scene_id?: string | null;
            /** Scene Title Fr */
            scene_title_fr?: string | null;
            /** Source */
            source?: string | null;
            /** Stamped At */
            stamped_at?: string | null;
            /** Title Fr */
            title_fr?: string | null;
            /** Title Native */
            title_native?: string | null;
        };
        /**
         * CarnetResponse
         * @description WP-95 «Le Carnet» — ``GET /api/v1/can-dos``.
         */
        CarnetResponse: {
            /** Bands */
            bands?: components["schemas"]["CarnetBand"][];
            /** Current Band */
            current_band?: string | null;
        };
        /** CarteCounts */
        CarteCounts: {
            /** France */
            france: number;
            /** Idf */
            idf: number;
            /** Paris */
            paris: number;
            /** Unplaced */
            unplaced: number;
        };
        /** CartePin */
        CartePin: {
            /** Closed At */
            closed_at?: string | null;
            /** Contribution Fr */
            contribution_fr?: string | null;
            /** Contribution Kind */
            contribution_kind?: string | null;
            /**
             * Contribution Spans
             * @default []
             */
            contribution_spans?: [
                number,
                number
            ][];
            /** Dossier Id */
            dossier_id: string;
            /**
             * Due Words
             * @default 0
             */
            due_words?: number;
            /** Headline Fr */
            headline_fr: string;
            /** Kept Words */
            kept_words: string[];
            /** Lat */
            lat: number;
            /**
             * Level
             * @enum {string}
             */
            level: "france" | "idf" | "paris";
            /** Lon */
            lon: number;
            /** Place Id */
            place_id?: string | null;
            /** Place Label Fr */
            place_label_fr: string;
            /** Plate Url */
            plate_url?: string | null;
            /**
             * Precision
             * @enum {string}
             */
            precision: "exact" | "city" | "region";
            /** Question Fr */
            question_fr?: string | null;
            relecture?: components["schemas"]["CarteRelectureMark"] | null;
            /** Session Id */
            session_id: string;
            vignette?: components["schemas"]["CarteVignette"] | null;
            /** Week */
            week: string;
        };
        /** CarteQuartierPlace */
        CarteQuartierPlace: {
            /** Id */
            id: string;
            /** Label Fr */
            label_fr: string;
            /** Lat */
            lat: number;
            /** Lon */
            lon: number;
            /** Name Fr */
            name_fr: string;
            /** Plate Url */
            plate_url?: string | null;
        };
        /** CarteRelectureMark */
        CarteRelectureMark: {
            /** Read At */
            read_at?: string | null;
            /**
             * State
             * @enum {string}
             */
            state: "eligible" | "read";
        };
        /** CarteReview */
        CarteReview: {
            /** Headline Fr */
            headline_fr?: string | null;
            /** Items */
            items: components["schemas"]["CarteReviewItem"][];
            /** Place Id */
            place_id: string;
            /** Place Label Fr */
            place_label_fr: string;
            /** Plate Url */
            plate_url?: string | null;
            /** Week */
            week: string;
            /** Words */
            words: components["schemas"]["CarteReviewWord"][];
        };
        /** CarteReviewGrade */
        CarteReviewGrade: {
            /** Item Id */
            item_id: string;
            /** Remaining */
            remaining: number;
            /** Results */
            results: components["schemas"]["CarteReviewResult"][];
            /** Task Type */
            task_type: string;
        };
        /** CarteReviewGradeRequest */
        CarteReviewGradeRequest: {
            /**
             * Assisted
             * @default false
             */
            assisted?: boolean;
            /** Item Id */
            item_id: string;
            /** Text */
            text?: string | null;
            /** Tile Ids */
            tile_ids?: string[] | null;
        };
        /** CarteReviewItem */
        CarteReviewItem: {
            /** Answer Key */
            answer_key?: {
                [key: string]: unknown;
            } | null;
            /** Audio Url */
            audio_url?: string | null;
            /** Id */
            id: string;
            /** Options */
            options: components["schemas"]["CarteReviewOption"][];
            /** Progress Ids */
            progress_ids: string[];
            /** Prompt Fr */
            prompt_fr?: string | null;
            /**
             * Task Type
             * @enum {string}
             */
            task_type: "match_pairs" | "word_bank" | "unscramble" | "dictation";
        };
        /** CarteReviewOption */
        CarteReviewOption: {
            /** Id */
            id: string;
            /** Side */
            side?: ("fr" | "native") | null;
            /** Text Fr */
            text_fr: string;
        };
        /** CarteReviewResult */
        CarteReviewResult: {
            /** Correct */
            correct: boolean;
            /** Due At */
            due_at?: string | null;
            /** Progress Id */
            progress_id: string;
            /** Rating */
            rating: number;
            /** Word Id */
            word_id: number;
        };
        /** CarteReviewWord */
        CarteReviewWord: {
            /** Gloss */
            gloss: string;
            /** Line Fr */
            line_fr: string;
            /** Progress Id */
            progress_id: string;
            /** Sentence Fr */
            sentence_fr: string;
            /** Session Id */
            session_id: string;
            /** Speaker Id */
            speaker_id: string;
            /** Speaker Name */
            speaker_name: string;
            /** Week */
            week: string;
            /** Word */
            word: string;
            /** Word Id */
            word_id: number;
        };
        /** CarteView */
        CarteView: {
            counts: components["schemas"]["CarteCounts"];
            /**
             * Due Total
             * @default 0
             */
            due_total?: number;
            /** Pins */
            pins: components["schemas"]["CartePin"][];
            /** Quartier */
            quartier: components["schemas"]["CarteQuartierPlace"][];
        };
        /** CarteVignette */
        CarteVignette: {
            /** Kept Contribution */
            kept_contribution: boolean;
            /** Pictogram Svg */
            pictogram_svg: string;
            /**
             * Ring
             * @enum {string}
             */
            ring: "headline" | "question" | "report";
        };
        /**
         * CastIntroEntry
         * @description WP-75. One face of the cast, introduced on the learner's first day.
         *
         *     ``character_id`` names a directory under
         *     ``web-frontend/public/assets/serial/characters/``; ``role_native`` and
         *     ``line_native`` are in the learner's language, ``line_fr`` is one short A1
         *     line the character says.
         */
        CastIntroEntry: {
            /** Character Id */
            character_id: string;
            /** Line Fr */
            line_fr: string;
            /** Line Native */
            line_native: string;
            /** Name */
            name: string;
            /** Role Native */
            role_native: string;
        };
        /**
         * CEFRProgressResponse
         * @description Visible CEFR estimate, threshold breakdown, and forecast.
         */
        CEFRProgressResponse: {
            /** Breakdown */
            breakdown?: {
                [key: string]: unknown;
            };
            /** Can Dos Stamped */
            can_dos_stamped?: number | null;
            /** Can Dos Total */
            can_dos_total?: number | null;
            /** Checkpoint */
            checkpoint?: {
                [key: string]: unknown;
            } | null;
            /** Computed Estimate */
            computed_estimate?: string | null;
            /** Coverage */
            coverage?: {
                [key: string]: unknown;
            } | null;
            /** Daily Minutes */
            daily_minutes?: number | null;
            /** Declared Level */
            declared_level?: string | null;
            /** Estimate */
            estimate: string;
            /** Estimate Source */
            estimate_source?: string | null;
            /** Forecast */
            forecast?: {
                [key: string]: unknown;
            } | null;
            /** Generated At */
            generated_at?: string | null;
            /** Level Label */
            level_label?: string | null;
            /** Next Can Do */
            next_can_do?: {
                [key: string]: unknown;
            } | null;
            /** Next Level */
            next_level?: string | null;
            /** Placement */
            placement?: {
                [key: string]: unknown;
            } | null;
            /** Release Floor */
            release_floor?: string | null;
            /** Rhythm */
            rhythm?: string | null;
            /** Rhythm Priors */
            rhythm_priors?: {
                [key: string]: unknown;
            } | null;
            /** Signals */
            signals?: {
                [key: string]: unknown;
            };
            /** Target */
            target: string;
            /** Thresholds */
            thresholds?: {
                [key: string]: {
                    [key: string]: number;
                };
            };
            /** Today Delta */
            today_delta?: {
                [key: string]: unknown;
            };
            /** Version */
            version: string;
        };
        /**
         * ChapterCompletionRequest
         * @description Request to complete a chapter.
         */
        ChapterCompletionRequest: {
            /** Goals Completed */
            goals_completed?: string[];
            /** Session Id */
            session_id: string;
        };
        /**
         * ChapterCompletionResponse
         * @description Response for chapter completion.
         */
        ChapterCompletionResponse: {
            /** Achievements Unlocked */
            achievements_unlocked?: {
                [key: string]: unknown;
            }[];
            /**
             * Is Perfect
             * @default false
             */
            is_perfect?: boolean;
            next_chapter?: components["schemas"]["ChapterRead"] | null;
            /** Next Chapter Id */
            next_chapter_id?: string | null;
            /**
             * Story Completed
             * @default false
             */
            story_completed?: boolean;
            /** Xp Earned */
            xp_earned: number;
        };
        /**
         * ChapterConceptRead
         * @description Grammar concept for a chapter.
         */
        ChapterConceptRead: {
            /** Category */
            category: string | null;
            /** Description */
            description: string | null;
            /** Id */
            id: number;
            /** Is Due */
            is_due: boolean;
            /** Level */
            level: string;
            /** Name */
            name: string;
            /** Reps */
            reps: number;
            /** Score */
            score: number;
            /** State */
            state: string;
            /** Visualization Type */
            visualization_type: string | null;
        };
        /**
         * ChapterRead
         * @description Schema for chapter information.
         */
        ChapterRead: {
            /** Id */
            id: string;
            /** Order Index */
            order_index: number;
            /** Story Id */
            story_id: string;
            /** Target Level */
            target_level?: string | null;
            /** Title */
            title: string;
        };
        /**
         * ChapterWithStatusRead
         * @description Chapter with user completion status for chapter timeline.
         */
        ChapterWithStatusRead: {
            /**
             * Completion Xp
             * @default 75
             */
            completion_xp?: number;
            /** Id */
            id: string;
            /**
             * Is Completed
             * @default false
             */
            is_completed?: boolean;
            /**
             * Is Locked
             * @default false
             */
            is_locked?: boolean;
            /** Order Index */
            order_index: number;
            /**
             * Perfect Completion Xp
             * @default 150
             */
            perfect_completion_xp?: number;
            /** Story Id */
            story_id: string;
            /** Target Level */
            target_level?: string | null;
            /** Title */
            title: string;
            /**
             * Was Perfect
             * @default false
             */
            was_perfect?: boolean;
        };
        /** ChoiceAttemptInput */
        ChoiceAttemptInput: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "choice";
            /** Option Id */
            option_id: string;
        };
        /**
         * ChoiceOptionRead
         * @description Schema for player choice options.
         */
        ChoiceOptionRead: {
            /** Id */
            id: string;
            /** Text */
            text: string;
        };
        /** ClaimAnswers */
        ClaimAnswers: {
            /** Answers */
            answers?: string[];
            /** Kind */
            kind: string;
            /** Target Id */
            target_id: string;
        };
        /**
         * ClaimRequest
         * @description «Je connais déjà », on one erratum or one word.
         */
        ClaimRequest: {
            /** Kind */
            kind: string;
            /** Target Id */
            target_id: string;
        };
        /** ClientErrorRequest */
        ClientErrorRequest: {
            /** Message */
            message: string;
            /** Route */
            route?: string | null;
            /**
             * Source
             * @default web
             */
            source?: string;
            /** Stack */
            stack?: string | null;
        };
        /**
         * ConceptGraphEdge
         * @description Edge in the concept dependency graph.
         */
        ConceptGraphEdge: {
            /** Source */
            source: number;
            /** Target */
            target: number;
        };
        /**
         * ConceptGraphNode
         * @description Node in the concept dependency graph.
         */
        ConceptGraphNode: {
            /** Category */
            category: string | null;
            /** Description */
            description: string | null;
            /** Id */
            id: number;
            /** Is Locked */
            is_locked: boolean;
            /** Level */
            level: string;
            /** Name */
            name: string;
            /** Prerequisites */
            prerequisites: number[];
            /** Reps */
            reps: number;
            /** Score */
            score: number;
            /** State */
            state: string;
            /** Visualization Type */
            visualization_type: string | null;
        };
        /**
         * ConceptGraphResponse
         * @description Complete concept dependency graph.
         */
        ConceptGraphResponse: {
            /** Edges */
            edges: components["schemas"]["ConceptGraphEdge"][];
            /** Levels */
            levels: {
                [key: string]: number[];
            };
            /** Nodes */
            nodes: components["schemas"]["ConceptGraphNode"][];
        };
        /**
         * ConjugationReviewRequest
         * @description Payload for rating one verb x tense conjugation item.
         */
        ConjugationReviewRequest: {
            /** Answer Text */
            answer_text?: string | null;
            /** Lemma */
            lemma: string;
            /** Person */
            person?: string | null;
            /** Rating */
            rating: number;
            /** Response Time Ms */
            response_time_ms?: number | null;
            /** Tense */
            tense: string;
        };
        /**
         * ConjugationReviewResponse
         * @description Result after scheduling a conjugation item.
         */
        ConjugationReviewResponse: {
            /** Correct */
            correct?: boolean | null;
            /** Expected */
            expected?: string | null;
            /** Lapses */
            lapses: number;
            /** Lemma */
            lemma: string;
            /** Next Review */
            next_review?: string | null;
            /** Note Native */
            note_native?: string | null;
            /** Proficiency Score */
            proficiency_score: number;
            /** Reps */
            reps: number;
            /** State */
            state: string;
            /** Tense */
            tense: string;
        };
        /** ConsentRequest */
        ConsentRequest: {
            /** Language */
            language?: string | null;
            /**
             * Surface
             * @default signup
             * @enum {string}
             */
            surface?: "signup" | "settings" | "reconsent";
            /** Version */
            version: string;
        };
        /** ConsentStatus */
        ConsentStatus: {
            /** Accepted At */
            accepted_at?: string | null;
            /** Accepted Version */
            accepted_version?: string | null;
            /** Current Version */
            current_version: string;
            /**
             * Up To Date
             * @default false
             */
            up_to_date?: boolean;
        };
        /**
         * ConsequenceRead
         * @description Schema for consequences of player actions.
         */
        ConsequenceRead: {
            /** Description */
            description?: string | null;
            /** Target */
            target: string;
            /** Type */
            type: string;
            /** Value */
            value?: unknown;
        };
        /** ContentImportRequest */
        ContentImportRequest: {
            /** Url */
            url: string;
        };
        /** CrCounts */
        CrCounts: {
            /** False Alarms */
            false_alarms: number;
            /** Missed */
            missed: number;
            /** Noticed */
            noticed: number;
            /** Repaired */
            repaired: number;
            /** Seeded */
            seeded: number;
        };
        /** CrDraftView */
        CrDraftView: {
            /** Band */
            band: string;
            /** Byline Fr */
            byline_fr: string;
            /** Dossier Id */
            dossier_id: string;
            /** Errors Count */
            errors_count: number;
            /** Id */
            id: string;
            /** Kicker Fr */
            kicker_fr: string;
            /** Options Enabled */
            options_enabled: boolean;
            result?: components["schemas"]["CrResult"] | null;
            /** Sentences */
            sentences: string[];
            /** Title Fr */
            title_fr: string;
            /** Units */
            units: components["schemas"]["CrUnit"][];
        };
        /** CrFalseAlarm */
        CrFalseAlarm: {
            /** Fix Fr */
            fix_fr?: string | null;
            /** Sentence Index */
            sentence_index: number;
            /** Span */
            span: number[];
            /** Text Fr */
            text_fr: string;
        };
        /** CrMark */
        CrMark: {
            /** Fix Fr */
            fix_fr?: string | null;
            /**
             * Picked
             * @default false
             */
            picked?: boolean;
            /** Sentence Index */
            sentence_index: number;
            /** Span */
            span: number[];
        };
        /** CrMarksRequest */
        CrMarksRequest: {
            /** Marks */
            marks?: components["schemas"]["CrMark"][];
        };
        /** CrResult */
        CrResult: {
            counts: components["schemas"]["CrCounts"];
            /** Dossier Id */
            dossier_id: string;
            /** False Alarms */
            false_alarms: components["schemas"]["CrFalseAlarm"][];
            /** Id */
            id: string;
            /** Outcomes */
            outcomes: components["schemas"]["CrSeedOutcome"][];
            /** Releve Href */
            releve_href: string;
            /** Romy Line Fr */
            romy_line_fr: string;
            /** Sentences */
            sentences: string[];
        };
        /** CrSeedOutcome */
        CrSeedOutcome: {
            /** Correct Fr */
            correct_fr: string;
            /** Fix Fr */
            fix_fr?: string | null;
            /** Grammar Point */
            grammar_point: string;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "repaired" | "noticed" | "missed";
            /** Sentence Index */
            sentence_index: number;
            /**
             * Source
             * @enum {string}
             */
            source: "errata" | "classique";
            /** Span */
            span: number[];
            /** Wrong Fr */
            wrong_fr: string;
        };
        /**
         * CrUnit
         * @description One tappable unit (a word, or a contraction pair like «de le»).
         */
        CrUnit: {
            /** Options */
            options?: string[] | null;
            /** Sentence Index */
            sentence_index: number;
            /** Span */
            span: number[];
            /** Text */
            text: string;
        };
        /** CrWeek */
        CrWeek: {
            /** Corrected */
            corrected: string[];
            /** Dossiers */
            dossiers: components["schemas"]["CrWeekDossier"][];
            /** Label */
            label: string;
            /** Week */
            week: string;
        };
        /** CrWeekDossier */
        CrWeekDossier: {
            /** Evergreen */
            evergreen: boolean;
            /** Id */
            id: string;
            /** Title Fr */
            title_fr: string;
            /** Topic */
            topic: string;
        };
        /**
         * DailyWordEntry
         * @description One word on today's slate with its triple-stamp state.
         */
        DailyWordEntry: {
            /** Anchor */
            anchor?: string | null;
            /**
             * Bucket
             * @default due
             */
            bucket?: string;
            /** Example Sentence */
            example_sentence?: string | null;
            /** Example Translation */
            example_translation?: string | null;
            /** Gender */
            gender?: string | null;
            /** Part Of Speech */
            part_of_speech?: string | null;
            /** Stamps */
            stamps?: {
                [key: string]: string | null;
            };
            /** Translation */
            translation?: string | null;
            /**
             * Triple
             * @default false
             */
            triple?: boolean;
            /** Word */
            word: string;
            /** Word Id */
            word_id: number;
        };
        /**
         * DailyWordSlateResponse
         * @description Les mots du jour — the day's coordinated vocabulary slate.
         */
        DailyWordSlateResponse: {
            /** Date */
            date: string;
            /**
             * Triples
             * @default 0
             */
            triples?: number;
            /**
             * Version
             * @default mots-du-jour-v1
             */
            version?: string;
            /** Words */
            words?: components["schemas"]["DailyWordEntry"][];
        };
        /**
         * DayTimeEstimate
         * @description WP-128 — the one estimate every surface shows: Home, the entry, the plan, the ending.
         *
         *     ``core_seconds`` is the recommended core path — the story and its practice —
         *     which the selected rhythm (``budget_seconds``) budgets. ``basis`` says where
         *     it comes from: ``plan`` (today's planned day) or ``forecast`` (before the
         *     day is planned: the learner's recent planned cores, else the rhythm's prior).
         *     ``longer_day``: the story alone does not fit the rhythm; it is planned
         *     whole, never cut, and said before the learner starts.
         */
        DayTimeEstimate: {
            /**
             * Basis
             * @enum {string}
             */
            basis: "plan" | "forecast";
            /** Budget Seconds */
            budget_seconds: number;
            /** Core Seconds */
            core_seconds: number;
            /** Extensions */
            extensions: components["schemas"]["TimeExtension"][];
            /**
             * Longer Day
             * @default false
             */
            longer_day: boolean;
        };
        /** DebriefRequest */
        DebriefRequest: {
            /**
             * Free Line
             * @default
             */
            free_line?: string;
            /**
             * Outcome
             * @description done | partly | not_yet
             */
            outcome: string;
        };
        /** DeclareRequest */
        DeclareRequest: {
            /**
             * Declaration
             * @default
             */
            declaration?: string;
        };
        /**
         * DeskPrompt
         * @description «Le bureau» (WP-121/122): one of the Revue's other desks, folded into an
         *     ordinary practice day after the ending. Advanced, not answered — each desk
         *     grades through its own routes. The client mounts:
         *
         *     * ``relecture`` — ``CarteRelecture`` on ``relecture`` (the offer of
         *       ``GET /revue/relecture/offer``), answered with ``POST /revue/relecture/{session_id}``;
         *     * ``radio`` — the Radio bulletin of ``dossier_id`` (``GET /revue/radio/{id}``),
         *       listen first, then the dictée, then «C'est entendu»;
         *     * ``correcteur`` — ``CorrecteurDesk`` on a new draft of ``dossier_id``
         *       (``POST /revue/correcteur/{id}``).
         */
        DeskPrompt: {
            /**
             * Desk
             * @enum {string}
             */
            desk: "relecture" | "radio" | "correcteur";
            /** Dossier Id */
            dossier_id: string | null;
            relecture: components["schemas"]["RelectureOffer"] | null;
            /** Seconds */
            seconds: number | null;
            /** Title Fr */
            title_fr: string;
        };
        /** DeskStep */
        DeskStep: {
            /** Assistance Used */
            assistance_used: components["schemas"]["AssistanceLevel"][];
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "desk";
            /** Ordinal */
            ordinal: number;
            prompt: components["schemas"]["DeskPrompt"];
            status: components["schemas"]["StepStatus"];
        };
        /**
         * DetectedErrorRead
         * @description Serialized error feedback for API consumers.
         */
        DetectedErrorRead: {
            /** Category */
            category: string;
            /** Code */
            code: string;
            /** Confidence */
            confidence: number;
            /**
             * Is Recurring
             * @default false
             */
            is_recurring?: boolean;
            /** Last Seen */
            last_seen?: string | null;
            /** Message */
            message: string;
            /**
             * Occurrence Count
             * @default 1
             */
            occurrence_count?: number;
            /** Severity */
            severity: string;
            /** Span */
            span: string;
            /** Suggestion */
            suggestion?: string | null;
        };
        /**
         * DossierEnvelope
         * @description One shape for every route, so the page renders one state machine.
         */
        DossierEnvelope: {
            /** Check */
            check?: {
                [key: string]: unknown;
            } | null;
            /** Claim Kinds */
            claim_kinds?: string[];
            /** Dossier */
            dossier?: {
                [key: string]: unknown;
            } | null;
            /**
             * Items Required
             * @default 2
             */
            items_required?: number;
            /** Verdict */
            verdict?: {
                [key: string]: unknown;
            } | null;
            /**
             * Version
             * @default learner-model-v1
             */
            version?: string;
        };
        /**
         * DueConceptRead
         * @description A concept due for review.
         */
        DueConceptRead: {
            /** Category */
            category: string | null;
            /** Current Score */
            current_score: number | null;
            /** Current State */
            current_state: string;
            /** Description */
            description: string | null;
            /** Id */
            id: number;
            /** Level */
            level: string;
            /** Name */
            name: string;
            /** Reps */
            reps: number;
        };
        /** EclairAnswer */
        EclairAnswer: {
            /** Answer */
            answer?: string | null;
            /** Id */
            id: string;
        };
        /** EclairFinishRequest */
        EclairFinishRequest: {
            /** Answers */
            answers?: components["schemas"]["EclairAnswer"][];
            /** Elapsed Ms */
            elapsed_ms?: number | null;
        };
        /** EclairStartRequest */
        EclairStartRequest: {
            /** Concept Id */
            concept_id?: number | null;
            /** Pair */
            pair?: string | null;
        };
        /**
         * EntreTempsItem
         * @description WP-99. One off-screen beat the cast lived while the learner was away.
         */
        EntreTempsItem: {
            /** Character Id */
            character_id: string | null;
            /** Date */
            date: string | null;
            /** Text Fr */
            text_fr: string;
        };
        /** EpisodeAudioClipRead */
        EpisodeAudioClipRead: {
            /** Char Count */
            char_count: number;
            /** Character Id */
            character_id: string;
            /** Content Type */
            content_type: string;
            /** Id */
            id: string;
            /** Line Key */
            line_key: string;
            /** Ordinal */
            ordinal: number;
            /** Text Fr */
            text_fr: string;
            /** Voice */
            voice: string;
        };
        /** EpisodeAudioManifestRead */
        EpisodeAudioManifestRead: {
            /** Clips */
            clips: components["schemas"]["EpisodeAudioClipRead"][];
            /** Reason */
            reason: string;
            /** Revision */
            revision: string;
            /**
             * Status
             * @enum {string}
             */
            status: "disabled" | "absent" | "empty" | "ready" | "failed";
            /** Truncated */
            truncated: boolean;
        };
        /**
         * EpisodeHeadline
         * @description WP-109: today's episode as Home and the Feuilleton headline it.
         */
        EpisodeHeadline: {
            /** Cast */
            cast: components["schemas"]["HeadlineCastMember"][];
            /** Cast Variants */
            cast_variants: {
                [key: string]: string;
            };
            /** Edition No */
            edition_no: number | null;
            /** Image Url */
            image_url: string | null;
            /** Season Title Fr */
            season_title_fr: string | null;
            /** Teaser Fr */
            teaser_fr: string | null;
            /** Title Fr */
            title_fr: string | null;
        };
        /** EpisodeRead */
        EpisodeRead: {
            /** Brief Payload */
            brief_payload?: {
                [key: string]: unknown;
            };
            /** Episode Index */
            episode_index: number;
            /** Hook From Previous */
            hook_from_previous?: {
                [key: string]: unknown;
            } | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "mission" | "feuilleton";
            /** Location Id */
            location_id?: string | null;
            /** Mission Id */
            mission_id?: string | null;
            /** Scene Id */
            scene_id?: string | null;
            /**
             * Status
             * @default available
             */
            status?: ("available" | "in_progress" | "completed") | string;
            /**
             * Thread Id
             * Format: uuid
             */
            thread_id: string;
        } & {
            [key: string]: unknown;
        };
        /** EpreuveCanDo */
        EpreuveCanDo: {
            /** Id */
            id: string;
            /** Title Fr */
            title_fr: string | null;
            /** Title Native */
            title_native: string | null;
        };
        /**
         * EpreuveView
         * @description WP-94 «Numéro spécial» — the band the épreuve closes and its can-dos.
         */
        EpreuveView: {
            /** Band */
            band: string | null;
            /** Can Dos */
            can_dos: components["schemas"]["EpreuveCanDo"][];
        };
        /**
         * ErrorCategoryCount
         * @description Error count by category.
         */
        ErrorCategoryCount: {
            /** Category */
            category: string;
            /** Count */
            count: number;
        };
        /**
         * ErrorFeedback
         * @description Aggregate feedback for a learner message.
         */
        ErrorFeedback: {
            /** Error Stats */
            error_stats?: components["schemas"]["ErrorOccurrenceStats"][];
            /** Errors */
            errors: components["schemas"]["DetectedErrorRead"][];
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            };
            /** Review Vocabulary */
            review_vocabulary?: string[];
            /** Summary */
            summary: string;
        };
        /**
         * ErrorOccurrenceStats
         * @description Statistics about error occurrences for spaced repetition.
         */
        ErrorOccurrenceStats: {
            /** Category */
            category: string;
            /** Last Seen */
            last_seen?: string | null;
            /** Next Review */
            next_review?: string | null;
            /**
             * Occurrences Today
             * @default 0
             */
            occurrences_today?: number;
            /** Pattern */
            pattern?: string | null;
            /**
             * State
             * @default new
             */
            state?: string;
            /** Total Occurrences */
            total_occurrences: number;
        };
        /**
         * ErrorPattern
         * @description Common learner error grouping.
         */
        ErrorPattern: {
            /** Count */
            count: number;
            /** Error Type */
            error_type: string;
            /** Example */
            example?: string | null;
            /** Severity */
            severity?: string | null;
        };
        /**
         * ErrorPatternsResponse
         * @description Collection of frequent learner errors.
         */
        ErrorPatternsResponse: {
            /** Items */
            items?: components["schemas"]["ErrorPattern"][];
            /** Total */
            total: number;
        };
        /**
         * ErrorStageCounts
         * @description Error counts by SRS stage.
         */
        ErrorStageCounts: {
            /**
             * Learning
             * @default 0
             */
            learning?: number;
            /**
             * Mastered
             * @default 0
             */
            mastered?: number;
            /**
             * New
             * @default 0
             */
            new?: number;
            /**
             * Relearning
             * @default 0
             */
            relearning?: number;
            /**
             * Review
             * @default 0
             */
            review?: number;
        };
        /**
         * ErrorSummary
         * @description Anki-like summary for error tracking.
         */
        ErrorSummary: {
            /** Categories */
            categories?: components["schemas"]["ErrorCategoryCount"][];
            /** Due Today */
            due_today: number;
            stage_counts: components["schemas"]["ErrorStageCounts"];
            /** Total Errors */
            total_errors: number;
        };
        /**
         * EvidenceKind
         * @description How strong the observation is. Reading or tapping is never production.
         * @enum {string}
         */
        EvidenceKind: "recognized" | "produced_supported" | "produced_independent" | "not_yet" | "unscored";
        /**
         * FeedbackReportCreate
         * @description Payload submitted by the global feedback widget.
         */
        FeedbackReportCreate: {
            /**
             * Category
             * @enum {string}
             */
            category: "bug" | "broken_link" | "content" | "layout" | "slow_loading" | "suggestion" | "other";
            /** Context Payload */
            context_payload?: {
                [key: string]: unknown;
            };
            /** Message */
            message?: string | null;
            /** Route */
            route: string;
            /** Screen */
            screen?: string | null;
            /** Url */
            url?: string | null;
            /** User Agent */
            user_agent?: string | null;
            /** Viewport */
            viewport?: {
                [key: string]: unknown;
            };
        };
        /**
         * FeedbackReportRead
         * @description Stored feedback report returned to the submitter or admins.
         */
        FeedbackReportRead: {
            /** Category */
            category: string;
            /** Context Payload */
            context_payload: {
                [key: string]: unknown;
            };
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Message */
            message?: string | null;
            /** Route */
            route: string;
            /** Screen */
            screen?: string | null;
            /** Url */
            url?: string | null;
            /** User Agent */
            user_agent?: string | null;
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
            /** Viewport */
            viewport: {
                [key: string]: unknown;
            };
        };
        /** FollowupRequest */
        FollowupRequest: {
            /**
             * Text
             * @default
             */
            text?: string;
        };
        /**
         * ForgeEntry
         * @description WP-S4 — where «Forge today's rule» opens, and how the day carries it.
         *
         *     ``folded``: Soutenu and Intensif carry the forge inside the day (a step in
         *     the Scène movement); Home then keeps «More practice» after the day.
         *     Léger and Régulier (``folded`` false) get the forge as the after-day chip.
         */
        ForgeEntry: {
            /** Budget Seconds */
            budget_seconds: number;
            /** Concept Id */
            concept_id: number | null;
            /**
             * Folded
             * @default false
             */
            folded: boolean;
            /**
             * Href
             * @default /atelier?mode=forge
             */
            href: string;
        };
        /**
         * ForgePrompt
         * @description WP-S4 «La Forge», folded into the day: a hand-off, not an exercise.
         *
         *     ``href`` opens the forge block on today's rule; ``forged`` turns true once
         *     a forge block started from this step was completed, so the step reads
         *     «Continue» when the learner comes back. Both are projected, never stored.
         */
        ForgePrompt: {
            /** Budget Seconds */
            budget_seconds: number;
            /** Concept Id */
            concept_id: number | null;
            /**
             * Forged
             * @default false
             */
            forged: boolean;
            /**
             * Href
             * @default /atelier?mode=forge
             */
            href: string;
            /**
             * Title Fr
             * @default
             */
            title_fr: string;
            /**
             * Title Native
             * @default
             */
            title_native: string;
        };
        /** ForgeStep */
        ForgeStep: {
            /** Assistance Used */
            assistance_used: components["schemas"]["AssistanceLevel"][];
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "forge";
            /** Ordinal */
            ordinal: number;
            prompt: components["schemas"]["ForgePrompt"];
            status: components["schemas"]["StepStatus"];
        };
        /**
         * GoalCheckRequest
         * @description Request to check narrative goal completion.
         */
        GoalCheckRequest: {
            /** Session Id */
            session_id: string;
        };
        /**
         * GoalCheckResponse
         * @description Response for narrative goal check.
         */
        GoalCheckResponse: {
            /**
             * Completion Rate
             * @default 0
             */
            completion_rate?: number;
            /** Goals Completed */
            goals_completed?: string[];
            /** Goals Remaining */
            goals_remaining?: string[];
        };
        /**
         * GrammarConceptCreate
         * @description Request to create a grammar concept.
         */
        GrammarConceptCreate: {
            /**
             * Active
             * @default true
             */
            active?: boolean;
            /** Anchor Examples */
            anchor_examples?: string | null;
            /** Category */
            category?: string | null;
            /** Core Rule */
            core_rule?: string | null;
            /** Description */
            description?: string | null;
            /**
             * Difficulty Order
             * @default 0
             */
            difficulty_order?: number;
            /** Examples */
            examples?: string | null;
            /** Exercise Tags */
            exercise_tags?: string[];
            /** External Id */
            external_id?: string | null;
            /**
             * Is Foundation
             * @default false
             */
            is_foundation?: boolean;
            /**
             * Language
             * @default fr
             */
            language?: string;
            /** Level */
            level: string;
            /** Main Traps */
            main_traps?: string | null;
            /** Name */
            name: string;
            /** Subskill */
            subskill?: string | null;
        };
        /**
         * GrammarConceptRead
         * @description Response for a grammar concept.
         */
        GrammarConceptRead: {
            /** Active */
            active: boolean;
            /** Anchor Examples */
            anchor_examples: string | null;
            /** Category */
            category: string | null;
            /** Core Rule */
            core_rule: string | null;
            /** Description */
            description: string | null;
            /** Difficulty Order */
            difficulty_order: number;
            /** Examples */
            examples: string | null;
            /** Exercise Tags */
            exercise_tags: string[];
            /** External Id */
            external_id: string | null;
            /** Id */
            id: number;
            /** Is Foundation */
            is_foundation: boolean;
            /** Language */
            language: string;
            /** Level */
            level: string;
            /** Main Traps */
            main_traps: string | null;
            /** Name */
            name: string;
            /** Subskill */
            subskill: string | null;
        };
        /** GrammarFocusRead */
        GrammarFocusRead: {
            /** Title Fr */
            title_fr: string;
            /** Title Native */
            title_native: string;
            /** Unit Id */
            unit_id: string;
            /** Woven */
            woven: boolean;
        };
        /** GrammarMarkRead */
        GrammarMarkRead: {
            /** End */
            end: number;
            /** Start */
            start: number;
            /** Unit Id */
            unit_id: string | number;
        };
        /**
         * GrammarNotebookDetailRead
         * @description Full notebook detail for one grammar concept.
         */
        GrammarNotebookDetailRead: {
            /** Active */
            active: boolean;
            /** Anchor Examples */
            anchor_examples?: string[];
            /** Atelier Blueprint */
            atelier_blueprint?: {
                [key: string]: unknown;
            };
            /** Blueprint Quality */
            blueprint_quality?: {
                [key: string]: unknown;
            };
            /** Blueprint Status */
            blueprint_status?: string | null;
            /** Catalog Version */
            catalog_version?: string | null;
            /** Category */
            category: string | null;
            /** Category Label Fr */
            category_label_fr?: string | null;
            /** Core Rule */
            core_rule: string | null;
            /** Description */
            description: string | null;
            /** Display Title */
            display_title: string;
            /** Due Errata */
            due_errata?: {
                [key: string]: unknown;
            }[];
            /** Due Errata Count */
            due_errata_count: number;
            /** Examples */
            examples: string | null;
            /** Exercise Tags */
            exercise_tags?: string[];
            /** External Id */
            external_id: string | null;
            /** Id */
            id: number;
            /** Is Foundation */
            is_foundation: boolean;
            /** Language */
            language: string;
            /** Level */
            level: string;
            /** Localized Category */
            localized_category?: string | null;
            /** Localized Subskill */
            localized_subskill?: string | null;
            /** Localized Title */
            localized_title?: string | null;
            /** Main Traps */
            main_traps?: string[];
            /** Mastery */
            mastery: number;
            /** Motif */
            motif?: {
                [key: string]: unknown;
            };
            /** Name */
            name: string;
            /** Next Review */
            next_review: string | null;
            /** Personal Notes */
            personal_notes?: string | null;
            progress?: components["schemas"]["GrammarNotebookProgressRead"] | null;
            /** Recent Errata */
            recent_errata?: {
                [key: string]: unknown;
            }[];
            /** Recent Errata Count */
            recent_errata_count: number;
            /** Rule Card */
            rule_card?: {
                [key: string]: unknown;
            } | null;
            /** Source Refs */
            source_refs?: {
                [key: string]: unknown;
            };
            /** State */
            state: string;
            /** State Label */
            state_label: string;
            /** Sub Band */
            sub_band?: string | null;
            /** Subskill */
            subskill: string | null;
            /** Title Fr */
            title_fr?: string | null;
            /** Xray */
            xray?: {
                [key: string]: unknown;
            } | null;
        };
        /**
         * GrammarNotebookItemRead
         * @description Concept list item for the personal grammar notebook.
         */
        GrammarNotebookItemRead: {
            /** Active */
            active: boolean;
            /** Blueprint Quality */
            blueprint_quality?: {
                [key: string]: unknown;
            };
            /** Blueprint Status */
            blueprint_status?: string | null;
            /** Catalog Version */
            catalog_version?: string | null;
            /** Category */
            category: string | null;
            /** Category Label Fr */
            category_label_fr?: string | null;
            /** Display Title */
            display_title: string;
            /** Due Errata Count */
            due_errata_count: number;
            /** External Id */
            external_id: string | null;
            /** Id */
            id: number;
            /** Is Foundation */
            is_foundation: boolean;
            /** Language */
            language: string;
            /** Level */
            level: string;
            /** Localized Category */
            localized_category?: string | null;
            /** Localized Subskill */
            localized_subskill?: string | null;
            /** Localized Title */
            localized_title?: string | null;
            /** Mastery */
            mastery: number;
            /** Motif */
            motif?: {
                [key: string]: unknown;
            };
            /** Name */
            name: string;
            /** Next Review */
            next_review: string | null;
            /** Recent Errata Count */
            recent_errata_count: number;
            /** Source Refs */
            source_refs?: {
                [key: string]: unknown;
            };
            /** State */
            state: string;
            /** State Label */
            state_label: string;
            /** Sub Band */
            sub_band?: string | null;
            /** Subskill */
            subskill: string | null;
            /** Title Fr */
            title_fr?: string | null;
        };
        /**
         * GrammarNotebookNotesRequest
         * @description Personal note update for one grammar concept.
         */
        GrammarNotebookNotesRequest: {
            /**
             * Notes
             * @default
             */
            notes?: string;
        };
        /**
         * GrammarNotebookProgressRead
         * @description Personal progress payload for the grammar notebook.
         */
        GrammarNotebookProgressRead: {
            /** Last Review */
            last_review: string | null;
            /** Next Review */
            next_review: string | null;
            /** Notes */
            notes: string | null;
            /** Reps */
            reps: number;
            /** Score */
            score: number;
            /** State */
            state: string;
            /** State Label */
            state_label: string;
        };
        /**
         * GrammarProgressRead
         * @description Response for user grammar progress.
         */
        GrammarProgressRead: {
            /** Concept Id */
            concept_id: number;
            /** Concept Level */
            concept_level: string;
            /** Concept Name */
            concept_name: string;
            /** Last Review */
            last_review: string | null;
            /** Next Review */
            next_review: string | null;
            /** Notes */
            notes: string | null;
            /** Reps */
            reps: number;
            /** Score */
            score: number;
            /** State */
            state: string;
            /** State Label */
            state_label: string;
        };
        /**
         * GrammarReviewRequest
         * @description Request to record a grammar review.
         */
        GrammarReviewRequest: {
            /** Concept Id */
            concept_id: number;
            /** Notes */
            notes?: string | null;
            /** Score */
            score: number;
        };
        /**
         * GrammarSummaryResponse
         * @description Summary of grammar progress.
         */
        GrammarSummaryResponse: {
            /** Due Today */
            due_today: number;
            /** Level Counts */
            level_counts: {
                [key: string]: number;
            };
            /** New Available */
            new_available: number;
            /** Started */
            started: number;
            /** State Counts */
            state_counts: {
                [key: string]: number;
            };
            /** Total Concepts */
            total_concepts: number;
        };
        /** GraphicNovelAttemptRequest */
        GraphicNovelAttemptRequest: {
            /** Answer Payload */
            answer_payload?: {
                [key: string]: unknown;
            };
            /** Task Id */
            task_id: string;
        };
        /** GraphicNovelAttemptResponse */
        GraphicNovelAttemptResponse: {
            /** Attempt */
            attempt: {
                [key: string]: unknown;
            };
            correction: components["schemas"]["MissionCorrectionRead"];
            /** Errata */
            errata?: components["schemas"]["LinkedVocabularyErratumRead"][];
            scene: components["schemas"]["GraphicNovelSceneRead"];
        };
        /** GraphicNovelCompleteResponse */
        GraphicNovelCompleteResponse: {
            /** Next Serial */
            next_serial?: {
                [key: string]: unknown;
            } | null;
            recap: components["schemas"]["GraphicNovelRecapRead"];
            scene: components["schemas"]["GraphicNovelSceneRead"];
        };
        /** GraphicNovelCreateRequest */
        GraphicNovelCreateRequest: {
            /**
             * Async Generation
             * @default false
             */
            async_generation?: boolean;
            /** Atelier Session Id */
            atelier_session_id?: string | null;
            /**
             * Cadence
             * @default ad_hoc
             */
            cadence?: string;
            /** Episode Index */
            episode_index?: number | null;
            /**
             * Experience Mode
             * @default study
             */
            experience_mode?: string;
            /**
             * Force New
             * @default false
             */
            force_new?: boolean;
            /**
             * Humor Style
             * @default satirical
             */
            humor_style?: string;
            /** Image Quality */
            image_quality?: string | null;
            /** Mission Id */
            mission_id?: string | null;
            /**
             * Panel Count
             * @description Requested Feuilleton length: 4, 6, or 8 panels
             */
            panel_count?: number | null;
            /** Personal Input Item Id */
            personal_input_item_id?: string | null;
            /** Preferred Concept Ids */
            preferred_concept_ids?: number[] | null;
            /** Preferred Errata Ids */
            preferred_errata_ids?: string[] | null;
            /**
             * Public Figure Mode
             * @default named_context
             */
            public_figure_mode?: string;
            /**
             * Refresh News
             * @default false
             */
            refresh_news?: boolean;
            /**
             * Render Mode
             * @default panels
             */
            render_mode?: string;
            /** Serial Thread Id */
            serial_thread_id?: string | null;
            /**
             * Story Quality
             * @default standard
             */
            story_quality?: string;
            /** Target Vocabulary Ids */
            target_vocabulary_ids?: number[] | null;
            /**
             * Use News
             * @default false
             */
            use_news?: boolean;
        };
        /** GraphicNovelPanelRead */
        GraphicNovelPanelRead: {
            /** Audio Payload */
            audio_payload?: {
                [key: string]: unknown;
            };
            /** Beat */
            beat: string;
            /** Created At */
            created_at?: string | null;
            /** Generation Metadata */
            generation_metadata?: {
                [key: string]: unknown;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Image Payload */
            image_payload?: {
                [key: string]: unknown;
            };
            /** Image Prompt */
            image_prompt: string;
            /** Image Url */
            image_url?: string | null;
            /** Overlay Payload */
            overlay_payload?: {
                [key: string]: unknown;
            };
            /** Panel Index */
            panel_index: number;
            /** Title */
            title: string;
        } & {
            [key: string]: unknown;
        };
        /** GraphicNovelRecapRead */
        GraphicNovelRecapRead: {
            vocabulary_credit?: components["schemas"]["VocabularyCreditSummary"];
        } & {
            [key: string]: unknown;
        };
        /** GraphicNovelSceneRead */
        GraphicNovelSceneRead: {
            /** Atelier Session Id */
            atelier_session_id?: string | null;
            /** Attempts */
            attempts?: {
                [key: string]: unknown;
            }[];
            /** Brief */
            brief: string;
            /** Cache Key */
            cache_key: string;
            /** Cadence */
            cadence: string;
            /** Completed At */
            completed_at?: string | null;
            /** Created At */
            created_at?: string | null;
            /** Episode Index */
            episode_index?: number | null;
            /** Hook */
            hook?: {
                [key: string]: unknown;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Image Model */
            image_model: string;
            /** Image Quality */
            image_quality: string;
            /** Mission Id */
            mission_id?: string | null;
            /** Panels */
            panels?: components["schemas"]["GraphicNovelPanelRead"][];
            /** Personal Input Item Id */
            personal_input_item_id?: string | null;
            /** Prompt Version */
            prompt_version: string;
            recap?: components["schemas"]["GraphicNovelRecapRead"];
            /** Script Payload */
            script_payload?: {
                [key: string]: unknown;
            };
            /** Selected Concept Ids */
            selected_concept_ids?: number[];
            /** Serial Thread Id */
            serial_thread_id?: string | null;
            /** Source Snapshot */
            source_snapshot?: {
                [key: string]: unknown;
            };
            /** Started At */
            started_at?: string | null;
            /** Status */
            status: string;
            /** Target Errata Ids */
            target_errata_ids?: string[];
            /** Target Vocabulary */
            target_vocabulary?: components["schemas"]["TargetVocabularyRead"][];
            /** Target Vocabulary Ids */
            target_vocabulary_ids?: number[];
            /** Title */
            title: string;
        } & {
            [key: string]: unknown;
        };
        /** GraphicNovelSceneResponse */
        GraphicNovelSceneResponse: {
            scene: components["schemas"]["GraphicNovelSceneRead"];
        };
        /** GraphicNovelTodayResponse */
        GraphicNovelTodayResponse: {
            active_scene?: components["schemas"]["GraphicNovelSceneRead"] | null;
            available_scene?: components["schemas"]["GraphicNovelSceneRead"] | null;
            /** Recent Completed */
            recent_completed?: components["schemas"]["GraphicNovelSceneRead"][];
            /** Recommendation */
            recommendation?: {
                [key: string]: unknown;
            };
        };
        /** HeadlineCastMember */
        HeadlineCastMember: {
            /** Id */
            id: string;
            /** Name */
            name: string;
        };
        /**
         * HelpKind
         * @enum {string}
         */
        HelpKind: "hint" | "translation" | "solution" | "suggested_response";
        /** HelpResult */
        HelpResult: {
            assistance_level: components["schemas"]["AssistanceLevel"];
            /** Content Fr */
            content_fr: string | null;
            /** Content Native */
            content_native: string | null;
            /**
             * Contract Version
             * @default 1
             * @constant
             */
            contract_version: 1;
            help_kind: components["schemas"]["HelpKind"];
            journey: components["schemas"]["JourneySnapshot"];
            /** Step Id */
            step_id: string;
        };
        /** HookRead */
        HookRead: {
            /**
             * Next Beat Kind
             * @default mission
             * @enum {string}
             */
            next_beat_kind?: "mission" | "feuilleton";
            /**
             * Teaser
             * @default
             */
            teaser?: string;
            /**
             * Text
             * @default
             */
            text?: string;
            /**
             * Unresolved Question
             * @default
             */
            unresolved_question?: string;
        } & {
            [key: string]: unknown;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * InfoboxRead
         * @description Schema for educational infobox content.
         */
        InfoboxRead: {
            /** Book Quote */
            book_quote?: string | null;
            /** Content */
            content: string;
            /** Grammar Note */
            grammar_note?: string | null;
            /** Title */
            title: string;
            /**
             * Type
             * @default grammar
             */
            type?: string;
        };
        /**
         * InputMode
         * @enum {string}
         */
        InputMode: "text" | "voice";
        /**
         * IntakeCapView
         * @description The weekly bound, as the learner sees it.
         */
        IntakeCapView: {
            /** Ceiling Usd */
            ceiling_usd: number;
            /** Enabled */
            enabled: boolean;
            /** Limit */
            limit: number;
            /** Remaining */
            remaining: number;
            /** Spent Usd */
            spent_usd: number;
            /** Used */
            used: number;
        };
        /**
         * IntakeEnvelope
         * @description One shape for every intake route, so the page renders one state machine.
         */
        IntakeEnvelope: {
            /** Artefact */
            artefact?: {
                [key: string]: unknown;
            } | null;
            /** Artefacts */
            artefacts?: {
                [key: string]: unknown;
            }[];
            cap: components["schemas"]["IntakeCapView"];
            /** Max Image Bytes */
            max_image_bytes?: number;
            /**
             * Max Text Chars
             * @default 6000
             */
            max_text_chars?: number;
            /**
             * Max Unknown Words
             * @default 8
             */
            max_unknown_words?: number;
            /** Mission */
            mission?: {
                [key: string]: unknown;
            } | null;
            /**
             * Version
             * @default intake-v1
             */
            version?: string;
        };
        /** IntakeTextRequest */
        IntakeTextRequest: {
            /**
             * Text
             * @default
             */
            text?: string;
        };
        /**
         * InterludeView
         * @description WP-98/99. The story is between seasons, named honestly, with its return date.
         */
        InterludeView: {
            /** Reason Fr */
            reason_fr: string | null;
            /** Returns On */
            returns_on: string | null;
        };
        /**
         * JournalCorrectionView
         * @description One correction in the foreground; the rest on demand.
         */
        JournalCorrectionView: {
            /**
             * Assessment Status
             * @default unavailable
             */
            assessment_status?: string;
            /**
             * Assessment Truncated
             * @default false
             */
            assessment_truncated?: boolean;
            /**
             * Corrected Answer
             * @default
             */
            corrected_answer?: string;
            /** Errata */
            errata?: {
                [key: string]: unknown;
            }[];
            /** Explanation Language */
            explanation_language?: string | null;
            /** Foreground */
            foreground?: {
                [key: string]: unknown;
            } | null;
            /** Verdict */
            verdict?: string | null;
        };
        /**
         * JournalCueView
         * @description What the learner sees *before* writing.
         *
         *     There is no ``setup_fr``, no ``character_line_fr`` and no ``title_fr`` here,
         *     and there must never be: free recall with the scene on screen is copying.
         */
        JournalCueView: {
            /** Character Name */
            character_name?: string | null;
            /** Days Ago */
            days_ago?: number | null;
            /** Location Name */
            location_name?: string | null;
            /** Scene Date */
            scene_date?: string | null;
        };
        /** JournalEntryView */
        JournalEntryView: {
            /** Content Recall */
            content_recall?: {
                [key: string]: unknown;
            } | null;
            correction?: components["schemas"]["JournalCorrectionView"] | null;
            cue: components["schemas"]["JournalCueView"];
            /** Entry Text */
            entry_text?: string | null;
            /**
             * Errata Recorded
             * @default 0
             */
            errata_recorded?: number;
            /** Followup Due On */
            followup_due_on: string;
            /** Id */
            id: string;
            /** Offered On */
            offered_on: string;
            /** Prompt Fr */
            prompt_fr: string;
            /** Reaction Fr */
            reaction_fr?: string | null;
            reveal?: components["schemas"]["JournalRevealView"] | null;
            /** Scene Date */
            scene_date: string;
            /** Status */
            status: string;
            /** Vocabulary Credit */
            vocabulary_credit?: {
                [key: string]: unknown;
            } | null;
        };
        /**
         * JournalEnvelope
         * @description One shape for every journal route.
         */
        JournalEnvelope: {
            entry?: components["schemas"]["JournalEntryView"] | null;
            followup?: components["schemas"]["JournalFollowupView"] | null;
            /**
             * Followup Offset Days
             * @default 7
             */
            followup_offset_days?: number;
            /**
             * Min Entry Words
             * @default 8
             */
            min_entry_words?: number;
            /**
             * Recall Offset Days
             * @default 1
             */
            recall_offset_days?: number;
            /** Status */
            status: string;
            /**
             * Version
             * @default journal-v1
             */
            version?: string;
        };
        /** JournalFollowupView */
        JournalFollowupView: {
            /**
             * Answered
             * @default false
             */
            answered?: boolean;
            /** Due On */
            due_on: string;
            /** Entry Id */
            entry_id: string;
            /** Prompt Fr */
            prompt_fr: string;
            /** Signal */
            signal?: string | null;
            /** Text */
            text?: string | null;
        };
        /**
         * JournalRevealView
         * @description The scene as it was. Attached only after the learner has written.
         */
        JournalRevealView: {
            /** Callback Fr */
            callback_fr?: string | null;
            /** Character Line Fr */
            character_line_fr?: string | null;
            /** Setup Fr */
            setup_fr?: string | null;
            /** Title Fr */
            title_fr?: string | null;
        };
        /** JourneyAdvanceRequest */
        JourneyAdvanceRequest: {
            /** Current Step Id */
            current_step_id: string;
            /** Expected Revision */
            expected_revision: number;
            /** Mutation Id */
            mutation_id: string;
        };
        /** JourneyAttemptRequest */
        JourneyAttemptRequest: {
            /** Expected Revision */
            expected_revision: number;
            /** Input */
            input: components["schemas"]["ChoiceAttemptInput"] | components["schemas"]["TilesAttemptInput"] | components["schemas"]["TextAttemptInput"] | components["schemas"]["VoiceAttemptInput"];
            /** Mutation Id */
            mutation_id: string;
        };
        /**
         * JourneyBecause
         * @description Why today's scene is this scene (WP-24, wired by WP-28).
         *
         *     Structured, never a rendered sentence: the server names the mistake and the
         *     component writes the French. ``kind`` is the only field a renderer may
         *     branch on, and an unknown kind must print nothing rather than guess —
         *     ``app/services/journey_errata.py::ErrataTarget.as_because`` produces it and
         *     ``app/services/journey_planner.py::plan_because`` decides whether the plan
         *     actually kept the target it names.
         */
        JourneyBecause: {
            /** Example */
            example: string | null;
            /** Kind */
            kind: string;
            /** Label */
            label: string;
            /** Reason */
            reason: string | null;
        };
        /** JourneyCorrection */
        JourneyCorrection: {
            /** Corrected Fr */
            corrected_fr: string;
            /** Note Native */
            note_native: string;
            /** Notes Native */
            notes_native?: string[];
            /** Span Fr */
            span_fr: string;
        };
        /** JourneyCreateRequest */
        JourneyCreateRequest: {
            /** Budget Seconds */
            budget_seconds?: (300 | 600 | 1200 | 1800) | null;
            /** Mutation Id */
            mutation_id: string;
            /** @default text */
            preferred_input_mode?: components["schemas"]["InputMode"];
            /**
             * Timezone
             * @default UTC
             */
            timezone?: string;
        };
        /** JourneyErrorBody */
        JourneyErrorBody: {
            detail: components["schemas"]["JourneyErrorDetail"];
        };
        /**
         * JourneyErrorCode
         * @enum {string}
         */
        JourneyErrorCode: "journey_version_conflict" | "idempotency_conflict" | "step_not_active" | "journey_not_active" | "empty_answer" | "journey_disabled" | "generation_unavailable" | "processing";
        /** JourneyErrorDetail */
        JourneyErrorDetail: {
            code: components["schemas"]["JourneyErrorCode"];
            /**
             * Current Revision
             * @default null
             */
            current_revision?: number | null;
            /** Message */
            message: string;
            /**
             * Refresh Href
             * @default null
             */
            refresh_href?: string | null;
            /**
             * Retry After Seconds
             * @default null
             */
            retry_after_seconds?: number | null;
        };
        /** JourneyFinishRequest */
        JourneyFinishRequest: {
            /** Expected Revision */
            expected_revision: number;
            /**
             * Finish Kind
             * @enum {string}
             */
            finish_kind: "complete" | "early";
            /** Mutation Id */
            mutation_id: string;
        };
        /** JourneyHelpRequest */
        JourneyHelpRequest: {
            /** Expected Revision */
            expected_revision: number;
            help_kind: components["schemas"]["HelpKind"];
            /** Mutation Id */
            mutation_id: string;
        };
        /** JourneyRecap */
        JourneyRecap: {
            /** Active Seconds */
            active_seconds: number | null;
            /** Can Dos Stamped */
            can_dos_stamped: string[];
            /** Capability Evidence */
            capability_evidence: components["schemas"]["CapabilityEvidence"][];
            chapter_closed: components["schemas"]["RecapChapterClosed"] | null;
            /** Collectible Ids */
            collectible_ids: string[];
            /**
             * Completion Kind
             * @enum {string}
             */
            completion_kind: "complete" | "early";
            /**
             * Consolidating
             * @default false
             */
            consolidating: boolean;
            /** Epreuve Line Fr */
            epreuve_line_fr: string | null;
            /** Epreuve Result */
            epreuve_result: ("passed" | "failed") | null;
            /** Estimated Core Seconds */
            estimated_core_seconds: number | null;
            forecast_line: components["schemas"]["RecapForecastLine"] | null;
            keepsake: components["schemas"]["RecapKeepsake"] | null;
            /** Level */
            level: string | null;
            level_up: components["schemas"]["RecapLevelUp"] | null;
            /** Margin Notes */
            margin_notes: components["schemas"]["MarginNote"][];
            mood: components["schemas"]["RecapMood"] | null;
            next_focus: components["schemas"]["NextFocus"] | null;
            objective_outcome: components["schemas"]["TaskOutcome"];
            /** Practiced Targets */
            practiced_targets: components["schemas"]["PracticedTarget"][];
            season_finished: components["schemas"]["RecapSeasonFinished"] | null;
            /**
             * Steps Done
             * @default 0
             */
            steps_done: number;
            story_outcome: components["schemas"]["StoryOutcome"] | null;
            teaser: components["schemas"]["RecapTeaser"] | null;
            /** Teaser Fr */
            teaser_fr: string | null;
            /** Words */
            words: components["schemas"]["RecapWord"][];
        };
        /** JourneyRetryRequest */
        JourneyRetryRequest: {
            /** Mutation Id */
            mutation_id: string;
        };
        /**
         * JourneyRevisionRequest
         * @description Body for pause and resume.
         */
        JourneyRevisionRequest: {
            /** Expected Revision */
            expected_revision: number;
            /** Mutation Id */
            mutation_id: string;
        };
        /** JourneySnapshot */
        JourneySnapshot: {
            absence: components["schemas"]["AbsenceView"] | null;
            /**
             * Budget Seconds
             * @default 300
             * @enum {integer}
             */
            budget_seconds: 300 | 600 | 1200 | 1800;
            /** Cast Intro */
            cast_intro: components["schemas"]["CastIntroEntry"][] | null;
            /**
             * Contract Version
             * @default 1
             * @constant
             */
            contract_version: 1;
            /** Current Step Id */
            current_step_id: string | null;
            /**
             * Day Shape
             * @default standard
             */
            day_shape: string;
            /** Edition No */
            edition_no: number | null;
            epreuve: components["schemas"]["EpreuveView"] | null;
            /** Estimated Active Seconds */
            estimated_active_seconds: number;
            /** Id */
            id: string;
            interlude: components["schemas"]["InterludeView"] | null;
            /** Learner Level */
            learner_level: string | null;
            /**
             * Local Date
             * Format: date
             */
            local_date: string;
            mastery_today: components["schemas"]["MasteryToday"] | null;
            /**
             * Missed Days
             * @default 0
             */
            missed_days: number;
            recap: components["schemas"]["JourneyRecap"] | null;
            retry: components["schemas"]["RetryHint"] | null;
            /** Revision */
            revision: number;
            scenario: components["schemas"]["ScenarioDescriptor"];
            season_premiere: components["schemas"]["SeasonPremiereView"] | null;
            /** Special */
            special: "epreuve" | null;
            status: components["schemas"]["JourneyStatus"];
            /** Steps */
            steps: (components["schemas"]["SceneStep"] | components["schemas"]["RecallStep"] | components["schemas"]["RespondStep"] | components["schemas"]["ResolutionStep"] | components["schemas"]["RuleStep"] | components["schemas"]["ForgeStep"] | components["schemas"]["ReadStep"] | components["schemas"]["DeskStep"])[];
            streak: components["schemas"]["StreakView"] | null;
            time_estimate: components["schemas"]["DayTimeEstimate"] | null;
            /** Timezone */
            timezone: string;
        };
        /**
         * JourneyStatus
         * @enum {string}
         */
        JourneyStatus: "preparing" | "active" | "paused" | "completed" | "ended_early" | "unavailable";
        /**
         * KeepWordRequest
         * @description WP-78 «Garder»: a word tapped in the story, and the sentence it was in.
         */
        KeepWordRequest: {
            /** Journey Id */
            journey_id?: string | null;
            /** Line Key */
            line_key?: string | null;
            /** Panel Id */
            panel_id?: string | null;
            /** Sentence */
            sentence: string;
            /** Speaker Id */
            speaker_id?: string | null;
            /** Surface */
            surface?: string | null;
            /** Term */
            term: string;
        };
        /**
         * LapsedLetter
         * @description WP-99. A letter that went cold during the absence.
         */
        LapsedLetter: {
            /** Correspondent Name */
            correspondent_name: string | null;
            /** Mission Id */
            mission_id: string;
        };
        /**
         * LearningFocusRead
         * @description Normalized focus item for the current learning moment.
         */
        LearningFocusRead: {
            /** Key */
            key: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "vocabulary" | "grammar" | "error";
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            };
            /**
             * Priority
             * @default 0
             */
            priority?: number;
            /** State */
            state?: string | null;
            /** Subtitle */
            subtitle?: string | null;
            /** Title */
            title: string;
        };
        /**
         * LearningMomentChoiceRead
         * @description Selectable choice for an inline learning moment.
         */
        LearningMomentChoiceRead: {
            /** Key */
            key: string;
            /** Label */
            label: string;
        };
        /**
         * LearningMomentRead
         * @description Serializable inline learning moment attached to a session turn.
         */
        LearningMomentRead: {
            /** Body */
            body: string;
            /** Choices */
            choices?: components["schemas"]["LearningMomentChoiceRead"][];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Input Mode
             * @enum {string}
             */
            input_mode: "free_text" | "single_choice" | "chips";
            /**
             * Kind
             * @enum {string}
             */
            kind: "conversation_turn" | "vocab_boost" | "vocab_check" | "grammar_challenge" | "grammar_repair" | "error_repair";
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            };
            /** Prefill Text */
            prefill_text?: string | null;
            /**
             * Source Type
             * @enum {string}
             */
            source_type: "vocabulary" | "grammar" | "error";
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "completed" | "skipped" | "expired";
            /** Title */
            title: string;
        };
        /**
         * LearningMomentResultRead
         * @description Outcome after resolving an inline learning moment.
         */
        LearningMomentResultRead: {
            /** Feedback Summary */
            feedback_summary: string;
            /** Is Correct */
            is_correct?: boolean | null;
            /**
             * Moment Id
             * Format: uuid
             */
            moment_id: string;
            /** Next Step Hint */
            next_step_hint?: string | null;
            /** Score 0 10 */
            score_0_10?: number | null;
        };
        /** LegacyResume */
        LegacyResume: {
            /** Href */
            href: string;
            /** Session Id */
            session_id: string;
        };
        /**
         * LevelCheckpointResultRequest
         * @description WP-L7: the story engine reports the band's épreuve.
         */
        LevelCheckpointResultRequest: {
            /** Band */
            band: string;
            /** Episode Id */
            episode_id?: string | null;
            /** Evidence */
            evidence?: {
                [key: string]: unknown;
            } | null;
            /** Passed */
            passed: boolean;
        };
        /**
         * LineAudioRequest
         * @description ``POST /daily-journeys/{journey_id}/steps/{step_id}/line-audio``.
         *
         *     ``text_fr`` must be a line that actually appears in that step for this
         *     learner (404 otherwise): the route never speaks arbitrary text.
         *     ``character_id`` is a hint for which speaker is meant when two say the same
         *     words; the voice is always the server's, from the line it matched.
         */
        LineAudioRequest: {
            /** Character Id */
            character_id?: string | null;
            /** Text Fr */
            text_fr: string;
        };
        /**
         * LineAudioResult
         * @description ``ready`` carries the clip to fetch; ``disabled`` means "use the device
         *     voice" (audio off on this deployment, the provider unavailable, or the
         *     learner's daily cap near). The four other fields are present only when
         *     ``ready``.
         */
        LineAudioResult: {
            /** Cached */
            cached?: boolean | null;
            /** Clip Id */
            clip_id?: string | null;
            /** Content Type */
            content_type?: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "disabled";
            /** Voice */
            voice?: string | null;
        };
        /** LinkedVocabularyErratumRead */
        LinkedVocabularyErratumRead: {
            /** Error Category */
            error_category?: string | null;
            /** Linked Word Id */
            linked_word_id?: number | null;
            /** Review Mode */
            review_mode?: string | null;
            /** Task Error Type */
            task_error_type?: string | null;
        } & {
            [key: string]: unknown;
        };
        /**
         * LiveStoryListResponse
         * @description Collection of live stories in the learner's target language.
         */
        LiveStoryListResponse: {
            /** Items */
            items: components["schemas"]["LiveStoryRead"][];
            /** Topics Used */
            topics_used?: string[];
        };
        /**
         * LiveStoryRead
         * @description Live headline item for story-based quick start.
         */
        LiveStoryRead: {
            /** Id */
            id: string;
            /** Language */
            language: string;
            /** Source */
            source: string;
            /** Summary */
            summary?: string | null;
            /** Title */
            title: string;
            /** Url */
            url: string;
        };
        /**
         * LogoutRequest
         * @description Optional refresh token payload for explicit session logout.
         */
        LogoutRequest: {
            /** Refresh Token */
            refresh_token?: string | null;
        };
        /**
         * MarginNote
         * @description WP-97 «Les suites»: a consequence or callback paid back on this page,
         *     printed as a dated note in the margin («Parce que vous avez dit … — Nº 4»).
         *     Read from the scene's ``script_payload.margin_notes`` (the story lane).
         */
        MarginNote: {
            /** Cause Date */
            cause_date: string | null;
            /** Cause Edition No */
            cause_edition_no: number | null;
            /** Cause Scene Id */
            cause_scene_id: string | null;
            /** Character Id */
            character_id: string | null;
            /** Panel Id */
            panel_id: string | null;
            /** Panel Index */
            panel_index: number | null;
            /** Text Fr */
            text_fr: string;
        };
        /**
         * MasteryToday
         * @description WP-S7: mastery earned on the journey's local day.
         */
        MasteryToday: {
            /** Held Concept Ids */
            held_concept_ids: number[];
            /** Tested Out Concept Ids */
            tested_out_concept_ids: number[];
        };
        /**
         * MetricPoint
         * @description Time series datapoint.
         */
        MetricPoint: {
            /**
             * Date
             * Format: date
             */
            date: string;
            /** Value */
            value: number;
        };
        /** MissionAttemptResponse */
        MissionAttemptResponse: {
            /** Attempt */
            attempt: {
                [key: string]: unknown;
            };
            correction: components["schemas"]["MissionCorrectionRead"];
            /** Errata */
            errata?: components["schemas"]["LinkedVocabularyErratumRead"][];
            mission: components["schemas"]["MissionRead"];
        };
        /** MissionCompleteResponse */
        MissionCompleteResponse: {
            mission: components["schemas"]["MissionRead"];
            /** Next Serial */
            next_serial?: {
                [key: string]: unknown;
            } | null;
            recap: components["schemas"]["MissionRecapRead"];
        };
        /** MissionCorrectionRead */
        MissionCorrectionRead: {
            /** Errata */
            errata?: components["schemas"]["LinkedVocabularyErratumRead"][];
            /** Vocabulary Events */
            vocabulary_events?: components["schemas"]["VocabularyEventRead"][];
        } & {
            [key: string]: unknown;
        };
        /** MissionCreateRequest */
        MissionCreateRequest: {
            /** Atelier Session Id */
            atelier_session_id?: string | null;
            /**
             * Cadence
             * @default weekly
             */
            cadence?: string;
            /** Custom Scenario */
            custom_scenario?: string | null;
            /** Desired Outcome */
            desired_outcome?: string | null;
            /** Episode Index */
            episode_index?: number | null;
            /**
             * Mission Type
             * @default message
             */
            mission_type?: string;
            /** Preferred Concept Ids */
            preferred_concept_ids?: number[] | null;
            /** Preferred Errata Ids */
            preferred_errata_ids?: string[] | null;
            /** Preferred Vocabulary Ids */
            preferred_vocabulary_ids?: number[] | null;
            /** Register */
            register?: string | null;
            /** Relationship */
            relationship?: string | null;
            /** Serial Thread Id */
            serial_thread_id?: string | null;
            /** Stakes Level */
            stakes_level?: number | null;
            /**
             * Use News
             * @default false
             */
            use_news?: boolean;
        };
        /** MissionRead */
        MissionRead: {
            /** Atelier Session Id */
            atelier_session_id?: string | null;
            /** Attempts */
            attempts?: {
                [key: string]: unknown;
            }[];
            /** Brief */
            brief: string;
            /** Cadence */
            cadence: string;
            /** Completed At */
            completed_at?: string | null;
            /** Created At */
            created_at?: string | null;
            /** Episode Index */
            episode_index?: number | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Iso Week */
            iso_week?: number | null;
            /** Iso Year */
            iso_year?: number | null;
            /**
             * Mission Format
             * @default chat_message
             */
            mission_format?: string;
            /** Mission Type */
            mission_type: string;
            /** Objectives */
            objectives?: {
                [key: string]: unknown;
            }[];
            /** Outcome */
            outcome?: {
                [key: string]: unknown;
            } | null;
            /** Prompt Payload */
            prompt_payload?: {
                [key: string]: unknown;
            };
            recap?: components["schemas"]["MissionRecapRead"];
            /** Selected Concept Ids */
            selected_concept_ids?: number[];
            /** Serial Thread Id */
            serial_thread_id?: string | null;
            /** Source Snapshot */
            source_snapshot?: {
                [key: string]: unknown;
            };
            /**
             * Stakes Level
             * @default 1
             */
            stakes_level?: number;
            /** Started At */
            started_at?: string | null;
            /** Status */
            status: string;
            /** Target Errata Ids */
            target_errata_ids?: string[];
            /** Target Vocabulary */
            target_vocabulary?: components["schemas"]["TargetVocabularyRead"][];
            /** Target Vocabulary Ids */
            target_vocabulary_ids?: number[];
            /** Title */
            title: string;
            /** Turns */
            turns?: {
                [key: string]: unknown;
            }[];
        } & {
            [key: string]: unknown;
        };
        /** MissionRecapRead */
        MissionRecapRead: {
            vocabulary_credit?: components["schemas"]["VocabularyCreditSummary"];
        } & {
            [key: string]: unknown;
        };
        /** MissionResponse */
        MissionResponse: {
            mission: components["schemas"]["MissionRead"];
        };
        /** MissionSubmitRequest */
        MissionSubmitRequest: {
            /**
             * Mode
             * @default writing
             */
            mode?: string;
            /**
             * Text
             * @default
             */
            text?: string;
        };
        /** MissionTodayResponse */
        MissionTodayResponse: {
            active_mission?: components["schemas"]["MissionRead"] | null;
            post_session_recommendation?: components["schemas"]["MissionRead"] | null;
            /** Recent Completed */
            recent_completed?: components["schemas"]["MissionRead"][];
            weekly_mission?: components["schemas"]["MissionRead"] | null;
        };
        /** MissionTurnRequest */
        MissionTurnRequest: {
            /**
             * Mode
             * @default chat
             */
            mode?: string;
            /**
             * Text
             * @default
             */
            text?: string;
            /** Transcript Metadata */
            transcript_metadata?: {
                [key: string]: unknown;
            };
        };
        /** MissionTurnResponse */
        MissionTurnResponse: {
            /** Assistant Turn */
            assistant_turn: {
                [key: string]: unknown;
            };
            correction: components["schemas"]["MissionCorrectionRead"];
            /** Errata */
            errata?: components["schemas"]["LinkedVocabularyErratumRead"][];
            mission: components["schemas"]["MissionRead"];
            /** Outcome */
            outcome?: {
                [key: string]: unknown;
            };
            /** User Turn */
            user_turn: {
                [key: string]: unknown;
            };
        };
        /**
         * NarrativeChoiceRequest
         * @description Request to make a narrative branching choice.
         */
        NarrativeChoiceRequest: {
            /** Choice Id */
            choice_id: string;
        };
        /**
         * NarrativeChoiceResponse
         * @description Response for narrative choice.
         */
        NarrativeChoiceResponse: {
            /** Choice Recorded */
            choice_recorded: string;
            next_chapter?: components["schemas"]["ChapterRead"] | null;
            /** Next Chapter Id */
            next_chapter_id: string;
        };
        /** NextFocus */
        NextFocus: {
            /** Reason Native */
            reason_native: string;
            target: components["schemas"]["TargetRef"];
        };
        /** NextTurn */
        NextTurn: {
            prompt: components["schemas"]["RespondPrompt"];
            /** Step Id */
            step_id: string;
        };
        /**
         * NPCDetailRead
         * @description Full NPC details including personality.
         */
        NPCDetailRead: {
            /** Appearance Description */
            appearance_description?: string | null;
            /** Avatar Url */
            avatar_url?: string | null;
            /** Backstory */
            backstory?: string | null;
            /** Display Name */
            display_name?: string | null;
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Personality */
            personality?: {
                [key: string]: unknown;
            };
            /** Role */
            role?: string | null;
            /** Speech Pattern */
            speech_pattern?: {
                [key: string]: unknown;
            };
        };
        /**
         * NPCInSceneRead
         * @description NPC with relationship context for scene display.
         */
        NPCInSceneRead: {
            /** Avatar Url */
            avatar_url?: string | null;
            /** Display Name */
            display_name?: string | null;
            /** Id */
            id: string;
            /**
             * Mood
             * @default neutral
             */
            mood?: string;
            /** Name */
            name: string;
            /**
             * Relationship Level
             * @default 1
             */
            relationship_level?: number;
            /** Role */
            role?: string | null;
            /**
             * Trust
             * @default 0
             */
            trust?: number;
        };
        /**
         * NPCMemoryRead
         * @description Schema for NPC memory items.
         */
        NPCMemoryRead: {
            /** Content */
            content: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Id */
            id: string;
            /** Memory Type */
            memory_type: string;
            /** Player Quote */
            player_quote?: string | null;
            /** Scene Id */
            scene_id?: string | null;
            /**
             * Sentiment
             * @default neutral
             */
            sentiment?: string;
        };
        /**
         * NPCRelationshipRead
         * @description Schema for NPC relationship status.
         */
        NPCRelationshipRead: {
            /** First Interaction At */
            first_interaction_at?: string | null;
            /** Last Interaction At */
            last_interaction_at?: string | null;
            /**
             * Level
             * @default 1
             */
            level?: number;
            /**
             * Mood
             * @default neutral
             */
            mood?: string;
            /**
             * Negative Interactions
             * @default 0
             */
            negative_interactions?: number;
            /** Npc Avatar Url */
            npc_avatar_url?: string | null;
            /** Npc Id */
            npc_id: string;
            /** Npc Name */
            npc_name: string;
            /**
             * Positive Interactions
             * @default 0
             */
            positive_interactions?: number;
            /**
             * Total Interactions
             * @default 0
             */
            total_interactions?: number;
            /**
             * Trust
             * @default 0
             */
            trust?: number;
        };
        /**
         * NPCResponseRead
         * @description Schema for NPC response to player input.
         */
        NPCResponseRead: {
            /** Content */
            content: string;
            /** Emotion */
            emotion?: string | null;
            infobox?: components["schemas"]["InfoboxRead"] | null;
            /** Memory Added */
            memory_added?: string | null;
            /** New Mood */
            new_mood?: string | null;
            /**
             * New Relationship Level
             * @default 1
             */
            new_relationship_level?: number;
            /** Npc Id */
            npc_id: string;
            /** Npc Name */
            npc_name: string;
            /**
             * Relationship Delta
             * @default 0
             */
            relationship_delta?: number;
            /** Voice Url */
            voice_url?: string | null;
        };
        /**
         * ObjectiveRead
         * @description Schema for scene objectives.
         */
        ObjectiveRead: {
            /**
             * Completed
             * @default false
             */
            completed?: boolean;
            /** Description */
            description: string;
            /** Id */
            id: string;
            /**
             * Optional
             * @default false
             */
            optional?: boolean;
            /**
             * Type
             * @default task
             */
            type?: string;
        };
        /**
         * PasswordResetConfirm
         * @description Confirm a password reset with a one-time link token, or email plus code.
         *
         *     The six-digit code is the phone path (WP-71): no web host or universal link
         *     is needed. The link token stays accepted for emails already sent.
         */
        PasswordResetConfirm: {
            /** Code */
            code?: string | null;
            /** Email */
            email?: string | null;
            /** New Password */
            new_password: string;
            /** Token */
            token?: string | null;
        };
        /**
         * PasswordResetRequest
         * @description Request a password reset code (and link, where a public app URL exists).
         */
        PasswordResetRequest: {
            /**
             * Email
             * Format: email
             */
            email: string;
        };
        /**
         * PasswordResetRequestResponse
         * @description Enumeration-safe password reset request response.
         */
        PasswordResetRequestResponse: {
            /** Message */
            message: string;
            /** Reset Code */
            reset_code?: string | null;
            /** Reset Token */
            reset_token?: string | null;
            /** Reset Url */
            reset_url?: string | null;
        };
        /**
         * PlacementEnvelope
         * @description One shape for every placement route.
         */
        PlacementEnvelope: {
            /**
             * Confidence
             * @default 0
             */
            confidence?: number;
            /** Estimate */
            estimate?: {
                [key: string]: unknown;
            } | null;
            /** Level */
            level?: string | null;
            /**
             * Offer
             * @default false
             */
            offer?: boolean;
            /** Prior */
            prior?: {
                [key: string]: unknown;
            } | null;
            prompt?: components["schemas"]["PlacementPromptView"] | null;
            /** Session Id */
            session_id?: string | null;
            /** Status */
            status: string;
            /**
             * Version
             * @default placement-v1
             */
            version?: string;
        };
        /**
         * PlacementOffer
         * @description WP-75 / WP-126: whether to offer the placement now. Never true at sign-up.
         */
        PlacementOffer: {
            /** Offer */
            offer: boolean;
            /** Reason */
            reason?: string | null;
            /**
             * Resume
             * @default false
             */
            resume?: boolean;
        };
        /**
         * PlacementPromptView
         * @description The turn on screen, or ``None`` when the conversation is over.
         */
        PlacementPromptView: {
            /** Band */
            band: string;
            /** Hint By Language */
            hint_by_language?: {
                [key: string]: string;
            };
            /** Hint Fr */
            hint_fr: string;
            /** Index */
            index: number;
            /**
             * Max Turns
             * @default 6
             */
            max_turns?: number;
            /** Prompt Fr */
            prompt_fr: string;
            /** Turns So Far */
            turns_so_far: number;
        };
        /** Position */
        Position: {
            /** Panel Index */
            panel_index: number;
        };
        /** PracticedTarget */
        PracticedTarget: {
            assistance_level: components["schemas"]["AssistanceLevel"];
            evidence_kind: components["schemas"]["EvidenceKind"];
            /** Practice Href */
            practice_href: string | null;
            target: components["schemas"]["TargetRef"];
        };
        /** PracticeIssue */
        PracticeIssue: {
            /** Category */
            category?: string | null;
            /** Correction */
            correction?: string | null;
            /** Issue */
            issue?: string | null;
            /** Sentence */
            sentence?: string | null;
            /** Translation */
            translation?: string | null;
            /** Word */
            word: string;
        };
        /** PredictionCheck */
        PredictionCheck: {
            /** Guess */
            guess: string;
            /** Supported */
            supported?: string | null;
            /** Verdict */
            verdict: string;
        };
        /**
         * ProgressDetail
         * @description Detailed view of a learner's progress for a word.
         */
        ProgressDetail: {
            /** Correct Count */
            correct_count: number;
            /** Difficulty */
            difficulty: number | null;
            /** Hint Count */
            hint_count: number;
            /** Incorrect Count */
            incorrect_count: number;
            /** Lapses */
            lapses: number;
            /** Last Review */
            last_review: string | null;
            /** Next Review */
            next_review: string | null;
            /** Proficiency Score */
            proficiency_score: number;
            /** Reps */
            reps: number;
            /** Reviews Logged */
            reviews_logged: number;
            /** Scheduled Days */
            scheduled_days: number | null;
            /** Stability */
            stability: number | null;
            /** State */
            state: string;
            /** Word Id */
            word_id: number;
        };
        /**
         * QueueWord
         * @description Vocabulary entry returned in the review queue.
         */
        QueueWord: {
            /** Difficulty Level */
            difficulty_level?: number | null;
            /** English Translation */
            english_translation?: string | null;
            /** French Translation */
            french_translation?: string | null;
            /** German Translation */
            german_translation?: string | null;
            /** Is New */
            is_new: boolean;
            /** Language */
            language: string;
            /** Next Review */
            next_review?: string | null;
            /** Part Of Speech */
            part_of_speech?: string | null;
            /** Scheduled Days */
            scheduled_days?: number | null;
            /** Scheduler */
            scheduler?: string | null;
            /** State */
            state: string;
            /** Word */
            word: string;
            /** Word Id */
            word_id: number;
        };
        /**
         * QuickStartRequest
         * @description Optional payload for quick-start customization.
         */
        QuickStartRequest: {
            /** Story Source */
            story_source?: string | null;
            /** Story Summary */
            story_summary?: string | null;
            /** Story Title */
            story_title?: string | null;
            /** Story Url */
            story_url?: string | null;
        };
        /** RadioBulletinView */
        RadioBulletinView: {
            /**
             * Audio
             * @enum {string}
             */
            audio: "ready" | "unavailable" | "text_only";
            /** Audio Reason */
            audio_reason?: ("spend_cap" | "tts_failed") | null;
            /** Band */
            band: string;
            dictee: components["schemas"]["RadioDictee"];
            /** Dossier Id */
            dossier_id: string;
            /** Guest Id */
            guest_id: string;
            /** Lines */
            lines: components["schemas"]["RadioLine"][];
            /** Seconds */
            seconds: number;
            stage: components["schemas"]["RadioStage"];
            /** Title Fr */
            title_fr: string;
            /** Topic */
            topic: string;
            /** Week */
            week: string;
        };
        /** RadioDictee */
        RadioDictee: {
            /** Line Index */
            line_index: number;
            /** Words */
            words: number;
        };
        /** RadioDicteeRequest */
        RadioDicteeRequest: {
            /** Band */
            band?: string | null;
            /**
             * Text
             * @default
             */
            text?: string;
        };
        /** RadioDicteeResult */
        RadioDicteeResult: {
            /** Expected Fr */
            expected_fr: string;
            /** Note */
            note?: string | null;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "met" | "partially_met" | "not_yet";
        };
        /** RadioHeardRequest */
        RadioHeardRequest: {
            /** Band */
            band?: string | null;
            /** Dictee */
            dictee?: ("met" | "partially_met" | "not_yet") | null;
        };
        /** RadioItem */
        RadioItem: {
            /** Dossier Id */
            dossier_id: string;
            /** Evergreen */
            evergreen: boolean;
            /** Title Fr */
            title_fr: string;
            /** Topic */
            topic: string;
        };
        /** RadioLine */
        RadioLine: {
            /** Claim Id */
            claim_id?: string | null;
            /** Clip Url */
            clip_url?: string | null;
            /** Index */
            index: number;
            /**
             * Role
             * @enum {string}
             */
            role: "lede" | "claim" | "uncertainty" | "guest" | "signoff";
            /** Speaker */
            speaker: string;
            /** Speaker Name */
            speaker_name: string;
            /** Text Fr */
            text_fr: string;
        };
        /** RadioStage */
        RadioStage: {
            /** Place Fr */
            place_fr: string;
            /** Plate Url */
            plate_url: string | null;
        };
        /** RadioWeekView */
        RadioWeekView: {
            /** Chip */
            chip: boolean;
            current: components["schemas"]["RadioItem"] | null;
            /** Heard */
            heard: string[];
            /** Heard Today */
            heard_today: boolean;
            /** Queue */
            queue: components["schemas"]["RadioItem"][];
            /** Seconds */
            seconds?: number | null;
            /** Week */
            week: string;
        };
        /**
         * ReadPrompt
         * @description WP-93 «Lecture»: a second page on a long rhythm, after the ending.
         *
         *     ``relecture`` is yesterday's page again (heard when ``audio_available``);
         *     ``coulisses`` is today's evening from another cast member's side, written
         *     after the day is planned. ``scene_id`` opens it through
         *     ``GET /api/v1/story-engine/episodes/{scene_id}`` once ``status`` is
         *     ``ready``; ``writing`` means poll the journey, ``unavailable`` means there
         *     is nothing to read today (the step is optional). Advanced, not answered.
         *     Projected on every read, never trusted from the stored plan alone.
         */
        ReadPrompt: {
            /**
             * Audio Available
             * @default false
             */
            audio_available: boolean;
            /** Character Id */
            character_id: string | null;
            /** Character Name */
            character_name: string | null;
            /** Scene Id */
            scene_id: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "writing" | "unavailable";
            /** Title Fr */
            title_fr: string;
            /**
             * Variant
             * @enum {string}
             */
            variant: "relecture" | "coulisses";
        };
        /** ReadStep */
        ReadStep: {
            /** Assistance Used */
            assistance_used: components["schemas"]["AssistanceLevel"][];
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "read";
            /** Ordinal */
            ordinal: number;
            prompt: components["schemas"]["ReadPrompt"];
            status: components["schemas"]["StepStatus"];
        };
        /**
         * RecallAnswerKey
         * @description WP-76. A key the client can check a pick against but cannot read.
         *
         *     ``digests`` are SHA-256 of ``salt + ":" + material`` (see
         *     ``app/services/journey_answer_key.py``). A preview only: the server's
         *     verdict on the attempt stays authoritative.
         */
        RecallAnswerKey: {
            /** Digests */
            digests: string[];
            /** Salt */
            salt: string;
            /**
             * Version
             * @default 1
             */
            version: number;
        };
        /**
         * RecallMet
         * @description WP-121 A.4: the Papier a recalled word was kept in, as one French line.
         */
        RecallMet: {
            /** Place Label Fr */
            place_label_fr: string;
        };
        /**
         * RecallOption
         * @description Never carries correctness: an option id says nothing about the answer.
         */
        RecallOption: {
            /** Character Id */
            character_id?: string | null;
            /** Id */
            id: string;
            /** Side */
            side?: ("fr" | "native") | null;
            /** Text Fr */
            text_fr: string;
        };
        /** RecallPrompt */
        RecallPrompt: {
            answer_key: components["schemas"]["RecallAnswerKey"] | null;
            /** Audio Url */
            audio_url?: string | null;
            /** Goal Native */
            goal_native: string | null;
            /** Help Available */
            help_available: components["schemas"]["HelpKind"][];
            /** Instruction Native */
            instruction_native: string;
            met?: components["schemas"]["RecallMet"] | null;
            /** Optional */
            optional: boolean;
            /** Options */
            options: components["schemas"]["RecallOption"][];
            /** Prompt Fr */
            prompt_fr: string | null;
            /** Source Fr */
            source_fr: string | null;
            target: components["schemas"]["TargetRef"];
            /**
             * Task Type
             * @enum {string}
             */
            task_type: "choice" | "tiles" | "short_answer" | "transform" | "classify" | "word_bank" | "match_pairs" | "listen_tap" | "unscramble" | "who_said" | "dictation";
        };
        /** RecallStep */
        RecallStep: {
            /** Assistance Used */
            assistance_used: components["schemas"]["AssistanceLevel"][];
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "recall";
            /** Ordinal */
            ordinal: number;
            prompt: components["schemas"]["RecallPrompt"];
            status: components["schemas"]["StepStatus"];
        };
        /**
         * RecapChapterClosed
         * @description WP-96: the chapter today closed, for the «Fin du chapitre» colophon.
         */
        RecapChapterClosed: {
            /** Digest Fr */
            digest_fr: string | null;
            /** Index */
            index: number;
            /**
             * Title Fr
             * @default
             */
            title_fr: string;
        };
        /**
         * RecapForecastLine
         * @description WP-L8 — «At this rhythm: A1.2 around <month>» (the client writes it).
         */
        RecapForecastLine: {
            /** Band */
            band: string | null;
            /**
             * Measured
             * @default true
             */
            measured: boolean;
            /** Month */
            month: string;
            /** Range Days */
            range_days: number[];
            /** Rhythm */
            rhythm: string | null;
            /** Target */
            target: string;
        };
        /**
         * RecapKeepsake
         * @description The vignette minted for a completed day (WP-09 §4), finally shown.
         */
        RecapKeepsake: {
            /** Collectible Id */
            collectible_id: string;
            /** Image Url */
            image_url: string | null;
            /**
             * Local Date
             * Format: date
             */
            local_date: string;
            /** Location Name */
            location_name: string | null;
            /** Title Fr */
            title_fr: string;
        };
        /**
         * RecapLevelUp
         * @description The CEFR estimate moved up since the previous recap (shown once).
         */
        RecapLevelUp: {
            /** From Level */
            from_level: string;
            /**
             * Mastered Grammar
             * @default 0
             */
            mastered_grammar: number;
            /**
             * Mastered Vocabulary
             * @default 0
             */
            mastered_vocabulary: number;
            /** To Level */
            to_level: string;
        };
        /**
         * RecapMood
         * @description The day's character, as the living story's WP-61 mood ledger left them.
         *
         *     ``shift`` is ``None`` unless the ledger's last move was *this* journey's
         *     exchange (``last_event_id``), so a face never claims a change the day did
         *     not make. ``mood`` is the ledger's −2 … +2.
         */
        RecapMood: {
            /** Character Id */
            character_id: string;
            /** Character Name */
            character_name: string;
            /**
             * Mood
             * @default 0
             */
            mood: number;
            /** Shift */
            shift: ("warmer" | "colder" | "steady") | null;
        };
        /**
         * RecapSeasonFinished
         * @description WP-96: the season today finished — it becomes «Tome N».
         */
        RecapSeasonFinished: {
            /** Number */
            number: number;
            /**
             * Title Fr
             * @default
             */
            title_fr: string;
        };
        /**
         * RecapTeaser
         * @description «La suite demain» — one French line in a character's voice.
         *
         *     ``source``: ``engine`` (the living story's ``next_teaser``), ``resolution``
         *     (the resolution's last forward-looking line) or ``authored`` (a line per
         *     band that promises no plot point). Same order as WP-80's morning push.
         */
        RecapTeaser: {
            /** Character Id */
            character_id: string | null;
            /** Character Name */
            character_name: string | null;
            /**
             * Source
             * @enum {string}
             */
            source: "engine" | "resolution" | "authored";
            /** Text Fr */
            text_fr: string;
        };
        /**
         * RecapWord
         * @description One vocabulary target the day actually practised (not a "not yet").
         */
        RecapWord: {
            evidence_kind: components["schemas"]["EvidenceKind"];
            /** Id */
            id: string;
            /** Label Fr */
            label_fr: string;
            /** Label Native */
            label_native: string | null;
        };
        /**
         * RefreshTokenRequest
         * @description Request body for rotating an access/refresh token pair.
         */
        RefreshTokenRequest: {
            /** Refresh Token */
            refresh_token: string;
        };
        /**
         * RehearsalCapView
         * @description The weekly bound, as the learner sees it.
         */
        RehearsalCapView: {
            /** Limit */
            limit: number;
            /** Next Slot At */
            next_slot_at?: string | null;
            /** Remaining */
            remaining: number;
            /** Used */
            used: number;
        };
        /**
         * RehearsalEnvelope
         * @description One shape for every rehearsal route.
         */
        RehearsalEnvelope: {
            cap: components["schemas"]["RehearsalCapView"];
            /** Debrief Due */
            debrief_due?: {
                [key: string]: unknown;
            } | null;
            /**
             * Max Turns
             * @default 6
             */
            max_turns?: number;
            /**
             * Min Turns
             * @default 3
             */
            min_turns?: number;
            /** Rehearsal */
            rehearsal?: {
                [key: string]: unknown;
            } | null;
            /**
             * Version
             * @default rehearsal-v1
             */
            version?: string;
        };
        /** RelectureAnswerRequest */
        RelectureAnswerRequest: {
            /** Answer Fr */
            answer_fr: string;
            /**
             * Mode
             * @default text
             * @enum {string}
             */
            mode?: "text" | "voice";
        };
        /** RelectureOffer */
        RelectureOffer: {
            /** Closed At */
            closed_at?: string | null;
            /** Dossier Title Fr */
            dossier_title_fr: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "question" | "headline";
            /** Place Label Fr */
            place_label_fr: string;
            /** Plate Url */
            plate_url?: string | null;
            /** Prompt Fr */
            prompt_fr: string;
            /** Session Id */
            session_id: string;
            /** Week */
            week: string;
        };
        /** RelectureOfferView */
        RelectureOfferView: {
            offer?: components["schemas"]["RelectureOffer"] | null;
        };
        /** RelecturePair */
        RelecturePair: {
            /** Asked At */
            asked_at: string;
            now: components["schemas"]["RelectureSide"];
            offer: components["schemas"]["RelectureOffer"];
            /** Romy Line Fr */
            romy_line_fr: string;
            /** Session Id */
            session_id: string;
            then: components["schemas"]["RelectureSide"];
        };
        /** RelectureSide */
        RelectureSide: {
            /** Label Fr */
            label_fr: string;
            /**
             * Spans
             * @default []
             */
            spans?: components["schemas"]["RelectureSpan"][];
            /** Text Fr */
            text_fr: string;
        };
        /** RelectureSpan */
        RelectureSpan: {
            /** End */
            end: number;
            /**
             * Flag
             * @enum {string}
             */
            flag: "register" | "grammar";
            /** Start */
            start: number;
        };
        /** ReleveClaim */
        ReleveClaim: {
            /** Attributed To */
            attributed_to?: string | null;
            /** Fr */
            fr: string;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Quote */
            quote: string;
            source: components["schemas"]["ReleveSource"];
        };
        /** ReleveEntry */
        ReleveEntry: {
            /** Claims */
            claims: components["schemas"]["ReleveClaim"][];
            /** Closed At */
            closed_at: string | null;
            /** Headline Fr */
            headline_fr?: string | null;
            made?: components["schemas"]["ReleveMade"] | null;
            /** Period */
            period: string;
            /** Period Label */
            period_label: string;
            /**
             * Second
             * @default false
             */
            second?: boolean;
            /** Session Id */
            session_id: string;
            /** Sources */
            sources: components["schemas"]["ReleveSource"][];
            /** Title Fr */
            title_fr: string;
            /** Words */
            words: components["schemas"]["ReleveWord"][];
        };
        /** ReleveMade */
        ReleveMade: {
            /** Kind */
            kind: string;
            /** Text Fr */
            text_fr: string;
        };
        /** ReleveSource */
        ReleveSource: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Published At */
            published_at: string;
            /** Url */
            url: string;
        };
        /** ReleveView */
        ReleveView: {
            /** Entries */
            entries: components["schemas"]["ReleveEntry"][];
        };
        /** ReleveWord */
        ReleveWord: {
            /** Claim Id */
            claim_id: string;
            /** Fr */
            fr: string;
            /** Gloss */
            gloss: string;
            /**
             * Used
             * @default false
             */
            used?: boolean;
        };
        /** ResolutionPrompt */
        ResolutionPrompt: {
            /** Chapter Recap Fr */
            chapter_recap_fr: string | null;
            /** Character Line Fr */
            character_line_fr: string;
            /** Image Url */
            image_url: string | null;
            /**
             * Narrated
             * @default false
             */
            narrated: boolean;
            /** Outcome Key */
            outcome_key: string;
            /** Register Note Fr */
            register_note_fr: string | null;
            /** Register Reason Native */
            register_reason_native: string | null;
            /**
             * Story Pending
             * @default false
             */
            story_pending: boolean;
            /** Summary Native */
            summary_native: string;
        };
        /** ResolutionStep */
        ResolutionStep: {
            /** Assistance Used */
            assistance_used: components["schemas"]["AssistanceLevel"][];
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "resolution";
            /** Ordinal */
            ordinal: number;
            prompt: components["schemas"]["ResolutionPrompt"];
            status: components["schemas"]["StepStatus"];
        };
        /**
         * RespondChoice
         * @description WP-113 «Le choix»: one card the learner can tap to answer the question.
         */
        RespondChoice: {
            /** Id */
            id: string;
            /** Label Fr */
            label_fr: string;
            /** Label Native */
            label_native: string | null;
        };
        /**
         * RespondLetter
         * @description WP-66 «jour de lettre»: the letter the learner is answering.
         *
         *     Public by construction — it is what the learner reads — and deliberately
         *     flat strings rather than a mission model: WP-64 owns the Courrier and this
         *     contract must not depend on its internals. ``None`` on every other shape.
         */
        RespondLetter: {
            /** Body Fr */
            body_fr: string;
            /** Correspondent Id */
            correspondent_id: string;
            /** Correspondent Name */
            correspondent_name: string;
            /** Mission Id */
            mission_id: string;
            /** Objective Native */
            objective_native: string;
            /** Subject Fr */
            subject_fr: string;
        };
        /** RespondPrompt */
        RespondPrompt: {
            /** Character Id */
            character_id: string;
            /** Character Line Audio Url */
            character_line_audio_url: string | null;
            /** Character Line Fr */
            character_line_fr: string;
            /** Character Name */
            character_name: string;
            /** Choices */
            choices: components["schemas"]["RespondChoice"][];
            /** Help Available */
            help_available: components["schemas"]["HelpKind"][];
            /** Input Modes */
            input_modes: components["schemas"]["InputMode"][];
            letter: components["schemas"]["RespondLetter"] | null;
            /** Max Turns */
            max_turns: number;
            /** Objective Native */
            objective_native: string;
            /** Repair Allowed */
            repair_allowed: boolean;
            /** Targets */
            targets: components["schemas"]["TargetRef"][];
            /** Thread */
            thread: components["schemas"]["ThreadExchange"][];
            /** Turn Index */
            turn_index: number;
        };
        /** RespondRequest */
        RespondRequest: {
            /**
             * Answer
             * @default
             */
            answer?: string;
            /** Turn Index */
            turn_index: number;
        };
        /** RespondStep */
        RespondStep: {
            /** Assistance Used */
            assistance_used: components["schemas"]["AssistanceLevel"][];
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "respond";
            /** Ordinal */
            ordinal: number;
            prompt: components["schemas"]["RespondPrompt"];
            status: components["schemas"]["StepStatus"];
        };
        /** RetryHint */
        RetryHint: {
            /** After Seconds */
            after_seconds: number;
            /** Allowed */
            allowed: boolean;
        };
        /**
         * ReviewRequest
         * @description Payload for submitting a review.
         */
        ReviewRequest: {
            /**
             * Rating
             * @description FSRS rating from 0 (Again) to 3 (Easy)
             */
            rating: number;
            /** Response Time Ms */
            response_time_ms?: number | null;
            /** Word Id */
            word_id: number;
        };
        /**
         * ReviewResponse
         * @description Response after scheduling a review.
         */
        ReviewResponse: {
            /** Difficulty */
            difficulty: number;
            /**
             * Next Review
             * Format: date-time
             */
            next_review: string;
            /** Scheduled Days */
            scheduled_days: number;
            /** Stability */
            stability: number;
            /** State */
            state: string;
            /** Word Id */
            word_id: number;
        };
        /** RuleCardContrast */
        RuleCardContrast: {
            /** Right */
            right: string;
            /** Wrong */
            wrong: string;
        };
        /** RuleCardExample */
        RuleCardExample: {
            /** Fr */
            fr: string;
            /** Tr */
            tr?: {
                [key: string]: string;
            } | null;
        };
        /**
         * RuleCardLink
         * @description A partner unit to compare with, by id, with its note and (when known) titles.
         */
        RuleCardLink: {
            /** Id */
            id: string;
            /** Note */
            note?: {
                [key: string]: string;
            } | null;
            /** Title */
            title?: {
                [key: string]: string;
            } | null;
        };
        /** RuleCardPattern */
        RuleCardPattern: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "rows" | "table";
            /** Note */
            note?: {
                [key: string]: string;
            } | null;
            /** Rows */
            rows?: components["schemas"]["RuleCardRow"][];
            /** Verb */
            verb?: string | null;
        };
        /**
         * RuleCardPayload
         * @description The card, every authored language at once; the client picks the learner's.
         */
        RuleCardPayload: {
            contrast?: components["schemas"]["RuleCardContrast"] | null;
            /** Contrast With */
            contrast_with?: components["schemas"]["RuleCardLink"][] | null;
            example: components["schemas"]["RuleCardExample"];
            /** Examples */
            examples?: components["schemas"]["RuleCardExample"][] | null;
            /** From Scene */
            from_scene?: boolean | null;
            /** How */
            how?: {
                [key: string]: string;
            } | null;
            /** More */
            more?: {
                [key: string]: string;
            } | null;
            pattern?: components["schemas"]["RuleCardPattern"] | null;
            /** Rule */
            rule: {
                [key: string]: string;
            };
            /** Speaker */
            speaker?: string | null;
            /** Traps */
            traps?: components["schemas"]["RuleCardTrap"][] | null;
        };
        /** RuleCardRow */
        RuleCardRow: {
            /** Fr */
            fr: string;
            /** Label */
            label?: string | null;
            /** P */
            p?: string | null;
            /** Shape */
            shape?: string | null;
        };
        /**
         * RuleCardTrap
         * @description A real learner mistake, its fix and why (content program 2026-10-03).
         */
        RuleCardTrap: {
            /** Right */
            right: string;
            /** Why */
            why?: {
                [key: string]: string;
            } | null;
            /** Wrong */
            wrong: string;
        };
        /**
         * RulePrompt
         * @description WP-L4 «Règle»: the day's new grammar unit as its WP-L10 rule card.
         *
         *     What the learner reads, so it carries no answer key. The step is advanced,
         *     not answered; advancing it introduces the unit.
         */
        RulePrompt: {
            /** Concept Id */
            concept_id: number;
            rule_card: components["schemas"]["RuleCardPayload"];
            /** Scene Example Fr */
            scene_example_fr: string | null;
            /** Scene Example Speaker */
            scene_example_speaker: string | null;
            /**
             * Title Fr
             * @default
             */
            title_fr: string;
            /**
             * Title Native
             * @default
             */
            title_native: string;
        };
        /** RuleStep */
        RuleStep: {
            /** Assistance Used */
            assistance_used: components["schemas"]["AssistanceLevel"][];
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "rule";
            /** Ordinal */
            ordinal: number;
            prompt: components["schemas"]["RulePrompt"];
            status: components["schemas"]["StepStatus"];
        };
        /** RvAngle */
        RvAngle: {
            /** Fr */
            fr: string;
            /** Id */
            id: string;
            /**
             * Purpose
             * @enum {string}
             */
            purpose: "understand_change" | "explain_disagreement" | "choose_angle" | "prepare_dispatch";
        };
        /** RvAngleRef */
        RvAngleRef: {
            /** Fr */
            fr: string;
            /** Id */
            id: string;
        };
        /** RvBudget */
        RvBudget: {
            /** Minutes */
            minutes: number;
            /** Turns */
            turns: number;
        };
        /** RvClaim */
        RvClaim: {
            /** Attributed To */
            attributed_to?: string | null;
            /** Fr */
            fr: string;
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "fact" | "interpretation" | "forecast";
            /** Quote */
            quote: string;
            source: components["schemas"]["RvSource"];
        };
        /** RvClaimsItem */
        RvClaimsItem: {
            /** At */
            at: string;
            /** Claims */
            claims: components["schemas"]["RvClaim"][];
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "claims";
            /** Seq */
            seq: number;
        };
        /** RvClosedWord */
        RvClosedWord: {
            /** Claim Id */
            claim_id: string;
            /** Fr */
            fr: string;
            /** Gloss */
            gloss: string;
            /** Outcome */
            outcome?: ("correct" | "incorrect" | "unscored") | null;
            /** Used */
            used: boolean;
        };
        /** RvCloseResult */
        RvCloseResult: {
            closing: components["schemas"]["RvClosing"];
            session: components["schemas"]["RvSessionView"];
        };
        /** RvClosing */
        RvClosing: {
            /**
             * Colophon Fr
             * @default La suite la semaine prochaine.
             * @constant
             */
            colophon_fr?: "La suite la semaine prochaine.";
            dispatch: components["schemas"]["RvDispatch"];
            kept: components["schemas"]["RvKept"];
            /** Question Kept Fr */
            question_kept_fr?: string | null;
            /** Romy Line Fr */
            romy_line_fr: string;
            vignette?: components["schemas"]["VignetteView"] | null;
        };
        /** RvDispatch */
        RvDispatch: {
            /** Body Fr */
            body_fr: string[];
            /** Byline Fr */
            byline_fr: string;
            /** Contribution */
            contribution: [
                number,
                number
            ][];
            /** Headline Fr */
            headline_fr: string;
            /** Kicker Fr */
            kicker_fr: string;
            /** Sources */
            sources: components["schemas"]["RvSource"][];
        };
        /** RvDossierView */
        RvDossierView: {
            /** Evergreen */
            evergreen: boolean;
            /** Id */
            id: string;
            /** Sources */
            sources: components["schemas"]["RvSource"][];
            /** Summary Fr */
            summary_fr: string;
            /** Title Fr */
            title_fr: string;
            /**
             * Topic
             * @enum {string}
             */
            topic: "food" | "culture" | "city" | "sport" | "nature" | "work" | "politics";
        };
        /** RvEvidence */
        RvEvidence: {
            /** Capability Known */
            capability_known: boolean;
            /**
             * Fact Fit
             * @default not_applicable
             * @enum {string}
             */
            fact_fit?: "supported" | "unsupported" | "contradicted" | "not_applicable";
            /** Grader */
            grader: string;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "correct" | "incorrect" | "unscored";
            /**
             * Pending
             * @default false
             */
            pending?: boolean;
            /**
             * Register Note
             * @default ok
             * @enum {string}
             */
            register_note?: "ok" | "vous_to_tu" | "tu_to_vous";
            /** Words */
            words?: components["schemas"]["RvWordEvidence"][];
        };
        /** RvFiled */
        RvFiled: {
            /** Closed At */
            closed_at: string;
            dispatch?: components["schemas"]["RvDispatch"] | null;
            /** Dossier Id */
            dossier_id: string;
            made?: components["schemas"]["RvMade"] | null;
            /** Session Id */
            session_id: string;
            /** Title Fr */
            title_fr: string;
        };
        /** RvGloss */
        RvGloss: {
            /** Claim Id */
            claim_id: string;
            /** Fr */
            fr: string;
            /** Gloss */
            gloss: string;
        };
        /**
         * RvGuestItem
         * @description Phase 2: a guest speaks (one guest per Papier).
         */
        RvGuestItem: {
            /** At */
            at: string;
            /** Cast Id */
            cast_id: string;
            /** Glosses */
            glosses?: components["schemas"]["RvGloss"][];
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "guest";
            /**
             * Move
             * @enum {string}
             */
            move: "enter" | "follow_up" | "disagree" | "moved";
            /** Position */
            position?: ("for" | "against" | "moved") | null;
            /** Reason */
            reason?: ("model_down" | "knowledge_refused" | "budget" | "no_match") | null;
            /** Reason Fr */
            reason_fr?: string | null;
            /** Seq */
            seq: number;
            /** Text Fr */
            text_fr: string;
        };
        /** RvHeadlineChoiceOffer */
        RvHeadlineChoiceOffer: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "headline_choice";
            /** Options */
            options: components["schemas"]["RvHeadlineOption"][];
        };
        /** RvHeadlineEvidence */
        RvHeadlineEvidence: {
            /** Claim Id */
            claim_id: string;
            /** Quote */
            quote: string;
            source: components["schemas"]["RvSource"];
        };
        /** RvHeadlineOption */
        RvHeadlineOption: {
            /** Id */
            id: string;
            /** Text Fr */
            text_fr: string;
        };
        /** RvHeadlinePick */
        RvHeadlinePick: {
            /**
             * Action
             * @constant
             */
            action: "pick";
            /**
             * Kind
             * @constant
             */
            kind: "headline_choice";
            /** Option Id */
            option_id: string;
        };
        /** RvHeadlinePickResult */
        RvHeadlinePickResult: {
            /** Answer Id */
            answer_id: string;
            /** Correct */
            correct: boolean;
            evidence: components["schemas"]["RvHeadlineEvidence"];
            /**
             * Kind
             * @default headline_choice
             * @constant
             */
            kind?: "headline_choice";
            line?: components["schemas"]["RvLineItem"] | null;
            made: components["schemas"]["RvMade"];
        };
        /** RvHeadlineWrite */
        RvHeadlineWrite: {
            /**
             * Action
             * @constant
             */
            action: "write";
            /**
             * Kind
             * @constant
             */
            kind: "headline_write";
            /** Text Fr */
            text_fr: string;
        };
        /** RvHeadlineWriteOffer */
        RvHeadlineWriteOffer: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "headline_write";
            /** Max Words */
            max_words: number;
        };
        /** RvHeadlineWriteResult */
        RvHeadlineWriteResult: {
            /** Accepted */
            accepted: boolean;
            evidence: components["schemas"]["RvEvidence"];
            /**
             * Kind
             * @default headline_write
             * @constant
             */
            kind?: "headline_write";
            line?: components["schemas"]["RvLineItem"] | null;
            made?: components["schemas"]["RvMade"] | null;
        };
        /** RvKept */
        RvKept: {
            /** Claims */
            claims: components["schemas"]["RvClaim"][];
            /** Words */
            words: components["schemas"]["RvClosedWord"][];
        };
        /** RvLineItem */
        RvLineItem: {
            /** At */
            at: string;
            /** Glosses */
            glosses?: components["schemas"]["RvGloss"][];
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "line";
            /** Reason */
            reason?: ("model_down" | "knowledge_refused" | "budget" | "no_match") | null;
            /**
             * Role
             * @enum {string}
             */
            role: "purpose" | "place_note" | "reply" | "steer" | "fallback" | "make_intro" | "make_done" | "close";
            /** Seq */
            seq: number;
            /**
             * Speaker
             * @default romy_tremblay
             */
            speaker?: string;
            /** Text Fr */
            text_fr: string;
            /** Translation */
            translation?: string | null;
        };
        /** RvMade */
        RvMade: {
            /** Contribution */
            contribution: [
                number,
                number
            ][];
            /**
             * Kind
             * @enum {string}
             */
            kind: "headline_choice" | "headline_write" | "reader_question" | "short_report";
            /** Learner Fr */
            learner_fr?: string | null;
            /** Text Fr */
            text_fr: string;
        };
        /** RvMadeItem */
        RvMadeItem: {
            /** At */
            at: string;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "made";
            made: components["schemas"]["RvMade"];
            /** Seq */
            seq: number;
        };
        /** RvMakeOffer */
        RvMakeOffer: {
            intro?: components["schemas"]["RvLineItem"] | null;
            /** Options */
            options: (components["schemas"]["RvHeadlineChoiceOffer"] | components["schemas"]["RvHeadlineWriteOffer"] | components["schemas"]["RvReaderQuestionOffer"] | components["schemas"]["RvShortReportOffer"])[];
            /**
             * Recommended
             * @enum {string}
             */
            recommended: "headline_choice" | "headline_write" | "reader_question" | "short_report";
        };
        /** RvMatchRequest */
        RvMatchRequest: {
            /** Text */
            text: string;
            /** Week */
            week?: string | null;
        };
        /** RvMatchResult */
        RvMatchResult: {
            /** Match */
            match: string | null;
            /** Romy Line Fr */
            romy_line_fr?: string | null;
        };
        /** RvMineItem */
        RvMineItem: {
            /** At */
            at: string;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "mine";
            /**
             * Mode
             * @default text
             * @enum {string}
             */
            mode?: "text" | "voice";
            /** Register Note */
            register_note?: ("vous_to_tu" | "tu_to_vous") | null;
            /** Seq */
            seq: number;
            /** Text Fr */
            text_fr: string;
        };
        /** RvNarrationItem */
        RvNarrationItem: {
            /** At */
            at: string;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "narration";
            /** Seq */
            seq: number;
            /** Text Fr */
            text_fr: string;
        };
        /** RvOffer */
        RvOffer: {
            /** Alternatives */
            alternatives: components["schemas"]["RvStoryCard"][];
            /** Evergreen Only */
            evergreen_only: boolean;
            filed?: components["schemas"]["RvFiled"] | null;
            recommended: components["schemas"]["RvStoryCard"] | null;
            /**
             * Recommended Reason
             * @enum {string}
             */
            recommended_reason: "topic_least_recent" | "interests" | "first";
            resume?: components["schemas"]["RvResume"] | null;
            week: components["schemas"]["RvWeek"];
        };
        /** RvPlanView */
        RvPlanView: {
            angle: components["schemas"]["RvAngle"];
            /**
             * Band
             * @enum {string}
             */
            band: "A1" | "A2" | "B1" | "B2";
            budget: components["schemas"]["RvBudget"];
            /**
             * Chosen By
             * @enum {string}
             */
            chosen_by: "learner" | "recommended";
            /**
             * Gloss Language
             * @enum {string}
             */
            gloss_language: "en" | "de" | "fr";
            /** Make Options */
            make_options: ("headline_choice" | "headline_write" | "reader_question" | "short_report")[];
            support: components["schemas"]["RvSupport"];
            /**
             * Ui Language
             * @enum {string}
             */
            ui_language: "en" | "de" | "fr";
            /** Vocabulary */
            vocabulary: components["schemas"]["RvGloss"][];
        };
        /** RvQuestionDraft */
        RvQuestionDraft: {
            /** Contribution */
            contribution: [
                number,
                number
            ][];
            /** Learner Fr */
            learner_fr: string;
            /** Proposal Fr */
            proposal_fr: string;
            /** Why Native */
            why_native?: string | null;
        };
        /** RvQuestionPropose */
        RvQuestionPropose: {
            /**
             * Action
             * @constant
             */
            action: "propose";
            /**
             * Kind
             * @constant
             */
            kind: "reader_question";
            /** Text */
            text?: string | null;
        };
        /** RvQuestionProposeResult */
        RvQuestionProposeResult: {
            draft: components["schemas"]["RvQuestionDraft"];
            /**
             * Kind
             * @default reader_question
             * @constant
             */
            kind?: "reader_question";
        };
        /** RvQuestionSend */
        RvQuestionSend: {
            /**
             * Action
             * @constant
             */
            action: "send";
            /**
             * Kind
             * @constant
             */
            kind: "reader_question";
            /** Text Fr */
            text_fr: string;
        };
        /** RvQuestionSendResult */
        RvQuestionSendResult: {
            /**
             * Kind
             * @default reader_question
             * @constant
             */
            kind?: "reader_question";
            line?: components["schemas"]["RvLineItem"] | null;
            made: components["schemas"]["RvMade"];
        };
        /** RvQuickReply */
        RvQuickReply: {
            /** Label */
            label: string;
            /** Send Fr */
            send_fr: string;
        };
        /** RvReaderQuestionOffer */
        RvReaderQuestionOffer: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "reader_question";
            /** Seed Fr */
            seed_fr?: string | null;
            /** Uncertainty Fr */
            uncertainty_fr?: string | null;
        };
        /** RvResume */
        RvResume: {
            /**
             * Beat
             * @enum {string}
             */
            beat: "arrive" | "facts" | "pursue" | "make" | "close";
            /** Dossier Id */
            dossier_id: string;
            /** Open Question Fr */
            open_question_fr?: string | null;
            /** Session Id */
            session_id: string;
            /** Started At */
            started_at: string;
            /** Title Fr */
            title_fr: string;
        };
        /** RvRoom */
        RvRoom: {
            /**
             * Phase
             * @enum {string}
             */
            phase: "open" | "bouclage" | "boucle";
            /** Remaining Turns */
            remaining_turns: number;
            /** Used */
            used: number;
        };
        /** RvSessionView */
        RvSessionView: {
            artifact?: components["schemas"]["RvMade"] | null;
            /**
             * Beat
             * @enum {string}
             */
            beat: "arrive" | "facts" | "pursue" | "make" | "close";
            /** Closed At */
            closed_at?: string | null;
            closing?: components["schemas"]["RvClosing"] | null;
            dossier: components["schemas"]["RvDossierView"];
            /** Id */
            id: string;
            plan: components["schemas"]["RvPlanView"];
            /** Quick Replies */
            quick_replies: components["schemas"]["RvQuickReply"][];
            room: components["schemas"]["RvRoom"];
            stage: components["schemas"]["RvStage"];
            /** Started At */
            started_at: string;
            /**
             * Status
             * @enum {string}
             */
            status: "active" | "closed" | "abandoned";
            /** Steer To Make */
            steer_to_make: boolean;
            /** Thread */
            thread: (components["schemas"]["RvNarrationItem"] | components["schemas"]["RvSummaryItem"] | components["schemas"]["RvLineItem"] | components["schemas"]["RvGuestItem"] | components["schemas"]["RvMineItem"] | components["schemas"]["RvClaimsItem"] | components["schemas"]["RvUncertaintyItem"] | components["schemas"]["RvShiftItem"] | components["schemas"]["RvMadeItem"])[];
            week: components["schemas"]["RvWeek"];
        };
        /** RvShiftItem */
        RvShiftItem: {
            angle?: components["schemas"]["RvAngleRef"] | null;
            /** At */
            at: string;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "shift";
            /**
             * Reason
             * @enum {string}
             */
            reason: "simplify" | "angle" | "bouclage" | "boucle";
            /** Seq */
            seq: number;
        };
        /** RvShortReport */
        RvShortReport: {
            /**
             * Action
             * @constant
             */
            action: "report";
            /**
             * Kind
             * @constant
             */
            kind: "short_report";
            /**
             * Mode
             * @default voice
             * @enum {string}
             */
            mode?: "text" | "voice";
            /** Transcript */
            transcript: string;
        };
        /** RvShortReportOffer */
        RvShortReportOffer: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "short_report";
            /**
             * Seconds
             * @default 30
             */
            seconds?: number;
        };
        /** RvShortReportResult */
        RvShortReportResult: {
            evidence: components["schemas"]["RvEvidence"];
            /**
             * Kind
             * @default short_report
             * @constant
             */
            kind?: "short_report";
            line?: components["schemas"]["RvLineItem"] | null;
            made: components["schemas"]["RvMade"];
        };
        /** RvSource */
        RvSource: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Published At */
            published_at: string;
            /** Url */
            url: string;
        };
        /** RvStage */
        RvStage: {
            /** Cast */
            cast: components["schemas"]["RvStageMember"][];
            /**
             * Dress
             * @enum {string}
             */
            dress: "coat" | "suit" | "apron" | "raincoat" | "sport" | "scarf_only" | "chef" | "hi_vis";
            /** Place Fr */
            place_fr: string;
            /** Place Id */
            place_id: string;
            /** Place Is Real */
            place_is_real: boolean;
            /** Plate Place Id */
            plate_place_id: string;
            /**
             * Plate Switched
             * @default false
             */
            plate_switched?: boolean;
            /** Plate Url */
            plate_url: string | null;
            /** Plate Url Second */
            plate_url_second?: string | null;
        };
        /** RvStageMember */
        RvStageMember: {
            /** Hold */
            hold?: string | null;
            /** Id */
            id: string;
        };
        /** RvStartRequest */
        RvStartRequest: {
            /** Angle Id */
            angle_id?: string | null;
            /** Dossier Id */
            dossier_id?: string | null;
            /** Free Request */
            free_request?: string | null;
            /** Week */
            week?: string | null;
        };
        /** RvStoryCard */
        RvStoryCard: {
            /** Dossier Id */
            dossier_id: string;
            /** Evergreen */
            evergreen: boolean;
            /** Place Fr */
            place_fr: string;
            /** Plate Url */
            plate_url: string | null;
            stage: components["schemas"]["RvStage"];
            /** Summary Fr */
            summary_fr: string;
            /** Title Fr */
            title_fr: string;
            /**
             * Topic
             * @enum {string}
             */
            topic: "food" | "culture" | "city" | "sport" | "nature" | "work" | "politics";
        };
        /** RvSummaryItem */
        RvSummaryItem: {
            /** At */
            at: string;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "summary";
            /** Seq */
            seq: number;
            /**
             * Speaker
             * @default romy_tremblay
             */
            speaker?: string;
            /** Text Fr */
            text_fr: string;
        };
        /** RvSupport */
        RvSupport: {
            /**
             * Glosses
             * @enum {string}
             */
            glosses: "shown" | "tap" | "none";
            /** Level */
            level: number;
            /** Reading Target Words */
            reading_target_words: number;
            /**
             * Translation
             * @enum {string}
             */
            translation: "one_tap" | "on_request" | "none";
            /** Vocab Target */
            vocab_target: number;
        };
        /** RvTurnRequest */
        RvTurnRequest: {
            /** Client Turn Id */
            client_turn_id?: string | null;
            /**
             * Mode
             * @default text
             * @enum {string}
             */
            mode?: "text" | "voice";
            /** Text */
            text: string;
        };
        /** RvTurnResult */
        RvTurnResult: {
            /**
             * Beat
             * @enum {string}
             */
            beat: "arrive" | "facts" | "pursue" | "make" | "close";
            evidence: components["schemas"]["RvEvidence"];
            /** Items */
            items: (components["schemas"]["RvNarrationItem"] | components["schemas"]["RvSummaryItem"] | components["schemas"]["RvLineItem"] | components["schemas"]["RvGuestItem"] | components["schemas"]["RvMineItem"] | components["schemas"]["RvClaimsItem"] | components["schemas"]["RvUncertaintyItem"] | components["schemas"]["RvShiftItem"] | components["schemas"]["RvMadeItem"])[];
            /** Quick Replies */
            quick_replies: components["schemas"]["RvQuickReply"][];
            room: components["schemas"]["RvRoom"];
            /** Steer To Make */
            steer_to_make: boolean;
            support: components["schemas"]["RvSupport"];
        };
        /** RvUncertaintyItem */
        RvUncertaintyItem: {
            /** At */
            at: string;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "uncertainty";
            /** Seq */
            seq: number;
            /** Text Fr */
            text_fr: string;
        };
        /** RvWeek */
        RvWeek: {
            /** Iso */
            iso: string;
            /** Label */
            label: string;
            /** Range */
            range: string;
        };
        /** RvWordEvidence */
        RvWordEvidence: {
            /** Capability Known */
            capability_known: boolean;
            /** Fr */
            fr: string;
            /**
             * Outcome
             * @enum {string}
             */
            outcome: "correct" | "incorrect" | "unscored";
        };
        /** ScenarioDescriptor */
        ScenarioDescriptor: {
            /** Character Id */
            character_id: string;
            /** Character Name */
            character_name: string;
            /** Content Version */
            content_version: string;
            epreuve: components["schemas"]["EpreuveView"] | null;
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Image Url */
            image_url: string | null;
            /**
             * Level Band
             * @enum {string}
             */
            level_band: "A1" | "A2" | "B1" | "B2" | "C1";
            /** Location Id */
            location_id: string;
            /** Location Name */
            location_name: string;
            /** Objective Key */
            objective_key: string;
            /** Objective Native */
            objective_native: string;
            /** Scenario Key */
            scenario_key: string;
            /** Serial Episode Id */
            serial_episode_id: string | null;
            /** Serial Thread Id */
            serial_thread_id: string | null;
            /** Special */
            special: "epreuve" | null;
            /** Title Fr */
            title_fr: string;
        };
        /**
         * ScenePanel
         * @description One panel of an authored scene's page (2026-09-25).
         */
        ScenePanel: {
            /** Alt Native */
            alt_native: string | null;
            /** Dialogue */
            dialogue: components["schemas"]["ScenePanelLine"][];
            /** Id */
            id: string;
            /**
             * Image Status
             * @default unavailable
             * @enum {string}
             */
            image_status: "panel_art" | "setting_reference" | "unavailable";
            /** Image Url */
            image_url: string | null;
            /** Index */
            index: number;
            /**
             * Narration Fr
             * @default
             */
            narration_fr: string;
            /** Plate Url */
            plate_url: string | null;
        };
        /** ScenePanelLine */
        ScenePanelLine: {
            /** Character Id */
            character_id: string;
            /** Character Name */
            character_name: string | null;
            /** Mood */
            mood: string | null;
            /** Text Fr */
            text_fr: string;
            /** Text Native */
            text_native: string | null;
        };
        /** ScenePrompt */
        ScenePrompt: {
            /**
             * Audio Available
             * @default false
             */
            audio_available: boolean;
            /** Character Line Audio Url */
            character_line_audio_url: string | null;
            /** Character Line Fr */
            character_line_fr: string | null;
            /** Image Url */
            image_url: string | null;
            /**
             * Listen First
             * @default false
             */
            listen_first: boolean;
            /** Margin Notes */
            margin_notes: components["schemas"]["MarginNote"][] | null;
            /** Objective Native */
            objective_native: string;
            /** Panels */
            panels: components["schemas"]["ScenePanel"][] | null;
            /** Previously Fr */
            previously_fr: string[] | null;
            /** Setup Fr */
            setup_fr: string;
            /** Setup Native */
            setup_native: string;
        };
        /**
         * SceneRead
         * @description Schema for scene rendering.
         */
        SceneRead: {
            /** Atmosphere */
            atmosphere?: string | null;
            /** Chapter Id */
            chapter_id: string;
            /** Choices */
            choices?: components["schemas"]["ChoiceOptionRead"][];
            /**
             * Estimated Duration Minutes
             * @default 10
             */
            estimated_duration_minutes?: number;
            /** Id */
            id: string;
            /**
             * Interaction Type
             * @default free_input
             */
            interaction_type?: string;
            /** Location */
            location?: string | null;
            /** Narration */
            narration: string;
            /** Npcs Present */
            npcs_present?: components["schemas"]["NPCInSceneRead"][];
            /** Objectives */
            objectives?: components["schemas"]["ObjectiveRead"][];
        };
        /** SceneStep */
        SceneStep: {
            /** Assistance Used */
            assistance_used: components["schemas"]["AssistanceLevel"][];
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Id */
            id: string;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            kind: "scene";
            /** Ordinal */
            ordinal: number;
            prompt: components["schemas"]["ScenePrompt"];
            status: components["schemas"]["StepStatus"];
        };
        /**
         * SceneTransitionRead
         * @description Schema for scene transition information.
         */
        SceneTransitionRead: {
            /**
             * Chapter Change
             * @default false
             */
            chapter_change?: boolean;
            /** New Chapter Title */
            new_chapter_title?: string | null;
            /** Next Scene Id */
            next_scene_id: string;
            /** Transition Narration */
            transition_narration?: string | null;
        };
        /**
         * SeasonPremiereView
         * @description WP-98/99. Today's scene opens a season: «Nouvelle saison».
         */
        SeasonPremiereView: {
            /** Logline Fr */
            logline_fr: string | null;
            /** Number */
            number: number;
            /** Title Fr */
            title_fr: string;
        };
        /** SerialAdvanceRequest */
        SerialAdvanceRequest: {
            /** Hook */
            hook?: components["schemas"]["HookRead"] | {
                [key: string]: unknown;
            } | null;
            /** Mission Id */
            mission_id?: string | null;
            /** Scene Id */
            scene_id?: string | null;
            /** State Delta */
            state_delta?: components["schemas"]["StateDelta"] | {
                [key: string]: unknown;
            } | null;
        } & {
            [key: string]: unknown;
        };
        /** SerialAvatarRequest */
        SerialAvatarRequest: {
            /** Avatar Builder */
            avatar_builder?: {
                [key: string]: unknown;
            };
            /**
             * Description
             * @default
             */
            description?: string;
            /**
             * Mode
             * @default avatar
             * @enum {string}
             */
            mode?: "avatar" | "pov";
            /** Reference Images */
            reference_images?: string[];
        } & {
            [key: string]: unknown;
        };
        /** SerialThreadCreateRequest */
        SerialThreadCreateRequest: {
            /** News Seed */
            news_seed?: {
                [key: string]: unknown;
            } | null;
            /** State */
            state?: {
                [key: string]: unknown;
            } | null;
            /** World Bible */
            world_bible?: {
                [key: string]: unknown;
            } | null;
        } & {
            [key: string]: unknown;
        };
        /** SerialThreadRead */
        SerialThreadRead: {
            /** Created At */
            created_at?: string | null;
            /**
             * Current Episode Index
             * @default 0
             */
            current_episode_index?: number;
            /** Episodes */
            episodes?: components["schemas"]["EpisodeRead"][];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** News Seed */
            news_seed?: {
                [key: string]: unknown;
            };
            /** State */
            state?: {
                [key: string]: unknown;
            };
            /**
             * Status
             * @default active
             */
            status?: string;
            /** Updated At */
            updated_at?: string | null;
            /**
             * User Id
             * Format: uuid
             */
            user_id: string;
            world_bible?: components["schemas"]["WorldBibleRead"];
        } & {
            [key: string]: unknown;
        };
        /**
         * SessionCreateRequest
         * @description Payload for starting a learning session.
         */
        SessionCreateRequest: {
            /**
             * Anki Direction
             * @description Preferred Anki card direction for the session
             */
            anki_direction?: ("fr_to_de" | "de_to_fr" | "both") | null;
            /**
             * Conversation Style
             * @description High-level conversation style such as tutor, casual, exam-prep
             * @default tutor
             */
            conversation_style?: string;
            /**
             * Difficulty Preference
             * @description Optional learner difficulty preference
             */
            difficulty_preference?: string | null;
            /**
             * Generate Greeting
             * @description Whether to immediately create an assistant greeting
             * @default true
             */
            generate_greeting?: boolean;
            /** Planned Duration Minutes */
            planned_duration_minutes: number;
            /**
             * Scenario
             * @description Roleplay scenario context (e.g. 'Bakery', 'Train Station')
             */
            scenario?: string | null;
            /** Topic */
            topic?: string | null;
        };
        /**
         * SessionMessageListResponse
         * @description Paginated collection of session messages.
         */
        SessionMessageListResponse: {
            /** Items */
            items: components["schemas"]["SessionMessageRead"][];
            /** Total */
            total: number;
        };
        /**
         * SessionMessageRead
         * @description Response model for persisted conversation messages.
         */
        SessionMessageRead: {
            /** Content */
            content: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            error_feedback?: components["schemas"]["ErrorFeedback"] | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Learning Focus */
            learning_focus?: components["schemas"]["LearningFocusRead"][];
            pending_moment?: components["schemas"]["LearningMomentRead"] | null;
            /**
             * Sender
             * @enum {string}
             */
            sender: "user" | "assistant";
            /** Sequence Number */
            sequence_number: number;
            /** Suggested Words Used */
            suggested_words_used?: number[];
            /** Target Details */
            target_details?: components["schemas"]["TargetWordRead"][];
            /** Target Words */
            target_words?: number[];
            /** Words Used */
            words_used?: number[];
            /**
             * Xp Earned
             * @default 0
             */
            xp_earned?: number;
        };
        /**
         * SessionMessageRequest
         * @description Payload for sending a learner message within a session.
         */
        SessionMessageRequest: {
            /** Content */
            content: string;
            /**
             * Suggested Word Ids
             * @description Identifiers of suggested words the learner actually attempted to use
             */
            suggested_word_ids?: number[] | null;
        };
        /**
         * SessionMomentSubmitRequest
         * @description Payload for resolving an inline learning moment.
         */
        SessionMomentSubmitRequest: {
            /** Answer Text */
            answer_text?: string | null;
            /** Selected Choice */
            selected_choice?: string | null;
            /**
             * Skipped
             * @default false
             */
            skipped?: boolean;
        };
        /**
         * SessionMomentSubmitResponse
         * @description Response returned after resolving an inline learning moment.
         */
        SessionMomentSubmitResponse: {
            assistant_turn?: components["schemas"]["AssistantTurnRead"] | null;
            moment_result: components["schemas"]["LearningMomentResultRead"];
            next_moment?: components["schemas"]["LearningMomentRead"] | null;
            session: components["schemas"]["SessionOverview"];
        };
        /**
         * SessionOverview
         * @description High-level view of a session.
         */
        SessionOverview: {
            /** Accuracy Rate */
            accuracy_rate: number | null;
            /** Anki Direction */
            anki_direction?: string | null;
            /** Completed At */
            completed_at?: string | null;
            /** Conversation Style */
            conversation_style?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Planned Duration Minutes */
            planned_duration_minutes: number;
            /**
             * Started At
             * Format: date-time
             */
            started_at: string;
            /** Status */
            status: string;
            /** Topic */
            topic?: string | null;
            /** Words Practiced */
            words_practiced: number;
            /** Xp Earned */
            xp_earned: number;
        };
        /**
         * SessionStartResponse
         * @description Response returned when a new session is created.
         */
        SessionStartResponse: {
            assistant_turn?: components["schemas"]["AssistantTurnRead"] | null;
            session: components["schemas"]["SessionOverview"];
        };
        /**
         * SessionStatusUpdate
         * @description Update the status of a session.
         */
        SessionStatusUpdate: {
            /**
             * Status
             * @enum {string}
             */
            status: "in_progress" | "paused" | "completed" | "abandoned";
        };
        /**
         * SessionSummaryResponse
         * @description Aggregate statistics for a session.
         */
        SessionSummaryResponse: {
            /** Accuracy Rate */
            accuracy_rate: number;
            /** Correct Responses */
            correct_responses: number;
            /** Error Examples */
            error_examples?: {
                [key: string]: unknown;
            }[];
            /** Flashcard Words */
            flashcard_words?: components["schemas"]["TargetWordRead"][];
            /** Incorrect Responses */
            incorrect_responses: number;
            /** New Words Introduced */
            new_words_introduced: number;
            /** Practice Items */
            practice_items?: components["schemas"]["PracticeIssue"][];
            /** Status */
            status: string;
            /** Success Examples */
            success_examples?: {
                [key: string]: unknown;
            }[];
            /** Words Practiced */
            words_practiced: number;
            /** Words Reviewed */
            words_reviewed: number;
            /** Xp Earned */
            xp_earned: number;
        };
        /**
         * SessionTurnResponse
         * @description Response returned after a learner message is processed.
         */
        SessionTurnResponse: {
            assistant_turn: components["schemas"]["AssistantTurnRead"];
            /**
             * Combo Count
             * @description Number of target words used in this turn (combo bonus)
             * @default 0
             */
            combo_count?: number;
            error_feedback: components["schemas"]["ErrorFeedback"];
            session: components["schemas"]["SessionOverview"];
            user_message: components["schemas"]["SessionMessageRead"];
            /** Word Feedback */
            word_feedback: components["schemas"]["SessionTurnWordFeedback"][];
            /** Xp Awarded */
            xp_awarded: number;
        };
        /**
         * SessionTurnWordFeedback
         * @description Detailed learner feedback for a targeted vocabulary item.
         */
        SessionTurnWordFeedback: {
            error?: components["schemas"]["DetectedErrorRead"] | null;
            /** Had Error */
            had_error: boolean;
            /** Is New */
            is_new: boolean;
            /** Rating */
            rating: number | null;
            /** Translation */
            translation?: string | null;
            /** Was Used */
            was_used: boolean;
            /** Word */
            word: string;
            /** Word Id */
            word_id: number;
        };
        /** StartRequest */
        StartRequest: {
            /**
             * Restart
             * @default false
             */
            restart?: boolean;
        };
        /** StateDelta */
        StateDelta: {
            /**
             * Reason
             * @default
             */
            reason?: string;
            /** Set */
            set?: {
                [key: string]: unknown;
            };
            /** Source */
            source?: {
                [key: string]: unknown;
            };
        } & {
            [key: string]: unknown;
        };
        /**
         * StepStatus
         * @enum {string}
         */
        StepStatus: "pending" | "active" | "completed" | "skipped";
        /** StoryArchive */
        StoryArchive: {
            current: components["schemas"]["ArchiveCurrent"];
            /** Seasons */
            seasons?: components["schemas"]["ArchiveSeason"][];
        };
        /** StoryChapterRead */
        StoryChapterRead: {
            /**
             * Finale
             * @default null
             */
            finale?: boolean | null;
            /** Id */
            id: string;
            /**
             * Interlude
             * @default null
             */
            interlude?: boolean | null;
            /**
             * Letter Beat
             * @default null
             */
            letter_beat?: string | null;
            /**
             * Shape
             * @default null
             */
            shape?: string | null;
            /** Title Fr */
            title_fr: string;
        };
        /** StoryDialogueRead */
        StoryDialogueRead: {
            /** Character Id */
            character_id: string;
            /**
             * Character Name
             * @default null
             */
            character_name?: string | null;
            /**
             * Grammar Marks
             * @default null
             */
            grammar_marks?: components["schemas"]["GrammarMarkRead"][] | null;
            /**
             * Mood
             * @default null
             */
            mood?: string | null;
            /** Text Fr */
            text_fr: string;
            /**
             * Text Native
             * @default null
             */
            text_native?: string | null;
        };
        /** StoryEpisodePageRead */
        StoryEpisodePageRead: {
            /** Episodes */
            episodes: components["schemas"]["StoryEpisodeRead"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** StoryEpisodeRead */
        StoryEpisodeRead: {
            chapter: components["schemas"]["StoryChapterRead"] | null;
            grammar_focus: components["schemas"]["GrammarFocusRead"] | null;
            /** Id */
            id: string;
            /** Journey Id */
            journey_id: string | null;
            /** @default null */
            page?: components["schemas"]["StoryPageRead"] | null;
            /** Panel Index */
            panel_index: number;
            /** Panels */
            panels: components["schemas"]["StoryPanelRead"][];
            resolution: components["schemas"]["StoryResolutionRead"] | null;
            /** Scene Id */
            scene_id: string;
            /** Serial Episode Id */
            serial_episode_id: string | null;
            /** Serial Thread Id */
            serial_thread_id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "available" | "completed" | "abandoned";
            /** Title Fr */
            title_fr: string;
        };
        /**
         * StoryInputRequest
         * @description Request for player input in a story.
         */
        StoryInputRequest: {
            /** Choice Id */
            choice_id?: string | null;
            /** Content */
            content: string;
            /** Conversation History */
            conversation_history?: {
                [key: string]: unknown;
            }[] | null;
            /**
             * Is Voice
             * @default false
             */
            is_voice?: boolean;
            /** Target Npc Id */
            target_npc_id?: string | null;
        };
        /**
         * StoryInputResponse
         * @description Full response to player input in a story.
         */
        StoryInputResponse: {
            /** Achievements Unlocked */
            achievements_unlocked?: string[];
            /** Consequences */
            consequences?: components["schemas"]["ConsequenceRead"][];
            /** Errors Detected */
            errors_detected?: {
                [key: string]: unknown;
            }[];
            /** Minted Collectibles */
            minted_collectibles?: {
                [key: string]: unknown;
            }[];
            npc_response?: components["schemas"]["NPCResponseRead"] | null;
            scene_transition?: components["schemas"]["SceneTransitionRead"] | null;
            /** Updated Flags */
            updated_flags?: string[];
            /** Xp Breakdown */
            xp_breakdown?: {
                [key: string]: unknown;
            }[];
            /**
             * Xp Earned
             * @default 0
             */
            xp_earned?: number;
        };
        /** StoryOutcome */
        StoryOutcome: {
            /** Callback Fr */
            callback_fr: string | null;
            /** Outcome Key */
            outcome_key: string;
            /** Serial Episode Id */
            serial_episode_id: string | null;
            /** Serial Thread Id */
            serial_thread_id: string | null;
        };
        /** StoryPageLineRead */
        StoryPageLineRead: {
            /** Character Id */
            character_id: string;
            /**
             * Character Name
             * @default null
             */
            character_name?: string | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "speech" | "you" | "sms" | "letter" | "card";
            /**
             * Mood
             * @default null
             */
            mood?: string | null;
            /** Text Fr */
            text_fr: string;
            /**
             * Text Native
             * @default null
             */
            text_native?: string | null;
            /** You */
            you: boolean;
        };
        /**
         * StoryPageRead
         * @description WP-110: a completed day as one page — the scene, the learner's lines as
         *     balloons, the reactions, the solve, the drawn ending — and «À suivre…».
         */
        StoryPageRead: {
            /**
             * A Suivre Fr
             * @default null
             */
            a_suivre_fr?: string | null;
            /** Rows */
            rows: components["schemas"]["StoryPageRowRead"][];
        };
        /** StoryPageRowRead */
        StoryPageRowRead: {
            /**
             * Alt Native
             * @default null
             */
            alt_native?: string | null;
            /** Dialogue */
            dialogue: components["schemas"]["StoryPageLineRead"][];
            /**
             * Flashback
             * @default false
             */
            flashback?: boolean;
            /** Id */
            id: string;
            /**
             * Image Status
             * @enum {string}
             */
            image_status: "panel_art" | "rendering" | "setting_reference" | "unavailable";
            /** Image Url */
            image_url: string | null;
            /**
             * Movement
             * @enum {string}
             */
            movement: "act" | "turn" | "reaction" | "solve" | "ending";
            /** Narration Fr */
            narration_fr: string;
            /**
             * Plate Url
             * @default null
             */
            plate_url?: string | null;
            /**
             * Silence
             * @default false
             */
            silence?: boolean;
        };
        /** StoryPanelRead */
        StoryPanelRead: {
            /**
             * Alt Native
             * @default null
             */
            alt_native?: string | null;
            /** Dialogue */
            dialogue: components["schemas"]["StoryDialogueRead"][];
            /** Id */
            id: string;
            /**
             * Image Status
             * @enum {string}
             */
            image_status: "panel_art" | "rendering" | "setting_reference" | "unavailable";
            /** Image Url */
            image_url: string | null;
            /** Index */
            index: number;
            /** Narration Fr */
            narration_fr: string;
            /**
             * Plate Url
             * @default null
             */
            plate_url?: string | null;
        };
        /** StoryPositionRead */
        StoryPositionRead: {
            /** Panel Index */
            panel_index: number;
            /** Scene Id */
            scene_id: string;
        };
        /**
         * StoryProgressRead
         * @description Schema for user's story progress.
         */
        StoryProgressRead: {
            /** Book Quotes Unlocked */
            book_quotes_unlocked?: string[];
            /**
             * Completion Percentage
             * @default 0
             */
            completion_percentage?: number;
            /** Current Chapter Id */
            current_chapter_id?: string | null;
            /** Current Chapter Title */
            current_chapter_title?: string | null;
            /** Current Scene Id */
            current_scene_id?: string | null;
            /** Last Played At */
            last_played_at?: string | null;
            /** Philosophical Learnings */
            philosophical_learnings?: string[];
            /** Started At */
            started_at?: string | null;
            /**
             * Status
             * @default in_progress
             */
            status?: string;
            /** Story Flags */
            story_flags?: {
                [key: string]: unknown;
            };
            /** Story Id */
            story_id: string;
        };
        /** StoryResolutionRead */
        StoryResolutionRead: {
            /** Summary Native */
            summary_native: string | null;
            /** Text Fr */
            text_fr: string | null;
        };
        /**
         * StoryStartResponse
         * @description Response when starting a story.
         */
        StoryStartResponse: {
            chapter: components["schemas"]["ChapterRead"];
            progress: components["schemas"]["StoryProgressRead"];
            scene: components["schemas"]["SceneRead"];
        };
        /**
         * StoryWithProgressRead
         * @description Story with optional progress information.
         */
        StoryWithProgressRead: {
            /** Cover Image Url */
            cover_image_url?: string | null;
            /**
             * Estimated Duration Minutes
             * @default 60
             */
            estimated_duration_minutes?: number;
            /** Id */
            id: string;
            /**
             * Is Unlocked
             * @default true
             */
            is_unlocked?: boolean;
            progress?: components["schemas"]["StoryProgressRead"] | null;
            /** Source Author */
            source_author?: string | null;
            /** Source Book */
            source_book?: string | null;
            /** Subtitle */
            subtitle?: string | null;
            /** Target Levels */
            target_levels?: string[];
            /** Themes */
            themes?: string[];
            /** Title */
            title: string;
        };
        /**
         * StreakCalendarDay
         * @description One learner-local day of «Vos sceaux» (WP-D5).
         */
        StreakCalendarDay: {
            /**
             * Completed
             * @default 0
             */
            completed?: number;
            /**
             * Date
             * Format: date
             */
            date: string;
            /** Edition No */
            edition_no?: number | null;
            /**
             * Is Today
             * @default false
             */
            is_today?: boolean;
            /** Seal Variant */
            seal_variant?: string | null;
            /**
             * Sealed
             * @default false
             */
            sealed?: boolean;
            /**
             * State
             * @default missed
             */
            state?: string;
        };
        /**
         * StreakInfo
         * @description The streak number and its calendar, read from the same rows (WP-D5).
         */
        StreakInfo: {
            /** Calendar */
            calendar?: components["schemas"]["StreakCalendarDay"][];
            /** Current Streak */
            current_streak: number;
            /**
             * Freeze Available
             * @default false
             */
            freeze_available?: boolean;
            /** Longest Streak */
            longest_streak: number;
            /** Timezone */
            timezone?: string | null;
            /** Today */
            today?: string | null;
            /**
             * Today Done
             * @default false
             */
            today_done?: boolean;
        };
        /**
         * StreakInfoRead
         * @description Grammar streak information.
         */
        StreakInfoRead: {
            /** Current Streak */
            current_streak: number;
            /** Is Active Today */
            is_active_today: boolean;
            /** Last Review Date */
            last_review_date: string | null;
            /** Longest Streak */
            longest_streak: number;
        };
        /**
         * StreakView
         * @description WP-80. The practice streak, checked against the learner's local date.
         *
         *     ``days`` is 0 the moment a day was missed without a banked «jour de
         *     relâche»; ``freeze_used_on`` is the local day the last one covered.
         */
        StreakView: {
            /** Days */
            days: number;
            /** Freeze Available */
            freeze_available: boolean;
            /** Freeze Used On */
            freeze_used_on: string | null;
            /** Today Done */
            today_done: boolean;
        };
        /**
         * TargetedErrorRead
         * @description Error pattern being targeted in the assistant's response.
         */
        TargetedErrorRead: {
            /** Category */
            category: string;
            /** Context */
            context?: string | null;
            /** Correction */
            correction?: string | null;
            /**
             * Lapses
             * @default 0
             */
            lapses?: number;
            /** Pattern */
            pattern?: string | null;
            /**
             * Reps
             * @default 0
             */
            reps?: number;
        };
        /**
         * TargetKind
         * @enum {string}
         */
        TargetKind: "vocabulary" | "grammar" | "error";
        /** TargetRef */
        TargetRef: {
            /**
             * Concept Title
             * @default false
             */
            concept_title: boolean;
            /** Id */
            id: string;
            kind: components["schemas"]["TargetKind"];
            /** Label Fr */
            label_fr: string;
            /** Label Native */
            label_native: string | null;
        };
        /** TargetVocabularyRead */
        TargetVocabularyRead: {
            /** Bucket */
            bucket?: string | null;
            /** Example Sentence */
            example_sentence?: string | null;
            /** Example Translation */
            example_translation?: string | null;
            /** Priority Score */
            priority_score?: number | null;
            /** Scheduler */
            scheduler?: string | null;
            /** Translation */
            translation?: string | null;
            /** Word */
            word: string;
            /** Word Id */
            word_id: number;
        } & {
            [key: string]: unknown;
        };
        /**
         * TargetWordRead
         * @description Metadata about a vocabulary item targeted in a turn.
         */
        TargetWordRead: {
            /** Familiarity */
            familiarity?: ("new" | "learning" | "familiar") | null;
            /** Hint Sentence */
            hint_sentence?: string | null;
            /** Hint Translation */
            hint_translation?: string | null;
            /** Is New */
            is_new: boolean;
            /** Translation */
            translation?: string | null;
            /** Word */
            word: string;
            /** Word Id */
            word_id: number;
        };
        /**
         * TaskOutcome
         * @enum {string}
         */
        TaskOutcome: "met" | "partially_met" | "not_yet" | "unscored";
        /** TextAttemptInput */
        TextAttemptInput: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "text";
            /** Text */
            text: string;
        };
        /**
         * ThreadExchange
         * @description WP-89 «Le fil»: one exchange of the reply conversation, as it happened.
         *
         *     ``character_fr`` is the character's answer to ``learner_fr``; ``correction``
         *     is the one public correction that turn earned, if any. Additive to contract
         *     v1: a reloaded client redraws the conversation from it.
         */
        ThreadExchange: {
            /** Character Fr */
            character_fr: string;
            /** Character Lines */
            character_lines: components["schemas"]["ThreadLine"][];
            correction: components["schemas"]["JourneyCorrection"] | null;
            /** Learner Fr */
            learner_fr: string;
        };
        /**
         * ThreadLine
         * @description One spoken line of a many-voiced reply: who says it and what.
         */
        ThreadLine: {
            /** Speaker Id */
            speaker_id: string | null;
            /** Speaker Name */
            speaker_name: string | null;
            /** Text Fr */
            text_fr: string;
        };
        /** TilesAttemptInput */
        TilesAttemptInput: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "tiles";
            /** Tile Ids */
            tile_ids?: string[];
        };
        /**
         * TimeExtension
         * @description WP-128 — one optional extension of the day, with its own estimate.
         *
         *     ``words`` (the drill), ``letter`` (one Courrier reply), ``forge`` (La Forge's
         *     block), ``reading`` (the «Lecture») and ``desk`` (a Revue desk). None of them
         *     is part of the core the rhythm budgets, and none is a completion requirement.
         *     ``in_day``: planned inside today's journey (Soutenu/Intensif's folded forge
         *     and «Lecture», a desk); otherwise an activity of its own, offered beside it.
         */
        TimeExtension: {
            /**
             * In Day
             * @default false
             */
            in_day: boolean;
            /**
             * Kind
             * @enum {string}
             */
            kind: "words" | "letter" | "forge" | "reading" | "desk";
            /** Seconds */
            seconds: number;
        };
        /** TodayEnvelope */
        TodayEnvelope: {
            absence: components["schemas"]["AbsenceView"] | null;
            available: components["schemas"]["ScenarioDescriptor"] | null;
            because: components["schemas"]["JourneyBecause"] | null;
            /**
             * Contract Version
             * @default 1
             * @constant
             */
            contract_version: 1;
            /**
             * Control Language
             * @enum {string}
             */
            control_language: "en" | "de" | "fr";
            /** Enabled */
            enabled: boolean;
            forge: components["schemas"]["ForgeEntry"] | null;
            headline: components["schemas"]["EpisodeHeadline"] | null;
            interlude: components["schemas"]["InterludeView"] | null;
            /**
             * Is Warm
             * @default false
             */
            is_warm: boolean;
            journey: components["schemas"]["JourneySnapshot"] | null;
            /** Learner Level */
            learner_level: string | null;
            legacy_resume: components["schemas"]["LegacyResume"] | null;
            /**
             * Local Date
             * Format: date
             */
            local_date: string;
            /**
             * Missed Days
             * @default 0
             */
            missed_days: number;
            /**
             * Practice Href
             * @default /atelier?mode=practice
             */
            practice_href: string;
            season_premiere: components["schemas"]["SeasonPremiereView"] | null;
            streak: components["schemas"]["StreakView"] | null;
            time_estimate: components["schemas"]["DayTimeEstimate"] | null;
            /** Timezone */
            timezone: string;
        };
        /**
         * Token
         * @description Token response returned after successful authentication.
         */
        Token: {
            /** Access Token */
            access_token: string;
            /** Refresh Token */
            refresh_token: string;
            /**
             * Token Type
             * @default bearer
             */
            token_type?: string;
        };
        /** TranslateRequest */
        TranslateRequest: {
            /** Text */
            text: string;
        };
        /**
         * TTSRequest
         * @description Request body for text-to-speech.
         */
        TTSRequest: {
            /** Provider */
            provider?: string | null;
            /** Text */
            text: string;
            /**
             * Voice
             * @description Voice ID or name (e.g. nova, Rachel)
             * @default nova
             */
            voice?: string;
        };
        /** TurnRequest */
        TurnRequest: {
            /**
             * Mode
             * @default text
             */
            mode?: string;
            /**
             * Text
             * @default
             */
            text?: string;
            /** Turn Index */
            turn_index: number;
        };
        /**
         * UnifiedQueueItem
         * @description Cross-mode learning item returned by the unified SRS queue.
         */
        UnifiedQueueItem: {
            /** Display Subtitle */
            display_subtitle: string;
            /** Display Title */
            display_title: string;
            /** Due Since Days */
            due_since_days: number;
            /** Estimated Seconds */
            estimated_seconds: number;
            /** Id */
            id: string;
            /** Item Type */
            item_type: string;
            /** Level */
            level: string;
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            };
            /** Original Id */
            original_id?: string | number | null;
            /** Priority Score */
            priority_score: number;
        };
        /**
         * UnifiedQueueResponse
         * @description Unified SRS queue response.
         */
        UnifiedQueueResponse: {
            /** Interleaving Mode */
            interleaving_mode: string;
            /** Queue */
            queue: components["schemas"]["UnifiedQueueItem"][];
            summary: components["schemas"]["UnifiedQueueSummary"];
            /** Time Budget Minutes */
            time_budget_minutes?: number | null;
        };
        /**
         * UnifiedQueueSummary
         * @description Unified workload summary across vocabulary, grammar, and errata.
         */
        UnifiedQueueSummary: {
            /** By Type */
            by_type: {
                [key: string]: components["schemas"]["UnifiedQueueTypeSummary"];
            };
            /** Estimated Minutes */
            estimated_minutes: number;
            /** Total Due */
            total_due: number;
            /**
             * Total New
             * @default 0
             */
            total_new?: number;
        };
        /**
         * UnifiedQueueTypeSummary
         * @description Due-count summary for one SRS item type.
         */
        UnifiedQueueTypeSummary: {
            /** Due */
            due: number;
            /** Minutes */
            minutes: number;
            /**
             * New
             * @default 0
             */
            new?: number;
        };
        /**
         * UserCreate
         * @description Schema for user registration input.
         *
         *     WP-75: email and password are the only required fields. Every profile field
         *     has a default (``UserBase``) and moves to Réglages; ``starting_point`` is
         *     the one question sign-up still asks.
         */
        UserCreate: {
            /**
             * Achievement Notifications
             * @default true
             */
            achievement_notifications?: boolean;
            /**
             * Auto Play Pronunciation
             * @default true
             */
            auto_play_pronunciation?: boolean;
            /**
             * Cefr Estimate
             * @default A1.1
             */
            cefr_estimate?: string;
            /** Cefr Estimate Payload */
            cefr_estimate_payload?: {
                [key: string]: unknown;
            } | null;
            /**
             * Cefr Target Level
             * @default A1.2
             */
            cefr_target_level?: string;
            /**
             * Daily Goal Minutes
             * @default 10
             */
            daily_goal_minutes?: number;
            /**
             * Daily Goal Xp
             * @default 50
             */
            daily_goal_xp?: number;
            /** Default Vocab Direction */
            default_vocab_direction?: string | null;
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Font Size
             * @default medium
             */
            font_size?: string;
            /** Full Name */
            full_name?: string | null;
            /**
             * Grammar Correction Level
             * @default moderate
             */
            grammar_correction_level?: string;
            /**
             * Interests
             * @description Comma-separated interest topics for personalized content
             * @default
             */
            interests?: string;
            /**
             * Learning Motivation
             * @default
             */
            learning_motivation?: string;
            /**
             * Max Reviews Per Day
             * @default 200
             */
            max_reviews_per_day?: number;
            /**
             * Native Language
             * @default en
             */
            native_language?: string;
            /**
             * New Words Per Day
             * @default 10
             */
            new_words_per_day?: number;
            /**
             * Notifications Enabled
             * @default true
             */
            notifications_enabled?: boolean;
            /** Password */
            password: string;
            /**
             * Practice Reminders
             * @default true
             */
            practice_reminders?: boolean;
            /** Preferred Session Time */
            preferred_session_time?: string | null;
            /**
             * Proficiency Level
             * @default beginner
             */
            proficiency_level?: string;
            /**
             * Reminder Time
             * @default 09:00
             */
            reminder_time?: string;
            /**
             * Serial Edition Notifications
             * @default true
             */
            serial_edition_notifications?: boolean;
            /**
             * Show Grammar Explanations
             * @default true
             */
            show_grammar_explanations?: boolean;
            /**
             * Speaking Comfort
             * @default warming_up
             */
            speaking_comfort?: string;
            /** Starting Point */
            starting_point?: ("new" | "some" | "comfortable" | "confident" | "advanced") | null;
            /**
             * Streak Notifications
             * @default true
             */
            streak_notifications?: boolean;
            /**
             * Target Language
             * @default fr
             */
            target_language?: string;
            /**
             * Text To Speech Enabled
             * @default true
             */
            text_to_speech_enabled?: boolean;
            /**
             * Theme
             * @default system
             */
            theme?: string;
            /**
             * Tts Speed
             * @default 1.0
             */
            tts_speed?: string;
            /**
             * Voice Input Enabled
             * @default true
             */
            voice_input_enabled?: boolean;
            /**
             * Weekly Email Summary
             * @default true
             */
            weekly_email_summary?: boolean;
        };
        /**
         * UserEmailChange
         * @description Email change payload for the current user.
         */
        UserEmailChange: {
            /** Current Password */
            current_password: string;
            /**
             * New Email
             * Format: email
             */
            new_email: string;
        };
        /**
         * UserLogin
         * @description Schema for user login request.
         */
        UserLogin: {
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Password */
            password: string;
        };
        /**
         * UserPasswordChange
         * @description Password change payload for the current user.
         */
        UserPasswordChange: {
            /** Current Password */
            current_password: string;
            /** New Password */
            new_password: string;
        };
        /**
         * UserRead
         * @description Schema returned after user registration or retrieval.
         */
        UserRead: {
            /**
             * Achievement Notifications
             * @default true
             */
            achievement_notifications?: boolean;
            /**
             * Address Preference
             * @default neutral
             * @enum {string}
             */
            address_preference?: "feminine" | "masculine" | "neutral";
            /**
             * Auto Play Pronunciation
             * @default true
             */
            auto_play_pronunciation?: boolean;
            /**
             * Cefr Estimate
             * @default A1.1
             */
            cefr_estimate?: string;
            /** Cefr Estimate Payload */
            cefr_estimate_payload?: {
                [key: string]: unknown;
            } | null;
            /**
             * Cefr Target Level
             * @default A1.2
             */
            cefr_target_level?: string;
            /** Current Streak */
            current_streak: number;
            /**
             * Daily Goal Minutes
             * @default 10
             */
            daily_goal_minutes?: number;
            /**
             * Daily Goal Xp
             * @default 50
             */
            daily_goal_xp?: number;
            /** Default Vocab Direction */
            default_vocab_direction?: string | null;
            /**
             * Email
             * Format: email
             */
            email: string;
            /**
             * Font Size
             * @default medium
             */
            font_size?: string;
            /** Full Name */
            full_name?: string | null;
            /**
             * Grammar Correction Level
             * @default moderate
             */
            grammar_correction_level?: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Interests
             * @description Comma-separated interest topics for personalized content
             * @default
             */
            interests?: string;
            /** Is Active */
            is_active: boolean;
            /** Is Verified */
            is_verified: boolean;
            /** Last Activity Date */
            last_activity_date: string | null;
            /**
             * Learning Motivation
             * @default
             */
            learning_motivation?: string;
            /** Level */
            level: number;
            /** Longest Streak */
            longest_streak: number;
            /**
             * Max Reviews Per Day
             * @default 200
             */
            max_reviews_per_day?: number;
            /**
             * Native Language
             * @default en
             */
            native_language?: string;
            /**
             * New Words Per Day
             * @default 10
             */
            new_words_per_day?: number;
            /**
             * Notifications Enabled
             * @default true
             */
            notifications_enabled?: boolean;
            /**
             * Practice Reminders
             * @default true
             */
            practice_reminders?: boolean;
            /** Preferred Session Time */
            preferred_session_time?: string | null;
            /**
             * Proficiency Level
             * @default beginner
             */
            proficiency_level?: string;
            /**
             * Reminder Time
             * @default 09:00
             */
            reminder_time?: string;
            /**
             * Role
             * @default user
             */
            role?: string;
            /**
             * Serial Edition Notifications
             * @default true
             */
            serial_edition_notifications?: boolean;
            /**
             * Serial Onboarding Seen
             * @default false
             */
            serial_onboarding_seen?: boolean;
            /**
             * Show Grammar Explanations
             * @default true
             */
            show_grammar_explanations?: boolean;
            /**
             * Speaking Comfort
             * @default warming_up
             */
            speaking_comfort?: string;
            /**
             * Streak Notifications
             * @default true
             */
            streak_notifications?: boolean;
            /** Subscription Expires At */
            subscription_expires_at: string | null;
            /** Subscription Tier */
            subscription_tier: string;
            /**
             * Target Language
             * @default fr
             */
            target_language?: string;
            /**
             * Text To Speech Enabled
             * @default true
             */
            text_to_speech_enabled?: boolean;
            /**
             * Theme
             * @default system
             */
            theme?: string;
            /** Total Xp */
            total_xp: number;
            /**
             * Tts Speed
             * @default 1.0
             */
            tts_speed?: string;
            /**
             * Voice Input Enabled
             * @default true
             */
            voice_input_enabled?: boolean;
            /**
             * Weekly Email Summary
             * @default true
             */
            weekly_email_summary?: boolean;
        };
        /**
         * UserSettingsRead
         * @description Current account, learning, notification, appearance, audio, and grammar settings.
         */
        UserSettingsRead: {
            /** Achievement Notifications */
            achievement_notifications: boolean;
            /**
             * Address Preference
             * @default neutral
             * @enum {string}
             */
            address_preference?: "feminine" | "masculine" | "neutral";
            /** Auto Play Pronunciation */
            auto_play_pronunciation: boolean;
            /**
             * Cefr Estimate
             * @default A1.1
             */
            cefr_estimate?: string;
            /** Cefr Estimate Payload */
            cefr_estimate_payload?: {
                [key: string]: unknown;
            } | null;
            /**
             * Cefr Target Level
             * @default A1.2
             */
            cefr_target_level?: string;
            /** Daily Goal Minutes */
            daily_goal_minutes: number;
            /** Daily Goal Xp */
            daily_goal_xp: number;
            /** Default Vocab Direction */
            default_vocab_direction: string;
            /**
             * Email
             * Format: email
             */
            email: string;
            /** Episode Audio Enabled */
            episode_audio_enabled?: boolean;
            /** Font Size */
            font_size: string;
            /** Full Name */
            full_name?: string | null;
            /** Grammar Correction Level */
            grammar_correction_level: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Interests */
            interests: string;
            /** Is Active */
            is_active: boolean;
            /** Is Verified */
            is_verified: boolean;
            /** Learning Motivation */
            learning_motivation: string;
            /**
             * Max Reviews Per Day
             * @default 200
             */
            max_reviews_per_day?: number;
            /** Native Language */
            native_language: string;
            /** New Words Per Day */
            new_words_per_day: number;
            /** Notifications Enabled */
            notifications_enabled: boolean;
            /** Practice Reminders */
            practice_reminders: boolean;
            /** Preferred Session Time */
            preferred_session_time?: string | null;
            /** Proficiency Level */
            proficiency_level: string;
            /** Reminder Time */
            reminder_time: string;
            /**
             * Rhythm
             * @default regulier
             * @enum {string}
             */
            rhythm?: "leger" | "regulier" | "soutenu" | "intensif";
            /** Role */
            role: string;
            /** Serial Edition Notifications */
            serial_edition_notifications: boolean;
            /** Show Grammar Explanations */
            show_grammar_explanations: boolean;
            /** Speaking Comfort */
            speaking_comfort: string;
            /** Streak Notifications */
            streak_notifications: boolean;
            /** Target Language */
            target_language: string;
            /** Text To Speech Enabled */
            text_to_speech_enabled: boolean;
            /** Theme */
            theme: string;
            /**
             * Timezone
             * @default Europe/Paris
             */
            timezone?: string | null;
            /** Tts Speed */
            tts_speed: string;
            /** Updated At */
            updated_at?: string | null;
            /** Voice Input Enabled */
            voice_input_enabled: boolean;
            /** Weekly Email Summary */
            weekly_email_summary: boolean;
        };
        /**
         * UserSettingsUpdate
         * @description Partial settings update payload for the current user.
         */
        UserSettingsUpdate: {
            /** Achievement Notifications */
            achievement_notifications?: boolean | null;
            /** Address Preference */
            address_preference?: ("feminine" | "masculine" | "neutral") | null;
            /** Auto Play Pronunciation */
            auto_play_pronunciation?: boolean | null;
            /** Cefr Target Level */
            cefr_target_level?: string | null;
            /** Daily Goal Minutes */
            daily_goal_minutes?: number | null;
            /** Daily Goal Xp */
            daily_goal_xp?: number | null;
            /** Default Vocab Direction */
            default_vocab_direction?: ("fr_to_de" | "de_to_fr" | "fr_to_en" | "en_to_fr" | "mixed") | null;
            /** Font Size */
            font_size?: ("small" | "medium" | "large") | null;
            /** Full Name */
            full_name?: string | null;
            /** Grammar Correction Level */
            grammar_correction_level?: ("strict" | "moderate" | "lenient") | null;
            /** Interests */
            interests?: string | null;
            /** Learning Motivation */
            learning_motivation?: string | null;
            /** Max Reviews Per Day */
            max_reviews_per_day?: number | null;
            /** Native Language */
            native_language?: string | null;
            /** New Words Per Day */
            new_words_per_day?: number | null;
            /** Notifications Enabled */
            notifications_enabled?: boolean | null;
            /** Practice Reminders */
            practice_reminders?: boolean | null;
            /** Preferred Session Time */
            preferred_session_time?: string | null;
            /** Proficiency Level */
            proficiency_level?: ("beginner" | "A1" | "A2" | "B1" | "B2" | "C1" | "C2") | null;
            /** Reminder Time */
            reminder_time?: string | null;
            /** Rhythm */
            rhythm?: ("leger" | "regulier" | "soutenu" | "intensif") | null;
            /** Serial Edition Notifications */
            serial_edition_notifications?: boolean | null;
            /** Show Grammar Explanations */
            show_grammar_explanations?: boolean | null;
            /** Speaking Comfort */
            speaking_comfort?: ("warming_up" | "ready" | "confident") | null;
            /** Streak Notifications */
            streak_notifications?: boolean | null;
            /** Target Language */
            target_language?: string | null;
            /** Text To Speech Enabled */
            text_to_speech_enabled?: boolean | null;
            /** Theme */
            theme?: ("light" | "dark" | "system") | null;
            /** Timezone */
            timezone?: string | null;
            /** Tts Speed */
            tts_speed?: string | null;
            /** Voice Input Enabled */
            voice_input_enabled?: boolean | null;
            /** Weekly Email Summary */
            weekly_email_summary?: boolean | null;
        };
        /**
         * UserUpdate
         * @description Schema for partial updates to the current user profile.
         */
        UserUpdate: {
            /** Achievement Notifications */
            achievement_notifications?: boolean | null;
            /** Address Preference */
            address_preference?: ("feminine" | "masculine" | "neutral") | null;
            /** Auto Play Pronunciation */
            auto_play_pronunciation?: boolean | null;
            /** Cefr Target Level */
            cefr_target_level?: string | null;
            /** Daily Goal Minutes */
            daily_goal_minutes?: number | null;
            /** Daily Goal Xp */
            daily_goal_xp?: number | null;
            /** Default Vocab Direction */
            default_vocab_direction?: string | null;
            /** Font Size */
            font_size?: string | null;
            /** Full Name */
            full_name?: string | null;
            /** Grammar Correction Level */
            grammar_correction_level?: string | null;
            /** Interests */
            interests?: string | null;
            /** Learning Motivation */
            learning_motivation?: string | null;
            /** Max Reviews Per Day */
            max_reviews_per_day?: number | null;
            /** Native Language */
            native_language?: string | null;
            /** New Words Per Day */
            new_words_per_day?: number | null;
            /** Notifications Enabled */
            notifications_enabled?: boolean | null;
            /** Practice Reminders */
            practice_reminders?: boolean | null;
            /** Preferred Session Time */
            preferred_session_time?: string | null;
            /** Proficiency Level */
            proficiency_level?: string | null;
            /** Reminder Time */
            reminder_time?: string | null;
            /** Serial Edition Notifications */
            serial_edition_notifications?: boolean | null;
            /** Show Grammar Explanations */
            show_grammar_explanations?: boolean | null;
            /** Speaking Comfort */
            speaking_comfort?: string | null;
            /** Streak Notifications */
            streak_notifications?: boolean | null;
            /** Target Language */
            target_language?: string | null;
            /** Text To Speech Enabled */
            text_to_speech_enabled?: boolean | null;
            /** Theme */
            theme?: string | null;
            /** Tts Speed */
            tts_speed?: string | null;
            /** Voice Input Enabled */
            voice_input_enabled?: boolean | null;
            /** Weekly Email Summary */
            weekly_email_summary?: boolean | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** VignettesResponse */
        VignettesResponse: {
            /** Vignettes */
            vignettes: components["schemas"]["VignetteView"][];
        };
        /**
         * VignetteView
         * @description One minted vignette with everything the stamp needs.
         */
        VignetteView: {
            /** Dossier Id */
            dossier_id: string;
            /** Headline Fr */
            headline_fr: string;
            /** Id */
            id: string;
            /** Kept Contribution */
            kept_contribution: boolean;
            /**
             * Minted At
             * Format: date-time
             */
            minted_at: string;
            /** Pictogram Svg */
            pictogram_svg: string;
            /** Place Label Fr */
            place_label_fr: string;
            /**
             * Ring
             * @enum {string}
             */
            ring: "headline" | "question" | "report";
            /** Session Id */
            session_id: string;
            /** Week */
            week: string;
        };
        /**
         * VocabularyBiographyEvent
         * @description One entry in the word's memory thread.
         */
        VocabularyBiographyEvent: {
            /** Description */
            description?: string | null;
            /** Event Type */
            event_type: string;
            /** Id */
            id: string;
            /** Label */
            label: string;
            /** Metadata */
            metadata?: {
                [key: string]: unknown;
            };
            /** Occurred At */
            occurred_at?: string | null;
            /** Source Id */
            source_id?: string | null;
            /** Source Type */
            source_type: string;
        };
        /**
         * VocabularyBiographyExample
         * @description One remembered or dictionary-backed example for a vocabulary word.
         */
        VocabularyBiographyExample: {
            /** Occurred At */
            occurred_at?: string | null;
            /** Sentence */
            sentence: string;
            /**
             * Source
             * @default dictionary
             */
            source?: string;
            /** Translation */
            translation?: string | null;
        };
        /**
         * VocabularyBiographyOrigin
         * @description Where a word first enters the learner-facing system.
         */
        VocabularyBiographyOrigin: {
            /** Created At */
            created_at?: string | null;
            /** Deck Name */
            deck_name?: string | null;
            /** Frequency Rank */
            frequency_rank?: number | null;
            /**
             * Imported
             * @default false
             */
            imported?: boolean;
            /** Label */
            label: string;
            /**
             * Source Type
             * @default deck
             */
            source_type?: string;
        };
        /**
         * VocabularyBiographyProgress
         * @description Human-readable SRS state for a word biography.
         */
        VocabularyBiographyProgress: {
            /** Difficulty */
            difficulty?: number | null;
            /** Due At */
            due_at?: string | null;
            /**
             * Fragility Label
             * @default New thread
             */
            fragility_label?: string;
            /**
             * Fragility Level
             * @default new
             */
            fragility_level?: string;
            /** Fragility Reason */
            fragility_reason?: string | null;
            /** Interval Days */
            interval_days?: number | null;
            /**
             * Lapses
             * @default 0
             */
            lapses?: number;
            /** Last Review */
            last_review?: string | null;
            /** Next Review */
            next_review?: string | null;
            /** Phase */
            phase?: string | null;
            /**
             * Proficiency Score
             * @default 0
             */
            proficiency_score?: number;
            /** Progress Id */
            progress_id?: string | null;
            /**
             * Reps
             * @default 0
             */
            reps?: number;
            /** Retrievability */
            retrievability?: number | null;
            /** Scheduled Days */
            scheduled_days?: number | null;
            /** Scheduler */
            scheduler?: string | null;
            /** Stability */
            stability?: number | null;
            /**
             * State
             * @default new
             */
            state?: string;
            /**
             * Times Seen
             * @default 0
             */
            times_seen?: number;
            /**
             * Times Used Correctly
             * @default 0
             */
            times_used_correctly?: number;
            /**
             * Times Used Incorrectly
             * @default 0
             */
            times_used_incorrectly?: number;
        };
        /**
         * VocabularyBiographyResponse
         * @description A compact, resilient biography for a vocabulary word.
         */
        VocabularyBiographyResponse: {
            /**
             * Context Event Count
             * @default 0
             */
            context_event_count?: number;
            /** Examples */
            examples?: components["schemas"]["VocabularyBiographyExample"][];
            /**
             * Linked Errata Count
             * @default 0
             */
            linked_errata_count?: number;
            origin: components["schemas"]["VocabularyBiographyOrigin"];
            progress: components["schemas"]["VocabularyBiographyProgress"];
            /** Revisited In */
            revisited_in?: components["schemas"]["VocabularyBiographyRevisit"][];
            /** Timeline */
            timeline?: components["schemas"]["VocabularyBiographyEvent"][];
            word: components["schemas"]["VocabularyWordRead"];
        };
        /**
         * VocabularyBiographyRevisit
         * @description WP-93 «revu dans l'épisode du 12»: a story page that brought the word back.
         */
        VocabularyBiographyRevisit: {
            /** Date */
            date: string;
            /** Scene Id */
            scene_id?: string | null;
            /** Scene Title Fr */
            scene_title_fr: string;
        };
        /** VocabularyCreditSummary */
        VocabularyCreditSummary: {
            /**
             * Missed Target
             * @default 0
             */
            missed_target?: number;
            /**
             * Produced Correct
             * @default 0
             */
            produced_correct?: number;
            /**
             * Produced Incorrect
             * @default 0
             */
            produced_incorrect?: number;
            /**
             * Recognized
             * @default 0
             */
            recognized?: number;
            /**
             * Seen Context
             * @default 0
             */
            seen_context?: number;
        } & {
            [key: string]: unknown;
        };
        /**
         * VocabularyDueContextResponse
         * @description Bucketed due-context vocabulary for mobile practice surfaces.
         */
        VocabularyDueContextResponse: {
            /**
             * Algorithm
             * @default fsrs_retrievability_v1
             */
            algorithm?: string;
            /** Due Words */
            due_words: components["schemas"]["VocabularyRecommendationItem"][];
            /** Fragile Words */
            fragile_words: components["schemas"]["VocabularyRecommendationItem"][];
            /** Linked Words */
            linked_words: components["schemas"]["VocabularyRecommendationItem"][];
            /** New Words */
            new_words: components["schemas"]["VocabularyRecommendationItem"][];
            /** New Words Left Today */
            new_words_left_today?: number | null;
            summary: components["schemas"]["VocabularyDueContextSummary"];
            /** Topic Compatible Words */
            topic_compatible_words: components["schemas"]["VocabularyRecommendationItem"][];
        };
        /**
         * VocabularyDueContextSummary
         * @description Selected counts for a contextual vocabulary review bundle.
         */
        VocabularyDueContextSummary: {
            /** Due */
            due: number;
            /** Due Total */
            due_total?: number | null;
            /** Fragile */
            fragile: number;
            /** Linked */
            linked: number;
            /** New */
            new: number;
            /** Topic Compatible */
            topic_compatible: number;
            /** Total */
            total: number;
        };
        /** VocabularyEventRead */
        VocabularyEventRead: {
            /** Event Type */
            event_type: string;
            /** Reason */
            reason?: string | null;
            /** Word Id */
            word_id: number;
        } & {
            [key: string]: unknown;
        };
        /**
         * VocabularyHeatmapEntry
         * @description Vocabulary mastery bin.
         */
        VocabularyHeatmapEntry: {
            /** Count */
            count: number;
            /** State */
            state: string;
        };
        /**
         * VocabularyHeatmapResponse
         * @description Heatmap payload summarising vocabulary states.
         */
        VocabularyHeatmapResponse: {
            /** States */
            states?: components["schemas"]["VocabularyHeatmapEntry"][];
            /** Total */
            total: number;
        };
        /**
         * VocabularyListResponse
         * @description Paginated vocabulary response payload.
         */
        VocabularyListResponse: {
            /** Items */
            items: components["schemas"]["VocabularyWordRead"][];
            /** Total */
            total: number;
        };
        /**
         * VocabularyMasteryMapCell
         * @description One tiny cell in the French 5000 mastery map.
         */
        VocabularyMasteryMapCell: {
            /** Frequency Rank */
            frequency_rank?: number | null;
            /**
             * Is Due
             * @default false
             */
            is_due?: boolean;
            /**
             * Lapses
             * @default 0
             */
            lapses?: number;
            /** Mastery State */
            mastery_state: string;
            /**
             * Proficiency Score
             * @default 0
             */
            proficiency_score?: number;
            /** Word */
            word: string;
            /** Word Id */
            word_id: number;
        };
        /**
         * VocabularyMasteryMapResponse
         * @description Typographic map of the imported French 5000 deck.
         */
        VocabularyMasteryMapResponse: {
            /** Cells */
            cells: components["schemas"]["VocabularyMasteryMapCell"][];
            /**
             * Deck Label
             * @default French 5000
             */
            deck_label?: string;
            summary: components["schemas"]["VocabularyMasteryMapSummary"];
        };
        /**
         * VocabularyMasteryMapSummary
         * @description Aggregate counts for the French 5000 mastery map.
         */
        VocabularyMasteryMapSummary: {
            /** Building */
            building: number;
            /** Due */
            due: number;
            /** Fragile */
            fragile: number;
            /** Mastered */
            mastered: number;
            /** New */
            new: number;
            /** Solid */
            solid: number;
            /** Total */
            total: number;
        };
        /**
         * VocabularyRecommendationItem
         * @description Vocabulary card selected for today's SRS work.
         */
        VocabularyRecommendationItem: {
            /** Bucket */
            bucket: string;
            /** Deck Name */
            deck_name?: string | null;
            /** Difficulty */
            difficulty?: number | null;
            /** Direction */
            direction?: string | null;
            /** Due At */
            due_at?: string | null;
            /** Episodic Anchor */
            episodic_anchor?: {
                [key: string]: unknown;
            } | null;
            /** Example Sentence */
            example_sentence?: string | null;
            /** Example Translation */
            example_translation?: string | null;
            /** Gender */
            gender?: string | null;
            /** Interval Days */
            interval_days?: number | null;
            /**
             * Is New
             * @default false
             */
            is_new?: boolean;
            /** Ladder */
            ladder?: string | null;
            /** Language */
            language: string;
            /**
             * Lapses
             * @default 0
             */
            lapses?: number;
            /** Last Review */
            last_review?: string | null;
            /**
             * Leech
             * @default false
             */
            leech?: boolean;
            /** Next Review */
            next_review?: string | null;
            /** Part Of Speech */
            part_of_speech?: string | null;
            /** Phase */
            phase?: string | null;
            /** Priority Score */
            priority_score: number;
            /**
             * Proficiency Score
             * @default 0
             */
            proficiency_score?: number;
            /** Progress Id */
            progress_id?: string | null;
            /** Recommendation Reason */
            recommendation_reason?: {
                [key: string]: unknown;
            } | null;
            /** Rescue Cue */
            rescue_cue?: {
                [key: string]: unknown;
            } | null;
            /** Retrievability */
            retrievability?: number | null;
            /** Scene Cue */
            scene_cue?: {
                [key: string]: unknown;
            } | null;
            /** Scheduled Days */
            scheduled_days?: number | null;
            /** Scheduler */
            scheduler?: string | null;
            /** Stability */
            stability?: number | null;
            /** State */
            state: string;
            /** Topic Tags */
            topic_tags?: string[];
            /** Translation */
            translation?: string | null;
            /** Translation Language */
            translation_language?: string | null;
            translations: components["schemas"]["VocabularyRecommendationTranslations"];
            /** Word */
            word: string;
            /** Word Id */
            word_id: number;
        };
        /**
         * VocabularyRecommendationResponse
         * @description Ranked vocabulary recommendations for the daily learning loop.
         */
        VocabularyRecommendationResponse: {
            /**
             * Algorithm
             * @default fsrs_retrievability_v1
             */
            algorithm?: string;
            /** Items */
            items: components["schemas"]["VocabularyRecommendationItem"][];
            summary: components["schemas"]["VocabularyRecommendationSummary"];
        };
        /**
         * VocabularyRecommendationSummary
         * @description Counts for each recommendation bucket.
         */
        VocabularyRecommendationSummary: {
            /** Due */
            due: number;
            /** Fragile */
            fragile: number;
            /** New */
            new: number;
            /** Total */
            total: number;
        };
        /**
         * VocabularyRecommendationTranslations
         * @description Translation hints for a recommended vocabulary item.
         */
        VocabularyRecommendationTranslations: {
            /** De */
            de?: string | null;
            /** En */
            en?: string | null;
            /** Fr */
            fr?: string | null;
        };
        /**
         * VocabularyWordRead
         * @description Representation of a vocabulary word.
         */
        VocabularyWordRead: {
            /** Definition */
            definition?: string | null;
            /** Difficulty Level */
            difficulty_level?: number | null;
            /** English Translation */
            english_translation?: string | null;
            /** Example Sentence */
            example_sentence?: string | null;
            /** Example Translation */
            example_translation?: string | null;
            /** French Translation */
            french_translation?: string | null;
            /** Frequency Rank */
            frequency_rank?: number | null;
            /** Gender */
            gender?: string | null;
            /** German Translation */
            german_translation?: string | null;
            /** Id */
            id: number;
            /** Language */
            language: string;
            /** Normalized Word */
            normalized_word: string;
            /** Part Of Speech */
            part_of_speech?: string | null;
            /** Topic Tags */
            topic_tags?: string[];
            /** Translation */
            translation?: string | null;
            /** Translation Language */
            translation_language?: string | null;
            /** Usage Notes */
            usage_notes?: string | null;
            /** Word */
            word: string;
        };
        /** VoiceAttemptInput */
        VoiceAttemptInput: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "voice";
            /** Text */
            text: string;
            /** Transcript Ref */
            transcript_ref?: string | null;
        };
        /**
         * WeeklyDossierResponse
         * @description Editorial weekly digest generated from local learning telemetry.
         */
        WeeklyDossierResponse: {
            /** Fragile Threads */
            fragile_threads: components["schemas"]["WeeklyDossierThread"][];
            /** Headline */
            headline: string;
            /** Next Actions */
            next_actions: components["schemas"]["WeeklyDossierThread"][];
            /**
             * Period End
             * Format: date-time
             */
            period_end: string;
            /**
             * Period Start
             * Format: date-time
             */
            period_start: string;
            stats: components["schemas"]["WeeklyDossierStats"];
            /** Strengths */
            strengths: components["schemas"]["WeeklyDossierThread"][];
        };
        /**
         * WeeklyDossierStats
         * @description Deterministic weekly learning stats for the editorial progress mirror.
         */
        WeeklyDossierStats: {
            /**
             * Feuilleton Scenes Completed
             * @default 0
             */
            feuilleton_scenes_completed?: number;
            /**
             * Missions Completed
             * @default 0
             */
            missions_completed?: number;
            /**
             * Repairs Filed
             * @default 0
             */
            repairs_filed?: number;
            /**
             * Vocabulary Reviews
             * @default 0
             */
            vocabulary_reviews?: number;
            /**
             * Words Produced
             * @default 0
             */
            words_produced?: number;
            /**
             * Words Seen
             * @default 0
             */
            words_seen?: number;
        };
        /**
         * WeeklyDossierThread
         * @description One highlighted strength, fragile item, or suggested next action.
         */
        WeeklyDossierThread: {
            /**
             * Count
             * @default 0
             */
            count?: number;
            /** Subtitle */
            subtitle?: string | null;
            /** Title */
            title: string;
            /**
             * Tone
             * @default neutral
             */
            tone?: string;
        };
        /**
         * WordExposureRequest
         * @description Payload for tracking hint/translation interactions.
         */
        WordExposureRequest: {
            /**
             * Exposure Type
             * @enum {string}
             */
            exposure_type: "hint" | "translation" | "flag";
            /** Word Id */
            word_id: number;
        };
        /** WorldBibleRead */
        WorldBibleRead: {
            /** Cast */
            cast?: {
                [key: string]: unknown;
            }[];
            /** Logline */
            logline?: string | null;
            /** Protagonist */
            protagonist?: {
                [key: string]: unknown;
            };
            /** Register Map */
            register_map?: {
                [key: string]: unknown;
            };
            /** Season Arcs */
            season_arcs?: {
                [key: string]: unknown;
            }[];
            /** Setting */
            setting?: {
                [key: string]: unknown;
            };
        } & {
            [key: string]: unknown;
        };
        /** WriteRequest */
        WriteRequest: {
            /**
             * Text
             * @default
             */
            text?: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    list_achievements_api_v1_achievements_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__schemas__achievement__AchievementRead"][];
                };
            };
        };
    };
    check_achievements_api_v1_achievements_check_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AchievementUnlockResponse"];
                };
            };
        };
    };
    get_my_achievements_api_v1_achievements_my_get: {
        parameters: {
            query?: {
                /** @description Include locked achievements */
                include_locked?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AchievementProgressResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    record_client_error_api_v1_analytics_client_error_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClientErrorRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    record_anonymous_client_error_api_v1_analytics_client_error_anonymous_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnonymousClientErrorRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_error_patterns_api_v1_analytics_errors_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorPatternsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_error_list_api_v1_analytics_errors_list_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_error_summary_api_v1_analytics_errors_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorSummary"];
                };
            };
        };
    };
    read_pilot_daily_api_v1_analytics_pilot_daily_get: {
        parameters: {
            query?: {
                day?: string | null;
                user_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_pilot_forge_api_v1_analytics_pilot_forge_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    read_pilot_operations_api_v1_analytics_pilot_ops_get: {
        parameters: {
            query?: {
                weeks?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_statistics_api_v1_analytics_statistics_get: {
        parameters: {
            query?: {
                days?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsStatisticsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_streak_api_v1_analytics_streak_get: {
        parameters: {
            query?: {
                window_days?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StreakInfo"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_analytics_summary_api_v1_analytics_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalyticsSummary"];
                };
            };
        };
    };
    read_vocabulary_heatmap_api_v1_analytics_vocabulary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VocabularyHeatmapResponse"];
                };
            };
        };
    };
    get_due_cards_api_v1_anki_due_cards_get: {
        parameters: {
            query?: {
                limit?: number;
                scheduler_type?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_anki_cards_api_v1_anki_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_import_anki_cards_api_v1_anki_import_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnkiImportResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_anki_cards_text_api_v1_anki_import_text_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnkiImportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnkiImportResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    rehydrate_from_last_import_api_v1_anki_rehydrate_post: {
        parameters: {
            query?: {
                deck_name?: string | null;
                preserve_scheduling?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnkiImportResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_anki_review_api_v1_anki_review_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnkiReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnkiReviewResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_anki_statistics_api_v1_anki_statistics_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnkiStatisticsResponse"];
                };
            };
        };
    };
    get_almanac_api_v1_atelier_almanac_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierAlmanacResponse"];
                };
            };
        };
    };
    get_attempt_api_v1_atelier_attempts__attempt_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                attempt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierAttemptResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    request_attempt_ai_review_api_v1_atelier_attempts__attempt_id__ai_review_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                attempt_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierAttemptResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    repair_attempt_api_v1_atelier_attempts__attempt_id__repair_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                attempt_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AtelierAttemptRepairRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierAttemptResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_erratum_review_attempt_api_v1_atelier_errata__error_id__attempt_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                error_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AtelierErrataAttemptRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierErrataAttemptResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    review_erratum_api_v1_atelier_errata__error_id__review_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                error_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AtelierErrataReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierErrataReviewResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_erratum_review_task_api_v1_atelier_errata__error_id__task_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                error_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierErrataTaskResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    report_exercise_api_v1_atelier_exercises_report_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AtelierExerciseReportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierExerciseReportResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_eclair_api_v1_atelier_forge_eclair_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EclairStartRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    finish_eclair_api_v1_atelier_forge_eclair__eclair_id__finish_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                eclair_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EclairFinishRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_grammar_map_api_v1_atelier_forge_map_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    record_grammar_map_opened_api_v1_atelier_forge_map_opened_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    get_forge_session_api_v1_atelier_forge_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_forge_state_api_v1_atelier_forge_state_get: {
        parameters: {
            query?: {
                concept_id?: number[] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierForgeStateResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_test_out_api_v1_atelier_forge_test_out_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AtelierForgeTestOutRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierSessionStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_session_api_v1_atelier_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["AtelierSessionStartRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierSessionStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_session_api_v1_atelier_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierSessionStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_attempt_api_v1_atelier_sessions__session_id__attempts_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AtelierAttemptRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierAttemptResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    complete_session_api_v1_atelier_sessions__session_id__complete_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierCompleteResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    exit_session_api_v1_atelier_sessions__session_id__exit_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_active_session_api_v1_atelier_sessions_active_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierActiveSessionResponse"];
                };
            };
        };
    };
    get_today_api_v1_atelier_today_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierTodayResponse"];
                };
            };
        };
    };
    translate_for_learner_api_v1_atelier_translate_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TranslateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    compose_workshop_plate_api_v1_atelier_workshop_compose_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AtelierWorkshopComposeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AtelierWorkshopComposeResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    end_audio_session_api_v1_audio_session_end_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AudioSessionEndRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AudioSessionEndResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    respond_to_audio_api_v1_audio_session_respond_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AudioSessionMessageRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AudioSessionMessageResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_audio_scenarios_api_v1_audio_session_scenarios_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
        };
    };
    start_audio_session_api_v1_audio_session_start_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["AudioSessionStartRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AudioSessionStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    text_to_speech_api_v1_audio_speak_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TTSRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    transcribe_audio_api_v1_audio_transcribe_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_transcribe_audio_api_v1_audio_transcribe_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserLogin"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Token"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["LogoutRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    confirm_password_reset_api_v1_auth_password_reset_confirm_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordResetConfirm"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    request_password_reset_api_v1_auth_password_reset_request_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PasswordResetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PasswordResetRequestResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_tokens_api_v1_auth_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RefreshTokenRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Token"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    register_user_api_v1_auth_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_carnet_api_v1_can_dos_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CarnetResponse"];
                };
            };
        };
    };
    create_journey_api_v1_daily_journeys_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JourneyCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JourneySnapshot"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_journey_api_v1_daily_journeys__journey_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                journey_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JourneySnapshot"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    advance_api_v1_daily_journeys__journey_id__advance_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                journey_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JourneyAdvanceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JourneySnapshot"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    finish_api_v1_daily_journeys__journey_id__finish_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                journey_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JourneyFinishRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JourneySnapshot"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    pause_api_v1_daily_journeys__journey_id__pause_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                journey_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JourneyRevisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JourneySnapshot"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resume_api_v1_daily_journeys__journey_id__resume_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                journey_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JourneyRevisionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JourneySnapshot"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_api_v1_daily_journeys__journey_id__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                journey_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JourneyRetryRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JourneySnapshot"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_attempt_api_v1_daily_journeys__journey_id__steps__step_id__attempts_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                journey_id: string;
                step_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JourneyAttemptRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AttemptResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    use_help_api_v1_daily_journeys__journey_id__steps__step_id__help_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                journey_id: string;
                step_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["JourneyHelpRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HelpResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    speak_step_line_api_v1_daily_journeys__journey_id__steps__step_id__line_audio_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                journey_id: string;
                step_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LineAudioRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineAudioResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_capability_progress_api_v1_daily_journeys_capabilities_progress_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CapabilityProgress"];
                };
            };
        };
    };
    line_audio_clip_api_v1_daily_journeys_line_audio__clip_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                clip_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_today_api_v1_daily_journeys_today_get: {
        parameters: {
            query?: {
                /** @description Client IANA timezone, used only when no journey exists yet. */
                timezone?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TodayEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    open_claim_api_v1_dossier_claims_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClaimRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DossierEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_api_v1_dossier_claims_verify_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClaimAnswers"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DossierEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_dossier_api_v1_dossier_state_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DossierEnvelope"];
                };
            };
        };
    };
    list_feedback_reports_api_v1_feedback_reports_get: {
        parameters: {
            query?: {
                category?: ("bug" | "broken_link" | "content" | "layout" | "slow_loading" | "suggestion" | "other") | null;
                limit?: number;
                offset?: number;
                route?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackReportRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_feedback_report_api_v1_feedback_reports_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FeedbackReportCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FeedbackReportRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_achievements_api_v1_grammar_achievements_get: {
        parameters: {
            query?: {
                category?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["app__api__v1__endpoints__grammar__AchievementRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_concepts_by_level_api_v1_grammar_by_level_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: {
                            [key: string]: unknown;
                        }[];
                    };
                };
            };
        };
    };
    list_concepts_api_v1_grammar_concepts_get: {
        parameters: {
            query?: {
                category?: string | null;
                level?: string | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrammarConceptRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_concept_api_v1_grammar_concepts_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GrammarConceptCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrammarConceptRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    bulk_import_concepts_api_v1_grammar_concepts_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BulkImportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: number;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_due_concepts_api_v1_grammar_due_get: {
        parameters: {
            query?: {
                level?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DueConceptRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_concepts_for_chapter_api_v1_grammar_for_chapter__chapter_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                chapter_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChapterConceptRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_concepts_for_errors_api_v1_grammar_for_errors_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_concept_graph_api_v1_grammar_graph_get: {
        parameters: {
            query?: {
                level?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConceptGraphResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mark_practiced_in_context_api_v1_grammar_mark_practiced_in_context_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": number[];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_grammar_notebook_api_v1_grammar_notebook_get: {
        parameters: {
            query?: {
                category?: string | null;
                level?: string | null;
                limit?: number;
                locale?: string;
                offset?: number;
                q?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrammarNotebookItemRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_grammar_notebook_concept_api_v1_grammar_notebook__concept_id__get: {
        parameters: {
            query?: {
                locale?: string;
            };
            header?: never;
            path: {
                concept_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrammarNotebookDetailRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_grammar_notebook_notes_api_v1_grammar_notebook__concept_id__notes_patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                concept_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GrammarNotebookNotesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrammarNotebookDetailRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_user_progress_api_v1_grammar_progress_get: {
        parameters: {
            query?: {
                level?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrammarProgressRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    record_review_api_v1_grammar_review_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GrammarReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrammarProgressRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    record_review_with_achievements_api_v1_grammar_review_with_achievements_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GrammarReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_streak_info_api_v1_grammar_streak_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StreakInfoRead"];
                };
            };
        };
    };
    get_summary_api_v1_grammar_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GrammarSummaryResponse"];
                };
            };
        };
    };
    create_graphic_novel_scene_api_v1_graphic_novel_scenes_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GraphicNovelCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GraphicNovelSceneResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_graphic_novel_scene_api_v1_graphic_novel_scenes__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GraphicNovelCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GraphicNovelSceneResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_graphic_novel_scene_api_v1_graphic_novel_scenes__scene_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GraphicNovelSceneResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_graphic_novel_attempt_api_v1_graphic_novel_scenes__scene_id__attempts_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GraphicNovelAttemptRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GraphicNovelAttemptResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    complete_graphic_novel_scene_api_v1_graphic_novel_scenes__scene_id__complete_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GraphicNovelCompleteResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_graphic_novel_today_api_v1_graphic_novel_today_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GraphicNovelTodayResponse"];
                };
            };
        };
    };
    list_artefacts_api_v1_intake_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IntakeEnvelope"];
                };
            };
        };
    };
    list_artefacts_api_v1_intake__get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IntakeEnvelope"];
                };
            };
        };
    };
    get_artefact_api_v1_intake__artefact_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                artefact_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IntakeEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_artefact_api_v1_intake__artefact_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                artefact_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_photo_api_v1_intake_photo_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_submit_photo_api_v1_intake_photo_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IntakeEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_text_api_v1_intake_text_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["IntakeTextRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IntakeEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    answer_followup_api_v1_journal__entry_id__followup_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                entry_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FollowupRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JournalEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    skip_entry_api_v1_journal__entry_id__skip_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                entry_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JournalEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    write_entry_api_v1_journal__entry_id__write_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                entry_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WriteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JournalEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_entries_api_v1_journal_entries_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JournalEntryView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_state_api_v1_journal_state_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JournalEnvelope"];
                };
            };
        };
    };
    read_consent_api_v1_legal_consent_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConsentStatus"];
                };
            };
        };
    };
    record_consent_api_v1_legal_consent_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConsentRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConsentStatus"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_mission_api_v1_missions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MissionCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MissionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_mission_api_v1_missions__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MissionCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MissionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_mission_api_v1_missions__mission_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                mission_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MissionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    complete_mission_api_v1_missions__mission_id__complete_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                mission_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MissionCompleteResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_mission_api_v1_missions__mission_id__submit_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                mission_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MissionSubmitRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MissionAttemptResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_mission_turn_api_v1_missions__mission_id__turns_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                mission_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MissionTurnRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MissionTurnResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    transcribe_mission_audio_api_v1_missions_audio_transcribe_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_transcribe_mission_audio_api_v1_missions_audio_transcribe_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_missions_today_api_v1_missions_today_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MissionTodayResponse"];
                };
            };
        };
    };
    subscribe_native_api_v1_notifications_native_subscribe_post: {
        parameters: {
            query?: never;
            header?: {
                "user-agent"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    subscribe_api_v1_notifications_subscribe_post: {
        parameters: {
            query?: never;
            header?: {
                "user-agent"?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    record_notification_tap_api_v1_notifications_tap_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": {
                    [key: string]: unknown;
                };
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    test_notification_api_v1_notifications_test_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    get_vapid_public_key_api_v1_notifications_vapid_public_key_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    get_npc_api_v1_npcs__npc_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                npc_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NPCDetailRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_npc_memories_api_v1_npcs__npc_id__memories_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path: {
                npc_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NPCMemoryRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_npc_relationship_api_v1_npcs__npc_id__relationship_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                npc_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NPCRelationshipRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    finish_api_v1_placement__session_id__finish_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlacementEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    respond_api_v1_placement__session_id__respond_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RespondRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlacementEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_offer_api_v1_placement_offer_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlacementOffer"];
                };
            };
        };
    };
    skip_api_v1_placement_skip_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlacementEnvelope"];
                };
            };
        };
    };
    start_api_v1_placement_start_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["StartRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlacementEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_state_api_v1_placement_state_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlacementEnvelope"];
                };
            };
        };
    };
    get_progress_detail_api_v1_progress__word_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                word_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProgressDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_anki_progress_api_v1_progress_anki_get: {
        parameters: {
            query?: {
                /** @description Optional card direction filter (fr_to_de or de_to_fr) */
                direction?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnkiWordProgressRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_anki_summary_api_v1_progress_anki_summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnkiProgressSummary"];
                };
            };
        };
    };
    sync_anki_progress_endpoint_api_v1_progress_anki_sync_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnkiConnectSyncRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: number;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    bump_word_difficulty_api_v1_progress_bump__word_id__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                word_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_cefr_progress_api_v1_progress_cefr_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CEFRProgressResponse"];
                };
            };
        };
    };
    get_level_checkpoint_api_v1_progress_cefr_checkpoint_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    record_level_checkpoint_api_v1_progress_cefr_checkpoint_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LevelCheckpointResultRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CEFRProgressResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    recompute_cefr_progress_api_v1_progress_cefr_recompute_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CEFRProgressResponse"];
                };
            };
        };
    };
    get_weekly_insights_api_v1_progress_insights_weekly_get: {
        parameters: {
            query?: {
                /** @description Force regenerate insights (bypass cache) */
                force_refresh?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_review_queue_api_v1_progress_queue_get: {
        parameters: {
            query?: {
                /** @description Optional card direction filter (fr_to_de or de_to_fr) */
                direction?: string | null;
                /** @description Maximum number of queue entries to return */
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["QueueWord"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_review_api_v1_progress_review_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_unified_review_queue_api_v1_progress_unified_queue_get: {
        parameters: {
            query?: {
                /** @description Queue strategy: random, blocks, or priority. Random is deterministic round-robin. */
                interleaving_mode?: string;
                /** @description Maximum number of unified queue entries */
                limit?: number;
                /** @description Optional budget used to truncate the queue by estimated time */
                time_budget_minutes?: number | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UnifiedQueueResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_vocabulary_mastery_map_api_v1_progress_vocabulary_map_get: {
        parameters: {
            query?: {
                /** @description Optional card direction filter */
                direction?: string | null;
                /** @description Maximum French 5000 cards to map */
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VocabularyMasteryMapResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_vocabulary_recommendations_api_v1_progress_vocabulary_recommendations_get: {
        parameters: {
            query?: {
                /** @description Optional imported deck name filter */
                deck_name?: string | null;
                /** @description Optional card direction filter (fr_to_de or de_to_fr) */
                direction?: string | null;
                /** @description Maximum due cards to include */
                due_limit?: number;
                /** @description Maximum fragile cards to include */
                fragile_limit?: number;
                /** @description Treat near-future reviews as due */
                include_upcoming_days?: number;
                /** @description Maximum number of recommendations */
                limit?: number;
                /** @description Maximum new cards to include */
                new_limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VocabularyRecommendationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_weekly_dossier_api_v1_progress_weekly_dossier_get: {
        parameters: {
            query?: {
                period_days?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WeeklyDossierResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    declare_api_v1_rehearsals_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DeclareRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RehearsalEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    abandon_api_v1_rehearsals__rehearsal_id__abandon_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rehearsal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RehearsalEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    debrief_api_v1_rehearsals__rehearsal_id__debrief_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rehearsal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DebriefRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RehearsalEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reveal_phrases_api_v1_rehearsals__rehearsal_id__phrases_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rehearsal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RehearsalEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    prepare_api_v1_rehearsals__rehearsal_id__prepare_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rehearsal_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RehearsalEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    respond_api_v1_rehearsals__rehearsal_id__turns_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rehearsal_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["TurnRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RehearsalEnvelope"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_state_api_v1_rehearsals_state_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RehearsalEnvelope"];
                };
            };
        };
    };
    refresh_intake_api_v1_revue_admin_refresh_post: {
        parameters: {
            query?: {
                enqueue?: boolean;
                period?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_carte_api_v1_revue_carte_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CarteView"];
                };
            };
        };
    };
    read_carte_review_api_v1_revue_carte_review__place_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                place_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CarteReview"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    grade_carte_review_api_v1_revue_carte_review__place_id__grade_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                place_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CarteReviewGradeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CarteReviewGrade"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_marks_api_v1_revue_correcteur__correction_id__marks_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                correction_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CrMarksRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CrResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    new_draft_api_v1_revue_correcteur__dossier_id__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dossier_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CrDraftView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_week_api_v1_revue_correcteur_week_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CrWeek"];
                };
            };
        };
    };
    match_request_api_v1_revue_match_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RvMatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RvMatchResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_bulletin_api_v1_revue_radio__dossier_id__get: {
        parameters: {
            query?: {
                band?: string | null;
            };
            header?: never;
            path: {
                dossier_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RadioBulletinView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    grade_dictee_api_v1_revue_radio__dossier_id__dictee_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dossier_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RadioDicteeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RadioDicteeResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mark_heard_api_v1_revue_radio__dossier_id__heard_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                dossier_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RadioHeardRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RadioWeekView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_radio_week_api_v1_revue_radio_week_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RadioWeekView"];
                };
            };
        };
    };
    read_pair_api_v1_revue_relecture__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RelecturePair"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_answer_api_v1_revue_relecture__session_id__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RelectureAnswerRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RelecturePair"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_offer_api_v1_revue_relecture_offer_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RelectureOfferView"];
                };
            };
        };
    };
    read_releve_api_v1_revue_releve_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReleveView"];
                };
            };
        };
    };
    start_session_api_v1_revue_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RvStartRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RvSessionView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_session_api_v1_revue_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RvSessionView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    close_session_api_v1_revue_sessions__session_id__close_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RvCloseResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_make_options_api_v1_revue_sessions__session_id__make_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RvMakeOffer"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_make_api_v1_revue_sessions__session_id__make_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RvHeadlinePick"] | components["schemas"]["RvQuestionPropose"] | components["schemas"]["RvQuestionSend"] | components["schemas"]["RvHeadlineWrite"] | components["schemas"]["RvShortReport"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RvHeadlinePickResult"] | components["schemas"]["RvQuestionProposeResult"] | components["schemas"]["RvQuestionSendResult"] | components["schemas"]["RvHeadlineWriteResult"] | components["schemas"]["RvShortReportResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_turn_api_v1_revue_sessions__session_id__turns_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RvTurnRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RvTurnResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_vignettes_api_v1_revue_vignettes_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VignettesResponse"];
                };
            };
        };
    };
    read_week_api_v1_revue_week_get: {
        parameters: {
            query?: {
                week?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RvOffer"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mark_serial_onboarding_seen_api_v1_serial_onboarding_seen_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_serial_season_api_v1_serial_season_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    create_serial_thread_api_v1_serial_threads_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SerialThreadCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SerialThreadRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_serial_thread_api_v1_serial_threads__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SerialThreadCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SerialThreadRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    advance_serial_thread_api_v1_serial_threads__thread_id__advance_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                thread_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SerialAdvanceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_current_serial_avatar_api_v1_serial_threads_current_avatar_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SerialAvatarRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_current_serial_cast_api_v1_serial_threads_current_cast_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_current_serial_episodes_api_v1_serial_threads_current_episodes_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_serial_today_api_v1_serial_today_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_sessions_api_v1_sessions_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionOverview"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_session_api_v1_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_session_api_v1_sessions__session_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionOverview"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_session_status_api_v1_sessions__session_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionStatusUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionOverview"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    mark_word_difficult_api_v1_sessions__session_id__difficult_words_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WordExposureRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    log_word_exposure_api_v1_sessions__session_id__exposures_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WordExposureRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_session_messages_api_v1_sessions__session_id__messages_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionMessageListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_session_message_api_v1_sessions__session_id__messages_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionMessageRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionTurnResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    skip_session_moment_api_v1_sessions__session_id__moments__moment_id__skip_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                moment_id: string;
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionMomentSubmitResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_session_moment_api_v1_sessions__session_id__moments__moment_id__submit_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                moment_id: string;
                session_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SessionMomentSubmitRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionMomentSubmitResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_session_summary_api_v1_sessions__session_id__summary_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                session_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionSummaryResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_live_stories_api_v1_sessions_live_stories_get: {
        parameters: {
            query?: {
                limit?: number;
                /** @description Optional comma-separated topics to override profile interests */
                topics?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LiveStoryListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_quick_session_api_v1_sessions_quick_start_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["QuickStartRequest"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_stories_api_v1_stories_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryWithProgressRead"][];
                };
            };
        };
    };
    get_story_api_v1_stories__story_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryWithProgressRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_chapter_cover_api_v1_stories__story_id__chapter__chapter_id__cover_get: {
        parameters: {
            query?: {
                style?: string | null;
            };
            header?: never;
            path: {
                chapter_id: string;
                story_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_story_chapters_api_v1_stories__story_id__chapters_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChapterWithStatusRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    check_chapter_goals_api_v1_stories__story_id__chapters__chapter_id__check_goals_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                chapter_id: string;
                story_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GoalCheckRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GoalCheckResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    complete_chapter_api_v1_stories__story_id__chapters__chapter_id__complete_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                chapter_id: string;
                story_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChapterCompletionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChapterCompletionResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_story_discussion_api_v1_stories__story_id__discuss_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    process_story_input_api_v1_stories__story_id__input_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StoryInputRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryInputResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    make_narrative_choice_api_v1_stories__story_id__make_choice_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["NarrativeChoiceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["NarrativeChoiceResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_story_progress_api_v1_stories__story_id__progress_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryProgressRead"] | null;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_current_scene_api_v1_stories__story_id__scene_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SceneRead"] | null;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_scene_visualization_api_v1_stories__story_id__scene__scene_id__visualization_get: {
        parameters: {
            query?: {
                include_avatar?: boolean;
                style?: string | null;
            };
            header?: never;
            path: {
                scene_id: string;
                story_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_story_api_v1_stories__story_id__start_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                story_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryStartResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_content_api_v1_stories_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ContentImportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_library_books_api_v1_stories_library_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
        };
    };
    get_library_book_api_v1_stories_library__book_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                book_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_library_episode_api_v1_stories_library__book_id__episodes__order_index__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                book_id: string;
                order_index: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    complete_library_episode_api_v1_stories_library__book_id__episodes__order_index__complete_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                book_id: string;
                order_index: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_library_book_api_v1_stories_library_upload_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_library_book_api_v1_stories_library_upload_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_book_api_v1_stories_upload_book_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_book_api_v1_stories_upload_book_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_upload_status_api_v1_stories_upload_status__task_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                task_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    archive_api_v1_story_engine_archive_get: {
        parameters: {
            query?: {
                season?: number | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryArchive"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    episodes_api_v1_story_engine_episodes_get: {
        parameters: {
            query?: {
                before?: string | null;
                journey_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryEpisodePageRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    episode_api_v1_story_engine_episodes__scene_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryEpisodeRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    audio_manifest_api_v1_story_engine_episodes__scene_id__audio_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EpisodeAudioManifestRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    synthesize_audio_api_v1_story_engine_episodes__scene_id__audio_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EpisodeAudioManifestRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    audio_clip_api_v1_story_engine_episodes__scene_id__audio__clip_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                clip_id: string;
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    prediction_api_v1_story_engine_episodes__scene_id__audio_prediction_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PredictionCheck"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    position_api_v1_story_engine_episodes__scene_id__position_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scene_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Position"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StoryPositionRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_users_api_v1_users__get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_user_by_id_api_v1_users__user_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_current_user_api_v1_users_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
        };
    };
    delete_current_user_api_v1_users_me_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    update_current_user_api_v1_users_me_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    change_current_user_email_api_v1_users_me_email_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserEmailChange"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_user_data_api_v1_users_me_export_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    change_current_user_password_api_v1_users_me_password_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserPasswordChange"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    read_current_user_settings_api_v1_users_me_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserSettingsRead"];
                };
            };
        };
    };
    update_current_user_settings_api_v1_users_me_settings_patch: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UserSettingsUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserSettingsRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sign_out_all_devices_api_v1_users_me_sign_out_all_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    list_vocabulary_api_v1_vocabulary__get: {
        parameters: {
            query?: {
                /** @description Language code to filter by */
                language?: string | null;
                limit?: number;
                offset?: number;
                search?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VocabularyListResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_vocabulary_word_api_v1_vocabulary__word_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                word_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VocabularyWordRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_vocabulary_word_biography_api_v1_vocabulary__word_id__biography_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                word_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VocabularyBiographyResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_band_checks_api_v1_vocabulary_band_check_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BandCheckSubBand"][];
                };
            };
        };
    };
    start_band_check_api_v1_vocabulary_band_check__sub_band__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sub_band: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BandCheckStart"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_band_check_api_v1_vocabulary_band_check__sub_band__post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sub_band: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BandCheckSubmit"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BandCheckResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    band_check_ladder_api_v1_vocabulary_band_check_ladder_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BandCheckLadder"];
                };
            };
        };
    };
    get_conjugation_review_queue_api_v1_vocabulary_conjugation_review_get: {
        parameters: {
            query?: {
                cefr_band?: string | null;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    submit_conjugation_review_api_v1_vocabulary_conjugation_review_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConjugationReviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConjugationReviewResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_vocabulary_coverage_api_v1_vocabulary_coverage_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_vocabulary_due_context_api_v1_vocabulary_due_context_get: {
        parameters: {
            query?: {
                /** @description Optional card direction filter; defaults to the learner's stored direction */
                direction?: string | null;
                due_limit?: number;
                feuilleton_scene_id?: string | null;
                fragile_limit?: number;
                limit?: number;
                linked_limit?: number;
                linked_word_ids?: string[] | null;
                mission_id?: string | null;
                new_limit?: number;
                topic_limit?: number;
                topic_tags?: string[] | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VocabularyDueContextResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    keep_vocabulary_word_api_v1_vocabulary_keep_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["KeepWordRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    lookup_vocabulary_word_api_v1_vocabulary_lookup_get: {
        parameters: {
            query: {
                language?: string | null;
                /** @description Surface form to look up */
                word: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VocabularyWordRead"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_words_of_the_day_api_v1_vocabulary_words_of_the_day_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DailyWordSlateResponse"];
                };
            };
        };
    };
}
