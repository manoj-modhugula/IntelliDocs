import type { Metadata, Viewport } from 'next';
import './globals.css';
import { AppShell } from '@/components/layout/AppShell';
import { Toaster } from '@/components/ui/Toaster';
import { ErrorBoundary } from '@/components/ErrorBoundary';

export const metadata: Metadata = {
  title: {
    default: 'IntelliDocs - AI Document Q&A',
    template: '%s | IntelliDocs',
  },
  description: 'AI-powered document Q&A platform with RAG. Upload documents and get accurate answers with citations.',
  keywords: ['AI', 'RAG', 'Documents', 'Q&A', 'Chat', 'AWS Bedrock', 'Next.js'],
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
  themeColor: '#f8fafc',
  colorScheme: 'light',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/favicon.svg" />
        <link rel="manifest" href="/manifest.json" />
      </head>
      <body className="font-sans text-slate-900 dark:text-slate-100 antialiased">
        <a 
          href="#main-content" 
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white focus:text-black"
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
