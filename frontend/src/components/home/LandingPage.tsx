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
  Activity,
  Clock,
  TrendingUp,
  Star,
  Eye,
  Phone,
  Mail,
  MapPin,
  Globe,
  Share2,
  Smartphone,
  Building2,
} from "lucide-react";
import ChatbotLauncher from "../chatbot/ChatbotLauncher";
import ChatbotWindow from "../chatbot/ChatbotWindow";
import { useState } from "react";

const IMG = {
  hero: "/handshake.png",
  pipeline: "/deescalate.webp",
  analytics: "/listen.jpg",
  handle: "/handle.webp",
};

// ─── Hero ─────────────────────────────────────────────────────────────────────

function HeroSection({ onAskAI }: { onAskAI: () => void }) {
  return (
    <section
      id="top"
      className="relative flex items-center"
      style={{
        minHeight: "88vh",
        backgroundImage: `url('${IMG.hero}')`,
        backgroundSize: "cover",
        backgroundPosition: "center",
        paddingTop: "64px", // navbar height
      }}
    >
      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-r from-[#001A4D]/96 via-[#002f87]/90 to-[#001A4D]/50" />

      <div className="relative w-full max-w-7xl mx-auto px-6 lg:px-8 py-16 lg:py-24 grid lg:grid-cols-[54%_46%] gap-8 lg:gap-12 items-center">
        {/* ── Left: headline + CTAs ── */}
        <div>
          <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-black/50 border border-white/10 text-amber-400 text-xs font-semibold mb-7">
            <Zap size={11} fill="currentColor" />
            Gen-AI Powered Platform
          </span>

          <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-[3.25rem] font-extrabold text-white leading-[1.08] tracking-tight mb-5">
            Intelligent Complaint
            <br />
            Resolution Ecosystem
          </h1>

          <p className="text-slate-800 text-base md:text-lg leading-relaxed mb-9 max-w-[520px]">
            Unified dashboard leveraging Gen-AI for seamless complaint
            management across all banking channels with NLP-powered insights and
            automated resolution.
          </p>

          <div className="flex flex-wrap items-center gap-3 md:gap-4">
            <button
              type="button"
              onClick={onAskAI}
              className="inline-flex items-center gap-2 px-6 md:px-8 py-3 md:py-3.5 rounded-lg bg-amber-400 hover:bg-amber-500 text-gray-900 font-bold text-sm transition-colors shadow-lg shadow-amber-400/20"
            >
              Ask AI
              <ArrowRight size={16} />
            </button>
            <button className="inline-flex items-center gap-2.5 px-6 md:px-8 py-3 md:py-3.5 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-100 hover:border-slate-400 hover:text-slate-900 transition-all">
              <span className="w-6 h-6 rounded-full border border-slate-300 flex items-center justify-center flex-shrink-0 bg-white shadow-sm">
                <Play size={9} className="fill-slate-700 text-slate-700" />
              </span>
              Watch Demo
            </button>
          </div>
        </div>

        {/* ── Right: truly floating stat cards ── */}
        <div className="hidden lg:block relative h-[440px] w-full">
          {/* Card 1 — Avg Response Time (top-right, white) */}
          <div
            className="absolute top-0 right-0 z-30 bg-white rounded-2xl px-5 py-4 shadow-2xl flex items-center gap-3.5 border border-gray-50 animate-float"
            style={{ animationDelay: "0s" }}
          >
            <div className="w-11 h-11 rounded-xl bg-amber-100 flex items-center justify-center flex-shrink-0">
              <Clock size={20} className="text-amber-500" />
            </div>
            <div>
              <div className="text-gray-900 font-extrabold text-2xl leading-none">
                2.5hr
              </div>
              <div className="text-gray-400 text-xs mt-1">
                Avg Response Time
              </div>
            </div>
          </div>

          {/* Card 2 — Live Dashboard (center, glassmorphism, main) */}
          <div
            className="absolute top-16 left-0 z-20 w-[82%] bg-white/10 backdrop-blur-md rounded-2xl p-5 border border-white/20 shadow-xl animate-float"
            style={{ animationDelay: "0.8s" }}
          >
            <div className="flex items-center gap-2 mb-4">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-dot" />
              <span className="text-white text-sm font-semibold">
                Live Dashboard
              </span>
              <span className="ml-auto text-blue-300/80 text-xs">
                Updated now
              </span>
            </div>
            <div className="flex items-end gap-10 mb-5">
              <div>
                <div className="text-white text-4xl font-extrabold">15K+</div>
                <div className="text-blue-300 text-xs mt-1">
                  Complaints Processed
                </div>
              </div>
              <div>
                <div className="text-blue-200 text-xs mb-1">Resolved</div>
                <div className="text-white text-2xl font-bold">10,578</div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1 bg-white/10 rounded-full h-2">
                <div
                  className="h-2 rounded-full bg-emerald-400"
                  style={{ width: "70%" }}
                />
              </div>
              <div className="text-right flex-shrink-0">
                <span className="text-emerald-400 font-extrabold text-sm">
                  98%
                </span>
                <span className="text-blue-300 text-xs ml-1.5">
                  Resolution Rate
                </span>
              </div>
            </div>
          </div>

          {/* Card 3 — AI Accuracy (mid-right, white) */}
          <div
            className="absolute top-[185px] right-0 z-30 bg-white rounded-xl px-4 py-3 shadow-xl flex items-center gap-3 border border-gray-50 animate-float"
            style={{ animationDelay: "1.6s" }}
          >
            <div className="w-9 h-9 rounded-lg bg-ub-blue/10 flex items-center justify-center flex-shrink-0">
              <BarChart2 size={16} className="text-ub-blue" />
            </div>
            <div>
              <div className="text-gray-900 font-extrabold text-lg leading-none">
                94.2%
              </div>
              <div className="text-gray-400 text-xs mt-0.5">AI Accuracy</div>
            </div>
          </div>

          {/* Card 4 — Customer Satisfaction (bottom-left, white) */}
          <div
            className="absolute bottom-12 left-0 z-30 bg-white rounded-xl px-4 py-3 shadow-xl border border-gray-50 animate-float"
            style={{ animationDelay: "2.4s" }}
          >
            <div className="text-gray-400 text-[11px] mb-2">
              Customer Satisfaction
            </div>
            <div className="flex items-center gap-2.5">
              <div className="flex gap-0.5">
                {[...Array(4)].map((_, i) => (
                  <Star
                    key={i}
                    size={13}
                    fill="#fbbf24"
                    className="text-amber-400"
                  />
                ))}
                <Star size={13} className="text-gray-200" fill="#e5e7eb" />
              </div>
              <span className="text-gray-900 font-extrabold text-base">
                4.2/5
              </span>
            </div>
          </div>

          {/* Card 5 — Agents Active (bottom-right, white) */}
          <div
            className="absolute bottom-0 right-0 z-30 bg-white rounded-xl px-4 py-3 shadow-xl flex items-center gap-3 border border-gray-50 animate-float"
            style={{ animationDelay: "0.4s" }}
          >
            <div className="w-9 h-9 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
              <Activity size={16} className="text-emerald-600" />
            </div>
            <div>
              <div className="text-gray-900 font-bold text-sm leading-none">
                6 Agents Active
              </div>
              <div className="flex items-center gap-1.5 mt-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <span className="text-emerald-500 text-xs font-medium">
                  Online · 92.4% confidence
                </span>
              </div>
            </div>
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
    <section className="bg-[#f5ecda] py-14">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 md:gap-12">
          {stats.map(({ icon: Icon, value, label, sub }) => (
            <div key={label} className="flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-full bg-white border border-gray-200 shadow-sm flex items-center justify-center mb-4">
                <Icon size={22} className="text-ub-blue" />
              </div>
              <div className="text-ub-blue font-extrabold text-2xl md:text-3xl">
                {value}
              </div>
              <div className="text-gray-800 font-semibold text-sm mt-1">
                {label}
              </div>
              <div className="text-gray-400 text-xs mt-0.5 hidden sm:block">
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
    <section id="analytics" className="py-16 md:py-24 bg-gray-50">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="text-center mb-12">
          <div className="text-ub-blue text-xs font-bold uppercase tracking-[0.15em] mb-3">
            Analytics &amp; Insights
          </div>
          <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900">
            Real-Time Intelligence at Your Fingertips
          </h2>
          <p className="text-gray-400 mt-4 max-w-2xl mx-auto text-sm md:text-[15px] leading-relaxed">
            Monitor complaint trends, sentiment distribution, SLA compliance,
            and agent health — all from a single unified command center.
          </p>
        </div>

        {/* Browser mockup */}
        <div className="max-w-4xl mx-auto">
          <div className="rounded-2xl overflow-hidden shadow-2xl border border-gray-200 bg-white">
            {/* Chrome bar */}
            <div className="bg-gray-100 px-4 py-3 flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-400 flex-shrink-0" />
              <div className="w-3 h-3 rounded-full bg-yellow-400 flex-shrink-0" />
              <div className="w-3 h-3 rounded-full bg-green-400 flex-shrink-0" />
              <div className="flex-1 mx-4 min-w-0">
                <div className="bg-white rounded px-3 py-1 text-xs text-gray-400 text-center shadow-sm truncate">
                  complaint-intelligence-hub.unionbank.in
                </div>
              </div>
              <div className="hidden sm:flex items-center gap-1.5 bg-white rounded-lg px-3 py-1 shadow text-xs border border-gray-100 flex-shrink-0">
                <Clock size={11} className="text-ub-red" />
                <span className="font-semibold text-gray-700">2.4 hrs</span>
                <span className="text-gray-400">Avg Resolution</span>
              </div>
            </div>
            {/* Image */}
            <div className="relative">
              <img
                src={IMG.analytics}
                alt="Customer service analytics platform"
                className="w-full h-56 sm:h-72 md:h-96 object-cover object-top"
              />
              <div className="absolute bottom-4 left-4 bg-white rounded-xl px-4 py-2.5 shadow-xl flex items-center gap-2">
                <BarChart2 size={16} className="text-blue-500" />
                <div>
                  <div className="font-extrabold text-gray-900 text-sm leading-none">
                    15K+
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    Processed Today
                  </div>
                </div>
              </div>
              <div className="absolute top-4 right-4 bg-white rounded-xl px-3 py-2 shadow-xl flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="text-xs font-semibold text-gray-700">
                  System Active
                </span>
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
      color: "bg-purple-700",
      label: "NLP-Powered Categorization",
      desc: "Gen-AI automatically classifies complaints by type, product, severity, and sentiment using advanced transformer-based NLP models.",
    },
    {
      icon: Eye,
      color: "bg-purple-500",
      label: "360° Complaint Visibility",
      desc: "Comprehensive view of each complaint with full communication history, SLA tracking, escalation management, and regulatory reporting.",
    },
    {
      icon: Zap,
      color: "bg-green-600",
      label: "Automated Response Drafts",
      desc: "AI generates personalized draft responses for agent review, suggests resolution templates, and identifies duplicate complaints.",
    },
    {
      icon: BarChart2,
      color: "bg-ub-blue",
      label: "Real-Time Analytics",
      desc: "Live dashboards showing complaint trends, sentiment analysis, resolution rates, and geographic distribution across all channels.",
    },
    {
      icon: Heart,
      color: "bg-amber-500",
      label: "Customer Satisfaction Tracking",
      desc: "CSAT scores, NPS metrics, verbatim feedback analysis, and AI-identified improvement areas to drive continuous service enhancement.",
    },
    {
      icon: TrendingUp,
      color: "bg-ub-red",
      label: "Feedback Intelligence",
      desc: "Automated feedback collection with AI-powered sentiment analysis, trend identification, and actionable improvement recommendations.",
    },
  ];

  return (
    <section id="features" className="py-16 md:py-24 bg-white">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900">
            Gen-AI Powered Complaint Management
          </h2>
          <p className="text-gray-400 mt-4 max-w-3xl mx-auto text-sm md:text-[15px] leading-relaxed">
            Transform how Union Bank handles customer complaints with AI-driven
            insights, automated workflows, and comprehensive analytics.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
          {features.map(({ icon: Icon, color, label, desc }) => (
            <div
              key={label}
              className="border border-gray-100 rounded-xl p-6 hover:shadow-lg transition-shadow group cursor-default"
            >
              <div
                className={`w-12 h-12 rounded-full ${color} flex items-center justify-center mb-5`}
              >
                <Icon size={20} className="text-white" />
              </div>
              <h3 className="text-gray-900 font-bold text-base mb-2">
                {label}
              </h3>
              <p className="text-gray-400 text-sm leading-relaxed mb-5">
                {desc}
              </p>
              <Link
                to="/complaint"
                className="inline-flex items-center gap-1.5 text-amber-500 font-semibold text-sm group-hover:gap-3 transition-all"
              >
                Learn More <ArrowRight size={13} />
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
    <section className="py-16 md:py-20 bg-gray-50">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 grid md:grid-cols-2 gap-10 md:gap-16 items-center">
        <div className="rounded-2xl overflow-hidden shadow-xl order-2 md:order-1">
          <img
            src={IMG.handle}
            alt="Handling customer complaints"
            className="w-full h-64 md:h-80 object-cover object-center"
          />
        </div>
        <div className="order-1 md:order-2">
          <div className="text-ub-blue text-xs font-bold uppercase tracking-[0.15em] mb-3">
            Ready to Transform?
          </div>
          <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 mb-4 leading-tight">
            Start Resolving Complaints Smarter, Faster
          </h2>
          <p className="text-gray-500 text-sm md:text-base leading-relaxed mb-8">
            Join Union Bank's AI-powered complaint management platform and
            deliver faster resolutions, higher satisfaction, and full regulatory
            compliance — all in one unified dashboard.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              to="/complaint"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-lg bg-ub-blue text-white font-bold text-sm hover:bg-ub-blue-dark transition-colors shadow-lg shadow-blue-900/20"
            >
              Get Started Now <ArrowRight size={16} />
            </Link>
            <a
              href="#Reach Out"
              className="inline-flex items-center gap-2 px-6 py-3.5 rounded-lg border border-gray-200 text-gray-700 font-semibold text-sm hover:bg-gray-100 transition-colors"
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

function OmnichannelSection() {
  const channels = [
    {
      icon: Building2,
      label: "Branch",
      count: "4,200 complaints",
      color: "bg-slate-500",
    },
    {
      icon: Phone,
      label: "Phone",
      count: "3,800 complaints",
      color: "bg-teal-500",
    },
    {
      icon: Mail,
      label: "Email",
      count: "2,800 complaints",
      color: "bg-green-600",
    },
    {
      icon: Smartphone,
      label: "Mobile App",
      count: "3,400 complaints",
      color: "bg-purple-600",
    },
    {
      icon: Globe,
      label: "Web Portal",
      count: "2,900 complaints",
      color: "bg-orange-500",
    },
    {
      icon: Share2,
      label: "Social Media",
      count: "1,200 complaints",
      color: "bg-ub-red",
    },
  ];

  return (
    <section className="py-16 md:py-24 bg-ub-blue">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="text-center mb-12">
          <span className="inline-block px-4 py-1.5 rounded-full bg-white/10 text-white/80 text-xs font-semibold uppercase tracking-wider mb-5">
            Omnichannel
          </span>
          <h2 className="text-3xl md:text-4xl font-extrabold text-white">
            All Channels, One Platform
          </h2>
          <p className="text-blue-200 mt-4 max-w-2xl mx-auto text-sm md:text-[15px] leading-relaxed">
            Seamlessly aggregate complaints from every customer touchpoint into
            a unified Gen-AI powered dashboard.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 md:gap-4">
          {channels.map(({ icon: Icon, label, count, color }) => (
            <div
              key={label}
              className="flex flex-col items-center text-center p-4 md:p-5 rounded-xl border border-white/15 bg-white/5 hover:bg-white/10 transition-colors"
            >
              <div
                className={`w-12 h-12 rounded-full ${color} flex items-center justify-center mb-3 shadow-lg flex-shrink-0`}
              >
                <Icon size={20} className="text-white" />
              </div>
              <div className="text-white font-bold text-sm mb-1">{label}</div>
              <div className="text-blue-200 text-xs mb-2.5">{count}</div>
              <div className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <span className="text-emerald-400 text-xs font-medium">
                  Active
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Footer ───────────────────────────────────────────────────────────────────

function Footer() {
  const platform = [
    "Analytics Dashboard",
    "AI Performance",
    "Complaints Table",
    "AI Reach Out",
  ];
  const insights = [
    "Customer Satisfaction",
    "Feedback Center",
    "SLA Tracking",
    "Trend Analysis",
  ];
  const legal = ["Privacy Policy", "Terms of Service", "Regulatory Compliance"];

  return (
    <footer className="bg-[#001A4D]">
      <div className="max-w-7xl mx-auto px-6 lg:px-8 pt-14 pb-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10 lg:gap-12 mb-12">
          {/* Brand */}
          <div className="sm:col-span-2 lg:col-span-1">
            <div className="bg-white rounded-lg px-3 py-2 inline-flex mb-5">
              <img
                src="/logo.jpeg"
                alt="Union Bank of India"
                className="h-9 w-auto object-contain"
              />
            </div>
            <p className="text-blue-300/80 text-sm leading-relaxed">
              Unified Customer Complaint Communication Dashboard powered by
              Gen-AI for seamless complaint management across all banking
              channels.
            </p>
          </div>

          {/* Platform */}
          <div>
            <h4 className="text-white font-bold text-sm mb-5">Platform</h4>
            <ul className="space-y-3.5">
              {platform.map((item) => (
                <li key={item}>
                  <Link
                    to="/complaint"
                    className="text-blue-300/70 text-sm hover:text-white transition-colors"
                  >
                    {item}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Insights */}
          <div>
            <h4 className="text-white font-bold text-sm mb-5">Insights</h4>
            <ul className="space-y-3.5">
              {insights.map((item) => (
                <li key={item}>
                  <Link
                    to="/complaint"
                    className="text-blue-300/70 text-sm hover:text-white transition-colors"
                  >
                    {item}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Contact */}
          <div>
            <h4 className="text-white font-bold text-sm mb-5">Contact</h4>
            <ul className="space-y-4">
              <li className="flex items-start gap-3">
                <Phone
                  size={14}
                  className="text-blue-400 mt-0.5 flex-shrink-0"
                />
                <span className="text-blue-300/70 text-sm">1800 22 22 44</span>
              </li>
              <li className="flex items-start gap-3">
                <Mail
                  size={14}
                  className="text-blue-400 mt-0.5 flex-shrink-0"
                />
                <span className="text-blue-300/70 text-sm break-all">
                  contact@unionbankofindia.co.in
                </span>
              </li>
              <li className="flex items-start gap-3">
                <MapPin
                  size={14}
                  className="text-blue-400 mt-0.5 flex-shrink-0"
                />
                <span className="text-blue-300/70 text-sm">
                  Union Bank Bhavan, Nariman Point, Mumbai
                </span>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="border-t border-white/10 pt-7 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-blue-400/40 text-xs">
            © 2026 Union Bank of India. All rights reserved.
          </p>
          <div className="flex items-center gap-2 flex-wrap justify-center">
            {legal.map((item, i) => (
              <span key={item} className="flex items-center gap-2">
                <a
                  href="#"
                  className="text-blue-400/40 text-xs hover:text-white/70 transition-colors"
                >
                  {item}
                </a>
                {i < legal.length - 1 && (
                  <span className="text-white/15 text-xs">•</span>
                )}
              </span>
            ))}
          </div>
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
      <Footer />
      <ChatbotLauncher onClick={() => setChatbotOpen(true)} />
      {chatbotOpen && <ChatbotWindow onClose={() => setChatbotOpen(false)} />}
    </div>
  );
}
