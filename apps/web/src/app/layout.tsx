import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/layout/AppShell";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  title: "NeuralQuant — AI Stock Intelligence",
  description: "Institutional-grade AI stock analysis at retail prices",
  manifest: "/manifest.json",
  icons: {
    icon: "/icons/icon-512.png",
    apple: "/icons/icon-192.png",
  },
};

export const viewport = {
  themeColor: "#6366f1",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.variable} ${spaceGrotesk.variable} font-sans bg-surface text-on-surface min-h-screen antialiased`}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}