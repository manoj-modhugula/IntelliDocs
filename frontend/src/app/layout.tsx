import type { Metadata, Viewport } from 'next';
import { Fraunces, Plus_Jakarta_Sans } from 'next/font/google';
import Script from 'next/script';
import './globals.css';
import { AppShell } from '@/components/layout/AppShell';
import { Toaster } from '@/components/ui/Toaster';
import { ErrorBoundary } from '@/components/ErrorBoundary';

const fraunces = Fraunces({
  variable: '--font-display',
  subsets: ['latin'],
  axes: ['SOFT', 'WONK', 'opsz'],
  display: 'swap',
});

const jakarta = Plus_Jakarta_Sans({
  variable: '--font-sans',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'IntelliDocs - AI Document Q&A',
    template: '%s | IntelliDocs',
  },
  description: 'AI-powered document Q&A platform with RAG. Upload documents and get accurate answers with citations.',
  keywords: ['AI', 'RAG', 'Documents', 'Q&A', 'Chat'],
  authors: [{ name: 'IntelliDocs' }],
  creator: 'IntelliDocs',
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    title: 'IntelliDocs - AI Document Q&A',
    description: 'AI-powered document Q&A with citations',
    siteName: 'IntelliDocs',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'IntelliDocs - AI Document Q&A',
    description: 'AI-powered document Q&A with citations',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  viewportFit: 'cover',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#eef1f6' },
    { media: '(prefers-color-scheme: dark)', color: '#0b0d12' },
  ],
  colorScheme: 'light dark',
};

const themeInitScript = `(function(){try{var k='intellidocs-theme';var raw=localStorage.getItem(k);var pref='system';if(raw){try{var o=JSON.parse(raw);var s=o.state||o;if(s.preference==='light'||s.preference==='dark'||s.preference==='system')pref=s.preference;else if(s.theme==='light'||s.theme==='dark')pref=s.theme;}catch(e){}}var d;if(pref==='light'||pref==='dark')d=pref;else d=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';var r=document.documentElement;r.setAttribute('data-theme',d);r.style.colorScheme=d;if(d==='dark')r.classList.add('dark');else r.classList.remove('dark');}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning data-theme="light">
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/favicon.svg" />
        <link rel="manifest" href="/manifest.json" />
      </head>
      <body className={`${fraunces.variable} ${jakarta.variable} antialiased`}>
        <Script
          id="intellidocs-theme-init"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: themeInitScript }}
        />
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4"
        >
          Skip to main content
        </a>
        <ErrorBoundary>
          <AppShell>{children}</AppShell>
        </ErrorBoundary>
        <Toaster />
      </body>
    </html>
  );
}
