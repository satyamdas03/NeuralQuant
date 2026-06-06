import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service — NeuralQuant",
  description:
    "NeuralQuant terms of service — usage terms, disclaimers, and limitations of liability for AI-powered stock intelligence.",
  openGraph: {
    title: "Terms of Service — NeuralQuant",
    description:
      "NeuralQuant terms of service — usage terms, disclaimers, and limitations of liability for AI-powered stock intelligence.",
    url: "https://neuralquant.co/terms",
    siteName: "NeuralQuant",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Terms of Service — NeuralQuant",
    description:
      "NeuralQuant terms of service — usage terms, disclaimers, and limitations of liability for AI-powered stock intelligence.",
  },
  alternates: {
    canonical: "https://neuralquant.co/terms",
  },
};

export default function TermsPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16 text-text-muted">
      <h1 className="font-headline text-3xl font-bold text-text mb-8">Terms of Service</h1>
      <p className="text-sm text-text-dim mb-8">Last updated: June 1, 2026</p>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">1. Acceptance of Terms</h2>
        <p className="mb-3">
          By accessing or using NeuralQuant (neuralquant.co or our mobile applications), you agree to be bound by
          these Terms of Service. If you do not agree, do not use our services.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">2. Description of Service</h2>
        <p className="mb-3">
          NeuralQuant provides AI-powered stock analysis, portfolio intelligence, and market data tools.
          Our services include but are not limited to: AI stock scoring (QuantFactor), PARA-DEBATE multi-agent analysis,
          Ask Morgan research reports, QuantAstra voice portfolio management, AI Screener, and portfolio tracking.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">3. Not Investment Advice</h2>
        <p className="mb-3 font-semibold text-secondary">
          IMPORTANT: NeuralQuant is NOT a SEBI-registered investment advisor, research analyst, or broker-dealer.
          All outputs — including stock scores, IRS metrics, portfolio recommendations, and sell signals — are
          AI-generated algorithmic outputs for informational and educational purposes only. They do not constitute
          investment advice, buy/sell recommendations, or financial planning under any jurisdiction.
        </p>
        <p className="mb-3">
          You should not make investment decisions based solely on NeuralQuant outputs. Always consult a qualified,
          SEBI-registered financial advisor before investing. Past performance does not guarantee future results.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">4. Account Responsibilities</h2>
        <ul className="list-disc pl-6 space-y-2 mb-3">
          <li>You are responsible for maintaining the confidentiality of your account credentials.</li>
          <li>You must provide accurate information when creating an account.</li>
          <li>You agree not to share your account with others or use automated tools to exceed usage limits.</li>
          <li>You must be at least 18 years old to use this service.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">5. Subscription and Payments</h2>
        <ul className="list-disc pl-6 space-y-2 mb-3">
          <li>Free tier: Limited queries per day, basic features as described on our pricing page.</li>
          <li>Paid tiers: Billed monthly or annually via Stripe. Prices are subject to change with 30 days notice.</li>
          <li>Cancellation: You may cancel your subscription at any time. Access continues until the end of the billing period.</li>
          <li>Refunds: No refunds for partial billing periods unless required by law.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">6. Usage Limits</h2>
        <p className="mb-3">
          Each subscription tier has daily/monthly query limits as published on our pricing page.
          Exceeding these limits may result in throttled responses or temporary suspension of service.
          We reserve the right to limit usage to prevent abuse.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">7. Intellectual Property</h2>
        <p className="mb-3">
          NeuralQuant&apos;s proprietary algorithms, scoring models, AI prompts, and interface designs are our intellectual property.
          You may not reverse-engineer, scrape, or redistribute our analysis outputs in bulk. Individual stock analysis
          results may be shared for personal, non-commercial use with attribution.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">8. Limitation of Liability</h2>
        <p className="mb-3">
          NeuralQuant is provided &quot;as is&quot; without warranty of any kind. We do not guarantee the accuracy,
          timeliness, or completeness of any market data or AI-generated analysis. In no event shall NeuralQuant
          be liable for any investment losses, trading decisions, or financial outcomes based on information
          provided by our service. Our total liability shall not exceed the amount you paid us in the preceding
          12 months.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">9. Data Deletion</h2>
        <p className="mb-3">
          You may request deletion of your account and all associated data at any time via the Delete Account
          feature in Profile settings or by emailing <a href="mailto:support@neuralquant.co" className="text-primary hover:underline">support@neuralquant.co</a>.
          Deletion is permanent and irreversible — all portfolio data, conversation history, and account
          information will be removed within 30 days.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">10. Modifications</h2>
        <p className="mb-3">
          We may update these Terms from time to time. Material changes will be communicated via email
          or in-app notification at least 30 days before taking effect. Continued use of the service
          constitutes acceptance of updated terms.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">11. Contact</h2>
        <p className="mb-3">
          For legal or support inquiries: <a href="mailto:support@neuralquant.co" className="text-primary hover:underline">support@neuralquant.co</a>
        </p>
      </section>
    </div>
  );
}