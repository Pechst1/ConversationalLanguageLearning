// WP-99: the same table as `lib/push-deep-link.ts` (pinned together by
// `push-deep-link.test.js`): a Dépêche opens today's scene, a letter or a
// deadline opens that letter, anything else keeps a safe in-app route.
function safeRoute(route) {
    if (typeof route !== 'string') return null;
    const value = route.trim();
    if (value.charAt(0) !== '/' || value.charAt(1) === '/' || value.indexOf('\\') !== -1) return null;
    if (/^\/+[a-z][a-z0-9+.-]*:/i.test(value)) return null;
    return value;
}

function deepLink(payload) {
    const kind = typeof payload.kind === 'string' ? payload.kind.trim().toLowerCase() : '';
    const route = safeRoute(payload.route);
    if (['morning_teaser', 'morning_depeche', 'depeche', 'morning_edition', 'streak_reminder'].indexOf(kind) !== -1) {
        return route && route.indexOf('/atelier') === 0 ? route : '/atelier?start=today';
    }
    if (['letter_arrived', 'letter', 'facteur', 'courrier', 'le_facteur',
        'letter_deadline', 'deadline', 'dernier_jour', 'mission_deadline'].indexOf(kind) !== -1) {
        if (route && /[?&]mission=/.test(route)) return route;
        const id = payload.mission_id || payload.letter_id || payload.mission;
        if (id !== undefined && id !== null && String(id).trim()) {
            return '/missions?mission=' + encodeURIComponent(String(id).trim());
        }
        return route || '/missions';
    }
    return route || '/';
}

self.addEventListener('push', function (event) {
    if (event.data) {
        const data = event.data.json();
        // WP-80 / WP-99: the speaking character's portrait, when the server
        // names one (`image_url`, or the older `image`), and where a tap lands.
        const payload = data.data || {};
        const image = [payload.image_url, payload.image].find(function (value) {
            return typeof value === 'string'
                && ((value.charAt(0) === '/' && value.charAt(1) !== '/') || value.indexOf('https://') === 0);
        }) || null;
        const options = {
            body: data.body,
            icon: image || '/favicon.ico',
            vibrate: [100, 50, 100],
            data: {
                dateOfArrival: Date.now(),
                primaryKey: 1,
                route: deepLink(payload)
            }
        };
        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    const route = event.notification.data && event.notification.data.route
        ? event.notification.data.route
        : '/';
    event.waitUntil(
        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(function (clientList) {
            for (const client of clientList) {
                if ('navigate' in client) {
                    return client.navigate(route).then(function (navigatedClient) {
                        return navigatedClient && navigatedClient.focus();
                    });
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(route);
            }
        })
    );
});
