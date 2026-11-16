/**
 * The marker on every sentence the journey says about the connection (#794).
 *
 * «That did not reach the server», «Sending to the server…», «Something you did has not
 * reached the server yet» and the offline notices are facts about the connection, not
 * about the learner's work. Each element that says one carries `data-connection-banner`
 * with the copy key it says, so anything that needs to know whether such a banner is on
 * screen (the browser walk's `no-server-banner-while-typing`, e2e/lib/driver.mjs) reads
 * the element, never the screen's prose. The prose holds the scene, and a scene says
 * «serveur» (a waiter) or «gesendet» as freely as any other word.
 */

export const CONNECTION_BANNER_ATTR = 'data-connection-banner';

/** What a banner says: the journey-copy key of its sentence, or `stale` for an old saved copy. */
export type ConnectionBannerKind =
  | 'transport_error'
  | 'transport_error_plain'
  | 'syncing'
  | 'pending_sync'
  | 'offline_cached'
  | 'offline_empty'
  | 'stale';

/** The props that mark an element as a connection banner: spread them onto it. */
export function connectionBanner(kind: ConnectionBannerKind): { [CONNECTION_BANNER_ATTR]: ConnectionBannerKind } {
  return { [CONNECTION_BANNER_ATTR]: kind };
}
