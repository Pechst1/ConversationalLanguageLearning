/* S4 stage 2 — an unknown URL: the one error screen, in the learner's
   language, with one way back to La Une (no Next default page in English). */
import Head from 'next/head';

import { ErrorScreen } from '@/components/layout/ErrorScreen';

export default function NotFoundPage() {
  return (
    <>
      <Head><title>L’Atelier</title></Head>
      <ErrorScreen kind="not_found" />
    </>
  );
}
