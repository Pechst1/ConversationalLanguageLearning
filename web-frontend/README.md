# Conversational Language Learning - Web Frontend

Modern web interface for the Conversational Language Learning platform built with Next.js, TypeScript, and Tailwind CSS.

## Features

- 🔐 **Authentication** - NextAuth.js with JWT tokens
- 💬 **Real-time Chat** - WebSocket-powered conversation sessions
- 📊 **Analytics Dashboard** - Progress tracking and statistics
- 🎯 **Vocabulary Practice** - Spaced repetition system (SRS)
- 🏆 **Achievements** - Gamification with badges and streaks
- 📱 **Responsive Design** - Mobile-first approach
- 🌙 **Dark Mode** - Theme switching support

## Quick Start

### Prerequisites

- Node.js 18+
- Running backend API (see main README)

### Installation

```bash
# Clone and navigate to web frontend
cd web-frontend

# Install dependencies
npm install

# Copy environment configuration
cp .env.example .env.local

# Update .env.local with your settings:
# NEXTAUTH_URL=http://localhost:3000
# NEXTAUTH_SECRET=your-secret-here (keep this fixed between restarts)
# NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
# NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Start development server
npm run dev
```

The application will be available at http://localhost:3000

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXTAUTH_URL` | Application URL | `http://localhost:3000` |
| `NEXTAUTH_SECRET` | JWT secret key (must be a persistent random string so sessions survive restarts) | Required |
| `NEXT_PUBLIC_API_BASE_URL` | Native/browser direct FastAPI API URL | `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_API_URL` | Backend API URL | `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_WS_URL` | WebSocket URL | `ws://localhost:8000` |
| `API_URL` | Server-side API URL | `http://localhost:8000` |

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run build:native` - Build the static native export into `out/`
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript type checking
- `npm run cap:sync:ios` - Build the static native export and sync the Capacitor iOS shell
- `npm run cap:open:ios` - Open the generated iOS project in Xcode

## Capacitor iOS

The iOS shell defaults to the bundled static export in `out/`. Native auth uses direct FastAPI
JWT endpoints plus secure storage; web auth keeps NextAuth.

```bash
# Build static assets and sync them into ios/App/App/public
npm run cap:sync:ios
npm run cap:open:ios
```

For a temporary live-server debug run, set `CAPACITOR_SERVER_URL` before syncing:

```bash
CAPACITOR_SERVER_URL=http://127.0.0.1:3000 npm run cap:sync:ios -- --skip-build
```

For the native static bundle, set `NEXT_PUBLIC_API_BASE_URL` (or `NEXT_PUBLIC_API_URL`) to a
simulator/device-reachable FastAPI `/api/v1` URL. A physical iPhone cannot use Mac-local
`localhost`; use a LAN-reachable or hosted HTTPS API URL.

## Project Structure

```
web-frontend/
├── components/          # Reusable UI components
│   ├── ui/             # Base UI components (Button, Input, etc.)
│   ├── layout/         # Layout components (Navbar, Sidebar)
│   └── learning/       # Learning-specific components
├── pages/              # Next.js pages and API routes
│   ├── api/auth/       # NextAuth configuration
│   ├── auth/           # Authentication pages
│   └── learn/          # Learning session pages
├── hooks/              # Custom React hooks
├── services/           # API and WebSocket services
├── lib/                # Utility functions
├── types/              # TypeScript type definitions
└── styles/             # Global styles and Tailwind CSS
```

## Key Components

### Authentication
- JWT-based authentication with NextAuth.js
- Automatic token refresh
- Protected routes with session validation

### Learning Sessions
- Real-time conversation interface
- WebSocket communication with backend
- Vocabulary suggestion system
- Progress tracking during sessions

### Analytics Dashboard
- XP and streak tracking
- Vocabulary mastery statistics
- Session history and performance metrics
- Interactive charts and visualizations

### Vocabulary Practice
- Spaced repetition system (SRS)
- Difficulty-based word queuing
- Performance-based review scheduling

## Deployment

### Vercel (Recommended)

1. Connect your GitHub repository to Vercel
2. Set environment variables in Vercel dashboard
3. Deploy automatically on push to main branch

### Docker

```bash
# Build production image
docker build -t language-learning-web .

# Run container
docker run -p 3000:3000 \
  -e NEXTAUTH_URL=https://your-domain.com \
  -e NEXTAUTH_SECRET=your-secret \
  -e NEXT_PUBLIC_API_URL=https://api.your-domain.com/api/v1 \
  language-learning-web
```

## Development

### Adding New Pages

1. Create page component in `pages/`
2. Add authentication check if needed
3. Update navigation in `components/layout/Sidebar.tsx`

### API Integration

- Use `services/api.ts` for REST API calls
- Use `services/websocket.ts` for real-time communication
- All API calls include automatic authentication headers

### Styling

- Tailwind CSS for utility-first styling
- Custom components in `components/ui/`
- Consistent color scheme and spacing
- Dark mode support via CSS classes

## Browser Support

- Chrome/Edge 88+
- Firefox 85+
- Safari 14+
- WebSocket support required for real-time features

## Contributing

See main project README for contribution guidelines.
