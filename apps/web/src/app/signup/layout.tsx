import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Get Started — NeuralQuant",
  description:
    "Create your free NeuralQuant account. Access AI stock intelligence, multi-agent PARA-DEBATE, and nightly ForeCast scores for US and India markets.",
  openGraph: {
    title: "Get Started — Free AI Stock Intelligence | NeuralQuant",
    description:
      "Create your free NeuralQuant account. AI stock intelligence, PARA-DEBATE, and ForeCast scores for US and India markets.",
    url: "https://neuralquant.co/signup",
    siteName: "NeuralQuant",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NeuralQuant Sign Up",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Get Started — Free AI Stock Intelligence | NeuralQuant",
    description:
      "Create your free NeuralQuant account. AI stock intelligence, PARA-DEBATE, and ForeCast scores.",
    creator: "@neuralquant",
    site: "@neuralquant",
  },
  alternates: {
    canonical: "https://neuralquant.co/signup",
  },
};

export default function SignupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
