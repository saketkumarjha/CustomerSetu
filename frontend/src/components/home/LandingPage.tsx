import React from "react";
import { Link } from "react-router-dom";
import ComplaintReachSection from "./ComplaintReachSection";
import { AppHeader } from "../layout/AppHeader";
import {
  ArrowRight,
  Play,
  Zap,
  BarChart2,
  Shield,
  Tag,
  Heart,
  Clock,
  TrendingUp,
  Star,
  Eye,
  Globe,
  Share2,
  Smartphone,
  Building2,
  Phone,
  Mail,
} from "lucide-react";
import ChatbotLauncher from "../chatbot/ChatbotLauncher";
import ChatbotWindow from "../chatbot/ChatbotWindow";
import ChannelsDemoSection from "./ChannelsDemoSection";
import { useState } from "react";

const IMG = {
  hero: "/handshake.png",
  pipeline: "/deescalate.webp",
  analytics: "/listen.jpg",
  handle: "/handle.webp",
};

// ─── Hero ─────────────────────────────────────────────────────────────────────

const MOCK_ROWS = [
  {
    icon: "📄", summary: "Unauthorized transaction on credit card ending in 4291",
    category: "Fraud", channel: "Mobile App", risk: 9.8, riskPct: 98,
    avatars: [{ bg: "#4f46e5", label: "JM" }, { bg: "#0891b2", label: "RH" }, { bg: "#16a34a", label: "SA" }], extra: 18,
    priority: "Critical", priorityColor: "#ef4444", priorityIcon: "△",
  },
  {
    icon: "🕐", summary: "Home loan disbursement delayed beyond 48 hours",
    category: "Lending", channel: "Branch", risk: 7.2, riskPct: 72,
    avatars: [{ bg: "#d97706", label: "DV" }, { bg: "#7c3aed", label: "HK" }], extra: 11,
    priority: "High", priorityColor: "#f97316", priorityIcon: "△",
  },
  {
    icon: "⌨", summary: "Unable to reset net banking password via IVR",
    category: "Technical", channel: "WhatsApp", risk: 4.5, riskPct: 45,
    avatars: [{ bg: "#0284c7", label: "TQ" }, { bg: "#15803d", label: "NK" }], extra: 8,
    priority: "Medium", priorityColor: "#ca8a04", priorityIcon: "○",
  },
  {
    icon: "📅", summary: "Incorrect interest rate applied to savings account",
    category: "Compliance", channel: "Web Portal", risk: 6.1, riskPct: 61,
    avatars: [{ bg: "#be185d", label: "FA" }, { bg: "#0891b2", label: "LC" }], extra: 6,
    priority: "High", priorityColor: "#f97316", priorityIcon: "○",
  },
  {
    icon: "💱", summary: "Rude behavior reported at Jamshedpur main branch",
    category: "Service", channel: "WhatsApp · Mobile", risk: 8.8, riskPct: 88,
    avatars: [{ bg: "#7c3aed", label: "EG" }, { bg: "#0891b2", label: "QS" }], extra: 5,
    priority: "High", priorityColor: "#f97316", priorityIcon: "○",
  },
  {
    icon: "🔔", summary: "KYC verification pending for over 48 hours",
    category: "Onboarding", channel: "Web Portal · Branch", risk: 5.4, riskPct: 54,
    avatars: [{ bg: "#16a34a", label: "PR" }], extra: 3,
    priority: "Medium", priorityColor: "#ca8a04", priorityIcon: "○",
  },
];

const CATEGORY_COLORS: Record<string, { bg: string; text: string }> = {
  Fraud:      { bg: "#fef2f2", text: "#dc2626" },
  Lending:    { bg: "#fff7ed", text: "#c2410c" },
  Technical:  { bg: "#eff6ff", text: "#2563eb" },
  Compliance: { bg: "#faf5ff", text: "#7c3aed" },
  Service:    { bg: "#ecfdf5", text: "#059669" },
  Onboarding: { bg: "#f0fdf4", text: "#16a34a" },
};

