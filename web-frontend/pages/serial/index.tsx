/* WP-96 — «La saison» moved into the Feuilleton's one surface.
 *
 * `/serial` used to be a second season list beside the Feuilleton tab's own.
 * The tab now opens «Archives du journal» (`/graphic-novel`), so this route
 * only forwards there — replacing the history entry, so Back never lands on
 * an empty redirect. */

import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function SerialSeasonRedirect() {
  const router = useRouter();
  useEffect(() => {
    void router.replace('/graphic-novel');
  }, [router]);
  return null;
}
