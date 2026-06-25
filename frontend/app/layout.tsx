import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SidebarNav } from "@/components/sidebar-nav";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
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
    <html lang="en" className={inter.variable}>
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
