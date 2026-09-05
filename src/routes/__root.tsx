import { createRootRoute, HeadContent, Outlet, Scripts } from '@tanstack/react-router'
import appCss from '../styles.css?url'

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { title: 'SLEDGE — Steam Lighting Effects Daemon for Generic Equipment' },
      { name: 'description', content: 'SteamOS front-light compatibility for custom LED hardware, validated on BC-250 and Nollie1 CDC.' },
      { name: 'theme-color', content: '#0B0C10' },
      { property: 'og:title', content: 'SLEDGE' },
      { property: 'og:description', content: 'Steam Lighting Effects Daemon for Generic Equipment. Make custom lighting feel native to SteamOS.' },
      { property: 'og:image', content: '/og-sledge.svg' },
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
