import { createRootRoute, HeadContent, Outlet, Scripts } from '@tanstack/react-router'
import appCss from '../styles.css?url'

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { title: 'NexBar2 — SteamOS front light bar' },
      { name: 'description', content: 'Steam-native-first 24 LED front bar for Redux Steam Machines and Nollie1.' },
      { name: 'theme-color', content: '#0B0C10' },
      { property: 'og:title', content: 'NexBar2' },
      { property: 'og:description', content: 'Steam owns the bar. NexBar maps it to your hardware.' },
      { property: 'og:image', content: '/og-nexbar.svg' },
    ],
    links: [
      { rel: 'stylesheet', href: appCss },
      { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
      { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossOrigin: 'anonymous' },
      { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Syne:wght@500;600;700&display=swap' },
    ],
  }),
  component: () => (
    <html lang="en" className="antialiased">
      <head><HeadContent /></head>
      <body><Outlet /><Scripts /></body>
    </html>
  ),
})
