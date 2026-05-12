import { GetServerSideProps } from 'next';
import { getSession } from 'next-auth/react';
import { resolveLearningEntryDestination } from '@/lib/learning-entry';

/**
 * /learn route - resolves the next learning step:
 * continue an active session, otherwise start a quick session.
 */
export default function LearnIndex() {
    return null;
}

export const getServerSideProps: GetServerSideProps = async (context) => {
    const session = await getSession(context);

    if (!session) {
        return {
            redirect: {
                destination: '/auth/signin',
                permanent: false,
            },
        };
    }

    const destination = await resolveLearningEntryDestination(session);

    return {
        redirect: {
            destination,
            permanent: false,
        },
    };
};
