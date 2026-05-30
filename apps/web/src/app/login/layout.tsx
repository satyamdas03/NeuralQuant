import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign In — NeuralQuant",
  description: "Sign in to NeuralQuant to access your AI stock analysis dashboard, watchlists, and PARA-DEBATE reports.",
  openGraph: {
    title: "Sign In — NeuralQuant",
    description: "Sign in to NeuralQuant to access your AI stock analysis dashboard, watchlists, and PARA-DEBATE reports.",
    url: "https://neuralquant.co/login",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Sign In — NeuralQuant",
    description: "Sign in to NeuralQuant to access your AI stock analysis dashboard, watchlists, and PARA-DEBATE reports.",
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
