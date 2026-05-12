/**
 * ChannelsDemoSection
 *
 * Shows how each complaint intake channel works — with a live interactive demo
 * judges can trigger right from the browser — and a "Production Path" block
 * explaining exactly what small change is needed to go live.
 *
 * Email   → Live & working (send a real email)
 * Twitter → Simulated     (click a tweet card to submit)
 * IVR     → Simulated     (listen to call audio, click to submit)
 */

import { useState } from "react";
import {
  Mail,
  Phone,
  Twitter,
  Copy,
  Check,
  Loader2,
  ChevronDown,
  ArrowRight,
  Play,
  CheckCircle2,
  Zap,
  AlertTriangle,
  ExternalLink,
  Radio,
} from "lucide-react";
import { apiPost } from "../../lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DemoResult {
  complaint_id: string;
  channel: string;
  message: string;
}

type DemoState = "idle" | "loading" | "success" | "error";

// ─── Static data (mirrors the simulators) ─────────────────────────────────────

const SAMPLE_TWEETS = [
  {
    index: 0,
    username: "@rahul_sharma92",
    preview: "UPI payment of ₹15,000 failed but amount got deducted. Please help urgently!",
    full: "@UnionBankOfIndia my UPI payment of ₹15,000 failed but amount got deducted from my account. Transaction ID: UPI2026050812345.",
  },
  {
    index: 1,
    username: "@priya_mumbai",
    preview: "ATM swallowed my card and didn't dispense cash. 3 days with no resolution!",
    full: "@UnionBankOfIndia ATM at Andheri branch swallowed my card and didn't dispense cash. Waiting 3 days. Completely unacceptable!",
  },
  {
    index: 2,
    username: "@amit_delhi_ncr",
    preview: "Home loan EMI debited twice this month. Customer care not responding.",
    full: "@UnionBankOfIndia my home loan EMI was debited twice this month. Account ending 4521. Nobody responding. #BankingFail",
  },
  {
    index: 3,
    username: "@sneha_bangalore",
    preview: "Internet banking down. Credit card bill due today — will you waive the fee?",
    full: "@UnionBankOfIndia internet banking is down since yesterday. I can't pay my credit card bill and the due date is today.",
  },
  {
    index: 4,
    username: "@vikram_trades",
    preview: "FD maturity amount not credited even after 5 days. Branch gives no clarity.",
    full: "@UnionBankOfIndia FD maturity amount not credited even after 5 days of maturity date. #UnionBank",
  },
];

const SAMPLE_CALLS = [
  {
    index: 0,
    caller: "Rajesh Kumar",
    issue: "UPI transfer failed — ₹15,000 deducted, recipient never received",
    audio: "call_1_Rajesh_Kumar.mp3",
  },
  {
    index: 1,
    caller: "Priya Mehta",
    issue: "Unauthorised credit card transactions — fraud suspected",
    audio: "call_2_Priya_Mehta.mp3",
  },
  {
    index: 2,
    caller: "Amit Singh",
    issue: "Home loan EMI double-debited — overdraft fee charged",
    audio: "call_3_Amit_Singh.mp3",
  },
  {
    index: 3,
    caller: "Sunita Rao",
    issue: "ATM dispensed no cash — ₹10,000 deducted with no payout",
    audio: "call_4_Sunita_Rao.mp3",
  },
  {
    index: 4,
    caller: "Mohammed Farouk",
    issue: "FD maturity amount not credited — senior citizen, 7-day delay",
    audio: "call_5_Mohammed_Farouk.mp3",
  },
];

// ─── Small shared pieces ───────────────────────────────────────────────────────

function StatusBadge({ live }: { live: boolean }) {
  return live ? (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-[11px] font-bold">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
      Live &amp; Working
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 border border-amber-200 text-amber-700 text-[11px] font-bold">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
      Prototype · Simulated
    </span>
  );
}

function FlowStep({ step, label }: { step: number; label: string }) {
  return (
    <div className="flex items-center gap-2 flex-shrink-0">
      <div className="w-6 h-6 rounded-full bg-ub-blue text-white text-[10px] font-extrabold flex items-center justify-center flex-shrink-0">
        {step}
      </div>
      <span className="text-gray-700 text-xs font-medium leading-tight">{label}</span>
    </div>
  );
}

function FlowArrow() {
  return <ArrowRight size={14} className="text-gray-300 flex-shrink-0 hidden sm:block" />;
}

