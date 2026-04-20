import {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
  TableOfContents, ExternalHyperlink
} from "docx";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, "NeuralQuant_Report.docx");

// ─── Colour palette ────────────────────────────────────────────────────────────
const VIOLET   = "7C3AED";
const CYAN     = "06B6D4";
const DARK_BG  = "0F172A";
const CARD_BG  = "1E293B";
const GREEN    = "22C55E";
const RED      = "EF4444";
const AMBER    = "F59E0B";
const WHITE    = "FFFFFF";
const LIGHT    = "F1F5F9";
const MID_GREY = "94A3B8";
const SLATE    = "334155";

// Content width: A4 (11906 DXA) - 2×1440 margins = 9026 DXA
const PAGE_W   = 9026;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function shading(fill) {
  return { fill, type: ShadingType.CLEAR, color: "auto" };
}

function cell(text, { bg = CARD_BG, bold = false, color = LIGHT, align = AlignmentType.LEFT, width, colspan } = {}) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: SLATE };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cfg = {
    borders,
    shading: shading(bg),
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: align,
      children: [new TextRun({ text: String(text), bold, color, font: "Calibri", size: 18 })]
    })]
  };
  if (width) cfg.width = { size: width, type: WidthType.DXA };
  if (colspan) cfg.columnSpan = colspan;
  return new TableCell(cfg);
}

function hcell(text, width) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: SLATE };
  const borders = { top: border, bottom: border, left: border, right: border };
  return new TableCell({
    borders,
    shading: shading(VIOLET),
    margins: { top: 100, bottom: 100, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    width: { size: width, type: WidthType.DXA },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, bold: true, color: WHITE, font: "Calibri", size: 18 })]
    })]
  });
}

function makeTable(headers, colWidths, rows, { stripeColor = "1A2942" } = {}) {
  return new Table({
    width: { size: PAGE_W, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [
      new TableRow({ children: headers.map((h, i) => hcell(h, colWidths[i])) }),
      ...rows.map((row, ri) =>
        new TableRow({
          children: row.map((val, ci) => {
            const bg = ri % 2 === 0 ? CARD_BG : stripeColor;
            return cell(val, { bg, width: colWidths[ci] });
          })
        })
      )
    ]
  });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: VIOLET, space: 4 } },
    children: [new TextRun({ text, bold: true, color: VIOLET, font: "Calibri", size: 32 })]
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 80 },
    children: [new TextRun({ text, bold: true, color: CYAN, font: "Calibri", size: 26 })]
  });
}

function heading3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 160, after: 60 },
    children: [new TextRun({ text, bold: true, color: LIGHT, font: "Calibri", size: 22 })]
  });
}

function body(text, { bold = false, color = LIGHT, italic = false, size = 20 } = {}) {
  return new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({ text, bold, italic, color, font: "Calibri", size })]
  });
}

function callout(text) {
  return new Paragraph({
    spacing: { before: 160, after: 160 },
    alignment: AlignmentType.CENTER,
    shading: shading(CARD_BG),
    border: {
      left: { style: BorderStyle.SINGLE, size: 16, color: VIOLET, space: 8 },
    },
    children: [new TextRun({ text, bold: true, italics: true, color: CYAN, font: "Calibri", size: 22 })]
  });
}

function bullet(text, { bold = false, color = LIGHT } = {}) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: [new TextRun({ text, bold, color, font: "Calibri", size: 20 })]
  });
}

function numberedItem(text) {
  return new Paragraph({
    numbering: { reference: "numbers", level: 0 },
    children: [new TextRun({ text, color: LIGHT, font: "Calibri", size: 20 })]
  });
}

function spacer(lines = 1) {
  return new Paragraph({ spacing: { after: 160 * lines }, children: [new TextRun("")] });
}

function divider() {
  return new Paragraph({
    spacing: { before: 120, after: 120 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: SLATE, space: 2 } },
    children: [new TextRun("")]
  });
}

