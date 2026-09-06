self.addEventListener('push', function (event) {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: '/favicon.ico',
            vibrate: [100, 50, 100],
            data: {
                dateOfArrival: Date.now(),
                primaryKey: 1,
                route: data.data && typeof data.data.route === 'string'
                    ? data.data.route
                    : '/'
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