function ResultBanner({ state, result, error }: { state: DemoState; result: DemoResult | null; error: string }) {
  if (state === "idle") return null;
  if (state === "loading")
    return (
      <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-sm mt-3">
        <Loader2 size={14} className="animate-spin flex-shrink-0" />
        Submitting complaint to AI pipeline…
      </div>
    );
  if (state === "error")
    return (
      <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm mt-3">
        <AlertTriangle size={14} className="flex-shrink-0" />
        {error || "Something went wrong. Is the backend running?"}
      </div>
    );
  if (state === "success" && result)
    return (
      <div className="px-4 py-3 rounded-lg bg-emerald-50 border border-emerald-200 mt-3">
        <div className="flex items-center gap-2 text-emerald-700 text-sm font-semibold mb-1">
          <CheckCircle2 size={14} className="flex-shrink-0" />
          Complaint created successfully
        </div>
        <div className="text-xs text-emerald-600 space-y-0.5">
          <div>
            ID:{" "}
            <span className="font-mono font-bold">{result.complaint_id}</span>
          </div>
          <div className="text-emerald-500">
            Go to the Dashboard → Complaints tab to see it processed by the AI pipeline.
          </div>
        </div>
      </div>
    );
  return null;
}

// ─── Production Path Accordion ────────────────────────────────────────────────

