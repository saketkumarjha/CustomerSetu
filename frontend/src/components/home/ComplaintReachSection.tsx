import { useState } from "react";
import type { ReactNode } from "react";
import {
  ChevronDown,
  Phone,
  Mail,
  Globe,
  Smartphone,
  Building2,
  X,
  FileText,
  AlertTriangle,
  ExternalLink,
  Bot,
  Clock,
  CheckCircle,
  ArrowRight,
  MessageCircle,
  Share2,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

type ModalType =
  | "complaint"
  | "unauthorized"
  | "branch"
  | "callus"
  | "writetous"
  | "connect"
  | null;

// ─── Static data ──────────────────────────────────────────────────────────────

const CARDS = [
  {
    id: "complaint" as ModalType,
    image: "/form_Complaint.jpg",
    icon: FileText,
    title: "Submit Online Complaint",
    subtitle: "Query / Service Request",
    description:
      "Lodge any complaint, query, or service request online. AI routes it to the right team within minutes.",
    cta: "File a Complaint",
    ctaStyle: "bg-ub-blue hover:bg-ub-blue-dark shadow-ub-blue/20",
    urgent: false,
  },
  {
    id: "unauthorized" as ModalType,
    image: "/unauthorize%20Banking.png",
    icon: AlertTriangle,
    title: "Unauthorised Transaction",
    subtitle: "Report Fraud Instantly",
    description:
      "Spotted a transaction you didn't authorise? Report it immediately — our team acts within 24 hours.",
    cta: "Report Now",
    ctaStyle: "bg-ub-red hover:bg-red-700 shadow-red-200",
    urgent: true,
  },
  {
    id: "callus" as ModalType,
    image: "/call%20_us.png",
    icon: Phone,
    title: "Call Us",
    subtitle: "Speak to a Representative",
    description:
      "Toll-free helplines, NRI lines, and dedicated fraud numbers — available around the clock.",
    cta: "View Numbers",
    ctaStyle: "bg-ub-blue hover:bg-ub-blue-dark shadow-ub-blue/20",
    urgent: false,
  },
  {
    id: "branch" as ModalType,
    image: "/branch.webp",
    icon: Building2,
    title: "Branch Related Query",
    subtitle: "Branch & Zonal Support",
    description:
      "Query specific to your branch or zone? Our AI retrieves branch-level data and connects you instantly.",
    cta: "Raise Query",
    ctaStyle: "bg-ub-blue hover:bg-ub-blue-dark shadow-ub-blue/20",
    urgent: false,
  },
  {
    id: "writetous" as ModalType,
    image: "/email.jpg",
    icon: Mail,
    title: "Write to Us",
    subtitle: "Email & Digital Banking",
    description:
      "Reach us by email or lodge grievances via Mobile App, Internet Banking, or WhatsApp Banking.",
    cta: "Get in Touch",
    ctaStyle: "bg-ub-blue hover:bg-ub-blue-dark shadow-ub-blue/20",
    urgent: false,
  },
  {
    id: "connect" as ModalType,
    image: "/Social_media.jpg",
    icon: Share2,
    title: "Connect With Us",
    subtitle: "Social Media Channels",
    description:
      "Follow Union Bank on social platforms for updates, announcements, and community support.",
    cta: "Find Us Online",
    ctaStyle: "bg-ub-blue hover:bg-ub-blue-dark shadow-ub-blue/20",
    urgent: false,
  },
];

const CALL_ITEMS = [
  {
    label: "All-India Toll Free",
    numbers: ["1800-2333", "1800 208 2244", "1800 425 1515", "1800 425 3555", "1800 22 22 44"],
    type: "free" as const,
  },
  {
    label: "Fraud / Disputed Transaction Helpline",
    numbers: ["1800 2222 43"],
    type: "free" as const,
  },
  {
    label: "Premium Account Helpline",
    numbers: ["1800 425 2407"],
    type: "free" as const,
  },
  {
    label: "NRI Call Back Facility",
    numbers: ["+91 848 484 8458"],
    type: "nri" as const,
  },
  {
    label: "Charged Number",
    numbers: ["080-61817110"],
    note: "Call charges applicable to customer",
    type: "charged" as const,
  },
  {
    label: "NRI Dedicated Number",
    numbers: ["+91 806 181 7110"],
    type: "nri" as const,
  },
];

const BANKING_SUB_OPTIONS = [
  {
    id: "mobile",
    icon: Smartphone,
    label: "Union Ease Mobile App",
    steps: [
      "Login using your 4-digit PIN",
      "Go to Home Screen",
      'Search "Grievance Redressal"',
      "Select Grievance Redressal — Lodge / Track Grievances",
    ],
  },
  {
    id: "internet",
    icon: Globe,
    label: "Internet Banking Portal",
    steps: [
      "Visit the Internet Banking Homepage",
      "Click on Quick Links",
      "Select Grievances Online",
    ],
    link: "https://www.unionbankonline.bank.in/",
    linkLabel: "Open Internet Banking",
  },
  {
    id: "whatsapp",
    icon: MessageCircle,
    label: "WhatsApp Banking — UVConn (9666606060)",
    steps: [
      "WhatsApp 9666606060 → Select UVConn",
      "Login with MPIN → Authenticate MPIN",
      "Main Menu → Other Services → More Services",
      "More Services → Grievance Redressal",
    ],
  },
];

const SOCIALS = [
  { label: "Facebook", color: "bg-[#1877F2]" },
  { label: "Twitter / X", color: "bg-[#0F1419]" },
  { label: "LinkedIn", color: "bg-[#0A66C2]" },
  { label: "WhatsApp", color: "bg-[#25D366]" },
  { label: "YouTube", color: "bg-[#FF0000]" },
];

// ─── Shared form primitives ───────────────────────────────────────────────────

function FormField({
  label,
  type,
  placeholder,
  required,
}: {
  label: string;
  type: string;
  placeholder: string;
  required?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-600 mb-1.5">
        {label}
        {required && <span className="text-ub-red ml-0.5">*</span>}
      </label>
      <input
        type={type}
        placeholder={placeholder}
        className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ub-blue/20 focus:border-ub-blue transition-colors"
      />
    </div>
  );
}

function SelectField({
  label,
  options,
  required,
}: {
  label: string;
  options: string[];
  required?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold text-gray-600 mb-1.5">
        {label}
        {required && <span className="text-ub-red ml-0.5">*</span>}
      </label>
      <select className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-ub-blue/20 focus:border-ub-blue transition-colors bg-white">
        {options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}

// ─── Modal shell ──────────────────────────────────────────────────────────────

function ModalShell({
  title,
  onClose,
  children,
  headerColor = "bg-ub-blue",
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  headerColor?: string;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className={`${headerColor} px-6 py-4 flex items-center justify-between flex-shrink-0`}>
          <div>
            <p className="text-white/60 text-[10px] font-semibold uppercase tracking-widest mb-0.5">
              Union Bank of India
            </p>
            <h3 className="font-bold text-white text-sm">{title}</h3>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg bg-white/10 hover:bg-white/25 transition-colors text-white"
            aria-label="Close"
          >
            <X size={15} />
          </button>
        </div>

        {/* AI note strip */}
        <div className="bg-ub-blue-light border-b border-ub-blue/10 px-6 py-2.5 flex items-center gap-2.5 flex-shrink-0">
          <Bot size={13} className="text-ub-blue flex-shrink-0" />
          <p className="text-xs text-ub-blue leading-relaxed">
            Our AI agent will route your request and keep you updated via email or phone.
          </p>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto px-6 py-5 flex-1">{children}</div>
      </div>
    </div>
  );
}

// ─── Individual modals ────────────────────────────────────────────────────────

function ComplaintModal({ onClose }: { onClose: () => void }) {
  return (
    <ModalShell title="Submit Online Complaint / Query / Service Request" onClose={onClose}>
      <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Full Name" type="text" placeholder="Enter your full name" required />
          <FormField label="Account Number" type="text" placeholder="Enter account number" required />
          <FormField label="Email Address" type="email" placeholder="you@example.com" required />
          <FormField label="Phone Number" type="tel" placeholder="+91 XXXXX XXXXX" required />
        </div>
        <SelectField
          label="Complaint Category"
          options={["Account Issue", "Card Issue", "Loan Issue", "Digital Banking", "ATM / Cash Issue", "Service Request", "Other"]}
          required
        />
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">
            Describe Your Complaint <span className="text-ub-red">*</span>
          </label>
          <textarea
            rows={4}
            placeholder="Provide as much detail as possible..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ub-blue/20 focus:border-ub-blue transition-colors resize-none"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-2">Priority</label>
          <div className="flex gap-4">
            {["General", "Urgent"].map((p) => (
              <label key={p} className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="priority" defaultChecked={p === "General"} className="accent-ub-blue" />
                <span className="text-sm text-gray-700 font-medium">{p}</span>
              </label>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-400">
          <Clock size={11} className="text-amber-500" />
          General queries resolved in under 2 minutes
        </div>
        <button
          type="submit"
          className="w-full py-3 rounded-lg bg-ub-blue text-white font-bold text-sm hover:bg-ub-blue-dark transition-colors shadow-lg shadow-ub-blue/20 flex items-center justify-center gap-2"
        >
          Submit Complaint <ArrowRight size={14} />
        </button>
      </form>
    </ModalShell>
  );
}

function UnauthorizedModal({ onClose }: { onClose: () => void }) {
  return (
    <ModalShell title="Report Unauthorised Banking Transaction" onClose={onClose} headerColor="bg-ub-red">
      <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
        <div className="bg-red-50 border border-ub-red/20 rounded-lg px-4 py-3 flex items-start gap-2.5">
          <AlertTriangle size={14} className="text-ub-red mt-0.5 flex-shrink-0" />
          <p className="text-xs text-ub-red font-medium leading-relaxed">
            Also call our dedicated fraud helpline immediately:{" "}
            <strong>1800 2222 43</strong>
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Full Name" type="text" placeholder="Enter your full name" required />
          <FormField label="Account Number" type="text" placeholder="Enter account number" required />
          <FormField label="Transaction Date" type="date" placeholder="" required />
          <FormField label="Transaction Amount (₹)" type="number" placeholder="e.g. 5000" required />
          <FormField label="Transaction Reference / UTR ID" type="text" placeholder="Reference or UTR number" />
          <SelectField
            label="Transaction Type"
            options={["ATM Withdrawal", "UPI Transfer", "Net Banking", "Debit / Credit Card", "NEFT / RTGS", "Other"]}
            required
          />
          <FormField label="Contact Email" type="email" placeholder="you@example.com" required />
          <FormField label="Contact Phone" type="tel" placeholder="+91 XXXXX XXXXX" required />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">
            Describe the Incident <span className="text-ub-red">*</span>
          </label>
          <textarea
            rows={3}
            placeholder="When, where, and what happened..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ub-red/20 focus:border-ub-red transition-colors resize-none"
          />
        </div>
        <button
          type="submit"
          className="w-full py-3 rounded-lg bg-ub-red text-white font-bold text-sm hover:bg-red-700 transition-colors shadow-lg shadow-red-200 flex items-center justify-center gap-2"
        >
          Report Transaction <ArrowRight size={14} />
        </button>
      </form>
    </ModalShell>
  );
}

function BranchModal({ onClose }: { onClose: () => void }) {
  return (
    <ModalShell title="Branch Related Query" onClose={onClose}>
      <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Full Name" type="text" placeholder="Enter your full name" required />
          <FormField label="Account Number" type="text" placeholder="Enter account number" required />
          <FormField label="Branch Name" type="text" placeholder="e.g. Nariman Point Branch" required />
          <FormField label="Branch Code (optional)" type="text" placeholder="e.g. 001234" />
          <FormField label="City" type="text" placeholder="e.g. Mumbai" required />
          <FormField label="State" type="text" placeholder="e.g. Maharashtra" required />
          <FormField label="Contact Phone" type="tel" placeholder="+91 XXXXX XXXXX" required />
          <FormField label="Contact Email" type="email" placeholder="you@example.com" required />
        </div>
        <SelectField
          label="Query Type"
          options={["Account Services", "Loan Services", "Staff Behaviour", "Branch Timings / Availability", "Document Submission", "Locker Services", "Zonal / Regional Escalation", "Other"]}
          required
        />
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">
            Describe Your Query <span className="text-ub-red">*</span>
          </label>
          <textarea
            rows={3}
            placeholder="Describe your branch-related query. Our AI agent retrieves branch-specific information to assist you..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-ub-blue/20 focus:border-ub-blue transition-colors resize-none"
          />
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-400">
          <CheckCircle size={11} className="text-emerald-500" />
          Branch & zonal queries resolved within 24 hours
        </div>
        <button
          type="submit"
          className="w-full py-3 rounded-lg bg-ub-blue text-white font-bold text-sm hover:bg-ub-blue-dark transition-colors shadow-lg shadow-ub-blue/20 flex items-center justify-center gap-2"
        >
          Submit Query <ArrowRight size={14} />
        </button>
      </form>
    </ModalShell>
  );
}

function CallUsModal({ onClose }: { onClose: () => void }) {
  return (
    <ModalShell title="Call Us" onClose={onClose}>
      <div className="space-y-5">
        <p className="text-sm text-gray-500 leading-relaxed">
          Choose the helpline that matches your need. Tap any number to call directly from your device.
        </p>
        {CALL_ITEMS.map((item) => (
          <div key={item.label} className="flex items-start gap-3">
            <span
              className={`mt-2 w-2 h-2 rounded-full flex-shrink-0 ${
                item.type === "free"
                  ? "bg-emerald-400"
                  : item.type === "nri"
                    ? "bg-ub-blue"
                    : "bg-amber-400"
              }`}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-semibold text-gray-700">
                  {item.label}
                </span>
                {item.type === "free" && (
                  <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full">
                    TOLL FREE
                  </span>
                )}
                {item.type === "nri" && (
                  <span className="text-[10px] font-bold text-ub-blue bg-ub-blue-light border border-ub-blue/20 px-2 py-0.5 rounded-full">
                    NRI
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {item.numbers.map((num) => (
                  <a
                    key={num}
                    href={`tel:${num.replace(/[\s\-+]/g, "")}`}
                    className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white border border-gray-200 text-sm font-bold text-ub-blue hover:bg-ub-blue hover:text-white hover:border-ub-blue transition-all"
                  >
                    <Phone size={11} />
                    {num}
                  </a>
                ))}
              </div>
              {item.note && (
                <p className="text-[11px] text-amber-600 mt-1.5 flex items-center gap-1">
                  <AlertTriangle size={10} /> {item.note}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </ModalShell>
  );
}

function WriteToUsModal({ onClose }: { onClose: () => void }) {
  const [openOpt, setOpenOpt] = useState<string | null>(null);

  return (
    <ModalShell title="Write to Us" onClose={onClose}>
      <div className="space-y-6">
        {/* Email */}
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
            Dedicated Customer Service Email
          </div>
          <a
            href="mailto:customercare@unionbankofindia.bank.in"
            className="flex items-center gap-3 p-4 rounded-xl border border-ub-blue/20 bg-ub-blue-light hover:bg-ub-blue hover:text-white transition-all group"
          >
            <div className="w-10 h-10 rounded-lg bg-ub-blue flex items-center justify-center flex-shrink-0 group-hover:bg-white/20">
              <Mail size={16} className="text-white" />
            </div>
            <div className="min-w-0">
              <div className="text-xs text-ub-blue group-hover:text-white/80 font-medium mb-0.5">
                Email us at
              </div>
              <div className="text-sm font-bold text-ub-blue group-hover:text-white truncate">
                customercare@unionbankofindia.bank.in
              </div>
            </div>
            <ExternalLink size={14} className="ml-auto text-ub-blue/40 group-hover:text-white/60 flex-shrink-0" />
          </a>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-xs text-gray-400 font-medium">Banking Related Query</span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>

        {/* Sub-options */}
        <div className="space-y-2">
          {BANKING_SUB_OPTIONS.map((opt) => (
            <div
              key={opt.id}
              className={`border rounded-xl overflow-hidden transition-all ${
                openOpt === opt.id ? "border-ub-blue/25" : "border-gray-200"
              }`}
            >
              <button
                onClick={() => setOpenOpt(openOpt === opt.id ? null : opt.id)}
                className={`w-full flex items-center gap-3 px-4 py-3.5 text-left text-sm transition-colors ${
                  openOpt === opt.id
                    ? "bg-ub-blue-light text-ub-blue"
                    : "bg-white text-gray-700 hover:bg-gray-50"
                }`}
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${openOpt === opt.id ? "bg-ub-blue/10" : "bg-gray-100"}`}>
                  <opt.icon size={14} className={openOpt === opt.id ? "text-ub-blue" : "text-gray-500"} />
                </div>
                <span className="font-semibold flex-1">{opt.label}</span>
                <ChevronDown
                  size={14}
                  className={`flex-shrink-0 transition-transform duration-200 ${
                    openOpt === opt.id ? "rotate-180 text-ub-blue" : "text-gray-400"
                  }`}
                />
              </button>

              {openOpt === opt.id && (
                <div className="bg-gray-50 border-t border-gray-100 px-4 py-4">
                  <ol className="space-y-3">
                    {opt.steps.map((step, i) => (
                      <li key={i} className="flex items-start gap-3 text-xs text-gray-600">
                        <span className="w-5 h-5 rounded-full bg-ub-blue text-white font-bold text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5">
                          {i + 1}
                        </span>
                        {step}
                      </li>
                    ))}
                  </ol>
                  {"link" in opt && opt.link && (
                    <a
                      href={opt.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 mt-3 px-3 py-1.5 rounded-lg bg-ub-blue text-white text-xs font-semibold hover:bg-ub-blue-dark transition-colors"
                    >
                      {(opt as typeof opt & { linkLabel: string }).linkLabel}
                      <ExternalLink size={10} />
                    </a>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </ModalShell>
  );
}

function ConnectModal({ onClose }: { onClose: () => void }) {
  return (
    <ModalShell title="Connect With Us" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-gray-500 leading-relaxed">
          Follow Union Bank of India on our official social media channels for updates, alerts, and support.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {SOCIALS.map((s) => (
            <a
              key={s.label}
              href="#"
              className={`${s.color} text-white rounded-xl px-5 py-4 flex items-center gap-3 hover:opacity-90 transition-opacity shadow-sm`}
            >
              <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center flex-shrink-0">
                <Share2 size={15} className="text-white" />
              </div>
              <div>
                <div className="font-bold text-sm">{s.label}</div>
                <div className="text-white/70 text-xs">Union Bank of India</div>
              </div>
              <ExternalLink size={13} className="ml-auto text-white/50" />
            </a>
          ))}
        </div>
      </div>
    </ModalShell>
  );
}

// ─── Card ─────────────────────────────────────────────────────────────────────

function SupportCard({
  card,
  onClick,
}: {
  card: (typeof CARDS)[number];
  onClick: () => void;
}) {
  const Icon = card.icon;

  return (
    <button
      onClick={onClick}
      className="group text-left w-full bg-white rounded-2xl overflow-hidden border border-gray-100 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 flex flex-col"
    >
      {/* Image */}
      <div className="relative overflow-hidden h-48 flex-shrink-0">
        <img
          src={card.image}
          alt={card.title}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
        />
        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent" />

        {/* Urgent badge */}
        {card.urgent && (
          <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-ub-red text-white text-[10px] font-bold px-2.5 py-1 rounded-full shadow-lg">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            URGENT
          </div>
        )}

        {/* Icon badge bottom-left */}
        <div className="absolute bottom-3 left-3">
          <div className="w-9 h-9 rounded-xl bg-white shadow-lg flex items-center justify-center">
            <Icon size={16} className={card.urgent ? "text-ub-red" : "text-ub-blue"} />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-5 flex flex-col flex-1">
        <div className="flex-1">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">
            {card.subtitle}
          </div>
          <h3 className="font-extrabold text-gray-900 text-base mb-2 leading-snug">
            {card.title}
          </h3>
          <p className="text-gray-500 text-sm leading-relaxed">
            {card.description}
          </p>
        </div>

        {/* CTA */}
        <div className="mt-5">
          <span
            className={`inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-white text-xs font-bold transition-all shadow-md ${card.ctaStyle} group-hover:gap-3`}
          >
            {card.cta}
            <ArrowRight size={13} />
          </span>
        </div>
      </div>
    </button>
  );
}

// ─── Main section ─────────────────────────────────────────────────────────────

export default function ComplaintReachSection() {
  const [modal, setModal] = useState<ModalType>(null);

  return (
    <section id="pipeline" className="py-16 md:py-24 bg-gray-50">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">

        {/* ── Header ── */}
        <div className="text-center mb-10">
          <div className="text-ub-red text-xs font-bold uppercase tracking-[0.15em] mb-3">
            Customer Support
          </div>
          <h2 className="text-3xl md:text-4xl font-extrabold text-gray-900 mb-2">
            We're Here to Help
          </h2>
          <p className="text-gray-500 text-sm md:text-base max-w-xl mx-auto leading-relaxed mb-8">
            Choose the channel that works best for you. Our AI handles routing,
            escalation, and follow-up — automatically.
          </p>

          {/* AI tagline card */}
          <div className="max-w-2xl mx-auto bg-white border border-ub-blue/12 rounded-2xl px-6 py-5 flex items-start gap-4 text-left shadow-glass">
            <div className="w-10 h-10 rounded-xl bg-ub-blue flex items-center justify-center flex-shrink-0 shadow-lg shadow-ub-blue/25">
              <Bot size={18} className="text-white" />
            </div>
            <div className="min-w-0">
              <div className="font-bold text-gray-900 text-sm mb-1">
                Just reach out — our AI agent handles the rest
              </div>
              <p className="text-gray-500 text-xs leading-relaxed mb-3">
                Submit through any channel. Escalation, routing, and resolution
                happen automatically — no manual follow-up needed from you.
              </p>
              <div className="flex flex-wrap gap-2.5">
                <div className="flex items-center gap-1.5 bg-amber-50 border border-amber-200 rounded-full px-3 py-1.5">
                  <Clock size={11} className="text-amber-500" />
                  <span className="text-xs font-semibold text-amber-700">
                    &lt;2 min — General queries
                  </span>
                </div>
                <div className="flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 rounded-full px-3 py-1.5">
                  <CheckCircle size={11} className="text-emerald-500" />
                  <span className="text-xs font-semibold text-emerald-700">
                    &lt;24 hrs — Branch / Zonal queries
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Card grid ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 md:gap-6">
          {CARDS.map((card) => (
            <SupportCard
              key={card.id}
              card={card}
              onClick={() => setModal(card.id)}
            />
          ))}
        </div>
      </div>

      {/* ── Modals ── */}
      {modal === "complaint"   && <ComplaintModal   onClose={() => setModal(null)} />}
      {modal === "unauthorized"&& <UnauthorizedModal onClose={() => setModal(null)} />}
      {modal === "branch"      && <BranchModal       onClose={() => setModal(null)} />}
      {modal === "callus"      && <CallUsModal        onClose={() => setModal(null)} />}
      {modal === "writetous"   && <WriteToUsModal     onClose={() => setModal(null)} />}
      {modal === "connect"     && <ConnectModal       onClose={() => setModal(null)} />}
    </section>
  );
}
