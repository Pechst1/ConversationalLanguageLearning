import { GetServerSideProps } from 'next';

/**
 * /learn route - redirects to /learn/new (session creation page)
 */
export default function LearnIndex() {
    return null;
}

export const getServerSideProps: GetServerSideProps = async () => {
    return {
        redirect: {
            destination: '/learn/new',
            permanent: false,
        },
    };
};
