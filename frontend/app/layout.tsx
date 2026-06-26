import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { SidebarNav } from "@/components/sidebar-nav";

/**
 * Display font: Fraunces is served from Google Fonts in production.
 * In offline/CI environments we fall back gracefully to Georgia (system serif)
 * via the CSS font-family stack — no network fetch needed at build time.
 *
 * Body/UI font: Geist — self-hosted from the woff2 bundled inside Next.js.
 */
const geist = localFont({
  src: "../public/fonts/geist-latin.woff2",
  variable: "--font-sans",
  weight: "100 900",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Career Copilot",
  description: "AI-powered career assistant — find jobs, prep interviews, track applications",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={geist.variable}>
      <head>
        {/* Fraunces from Google Fonts — loaded async, graceful degradation to Georgia */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased bg-background text-foreground font-sans">
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar */}
          <aside className="hidden md:flex flex-col w-56 shrink-0 bg-sidebar border-r border-sidebar-border overflow-y-auto">
            <SidebarNav />
          </aside>

          {/* Main content area */}
          <div className="flex flex-col flex-1 overflow-hidden">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}
