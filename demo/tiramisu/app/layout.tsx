import type { Metadata } from "next";
import { Geist, Geist_Mono, Syne } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { Sidebar } from "@/components/sidebar";
import { Suspense } from "react";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const syne = Syne({
  variable: "--font-syne",
  weight: ["400", "600", "700", "800"],
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "DeepAnalyze",
  description: "Agentic data analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${syne.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full" suppressHydrationWarning>
        <ThemeProvider attribute="class" defaultTheme="light" storageKey="theme">
          <div className="flex h-full min-h-screen overflow-hidden">
            <Suspense fallback={<div className="w-[280px] bg-muted/20 border-r border-border/10" />}>
              <Sidebar />
            </Suspense>
            <main className="flex-1 relative overflow-hidden">
              {children}
            </main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