function HeroSection({ onAskAI }: { onAskAI: () => void }) {
  return (
    <section
      id="top"
      className="flex flex-col items-center"
      style={{ background: "#f5f0e6", paddingTop: "64px", minHeight: "92vh" }}
    >
      {/* ── Centered copy block ── */}
      <div className="flex flex-col items-center text-center px-4 pt-14 pb-8 w-full max-w-[1100px] mx-auto">
        {/* Badge */}
        <span className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full border border-gray-300/80 bg-white/60 text-gray-600 text-xs font-medium mb-7 shadow-sm">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
          Enterprise-grade AI for Finance
        </span>

        {/* Headline — wide enough for one line on desktop */}
        <h1
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            fontSize: "clamp(2.4rem, 5.2vw, 5rem)",
            fontWeight: 400,
            color: "#111111",
            letterSpacing: "-0.025em",
            lineHeight: 1.04,
            marginBottom: "0.9rem",
            whiteSpace: "nowrap",
          }}
          className="hidden sm:block"
        >
          One platform. Every complaint.
          <br />
          <span style={{ fontStyle: "italic", fontWeight: 300, color: "#8a8a8a" }}>
            Intelligently resolved.
          </span>
        </h1>
        {/* mobile — allow wrap */}
        <h1
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            fontSize: "2.4rem",
            fontWeight: 400,
            color: "#111111",
            letterSpacing: "-0.025em",
            lineHeight: 1.08,
            marginBottom: "0.9rem",
          }}
          className="block sm:hidden"
        >
          One platform. Every complaint.
          <br />
          <span style={{ fontStyle: "italic", fontWeight: 300, color: "#8a8a8a" }}>
            Intelligently resolved.
          </span>
        </h1>

        {/* Subtext */}
        <p style={{ color: "#6B6B6B" }} className="text-sm md:text-base leading-relaxed mb-8 max-w-[480px]">
          Consolidate complaints from WhatsApp, Email, and Branch into a unified
          AI workspace that classifies, investigates, and resolves issues with
          full regulatory grounding.
        </p>

        {/* CTAs */}
        <div className="flex flex-wrap items-center justify-center gap-3">
          <button
            type="button"
            onClick={onAskAI}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-gray-900 hover:bg-gray-800 text-white font-semibold text-sm transition-colors shadow-md"
          >
            Ask AI
            <ArrowRight size={15} />
          </button>
          <button className="inline-flex items-center gap-2.5 px-6 py-3 rounded-lg border border-gray-300 bg-white text-gray-700 text-sm font-medium hover:bg-gray-50 hover:border-gray-400 transition-all shadow-sm">
            <span className="w-5 h-5 rounded-full border border-gray-300 flex items-center justify-center flex-shrink-0 bg-white">
              <Play size={8} className="fill-gray-700 text-gray-700 ml-0.5" />
            </span>
            Watch Demo
          </button>
        </div>

        {/* Trust line */}
        <p className="mt-4 text-[11px] tracking-wide" style={{ color: "#9ca3af" }}>
          SOC2 Type II Compliant&nbsp;·&nbsp;RBI Grounding Validation&nbsp;·&nbsp;Full Audit Traceability
        </p>
      </div>

      {/* ── Browser mockup ── */}
      <div className="w-full max-w-[900px] mx-auto px-4 pb-0">
        <div className="rounded-2xl overflow-hidden border border-gray-200/70 bg-white" style={{ boxShadow: "0 20px 60px rgba(0,0,0,0.10), 0 4px 16px rgba(0,0,0,0.06)" }}>

          {/* Window chrome dots */}
          <div className="bg-[#f9f9f9] border-b border-gray-100 px-4 py-3 flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
            <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
            <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
          </div>

          {/* Tab bar + search */}
          <div className="bg-white border-b border-gray-100 px-5 flex items-center gap-6 py-3">
            {["Inbox", "Pipeline", "Analytics", "Compliance"].map((tab, i) => (
              <span
                key={tab}
                className="text-xs cursor-default select-none"
                style={{
                  fontWeight: i === 0 ? 600 : 400,
                  color: i === 0 ? "#111" : "#9ca3af",
                  borderBottom: i === 0 ? "2px solid #111" : "2px solid transparent",
                  paddingBottom: "4px",
                }}
              >
                {tab}
              </span>
            ))}
            <div className="ml-auto">
              <div
                className="px-3 py-1.5 rounded-lg border text-xs hidden sm:flex items-center gap-2"
                style={{ borderColor: "#e5e7eb", color: "#9ca3af", background: "#fafafa", width: "220px" }}
              >
                <span style={{ color: "#d1d5db" }}>⌕</span>
                Search complaints, UTRs, or customers...
              </div>
            </div>
          </div>

          {/* Filter pills + sort */}
          <div className="bg-white border-b border-gray-100 px-5 py-2.5 flex items-center gap-2">
            {["All", "Fraud", "Lending", "Dispute", "Service"].map((f, i) => (
              <span
                key={f}
                className="px-3 py-1 rounded-md text-xs cursor-default select-none"
                style={{
                  fontWeight: i === 0 ? 600 : 400,
                  background: i === 0 ? "#111" : "transparent",
                  color: i === 0 ? "#fff" : "#6b7280",
                }}
              >
                {f}
              </span>
            ))}
            <div className="ml-auto flex items-center gap-2">
              <span className="text-xs" style={{ color: "#6b7280" }}>Sort · Risk Score ↓</span>
              <span
                className="text-xs px-2.5 py-1 rounded-md border flex items-center gap-1 cursor-default"
                style={{ borderColor: "#e5e7eb", color: "#374151", background: "#fff", fontWeight: 500 }}
              >
                + Custom View
              </span>
            </div>
          </div>

          {/* Table header */}
          <div
            className="grid px-5 py-2.5 border-b border-gray-100"
            style={{ gridTemplateColumns: "2.6fr 0.8fr 1fr 1fr 0.9fr 0.7fr", gap: "12px", background: "#fafafa" }}
          >
            {["COMPLAINT SUMMARY", "CATEGORY", "CHANNEL", "RISK SCORE", "SLA STATUS", "PRIORITY"].map((h) => (
              <span key={h} className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "#9ca3af" }}>
                {h}
              </span>
            ))}
          </div>

          {/* Table rows */}
          <div className="bg-white divide-y" style={{ borderColor: "#f3f4f6" }}>
            {MOCK_ROWS.map((row) => {
              const cat = CATEGORY_COLORS[row.category] ?? { bg: "#f9fafb", text: "#374151" };
              return (
                <div
                  key={row.summary}
                  className="grid px-5 py-3 items-center cursor-default hover:bg-gray-50/60 transition-colors"
                  style={{ gridTemplateColumns: "2.6fr 0.8fr 1fr 1fr 0.9fr 0.7fr", gap: "12px" }}
                >
                  {/* Summary */}
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-gray-300 text-xs flex-shrink-0">{row.icon}</span>
                    <span className="text-xs font-medium truncate" style={{ color: "#1f2937" }}>{row.summary}</span>
                  </div>

                  {/* Category badge */}
                  <span
                    className="px-2 py-0.5 rounded text-[10px] font-semibold w-fit"
                    style={{ background: cat.bg, color: cat.text }}
                  >
                    {row.category}
                  </span>

                  {/* Channel */}
                  <span className="text-xs" style={{ color: "#6b7280" }}>{row.channel}</span>

                  {/* Risk score */}
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: "#f3f4f6", maxWidth: "72px" }}>
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${row.riskPct}%`, background: "#22c55e" }}
                      />
                    </div>
                    <span className="text-xs font-semibold" style={{ color: "#374151" }}>{row.risk}</span>
                  </div>

                  {/* Avatar stack (SLA STATUS) */}
                  <div className="flex items-center">
                    <div className="flex -space-x-1.5">
                      {row.avatars.map((av) => (
                        <span
                          key={av.label}
                          className="w-5 h-5 rounded-full flex items-center justify-center text-white border-2 border-white"
                          style={{ background: av.bg, fontSize: "7px", fontWeight: 700 }}
                        >
                          {av.label}
                        </span>
                      ))}
                      {row.extra > 0 && (
                        <span
                          className="w-5 h-5 rounded-full flex items-center justify-center border-2 border-white"
                          style={{ background: "#374151", fontSize: "7px", fontWeight: 700, color: "#fff" }}
                        >
                          +{row.extra}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Priority */}
                  <span className="text-xs font-semibold flex items-center gap-0.5" style={{ color: row.priorityColor }}>
                    <span style={{ fontSize: "10px" }}>{row.priorityIcon}</span>
                    {row.priority}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Stats Bar ────────────────────────────────────────────────────────────────

function StatsBar() {
  const stats = [
    {
      icon: Shield,
      value: "12,450+",
      label: "Complaints Processed",
      sub: "Unified across all channels",
    },
    {
      icon: Clock,
      value: "2.4 hrs",
      label: "Avg Resolution Time",
      sub: "Down 15% from last month",
    },
    {
      icon: BarChart2,
      value: "94.2%",
      label: "AI Classification Accuracy",
      sub: "NLP-powered categorization",
    },
    {
      icon: Star,
      value: "4.2/5",
      label: "Customer Satisfaction",
      sub: "Based on 12,450 responses",
    },
  ];

  return (
    <section style={{ background: "#ffffff", borderTop: "1px solid #ede9e0" }} className="py-16">
      <div className="max-w-4xl mx-auto px-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-gray-100">
          {stats.map(({ icon: Icon, value, label, sub }) => (
            <div key={label} className="flex flex-col items-center text-center px-6 py-2">
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center mb-4"
                style={{ border: "1px solid #e5e7eb", background: "#fafaf9" }}
              >
                <Icon size={15} style={{ color: "#9ca3af" }} />
              </div>
              <div
                style={{
                  fontFamily: "'Playfair Display', Georgia, serif",
                  fontSize: "clamp(1.6rem, 3vw, 2.2rem)",
                  fontWeight: 400,
                  color: "#111111",
                  letterSpacing: "-0.02em",
                  lineHeight: 1,
                }}
              >
                {value}
              </div>
              <div className="text-sm font-medium mt-2.5" style={{ color: "#374151" }}>
                {label}
              </div>
              <div className="text-xs mt-1 hidden sm:block" style={{ color: "#9ca3af" }}>
                {sub}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Analytics Section ────────────────────────────────────────────────────────

function AnalyticsSection() {
  return (
    <section id="analytics" style={{ background: "#f5f0e6" }} className="py-20 md:py-28">
      <div className="max-w-5xl mx-auto px-6 lg:px-8">
        <div className="text-center mb-14">
          <span
            className="inline-block uppercase tracking-[0.15em] mb-4"
            style={{ fontSize: "11px", color: "#9ca3af", fontWeight: 500, letterSpacing: "0.15em" }}
          >
            Analytics &amp; Insights
          </span>
          <h2
            style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              fontSize: "clamp(1.9rem, 4vw, 3rem)",
              fontWeight: 400,
              color: "#111111",
              letterSpacing: "-0.02em",
              lineHeight: 1.1,
            }}
          >
            Real-time intelligence,<br />
            <span style={{ fontStyle: "italic", fontWeight: 300, color: "#8a8a8a" }}>at your fingertips.</span>
          </h2>
          <p className="mt-4 max-w-xl mx-auto text-sm leading-relaxed" style={{ color: "#6b7280" }}>
            Monitor complaint trends, sentiment distribution, SLA compliance,
            and agent health — all from a single unified command center.
          </p>
        </div>

        {/* Browser mockup */}
        <div className="max-w-4xl mx-auto">
          <div
            className="rounded-2xl overflow-hidden border bg-white"
            style={{ borderColor: "#e5e7eb", boxShadow: "0 20px 60px rgba(0,0,0,0.09), 0 4px 16px rgba(0,0,0,0.05)" }}
          >
            {/* Chrome dots */}
            <div className="bg-[#f9f9f9] border-b px-4 py-3 flex items-center gap-1.5" style={{ borderColor: "#f0ede6" }}>
              <div className="w-3 h-3 rounded-full bg-[#ff5f56]" />
              <div className="w-3 h-3 rounded-full bg-[#ffbd2e]" />
              <div className="w-3 h-3 rounded-full bg-[#27c93f]" />
              <div className="hidden sm:flex items-center gap-1.5 ml-auto bg-white rounded-md px-2.5 py-1 text-xs border" style={{ borderColor: "#e5e7eb", color: "#9ca3af" }}>
                <Clock size={10} style={{ color: "#9ca3af" }} />
                <span style={{ color: "#374151", fontWeight: 600 }}>2.4 hrs</span>
                <span>Avg Resolution</span>
              </div>
            </div>
            {/* Image */}
            <div className="relative">
              <img
                src={IMG.analytics}
                alt="Customer service analytics platform"
                className="w-full h-56 sm:h-72 md:h-96 object-cover object-top"
              />
              <div
                className="absolute bottom-4 left-4 bg-white rounded-xl px-4 py-2.5 flex items-center gap-2"
                style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.10)" }}
              >
                <BarChart2 size={15} style={{ color: "#6b7280" }} />
                <div>
                  <div className="font-semibold text-sm leading-none" style={{ color: "#111" }}>15K+</div>
                  <div className="text-xs mt-0.5" style={{ color: "#9ca3af" }}>Processed Today</div>
                </div>
              </div>
              <div
                className="absolute top-4 right-4 bg-white rounded-xl px-3 py-2 flex items-center gap-2"
                style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.10)" }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <span className="text-xs font-medium" style={{ color: "#374151" }}>System Active</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Features Section ─────────────────────────────────────────────────────────

function FeaturesSection() {
  const features = [
    {
      icon: Tag,
      label: "NLP-Powered Categorization",
      desc: "Gen-AI automatically classifies complaints by type, product, severity, and sentiment using advanced transformer-based NLP models.",
    },
    {
      icon: Eye,
      label: "360° Complaint Visibility",
      desc: "Comprehensive view of each complaint with full communication history, SLA tracking, escalation management, and regulatory reporting.",
    },
    {
      icon: Zap,
      label: "Automated Response Drafts",
      desc: "AI generates personalized draft responses for agent review, suggests resolution templates, and identifies duplicate complaints.",
    },
    {
      icon: BarChart2,
      label: "Real-Time Analytics",
      desc: "Live dashboards showing complaint trends, sentiment analysis, resolution rates, and geographic distribution across all channels.",
    },
    {
      icon: Heart,
      label: "Customer Satisfaction Tracking",
      desc: "CSAT scores, NPS metrics, verbatim feedback analysis, and AI-identified improvement areas to drive continuous service enhancement.",
    },
    {
      icon: TrendingUp,
      label: "Feedback Intelligence",
      desc: "Automated feedback collection with AI-powered sentiment analysis, trend identification, and actionable improvement recommendations.",
    },
  ];

  return (
    <section id="features" style={{ background: "#ffffff" }} className="py-20 md:py-28">
      <div className="max-w-5xl mx-auto px-6 lg:px-8">
        <div className="text-center mb-16">
          <span
            className="inline-block uppercase tracking-[0.15em] mb-4"
            style={{ fontSize: "11px", color: "#9ca3af", fontWeight: 500 }}
          >
            Capabilities
          </span>
          <h2
            style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              fontSize: "clamp(1.9rem, 4vw, 3rem)",
              fontWeight: 400,
              color: "#111111",
              letterSpacing: "-0.02em",
              lineHeight: 1.1,
            }}
          >
            Gen-AI powered complaint management
          </h2>
          <p className="mt-4 max-w-xl mx-auto text-sm leading-relaxed" style={{ color: "#6b7280" }}>
            Transform how Union Bank handles customer complaints with AI-driven
            insights, automated workflows, and comprehensive analytics.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map(({ icon: Icon, label, desc }) => (
            <div
              key={label}
              className="rounded-2xl p-6 group cursor-default transition-all"
              style={{
                border: "1px solid #f0ede6",
                background: "#faf9f7",
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = "0 8px 32px rgba(0,0,0,0.07)"; (e.currentTarget as HTMLDivElement).style.background = "#fff"; }}
              onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = "none"; (e.currentTarget as HTMLDivElement).style.background = "#faf9f7"; }}
            >
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center mb-5"
                style={{ border: "1px solid #e5e7eb", background: "#fff" }}
              >
                <Icon size={15} style={{ color: "#6b7280" }} />
              </div>
              <h3 className="font-semibold text-sm mb-2.5" style={{ color: "#111111" }}>
                {label}
              </h3>
              <p className="text-sm leading-relaxed mb-5" style={{ color: "#6b7280" }}>
                {desc}
              </p>
              <Link
                to="/complaint"
                className="inline-flex items-center gap-1.5 text-sm font-medium group-hover:gap-2.5 transition-all"
                style={{ color: "#374151" }}
              >
                Learn more <ArrowRight size={12} />
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── CTA Section ─────────────────────────────────────────────────────────────

function CTASection() {
  return (
    <section style={{ background: "#f5f0e6" }} className="py-20 md:py-28">
      <div className="max-w-5xl mx-auto px-6 lg:px-8 grid md:grid-cols-2 gap-12 md:gap-20 items-center">
        <div
          className="rounded-2xl overflow-hidden order-2 md:order-1"
          style={{ boxShadow: "0 20px 60px rgba(0,0,0,0.09), 0 4px 16px rgba(0,0,0,0.05)" }}
        >
          <img
            src={IMG.handle}
            alt="Handling customer complaints"
            className="w-full h-64 md:h-80 object-cover object-center"
          />
        </div>
        <div className="order-1 md:order-2">
          <span
            className="inline-block uppercase tracking-[0.15em] mb-4"
            style={{ fontSize: "11px", color: "#9ca3af", fontWeight: 500 }}
          >
            Ready to Transform?
          </span>
          <h2
            style={{
              fontFamily: "'Playfair Display', Georgia, serif",
              fontSize: "clamp(1.8rem, 3.5vw, 2.6rem)",
              fontWeight: 400,
              color: "#111111",
              letterSpacing: "-0.02em",
              lineHeight: 1.15,
              marginBottom: "1rem",
            }}
          >
            Start resolving complaints<br />
            <span style={{ fontStyle: "italic", fontWeight: 300, color: "#8a8a8a" }}>smarter, and faster.</span>
          </h2>
          <p className="text-sm leading-relaxed mb-8" style={{ color: "#6b7280" }}>
            Join Union Bank's AI-powered complaint management platform and
            deliver faster resolutions, higher satisfaction, and full regulatory
            compliance — all in one unified dashboard.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              to="/complaint"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-white font-semibold text-sm transition-colors"
              style={{ background: "#111111" }}
            >
              Get Started Now <ArrowRight size={14} />
            </Link>
            <a
              href="#Reach Out"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg text-sm font-medium transition-all"
              style={{ border: "1px solid #d1d5db", color: "#374151", background: "#fff" }}
            >
              Learn More
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Omnichannel Section ──────────────────────────────────────────────────────

const CHANNEL_PILLS = ["WhatsApp", "Email", "Mobile Banking", "Call Center", "Branch Portal", "Web Portal"];

// Hub icon nodes: [icon, dark-bg?, top%, left%]
const HUB_NODES: { icon: React.ElementType; dark?: boolean; top: number; left: number }[] = [
  { icon: Mail,       dark: false, top: 4,  left: 28 },
  { icon: Globe,      dark: false, top: 4,  left: 68 },
  { icon: Phone,      dark: false, top: 42, left: 6  },
  { icon: Building2,  dark: false, top: 80, left: 28 },
  { icon: Share2,     dark: false, top: 80, left: 68 },
];

function OmnichannelSection() {
  return (
    <section style={{ background: "#f5f0e6" }} className="py-20 md:py-28">
      <div className="max-w-5xl mx-auto px-6 lg:px-8">
        <div className="grid md:grid-cols-2 gap-16 items-center">

          {/* ── Left: copy ── */}
          <div>
            <span
              className="inline-block uppercase tracking-[0.15em] mb-5"
              style={{ fontSize: "11px", color: "#9ca3af", fontWeight: 500 }}
            >
              Omnichannel Connectivity
            </span>
            <h2
              style={{
                fontFamily: "'Playfair Display', Georgia, serif",
                fontSize: "clamp(2rem, 4vw, 3rem)",
                fontWeight: 400,
                color: "#111111",
                letterSpacing: "-0.025em",
                lineHeight: 1.1,
                marginBottom: "1.2rem",
              }}
            >
              Sync every channel.<br />
              <span style={{ fontStyle: "italic", fontWeight: 300, color: "#8a8a8a" }}>
                Own the resolution.
              </span>
            </h2>
            <p className="text-sm leading-relaxed mb-8 max-w-sm" style={{ color: "#6b7280" }}>
              Our platform acts as a unified layer over your existing
              communication stack, ingesting complaints from WhatsApp, Email,
              and Branch portals into a single AI-powered pipeline. No data
              silos, just total visibility.
            </p>
            {/* Channel pills */}
            <div className="flex flex-wrap gap-2">
              {CHANNEL_PILLS.map((ch) => (
                <span
                  key={ch}
                  className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-sm cursor-default"
                  style={{ border: "1px solid #d1cfc8", color: "#374151", background: "transparent" }}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                  {ch}
                </span>
              ))}
            </div>
          </div>

          {/* ── Right: hub diagram ── */}
          <div className="relative hidden md:block" style={{ height: "340px" }}>
            {/* SVG dashed lines from center to each node */}
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none"
              style={{ zIndex: 0 }}
            >
              {HUB_NODES.map((n, i) => {
                const cx = 52, cy = 42; // center node % of 100
                return (
                  <line
                    key={i}
                    x1={`${cx}%`} y1={`${cy}%`}
                    x2={`${n.left + 4}%`} y2={`${n.top + 4}%`}
                    stroke="#d1cfc8"
                    strokeWidth="1"
                    strokeDasharray="4 4"
                  />
                );
              })}
              {/* Line to right dark node */}
              <line
                x1="52%" y1="42%"
                x2="92%" y2="42%"
                stroke="#d1cfc8"
                strokeWidth="1"
                strokeDasharray="4 4"
              />
            </svg>

            {/* Surrounding white icon cards */}
            {HUB_NODES.map(({ icon: Icon, top, left }) => (
              <div
                key={`${top}-${left}`}
                className="absolute flex items-center justify-center rounded-2xl"
                style={{
                  top: `${top}%`, left: `${left}%`,
                  width: "52px", height: "52px",
                  background: "#fff",
                  border: "1px solid #e5e7eb",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                  zIndex: 1,
                }}
              >
                <Icon size={20} style={{ color: "#6b7280" }} />
              </div>
            ))}

            {/* Center hub — dark */}
            <div
              className="absolute flex items-center justify-center rounded-2xl"
              style={{
                top: "34%", left: "44%",
                width: "60px", height: "60px",
                background: "#111111",
                boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
                zIndex: 2,
              }}
            >
              <Smartphone size={24} style={{ color: "#fff" }} />
            </div>

            {/* Far-right dark node */}
            <div
              className="absolute flex items-center justify-center rounded-2xl"
              style={{
                top: "34%", left: "84%",
                width: "52px", height: "52px",
                background: "#111111",
                boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
                zIndex: 2,
              }}
            >
              <Globe size={20} style={{ color: "#fff" }} />
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}

// ─── Footer ───────────────────────────────────────────────────────────────────

const FOOTER_QUESTIONS = [
  "How does it verify RBI compliance?",
  "Can it merge WhatsApp and Email tickets?",
  "What is the grounding accuracy score?",
  "Is the decision trail audit-ready?",
];

const FOOTER_COLS = [
  {
    heading: "Platform",
    links: ["Analytics Dashboard", "AI Performance", "Complaints Table", "AI Reach Out"],
  },
  {
    heading: "Solutions",
    links: ["Retail Banking", "Corporate Banking", "NRI Services", "Digital Banking"],
  },
  {
    heading: "Resources",
    links: ["Documentation", "API Reference", "Compliance Guide", "Security Whitepaper"],
  },
  {
    heading: "Company",
    links: ["About", "Careers", "Privacy Policy", "Terms of Service"],
  },
];

function Footer() {
  return (
    <footer style={{ background: "#f5f0e6", borderTop: "1px solid #ede9e0" }}>
      {/* Pre-footer CTA */}
      <div className="max-w-5xl mx-auto px-6 lg:px-8 pt-16 pb-14" style={{ borderBottom: "1px solid #ede9e0" }}>
        <h2
          className="mb-6 flex items-center gap-2"
          style={{
            fontFamily: "'Playfair Display', Georgia, serif",
            fontSize: "clamp(1.4rem, 3vw, 2rem)",
            fontWeight: 400,
            color: "#111111",
            letterSpacing: "-0.02em",
          }}
        >
          Ask about the intelligence layer
          <ArrowRight size={20} style={{ color: "#6b7280", marginTop: "2px" }} />
        </h2>
        <div className="flex flex-wrap gap-2">
          {FOOTER_QUESTIONS.map((q) => (
            <span
              key={q}
              className="px-4 py-2 rounded-full text-sm cursor-default transition-colors"
              style={{ border: "1px solid #d1cfc8", color: "#374151", background: "transparent" }}
              onMouseEnter={e => { (e.currentTarget as HTMLSpanElement).style.background = "#fff"; }}
              onMouseLeave={e => { (e.currentTarget as HTMLSpanElement).style.background = "transparent"; }}
            >
              {q}
            </span>
          ))}
        </div>
      </div>

      {/* Main footer grid */}
      <div className="max-w-5xl mx-auto px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-10 lg:gap-8">
          {/* Brand */}
          <div className="lg:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <div className="bg-white rounded-lg px-2 py-1.5 inline-flex border" style={{ borderColor: "#ede9e0" }}>
                <img src="/logo.jpeg" alt="Union Bank of India" className="h-6 w-auto object-contain" />
              </div>
              <span className="text-sm font-medium" style={{ color: "#111111" }}>Union Bank</span>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: "#9ca3af" }}>
              The intelligent workspace for modern financial institutions to resolve every customer complaint.
            </p>
          </div>

          {/* Nav columns */}
          {FOOTER_COLS.map(({ heading, links }) => (
            <div key={heading}>
              <h4
                className="mb-4 uppercase tracking-[0.12em]"
                style={{ fontSize: "11px", color: "#9ca3af", fontWeight: 600 }}
              >
                {heading}
              </h4>
              <ul className="space-y-3">
                {links.map((item) => (
                  <li key={item}>
                    <Link
                      to="/complaint"
                      className="text-sm transition-colors"
                      style={{ color: "#374151" }}
                      onMouseEnter={e => (e.currentTarget.style.color = "#111111")}
                      onMouseLeave={e => (e.currentTarget.style.color = "#374151")}
                    >
                      {item}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-12 pt-6 flex flex-col sm:flex-row items-center justify-between gap-3" style={{ borderTop: "1px solid #ede9e0" }}>
          <p className="text-xs" style={{ color: "#9ca3af" }}>
            © 2026 Union Bank of India Complaint Resolution Platform.
          </p>
          <p className="text-xs" style={{ color: "#9ca3af" }}>
            Designed and engineered in Jamshedpur, India.
          </p>
        </div>
      </div>
    </footer>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  const [chatbotOpen, setChatbotOpen] = useState(false);
  return (
    <div className="min-h-screen font-sans">
      <AppHeader variant="landing" />
      <HeroSection onAskAI={() => setChatbotOpen(true)} />
      <StatsBar />
      <ComplaintReachSection />
      <AnalyticsSection />
      <FeaturesSection />
      <CTASection />
      <OmnichannelSection />
      <ChannelsDemoSection />
      <Footer />
      <ChatbotLauncher onClick={() => setChatbotOpen(true)} />
      {chatbotOpen && <ChatbotWindow onClose={() => setChatbotOpen(false)} />}
    </div>
  );
}
