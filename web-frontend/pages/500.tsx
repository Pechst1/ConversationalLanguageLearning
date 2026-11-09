/* S4 stage 2 — a server error while a page was rendered: the one error screen,
   in the learner's language, with one way back to La Une. */
import Head from 'next/head';

import { ErrorScreen } from '@/components/layout/ErrorScreen';

export default function ServerErrorPage() {
  return (
    <>
      <Head><title>L’Atelier</title></Head>
      <ErrorScreen kind="down" />
    </>
  );
}
