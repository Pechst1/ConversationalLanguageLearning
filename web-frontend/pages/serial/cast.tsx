/* WP-96 — «Les personnages» moved into the Feuilleton's one surface as «Le
 * trombinoscope» (`/graphic-novel?view=cast`). This route only forwards there,
 * replacing the history entry. */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function SerialCastRedirect() {
  const router = useRouter();
  useEffect(() => {
    void router.replace('/graphic-novel?view=cast');
  }, [router]);
  return null;
}
