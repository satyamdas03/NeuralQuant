import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign In — NeuralQuant",
  description:
    "Sign in to NeuralQuant to access your AI stock analysis dashboard, watchlists, and PARA-DEBATE reports.",
  openGraph: {
    title: "Sign In — NeuralQuant",
    description:
      "Sign in to access your AI stock analysis dashboard, watchlists, and PARA-DEBATE reports.",
    url: "https://neuralquant.co/login",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Sign In",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Sign In — NeuralQuant",
    description:
      "Sign in to access your AI stock analysis dashboard, watchlists, and PARA-DEBATE reports.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/login",
  },
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
