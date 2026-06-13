const isNativeStaticExport = process.env.NATIVE_STATIC_EXPORT === 'true';

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
  env: {
    NEXTAUTH_URL: process.env.NEXTAUTH_URL || 'http://localhost:3000',
    NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET,
    API_URL: process.env.API_URL || 'http://localhost:8000',
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
    {
      source: '/api/backend/:path*',
      destination: `${process.env.API_URL || 'http://localhost:8000'}/api/v1/:path*`,
    },
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
    { source: '/learn', destination: '/atelier', permanent: false },
    { source: '/index', destination: '/atelier', permanent: false },
    { source: '/stories', destination: '/bibliotheque', permanent: false },
    { source: '/stories/:path*', destination: '/bibliotheque/:path*', permanent: false },
    { source: '/story/:id', destination: '/bibliotheque/:id', permanent: false },
    { source: '/atelier/auth/signin', destination: '/auth/signin', permanent: false },
    { source: '/atelier/auth/signup', destination: '/auth/signup', permanent: false },
  ];
}

module.exports = nextConfig;
