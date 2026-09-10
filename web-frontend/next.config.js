const isNativeStaticExport = process.env.NATIVE_STATIC_EXPORT === 'true';

// Never defaulted. An unset API_URL means "not configured", which the app
// reports as a configuration error at call time (lib/api-host.ts), rather than
// guessing a port that may belong to a different application on this machine.
const apiUrl = (process.env.API_URL || '').trim().replace(/\/+$/, '');
if (!apiUrl && !isNativeStaticExport) {
  // A build does not need the backend; a running server does. Warn, do not throw,
  // so CI (which builds without API_URL) stays green.
  console.warn(
    '[next.config] API_URL is not set. Backend proxies are disabled and any ' +
      'server-side call that needs the API will fail with a clear error.',
  );
}
const launchFlags = require('./launch-flags.json');
const isStoryFeatureVisible = Boolean(launchFlags.storyFeatureVisible);

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: isNativeStaticExport ? 'export' : undefined,
  trailingSlash: isNativeStaticExport,
  images: {
    domains: ['localhost', 'api.example.com'],
    unoptimized: isNativeStaticExport,
  },
  // API_URL is passed through only when it is actually set. It used to be
  // defaulted to http://localhost:8000 here, which meant the fail-fast in
  // lib/api-host.ts could never fire: the app always saw a value, and on a
  // machine where another project owns port 8000 that value was wrong.
  env: {
    ...(apiUrl ? { API_URL: apiUrl } : {}),
  },
  webpack: (config) => {
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
    };
    return config;
  },
};

if (!isNativeStaticExport) {
  nextConfig.rewrites = async () => [
    // The backend proxies exist only when a host was configured. Pointing them
    // at a guessed port would silently forward requests — including
    // credentials — to an unrelated local service.
    ...(apiUrl
      ? [
          {
            source: '/api/backend/:path*',
            destination: `${apiUrl}/api/v1/:path*`,
          },
          {
            // Locally persisted Feuilleton panel images live on the API host
            // (GRAPHIC_NOVEL_IMAGE_STORAGE=local mounts /media/graphic-novel there).
            source: '/media/:path*',
            destination: `${apiUrl}/media/:path*`,
          },
        ]
      : []),
    {
      source: '/anki-connect',
      destination: 'http://127.0.0.1:8765',
    },
  ];

  nextConfig.redirects = async () => [
    { source: '/dashboard', destination: '/atelier', permanent: false },
    { source: '/sessions', destination: '/atelier', permanent: false },
    { source: '/practice', destination: '/atelier', permanent: false },
    { source: '/daily-practice', destination: '/atelier', permanent: false },
    // WP-20 deleted these pages outright. The redirects stay so an old bookmark,
    // a push payload or a native deep link lands somewhere real instead of a 404.
    { source: '/progress', destination: '/notebook', permanent: false },
    { source: '/achievements', destination: '/notebook', permanent: false },
    { source: '/almanac', destination: '/graphic-novel', permanent: false },
    // The /learn cluster (conversation setup and its session viewer) was
    // disposed of on 2026-09-10; the Studio and the daily journey own
    // conversation now. `:path*` catches the deep session links that lived in
    // word traces and old bookmarks.
    { source: '/learn', destination: '/atelier', permanent: false },
    { source: '/learn/:path*', destination: '/atelier', permanent: false },
    { source: '/index', destination: '/atelier', permanent: false },
    ...(isStoryFeatureVisible
      ? [
          { source: '/stories', destination: '/bibliotheque', permanent: false },
          { source: '/stories/:path*', destination: '/bibliotheque/:path*', permanent: false },
          { source: '/story/:id', destination: '/bibliotheque/:id', permanent: false },
        ]
      : [
          { source: '/stories', destination: '/atelier', permanent: false },
          { source: '/stories/:path*', destination: '/atelier', permanent: false },
          { source: '/story/:id', destination: '/atelier', permanent: false },
          { source: '/bibliotheque', destination: '/atelier', permanent: false },
          { source: '/bibliotheque/:path*', destination: '/atelier', permanent: false },
        ]),
    { source: '/atelier/auth/signin', destination: '/auth/signin', permanent: false },
    { source: '/atelier/auth/signup', destination: '/auth/signup', permanent: false },
  ];
}

module.exports = nextConfig;