function ProductionPath({
  steps,
  cost,
  time,
}: {
  steps: { label: string; detail: string }[];
  cost: string;
  time: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`rounded-xl border transition-all ${open ? "border-ub-blue/30 bg-ub-blue/[0.03]" : "border-gray-200 bg-white"}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3.5 text-left"
      >
        <div className="flex items-center gap-2">
          <Zap size={14} className="text-amber-500 flex-shrink-0" />
          <span className="text-sm font-bold text-gray-800">Production Path</span>
          <span className="text-[11px] text-gray-400 hidden sm:inline">— what changes to go live</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-semibold text-gray-500 hidden md:block">{time}</span>
          <ChevronDown
            size={14}
            className={`text-gray-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-gray-100 pt-4">
          {steps.map((s, i) => (
            <div key={i} className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-ub-blue/10 text-ub-blue text-[10px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                {i + 1}
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-800">{s.label}</div>
                <div className="text-xs text-gray-500 mt-0.5">{s.detail}</div>
              </div>
            </div>
          ))}
          <div className="flex flex-wrap gap-2 pt-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 text-xs font-semibold">
              Cost: {cost}
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 text-xs font-semibold">
              Timeline: {time}
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold">
              <CheckCircle2 size={11} />
              Backend endpoint — no change
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Email Channel ────────────────────────────────────────────────────────────

function EmailChannel() {
  const [copied, setCopied] = useState(false);
  const email = "unionbank.complaints.demo@gmail.com";

  const copy = () => {
    navigator.clipboard.writeText(email);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="border-b border-gray-100 px-6 py-5 flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500 flex items-center justify-center flex-shrink-0 shadow-lg shadow-emerald-200">
            <Mail size={22} className="text-white" />
          </div>
          <div>
            <h3 className="font-extrabold text-gray-900 text-lg leading-tight">Email Channel</h3>
            <p className="text-gray-500 text-sm mt-0.5">Gmail IMAP Poller</p>
          </div>
        </div>
        <StatusBadge live={true} />
      </div>

      <div className="px-6 py-5 space-y-5">
        {/* What it does */}
        <div>
          <p className="text-gray-600 text-sm leading-relaxed">
            A Python poller connects to Gmail every 30 seconds via IMAP, reads unread complaint
            emails, and automatically submits them to the AI pipeline. The customer's email address
            becomes their customer ID. No manual intervention needed.
          </p>
        </div>

        {/* How it works flow */}
        <div>
          <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">How it works</div>
          <div className="flex flex-wrap items-center gap-2">
            <FlowStep step={1} label="Customer sends email" />
            <FlowArrow />
            <FlowStep step={2} label="Gmail poller picks up (30s)" />
            <FlowArrow />
            <FlowStep step={3} label="Submits to /complaints/submit" />
            <FlowArrow />
            <FlowStep step={4} label="AI pipeline runs" />
          </div>
        </div>

        {/* Live demo */}
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
          <div className="text-xs font-bold text-emerald-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Radio size={11} />
            Try it live right now
          </div>
          <p className="text-sm text-emerald-800 mb-3 leading-relaxed">
            Send an email to the address below with any banking complaint. It will appear in the
            dashboard within 30 seconds.
          </p>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-white border border-emerald-300 rounded-lg px-4 py-2.5 font-mono text-sm text-gray-800 truncate">
              {email}
            </div>
            <button
              onClick={copy}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold transition-colors"
            >
              {copied ? <Check size={13} /> : <Copy size={13} />}
              {copied ? "Copied!" : "Copy"}
            </button>
            <a
              href={`mailto:${email}?subject=Complaint%3A%20UPI%20Transfer%20Failed&body=I%20tried%20to%20transfer%20Rs.%2015%2C000%20via%20UPI%20but%20the%20amount%20was%20deducted%20and%20the%20recipient%20never%20received%20it.%20Please%20investigate.`}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2.5 rounded-lg border border-emerald-300 bg-white hover:bg-emerald-50 text-emerald-700 text-xs font-bold transition-colors"
            >
              <ExternalLink size={13} />
              Open Mail
            </a>
          </div>
        </div>

        {/* Production Path */}
        <ProductionPath
          cost="Free (Gmail IMAP)"
          time="~2 hours"
          steps={[
            {
              label: "Configure Gmail App Password",
              detail:
                "Google Account → Security → 2-Step Verification → App Passwords. Takes 2 minutes.",
            },
            {
              label: "Deploy email_poller.py as a background service",
              detail:
                "Run on Railway, Render, or any server using PM2 / systemd. The code is already complete.",
            },
            {
              label: "Update .env with real credentials",
              detail:
                "Set GMAIL_USER, GMAIL_APP_PASSWORD, BACKEND_URL, and API_KEY. Nothing else changes.",
            },
          ]}
        />
      </div>
    </div>
  );
}

// ─── Twitter Channel ──────────────────────────────────────────────────────────

function TwitterChannel() {
  const [states, setStates] = useState<Record<number, DemoState>>({});
  const [results, setResults] = useState<Record<number, DemoResult>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});

  const simulate = async (index: number) => {
    setStates((s) => ({ ...s, [index]: "loading" }));
    const autoRun = localStorage.getItem("auto_resolution_enabled") === "true";
    try {
      const res = await apiPost<DemoResult>("/api/v1/channels/twitter/demo", {
        tweet_index: index,
        auto_run: autoRun,
      });
      setResults((r) => ({ ...r, [index]: res }));
      setStates((s) => ({ ...s, [index]: "success" }));
    } catch (e: unknown) {
      setErrors((err) => ({ ...err, [index]: e instanceof Error ? e.message : "Error" }));
      setStates((s) => ({ ...s, [index]: "error" }));
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="border-b border-gray-100 px-6 py-5 flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-[#0F1419] flex items-center justify-center flex-shrink-0 shadow-lg shadow-slate-300">
            <Twitter size={22} className="text-white" />
          </div>
          <div>
            <h3 className="font-extrabold text-gray-900 text-lg leading-tight">Twitter / X Channel</h3>
            <p className="text-gray-500 text-sm mt-0.5">Complaint Tweet Simulator</p>
          </div>
        </div>
        <StatusBadge live={false} />
      </div>

      <div className="px-6 py-5 space-y-5">
        {/* What it does */}
        <div>
          <p className="text-gray-600 text-sm leading-relaxed">
            In production, a Tweepy stream listener monitors tweets mentioning{" "}
            <span className="font-mono font-semibold text-gray-800">@UnionBankOfIndia</span> in real
            time. For this prototype, the simulator sends pre-written tweet payloads directly to
            the same backend endpoint — demonstrating the full complaint pipeline.
          </p>
        </div>

        {/* How it works flow */}
        <div>
          <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">How it works</div>
          <div className="flex flex-wrap items-center gap-2">
            <FlowStep step={1} label="Tweet @UnionBankOfIndia" />
            <FlowArrow />
            <FlowStep step={2} label="Simulator / Tweepy picks it up" />
            <FlowArrow />
            <FlowStep step={3} label="Submits to /complaints/submit" />
            <FlowArrow />
            <FlowStep step={4} label="AI pipeline runs" />
          </div>
        </div>

        {/* Demo tweets */}
        <div>
          <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Play size={11} className="fill-gray-400" />
            Click any tweet to simulate
          </div>
          <div className="space-y-3">
            {SAMPLE_TWEETS.map((tweet) => {
              const s = states[tweet.index] ?? "idle";
              const res = results[tweet.index];
              const err = errors[tweet.index] ?? "";
              return (
                <div
                  key={tweet.index}
                  className="border border-gray-200 rounded-xl p-4 hover:border-gray-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      {/* Twitter-style header */}
                      <div className="flex items-center gap-2 mb-1.5">
                        <div className="w-7 h-7 rounded-full bg-[#0F1419] flex items-center justify-center flex-shrink-0">
                          <Twitter size={12} className="text-white" />
                        </div>
                        <span className="font-bold text-gray-900 text-sm">{tweet.username}</span>
                        <span className="text-gray-400 text-xs">· just now</span>
                      </div>
                      <p className="text-gray-700 text-sm leading-relaxed">{tweet.preview}</p>
                    </div>
                    <button
                      onClick={() => simulate(tweet.index)}
                      disabled={s === "loading" || s === "success"}
                      className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                        s === "success"
                          ? "bg-emerald-100 text-emerald-700 cursor-default"
                          : s === "loading"
                            ? "bg-gray-100 text-gray-400 cursor-wait"
                            : "bg-[#0F1419] hover:bg-[#1d2733] text-white"
                      }`}
                    >
                      {s === "loading" ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : s === "success" ? (
                        <CheckCircle2 size={12} />
                      ) : (
                        <Twitter size={12} />
                      )}
                      {s === "success" ? "Sent!" : s === "loading" ? "Sending…" : "Simulate"}
                    </button>
                  </div>
                  <ResultBanner state={s} result={res ?? null} error={err} />
                </div>
              );
            })}
          </div>
        </div>

        {/* Production Path */}
        <ProductionPath
          cost="$100/month (Twitter Basic API)"
          time="~5 days (incl. approval)"
          steps={[
            {
              label: "Apply for Twitter Developer Account",
              detail:
                "developer.twitter.com → Create project → mention 'banking complaint monitoring'. Approval takes 1–3 days.",
            },
            {
              label: "Replace twitter_simulator.py with a Tweepy stream listener",
              detail:
                "~50 lines of code. Stream filters tweets mentioning @UnionBankOfIndia and posts to the same backend endpoint. No backend changes.",
            },
            {
              label: "Add 3 env variables",
              detail:
                "TWITTER_BEARER_TOKEN, TWITTER_API_KEY, TWITTER_API_SECRET — all from the Developer dashboard.",
            },
          ]}
        />
      </div>
    </div>
  );
}

// ─── IVR Channel ──────────────────────────────────────────────────────────────

function IVRChannel() {
  const [states, setStates] = useState<Record<number, DemoState>>({});
  const [results, setResults] = useState<Record<number, DemoResult>>({});
  const [errors, setErrors] = useState<Record<number, string>>({});

  const API_KEY =
    (import.meta.env.VITE_API_KEY as string) || "sk_my_super_secret_key_123";
  const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || "";

  const audioUrl = (filename: string) =>
    `${BASE_URL}/api/v1/channels/ivr/audio/${filename}?api_key=${encodeURIComponent(API_KEY)}`;

  const simulate = async (index: number) => {
    setStates((s) => ({ ...s, [index]: "loading" }));
    const autoRun = localStorage.getItem("auto_resolution_enabled") === "true";
    try {
      const res = await apiPost<DemoResult>("/api/v1/channels/ivr/demo", {
        call_index: index,
        auto_run: autoRun,
      });
      setResults((r) => ({ ...r, [index]: res }));
      setStates((s) => ({ ...s, [index]: "success" }));
    } catch (e: unknown) {
      setErrors((err) => ({ ...err, [index]: e instanceof Error ? e.message : "Error" }));
      setStates((s) => ({ ...s, [index]: "error" }));
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="border-b border-gray-100 px-6 py-5 flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-ub-blue flex items-center justify-center flex-shrink-0 shadow-lg shadow-blue-200">
            <Phone size={22} className="text-white" />
          </div>
          <div>
            <h3 className="font-extrabold text-gray-900 text-lg leading-tight">IVR / Voice Channel</h3>
            <p className="text-gray-500 text-sm mt-0.5">OpenAI Whisper Transcription</p>
          </div>
        </div>
        <StatusBadge live={false} />
      </div>

      <div className="px-6 py-5 space-y-5">
        {/* What it does */}
        <div>
          <p className="text-gray-600 text-sm leading-relaxed">
            In production, incoming customer calls are recorded via Exotel/Twilio and sent to
            OpenAI Whisper for transcription. For this prototype, 5 realistic call audio files are
            pre-generated using OpenAI TTS — you can listen to each call and click to submit it as
            a complaint.
          </p>
        </div>

        {/* How it works flow */}
        <div>
          <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">How it works</div>
          <div className="flex flex-wrap items-center gap-2">
            <FlowStep step={1} label="Customer calls bank number" />
            <FlowArrow />
            <FlowStep step={2} label="Audio recorded (Exotel)" />
            <FlowArrow />
            <FlowStep step={3} label="Whisper transcribes" />
            <FlowArrow />
            <FlowStep step={4} label="Submits to /complaints/submit" />
          </div>
        </div>

        {/* Demo calls */}
        <div>
          <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
            <Play size={11} className="fill-gray-400" />
            Listen to the call, then simulate it
          </div>
          <div className="space-y-3">
            {SAMPLE_CALLS.map((call) => {
              const s = states[call.index] ?? "idle";
              const res = results[call.index];
              const err = errors[call.index] ?? "";
              return (
                <div
                  key={call.index}
                  className="border border-gray-200 rounded-xl p-4 hover:border-gray-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-7 h-7 rounded-full bg-ub-blue/10 flex items-center justify-center flex-shrink-0">
                          <Phone size={12} className="text-ub-blue" />
                        </div>
                        <span className="font-bold text-gray-900 text-sm">{call.caller}</span>
                      </div>
                      <p className="text-gray-500 text-xs leading-relaxed pl-9">{call.issue}</p>
                    </div>
                    <button
                      onClick={() => simulate(call.index)}
                      disabled={s === "loading" || s === "success"}
                      className={`flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold transition-all ${
                        s === "success"
                          ? "bg-emerald-100 text-emerald-700 cursor-default"
                          : s === "loading"
                            ? "bg-gray-100 text-gray-400 cursor-wait"
                            : "bg-ub-blue hover:bg-ub-blue-dark text-white"
                      }`}
                    >
                      {s === "loading" ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : s === "success" ? (
                        <CheckCircle2 size={12} />
                      ) : (
                        <Phone size={12} />
                      )}
                      {s === "success" ? "Submitted!" : s === "loading" ? "Processing…" : "Simulate"}
                    </button>
                  </div>

                  {/* Audio player */}
                  <audio
                    controls
                    src={audioUrl(call.audio)}
                    className="w-full h-8 rounded"
                    preload="none"
                  />

                  <ResultBanner state={s} result={res ?? null} error={err} />
                </div>
              );
            })}
          </div>
        </div>

        {/* Production Path */}
        <ProductionPath
          cost="₹2,000/month + usage (Exotel India)"
          time="~3 days"
          steps={[
            {
              label: "Sign up for Exotel (India) or Twilio",
              detail:
                "Exotel is the go-to for Indian banks (₹2,000/month + ₹0.12/min). Same-day signup. Gets you a real bank-grade IVR number.",
            },
            {
              label: "Add one new webhook route to the backend (~50 lines)",
              detail:
                "POST /api/v1/channels/ivr/incoming — receives call recording URL from Exotel, downloads audio, runs Whisper, submits complaint. The AI pipeline code stays untouched.",
            },
            {
              label: "Add 3 env variables",
              detail:
                "EXOTEL_API_KEY, EXOTEL_API_TOKEN, EXOTEL_SID — from Exotel dashboard. That's it.",
            },
          ]}
        />
      </div>
    </div>
  );
}

// ─── Main Section ─────────────────────────────────────────────────────────────

export default function ChannelsDemoSection() {
  return (
    <section id="channels" className="py-16 md:py-24 bg-white">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Section header */}
        <div className="text-center mb-12">
          <div className="text-ub-blue text-xs font-bold uppercase tracking-[0.15em] mb-3">
            Intake Channels
          </div>
          <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900">
            How Complaints Reach the Platform
          </h2>
          <p className="text-gray-500 mt-4 max-w-2xl mx-auto text-sm md:text-[15px] leading-relaxed">
            Three complaint channels — all feeding the same AI pipeline. Email is live and working
            today. Twitter and IVR are fully simulated for this prototype so you can trigger them
            right here from the browser.
          </p>

          {/* Key insight banner */}
          <div className="max-w-2xl mx-auto mt-6 bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 flex items-start gap-3 text-left">
            <Zap size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-amber-800 leading-relaxed">
              <span className="font-bold">Channels are just intake pipes.</span> Once a complaint
              enters the system — regardless of source — the same LangGraph multi-agent AI pipeline
              runs identically. No backend changes needed to add a new channel.
            </p>
          </div>
        </div>

        {/* Channel cards */}
        <div className="space-y-6">
          <EmailChannel />
          <TwitterChannel />
          <IVRChannel />
        </div>
      </div>
    </section>
  );
}
