import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — NeuralQuant",
  description: "NeuralQuant privacy policy — data usage, third parties, GDPR/CCPA rights.",
};

export default function PrivacyPolicyPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16 text-text-muted">
      <h1 className="font-headline text-3xl font-bold text-text mb-8">Privacy Policy</h1>
      <p className="text-sm text-text-dim mb-8">Last updated: June 1, 2026</p>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">1. Overview</h2>
        <p className="mb-3">
          NeuralQuant (&quot;we&quot;, &quot;us&quot;, &quot;our&quot;) operates the website neuralquant.co and associated mobile applications.
          This policy describes how we collect, use, store, and protect your personal information.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">2. Information We Collect</h2>
        <ul className="list-disc pl-6 space-y-2 mb-3">
          <li><strong>Account data:</strong> Email, display name, authentication credentials (via Supabase Auth).</li>
          <li><strong>Portfolio data:</strong> Stock tickers, watchlists, risk profiles you voluntarily provide.</li>
          <li><strong>Query data:</strong> Questions asked via Ask Morgan, PARA-DEBATE results, conversation history.</li>
          <li><strong>Usage analytics:</strong> Weekly active user tracking, feature usage patterns (anonymous).</li>
          <li><strong>Device data:</strong> Push notification tokens (iOS/Android), platform type for notification delivery.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">3. How We Use Your Information</h2>
        <ul className="list-disc pl-6 space-y-2 mb-3">
          <li>Provide and improve our AI stock analysis and portfolio management services.</li>
          <li>Personalize analysis based on your risk profile and portfolio holdings.</li>
          <li>Send push notifications for alerts and sell signals you have opted into.</li>
          <li>Process payments and manage subscriptions (via Stripe).</li>
          <li>Comply with legal obligations and prevent fraud.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">4. Third-Party Services</h2>
        <p className="mb-3">We use the following third-party services that may process your data:</p>
        <ul className="list-disc pl-6 space-y-2 mb-3">
          <li><strong>Supabase</strong> — Authentication, database hosting (US region). Data encrypted at rest and in transit.</li>
          <li><strong>Anthropic</strong> — AI model inference for Ask Morgan and PARA-DEBATE. Queries are processed per Anthropic&apos;s data usage policy.</li>
          <li><strong>Stripe</strong> — Payment processing. We do not store credit card details; Stripe handles PCI compliance.</li>
          <li><strong>LiveKit</strong> — Voice/video infrastructure for QuantAstra sessions.</li>
          <li><strong>Deepgram</strong> — Speech-to-text for QuantAstra voice input.</li>
          <li><strong>ElevenLabs</strong> — Text-to-speech for QuantAstra voice output.</li>
          <li><strong>Resend</strong> — Transactional email delivery.</li>
          <li><strong>FMP (Financial Modeling Prep)</strong> — Market data. We send ticker symbols; no personal data is shared.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">5. Data Retention</h2>
        <ul className="list-disc pl-6 space-y-2 mb-3">
          <li><strong>Account data:</strong> Retained while your account is active. Deleted within 30 days of account deletion request.</li>
          <li><strong>Conversation history:</strong> Retained for 30 days (free) or 90 days (paid). Deleted on account deletion.</li>
          <li><strong>Analytics:</strong> Anonymized and aggregated. Retained indefinitely for product improvement.</li>
          <li><strong>Push tokens:</strong> Deleted on logout or account deletion.</li>
        </ul>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">6. Your Rights (GDPR / CCPA)</h2>
        <ul className="list-disc pl-6 space-y-2 mb-3">
          <li><strong>Access:</strong> Request a copy of all personal data we hold about you.</li>
          <li><strong>Rectification:</strong> Correct inaccurate personal data.</li>
          <li><strong>Erasure:</strong> Request deletion of your account and all associated data.</li>
          <li><strong>Portability:</strong> Export your data in a machine-readable format.</li>
          <li><strong>Objection:</strong> Object to processing of your data for specific purposes.</li>
          <li><strong>Withdraw consent:</strong> Opt out of push notifications at any time via device settings.</li>
        </ul>
        <p className="mb-3">
          To exercise any of these rights, email <a href="mailto:privacy@neuralquant.co" className="text-primary hover:underline">privacy@neuralquant.co</a> or use the Delete Account feature in your Profile settings.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">7. SEBI Disclaimer</h2>
        <p className="mb-3">
          NeuralQuant is not registered with the Securities and Exchange Board of India (SEBI) as an investment advisor,
          research analyst, or in any other capacity. All AI-generated stock analysis, portfolio recommendations,
          and sell signals are algorithmic outputs for informational purposes only. They do not constitute
          investment advice under SEBI regulations. Users should consult a SEBI-registered investment advisor
          before making any investment decisions.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">8. Security</h2>
        <p className="mb-3">
          We use industry-standard encryption (TLS 1.3) for data in transit and AES-256 encryption at rest via Supabase.
          Authentication uses JWT tokens with secure, HttpOnly cookies where applicable. We implement row-level
          security (RLS) on all database tables to ensure users can only access their own data.
        </p>
      </section>

      <section className="mb-8">
        <h2 className="font-headline text-xl font-semibold text-text mb-4">9. Contact</h2>
        <p className="mb-3">
          For privacy inquiries: <a href="mailto:privacy@neuralquant.co" className="text-primary hover:underline">privacy@neuralquant.co</a>
        </p>
      </section>
    </div>
  );
}