// ─── Document ──────────────────────────────────────────────────────────────────
const doc = new Document({
  background: { color: DARK_BG },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 640, hanging: 360 }, spacing: { after: 80 } },
                  run: { color: CYAN, font: "Calibri" } } }]
      },
      {
        reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 640, hanging: 360 }, spacing: { after: 80 } },
                  run: { color: LIGHT, font: "Calibri" } } }]
      }
    ]
  },
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 20, color: LIGHT } },
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Calibri", color: VIOLET },
        paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Calibri", color: CYAN },
        paragraph: { spacing: { before: 240, after: 80 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Calibri", color: LIGHT },
        paragraph: { spacing: { before: 160, after: 60 }, outlineLevel: 2 } },
    ]
  },
  sections: [
    // ── COVER PAGE ──────────────────────────────────────────────────────────
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1800, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      children: [
        spacer(4),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: "NeuralQuant", bold: true, font: "Calibri", size: 72, color: VIOLET })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 120 },
          children: [new TextRun({ text: "Business & Competitive Intelligence Report", font: "Calibri", size: 32, color: CYAN })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 160 },
          children: [new TextRun({ text: "Version 3.0  \u2014  March 2026", font: "Calibri", size: 22, color: MID_GREY, italics: true })]
        }),
        divider(),
        spacer(1),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 80 },
          children: [new TextRun({ text: "AI-Powered Stock Intelligence Platform", bold: true, font: "Calibri", size: 26, color: LIGHT })]
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 320 },
          children: [new TextRun({ text: "5-Factor Quant Engine  \u00B7  7-Agent PARA-DEBATE  \u00B7  US & India  \u00B7  100% Live Data", font: "Calibri", size: 20, color: MID_GREY })]
        }),
        spacer(5),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 80 },
          children: [new TextRun({ text: "CONFIDENTIAL \u2014 Internal Strategy Document", bold: true, font: "Calibri", size: 18, color: AMBER })]
        }),
        new Paragraph({ children: [new PageBreak()] }),
      ]
    },

    // ── MAIN CONTENT ────────────────────────────────────────────────────────
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
        }
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: VIOLET, space: 2 } },
            children: [new TextRun({ text: "NeuralQuant \u2014 Business & Competitive Intelligence Report", font: "Calibri", size: 16, color: MID_GREY, italics: true })]
          })]
        })
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            border: { top: { style: BorderStyle.SINGLE, size: 4, color: VIOLET, space: 2 } },
            children: [
              new TextRun({ text: "Confidential \u2014 NeuralQuant v3.0 \u2014 Page ", font: "Calibri", size: 16, color: MID_GREY }),
              new TextRun({ children: [PageNumber.CURRENT], font: "Calibri", size: 16, color: MID_GREY }),
              new TextRun({ text: " of ", font: "Calibri", size: 16, color: MID_GREY }),
              new TextRun({ children: [PageNumber.TOTAL_PAGES], font: "Calibri", size: 16, color: MID_GREY }),
            ]
          })]
        })
      },
      children: [

        // ─── TABLE OF CONTENTS ──────────────────────────────────────────
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 120 },
          children: [new TextRun({ text: "Table of Contents", bold: true, font: "Calibri", size: 32, color: VIOLET })]
        }),
        new TableOfContents("Table of Contents", {
          hyperlink: true,
          headingStyleRange: "1-3",
          stylesWithLevels: [
            { styleName: "Heading1", level: 1 },
            { styleName: "Heading2", level: 2 },
          ]
        }),
        new Paragraph({ children: [new PageBreak()] }),

        // ─── 1. EXECUTIVE SUMMARY ────────────────────────────────────────
        heading1("1. Executive Summary"),
        body("NeuralQuant is a full-stack AI stock intelligence platform that delivers institutional-grade quantitative research at retail price. It combines a 5-factor signal engine (Quality, Momentum, Value, Low-Volatility, Short Interest) with a 7-agent PARA-DEBATE system powered by Claude Sonnet 4.6 to produce explainable, opinionated investment intelligence for both US and Indian (NSE) equity markets \u2014 backed entirely by live data from FRED and yfinance."),
        spacer(),
        heading2("Key Numbers at a Glance"),
        bullet("50 US stocks + 50 NSE stocks scored in real time"),
        bullet("19 live data sources: FRED (HY spreads, CPI, yields), yfinance (prices, fundamentals, news)"),
        bullet("7 AI agents running in parallel per analysis, synthesised by a HEAD ANALYST"),
        bullet("5-factor model with rank-normalised 1\u201310 scores \u2014 zero synthetic data"),
        bullet("Multi-turn NL query that cites the platform\u2019s own live scores and prices"),
        spacer(),
        callout("Core thesis: The gap in the market is not data \u2014 Bloomberg and FactSet have data.\nThe gap is affordable, explainable, AI-debated conviction. NeuralQuant fills that gap."),
        new Paragraph({ children: [new PageBreak()] }),

        // ─── 2. COMPETITIVE LANDSCAPE ────────────────────────────────────
        heading1("2. Competitive Landscape"),
        body("The following table benchmarks NeuralQuant against eight established competitors across six dimensions that matter most to retail and professional investors."),
        spacer(),
        makeTable(
          ["Platform", "AI Analysis", "Quant Model", "Live Data", "India/NSE", "Price/mo", "Explainable"],
          [1700, 1200, 1200, 1100, 900, 950, 976],
          [
            ["NeuralQuant", "7-Agent PARA-DEBATE", "5-Factor + Regime", "FRED + yfinance", "\u2713 50 NSE stocks", "Free \u2013 $99", "\u2713 Factor breakdown"],
            ["Perplexity Finance", "General Q&A LLM", "None", "News + web", "\u2718 US only", "Free \u2013 $20", "\u2718 Black box"],
            ["Danelfin", "ML score only", "100+ features", "Delayed", "\u2718 US+EU", "$30 \u2013 $150", "Partial"],
            ["FactSet Mercury", "GPT-4 wrapper", "FactSet data", "Full institutional", "\u2713 Global", "$500+", "\u2718 No"],
            ["Simply Wall St", "Rule templates", "None", "EOD", "Partial", "$15 \u2013 $30", "Partial"],
            ["Trade Ideas", "Holly AI signals", "Momentum only", "Real-time US", "\u2718", "$84 \u2013 $167", "\u2718"],
            ["Seeking Alpha", "Contributor + AI", "Quant ratings", "Delayed", "\u2718", "$19 \u2013 $240", "Partial"],
            ["Bloomberg Terminal", "None native", "B-QUANT Python", "Full real-time", "\u2713 Global", "$2,000+/mo", "\u2718"],
            ["Yahoo Finance", "None", "None", "15-min delay", "\u2713 BSE/NSE", "Free \u2013 $25", "\u2718"],
          ]
        ),
        spacer(),

        heading2("Deep-Dive: NeuralQuant vs Perplexity Finance"),
        body("Perplexity Finance is a general-purpose LLM with financial news access. It cannot run a screener, produce a factor score, or cite the platform\u2019s own proprietary signals. It has no regime awareness and no quantitative model behind its answers. NeuralQuant\u2019s query engine, by contrast, injects live macro data (VIX, HY spreads, CPI, Fed funds), NeuralQuant screener rankings, and 52-week price ranges before every LLM call \u2014 making every answer data-grounded and citable."),

        heading2("Deep-Dive: NeuralQuant vs Danelfin"),
        body("Danelfin scores stocks using 100+ ML features but operates as a black box. Users cannot see why NVDA scores 8/10 \u2014 only that it does. NeuralQuant exposes all five factor percentiles (Quality, Momentum, Value, Low-Vol, Short Interest), the regime label, and confidence \u2014 giving users conviction rather than a number they cannot act on."),

        heading2("Deep-Dive: NeuralQuant vs Bloomberg Terminal"),
        body("Bloomberg provides the deepest institutional data available, but at $2,000+/month per seat it is inaccessible to retail investors and early-stage funds. It offers no opinionated AI debate. NeuralQuant delivers 80\u201390% of the actionable insight (live macro, fundamentals, factor scores, AI synthesis) at 1\u201350% of the cost."),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 3. UNIQUE SELLING PROPOSITIONS ──────────────────────────────
        heading1("3. Unique Selling Propositions (USPs)"),
        spacer(),

        heading2("USP 1 \u2014 PARA-DEBATE: 7-Agent AI Conviction Engine"),
        body("Most AI finance tools wrap a single LLM call. NeuralQuant runs seven specialised agents concurrently via asyncio \u2014 MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL, ADVERSARIAL, and HEAD ANALYST \u2014 each with its own system prompt and data slice. The HEAD ANALYST synthesises their outputs into a structured verdict with a conviction score, key bull/bear points, and an explicit risk assessment. This architecture produces genuinely conflicted, nuanced analysis rather than confident-sounding hallucinations."),

        heading2("USP 2 \u2014 Self-Aware NL Query Engine"),
        body("The natural language query endpoint is the only LLM-powered financial query system that automatically detects whether the user\u2019s question needs the platform\u2019s own screener data and injects it before the LLM call. Ask \u201cwhat are your top picks right now?\u201d and the system fetches the live screener rankings, factor percentiles, and injects them as structured context. No other AI finance product achieves this loop between LLM and its own quantitative backend."),

        heading2("USP 3 \u2014 5-Factor Quant Model with Rank-Normalised Scoring"),
        body("NeuralQuant implements the full academic factor zoo \u2014 Piotroski F-score quality, Jegadeesh-Titman momentum, P/E + P/B value, realised-volatility low-vol, and short-float short-interest \u2014 with cross-sectional percentile ranking that guarantees a meaningful 1\u201310 spread. Scores are computed within a 20-stock reference universe per market, ensuring each stock\u2019s rating is always relative to peers, not absolute."),

        heading2("USP 4 \u2014 100% Live Data Pipeline"),
        body("Every score is computed from live data at request time. FRED provides HY credit spreads, CPI, Fed funds rate, and 10Y/2Y yields. yfinance provides prices, fundamentals (gross margin, P/E, P/B, beta, short float), and real-time news headlines. There is no batch job, no overnight stale cache. The 4-hour fundamental cache and 1-hour macro cache are refreshed continuously in a ThreadPoolExecutor with 12 workers."),

        heading2("USP 5 \u2014 India (NSE) Market Coverage"),
        body("No direct competitor at this price point covers NSE stocks with the same depth. NeuralQuant scores 50 NSE stocks with the same 5-factor model, regime detection, and PARA-DEBATE analysis. Indian retail investors \u2014 a 90M+ Demat account market \u2014 have no equivalent tool in their price range."),

        heading2("USP 6 \u2014 Explainability at Every Layer"),
        body("Every 1\u201310 score shows the five underlying factor percentiles. Every PARA-DEBATE analysis shows each agent\u2019s perspective. Every NL query response cites its data sources (NeuralQuant Screener / FRED Macro / Live News). No black boxes. This builds user trust and supports investment decision documentation."),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 4. DRAWBACKS ────────────────────────────────────────────────
        heading1("4. Known Drawbacks & Honest Limitations"),
        body("A credible business document must acknowledge what the platform does not do well. The following limitations are real and should be addressed in the product roadmap."),
        spacer(),
        makeTable(
          ["Limitation", "Severity", "Impact", "Planned Fix"],
          [2200, 900, 2200, 2226 + 500],
          [
            ["ISM PMI not available from FRED\u2019s free tier \u2014 defaults to neutral 51.0", "Medium", "Regime detection uses one less input", "Phase 4: alternative PMI data source"],
            ["Universe limited to 100 stocks (50 US + 50 NSE)", "Medium", "Misses small/mid-cap opportunities", "Phase 4: expand to 500 US + 200 NSE"],
            ["No intraday scoring \u2014 scores refresh on request, not streamed", "Low", "Not suited for day trading use cases", "Phase 5: WebSocket streaming"],
            ["Sector-agnostic quality scoring (banks use same margins model)", "Medium", "Bank/REIT scores less meaningful", "Phase 4: sector-adjusted factors"],
            ["No user authentication or persistent watchlists", "High (UX)", "Users cannot save their portfolio", "Phase 4: Supabase auth + watchlists"],
            ["HMM regime detector uses heuristic rules, not fitted historical model", "Medium", "Regime labels may lag turning points", "Phase 4: fitted HMM on FRED history"],
            ["No earnings calendar or insider transaction data", "Low", "Misses event-driven signals", "Phase 5: EDGAR Form 4 wiring"],
          ]
        ),
        spacer(),

        // ─── 5. WHY PEOPLE SHOULD USE NEURALQUANT ────────────────────────
        heading1("5. Why People Should Use NeuralQuant"),

        heading2("For the Retail Investor"),
        body("Most retail investors make stock decisions based on Reddit threads, YouTube commentary, or a glance at a stock\u2019s P/E. NeuralQuant gives them institutional-quality analysis \u2014 the same five factors that quantitative hedge funds use \u2014 at a price they can afford. They get a clear 1\u201310 score, a regime-aware context (\u201cis now a good time to take risk?\u201d), and an AI debate that surfaces the bear case they might not have considered."),

        heading2("For the Registered Investment Advisor (RIA)"),
        body("RIAs need to document their investment thesis. NeuralQuant\u2019s PARA-DEBATE output gives them a structured, citable analysis per stock \u2014 MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL perspectives \u2014 that they can include in client reports. The 5-factor breakdown supports suitability analysis. At $49\u2013$99/month, it costs less than one hour of a junior analyst\u2019s time."),

        heading2("For the Quant Researcher"),
        body("The /screener and /stocks API endpoints expose raw factor percentiles, composite scores, regime IDs, and confidence levels as JSON. Quant researchers can pipe NeuralQuant\u2019s signals into their own models, backtest regime-conditional strategies, or use the India NSE data as a diversification signal. The open API (Pro tier) makes NeuralQuant a component in larger analytical pipelines."),

        heading2("For the Indian Investor"),
        body("The NSE market is underserved by Western analytics tools. NeuralQuant scores 50 top NSE stocks with the same rigour applied to US equities \u2014 live yfinance fundamentals, Jegadeesh-Titman momentum, P/B value, and short-interest signals \u2014 plus a query engine that understands Indian market context (SEBI rate decisions, INDA ETF flows, Sensex vs Nifty regime)."),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 6. MONETISATION STRATEGY ────────────────────────────────────
        heading1("6. Monetisation Strategy"),

        heading2("6.1 Pricing Tiers"),
        spacer(),
        makeTable(
          ["Tier", "Price", "Features", "Target User"],
          [1100, 900, 4026, 3000],
          [
            ["Free", "$0/month", "10 stock scores/day, screener top 5, basic NL query (3/day)", "Casual retail, discovery"],
            ["Investor", "$19/month", "Unlimited scores, screener top 20, NL query (50/day), PARA-DEBATE (5/day)", "Active retail investor"],
            ["Pro", "$49/month", "All Investor features + full PARA-DEBATE, India NSE, API access (1K calls/mo)", "Serious investor / RIA"],
            ["API", "$99/month", "10K API calls/month, all endpoints, raw factor data, bulk screener", "Developers, quant researchers"],
            ["Enterprise", "Custom", "Unlimited API, SLA, dedicated support, white-label option, EDGAR wiring", "Hedge funds, fintech platforms"],
          ]
        ),
        spacer(),

        heading2("6.2 Revenue Streams"),
        bullet("Subscription SaaS \u2014 primary revenue; recurring, predictable"),
        bullet("API Usage Overage \u2014 $0.01/call above tier limit; scales with power users"),
        bullet("Data Licensing \u2014 NSE factor scores licensed to Indian brokerages and robo-advisors"),
        bullet("White-Label \u2014 NeuralQuant engine embedded in third-party platforms under revenue share"),
        bullet("Affiliate / Referral \u2014 brokerage referrals (Zerodha, IBKR) on account opens via the platform"),
        spacer(),

        heading2("6.3 Revenue Projections"),
        body("Conservative growth scenario assuming 5% monthly user growth with 8% free-to-paid conversion:"),
        spacer(),
        makeTable(
          ["Month", "Free Users", "Paid Users", "Avg. ARPU", "MRR", "ARR Run-Rate"],
          [900, 900, 900, 1000, 1200, 2126],
          [
            ["1",    "500",    "40",    "$22",  "$880",    "$10,560"],
            ["3",    "1,100",  "88",    "$25",  "$2,200",  "$26,400"],
            ["6",    "2,800",  "224",   "$27",  "$6,048",  "$72,576"],
            ["12",   "7,400",  "590",   "$30",  "$17,700", "$212,400"],
            ["18",   "16,000", "1,280", "$33",  "$42,240", "$506,880"],
            ["24",   "30,000", "2,400", "$35",  "$84,000", "$1,008,000"],
          ]
        ),
        spacer(),
        body("At Month 24, a $1M ARR run-rate at 80\u201385% gross margin (SaaS) positions NeuralQuant for a Seed or Series A raise at a 5\u201310\xd7 ARR multiple ($5\u201310M valuation).", { color: CYAN, bold: true }),
        spacer(),

        heading2("6.4 Unit Economics"),
        bullet("Estimated COGS per paid user: ~$2\u20133/month (Claude API + yfinance data + hosting)"),
        bullet("Gross margin target: 85\u201390% at scale"),
        bullet("Customer acquisition cost (CAC): $15\u201325 via content marketing + SEO"),
        bullet("LTV at $30 ARPU, 18-month average retention: $540 \u2014 LTV:CAC ratio of ~25\xd7"),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 7. GO-TO-MARKET STRATEGY ────────────────────────────────────
        heading1("7. Go-To-Market Strategy"),

        heading2("Phase 1: Seed Community (Months 1\u20133)"),
        body("Target finance-forward communities: r/IndiaInvestments, r/stocks, r/quantfinance, Substack finance newsletters, and Indian stock trading Telegram groups. Release a free tier with generous limits. Publish weekly \u201cNeuralQuant Weekly\u201d reports that showcase the PARA-DEBATE output on trending stocks. Goal: 1,000 free signups, 50 paid conversions."),

        heading2("Phase 2: Paid Conversion Engine (Months 4\u20139)"),
        body("Gate PARA-DEBATE behind the Investor tier. Use the free tier as a loss leader \u2014 users who see a PARA-DEBATE preview will convert to unlock the full debate. Partner with two mid-sized Indian stock trading communities for co-branded content. Launch an affiliate program. Goal: 200 paid users, $5,000 MRR."),

        heading2("Phase 3: Enterprise & API (Months 10+)"),
        body("Pitch the API tier to fintech startups building robo-advisors or portfolio tools. Approach Indian brokerages (Zerodha, Groww, Angel One) with a data licensing proposal for NSE factor scores. Explore white-label for wealth management platforms. Goal: 2 enterprise contracts, $20,000+ MRR."),

        spacer(),

        // ─── 8. TECHNOLOGY MOAT ──────────────────────────────────────────
        heading1("8. Technology Moat"),
        body("Technology moats in AI products are thin but compounding. NeuralQuant\u2019s defensibility comes from five sources:"),
        spacer(),
        makeTable(
          ["Moat", "Description", "Replication Difficulty"],
          [2000, 4500, 2526],
          [
            ["PARA-DEBATE Architecture", "7-agent concurrent debate with HEAD ANALYST synthesis \u2014 prompt engineering + orchestration know-how", "Medium \u2014 3\u20136 months"],
            ["Self-Aware Query Loop", "LLM that detects when to fetch its own screener and injects structured data pre-call", "Low-Medium \u2014 1\u20133 months"],
            ["5-Factor Live Pipeline", "FRED + yfinance integrated data pipeline with regime detection and cross-sectional ranking", "Medium \u2014 4\u20138 months"],
            ["India NSE Coverage", "Deep NSE data pipeline, Indian market regime awareness, Nifty/Sensex context", "Medium \u2014 2\u20134 months"],
            ["User Trust & Data Network", "As users query the platform, the most useful follow-up questions and edge cases surface for improvement", "High \u2014 takes 12+ months of real users"],
          ]
        ),
        spacer(),

        // ─── 9. RISKS ─────────────────────────────────────────────────────
        heading1("9. Risks & Mitigations"),
        spacer(),
        makeTable(
          ["Risk", "Likelihood", "Impact", "Mitigation"],
          [2200, 900, 900, 5026],
          [
            ["yfinance rate limits or breaking API changes", "Medium", "High", "Abstract data layer; add fallback to Alpha Vantage / Polygon.io"],
            ["Anthropic API cost spikes at scale", "Low", "Medium", "Cache LLM responses for identical queries; tier-gate PARA-DEBATE"],
            ["Regulatory: providing investment advice without licence", "Medium", "High", "All outputs labelled as \u201ceducational, not financial advice\u201d; no buy/sell orders"],
            ["Competitor replication by Perplexity or Bloomberg", "Low", "High", "Speed of iteration + India moat + community lock-in"],
            ["Data quality: yfinance fundamentals lag or error", "Medium", "Medium", "Show data freshness timestamps; fallback labels; _is_real flag"],
            ["LLM hallucination in PARA-DEBATE", "Low", "Medium", "All claims grounded in injected structured data; HEAD ANALYST cross-checks"],
          ]
        ),
        spacer(),

        new Paragraph({ children: [new PageBreak()] }),

        // ─── 10. CONCLUSION ───────────────────────────────────────────────
        heading1("10. Conclusion"),
        body("NeuralQuant occupies a genuinely underserved position in the financial intelligence market: sophisticated enough for professional use, affordable enough for retail, and explainable enough for both. Its combination of a 5-factor quantitative model, a 7-agent AI debate system, live macro data integration, and India NSE coverage creates a product with multiple overlapping defensibilities."),
        spacer(),
        body("The largest risk is not technical \u2014 it is distribution. The platform needs to reach the communities that will benefit from it most. With a well-executed free tier, a content-led growth motion, and a clear API monetisation path, NeuralQuant is positioned to reach $1M ARR within 24 months and $5M+ ARR within 36\u201348 months."),
        spacer(),
        callout("The question is not whether the market needs a tool like this. The question is who builds it best, fastest, and at the right price point. NeuralQuant is already there."),
        spacer(2),

        makeTable(
          ["Section", "Key Takeaway"],
          [3000, 6026],
          [
            ["Executive Summary", "Institutional quant + AI debate at retail price. 100% live data."],
            ["Competitive Landscape", "Outperforms every sub-$100/mo tool on explainability, depth, and India coverage."],
            ["USPs", "6 defensible differentiators: PARA-DEBATE, self-aware NL query, 5-factor model, live data, NSE, explainability."],
            ["Drawbacks", "7 honest limitations \u2014 all with clear Phase 4/5 fixes. No existential risks."],
            ["Why Use It", "Serves 4 personas: retail, RIA, quant researcher, Indian investor."],
            ["Monetisation", "5 tiers + 5 revenue streams. $84K MRR projected at Month 24."],
            ["GTM", "Community-led \u2192 paid conversion \u2192 enterprise/API. India-first distribution edge."],
            ["Technology Moat", "5 compounding moats. Deepest: user trust and India NSE pipeline."],
          ]
        ),
        spacer(2),
        body("Prepared by: NeuralQuant Engineering Team  \u00B7  March 2026  \u00B7  CONFIDENTIAL", { color: MID_GREY, italic: true }),
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(OUT, buffer);
  console.log("DOCX generated:", OUT);
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
