import React from 'react';
import { useRouter } from 'next/router';

import { useAppSession } from '@/lib/app-auth';
import { resolveLearningEntryDestination } from '@/lib/learning-entry';

/**
 * /learn route - resolves the next learning step:
 * continue an active session, otherwise start a quick session.
 */
export default function LearnIndex() {
    const router = useRouter();
    const { data: session, status } = useAppSession();

    React.useEffect(() => {
        if (status !== 'authenticated') return;

        let cancelled = false;
        resolveLearningEntryDestination(session).then((destination) => {
            if (!cancelled) {
                router.replace(destination);
            }
        });

        return () => {
            cancelled = true;
        };
    }, [router, session, status]);

    return null;
}
