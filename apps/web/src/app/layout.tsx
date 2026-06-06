import type { Metadata } from "next";
import Script from "next/script";
import { Syne, Space_Mono, Instrument_Serif } from "next/font/google";
import "./globals.css";
import AppShell from "@/components/layout/AppShell";
import WalkthroughProvider from "@/components/onboarding/WalkthroughProvider";
import ServiceWorkerRegister from "@/components/ui/ServiceWorkerRegister";
import InstallPWA from "@/components/ui/InstallPWA";
import UpgradePrompt from "@/components/ui/UpgradePrompt";
import { SessionProvider } from "@/lib/session-tracker";
import AnalyticsRouteTracker from "@/components/AnalyticsRouteTracker";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  weight: ["400", "600", "700", "800"],
});

const spaceMono = Space_Mono({
  subsets: ["latin"],
  variable: "--font-space-mono",
  weight: ["400", "700"],
});

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  variable: "--font-serif",
  weight: ["400"],
  style: ["normal", "italic"],
});

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      name: "NeuralQuant",
      url: "https://neuralquant.co",
      logo: "https://www.neuralquant.co/icons/icon-512.png",
      description:
        "AI-powered stock intelligence platform with IRS% scoring and 7-agent PARA-DEBATE analysis for US and India markets.",
    },
    {
      "@type": "WebSite",
      name: "NeuralQuant",
      url: "https://neuralquant.co",
      potentialAction: {
        "@type": "SearchAction",
        target: "https://www.neuralquant.co/stocks/{search_term_string}",
        "query-input": "required name=search_term_string",
      },
    },
    {
      "@type": "SoftwareApplication",
      name: "NeuralQuant",
      applicationCategory: "FinanceApplication",
      operatingSystem: "Web",
      url: "https://neuralquant.co",
      description:
        "Institutional-grade AI stock analysis with IRS% scoring, PARA-DEBATE multi-agent consensus, and regime detection for US and India markets.",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
        description: "Free tier with limited queries. Pro plans from $9.99/mo.",
      },
    },
  ],
};

export const metadata: Metadata = {
  metadataBase: new URL("https://neuralquant.co"),
  title: {
    default: "NeuralQuant — AI Stock Intelligence for US & India Markets",
    template: "%s | NeuralQuant",
  },
  description:
    "Beat the market with IRS% scoring and 7-agent PARA-DEBATE analysis. Institutional-grade AI stock intelligence for US and India markets.",
  keywords: [
    "stock analysis",
    "AI investing",
    "Indian stocks",
    "IRS score",
    "PARA-DEBATE",
    "QuantAlpha",
    "NeuralQuant",
    "SmallCap",
    "MicroCap",
    "stock screener",
    "portfolio intelligence",
  ],
  authors: [{ name: "QuantAlpha" }],
  robots: "index, follow",
  manifest: "/manifest.json",
  icons: {
    icon: [
      { url: "/icons/icon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/icons/icon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { url: "/icons/icon.svg", sizes: "any", type: "image/svg+xml" },
    ],
    apple: [
      { url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  },
  appleWebApp: {
    capable: true,
    title: "NeuralQuant",
    statusBarStyle: "black-translucent",
  },
  openGraph: {
    title: "NeuralQuant — AI Stock Intelligence",
    description:
      "Institutional-grade AI stock analysis for US and India markets. IRS% scoring, PARA-DEBATE 7-agent consensus, and regime detection.",
    siteName: "NeuralQuant",
    type: "website",
    url: "/",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant — AI Stock Intelligence",
      },
    ],
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: "NeuralQuant — AI Stock Intelligence",
    description:
      "Institutional-grade AI stock analysis for US and India markets. IRS% scoring, PARA-DEBATE 7-agent consensus, and regime detection.",
    images: ["/og-image.png"],
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co",
  },
};

export const viewport = {
  themeColor: "#00ffb2",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className="dark"
      suppressHydrationWarning
    >
      <body
        className={`${syne.variable} ${spaceMono.variable} ${instrumentSerif.variable} font-sans min-h-screen antialiased`}
      >
        {process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN && (
          <Script
            defer
            data-domain={process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN}
            src="https://plausible.io/js/script.js"
          />
        )}
        <ServiceWorkerRegister />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <AnalyticsRouteTracker />
        <SessionProvider>
          <WalkthroughProvider>
            <AppShell>{children}</AppShell>
            <InstallPWA />
            <UpgradePrompt />
          </WalkthroughProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
