import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Star, CheckCircle, AlertTriangle, Loader2, Send } from "lucide-react";
import { api } from "../../lib/api";

const ISSUE_TAGS = [
  { id: "too_slow",       label: "Too Slow" },
  { id: "wrong_solution", label: "Wrong Solution" },
  { id: "rude",           label: "Rude Staff" },
  { id: "incomplete",     label: "Incomplete Response" },
];

const RATING_LABELS: Record<number, string> = {
  1: "Very Dissatisfied",
  2: "Dissatisfied",
  3: "Neutral",
  4: "Satisfied",
  5: "Very Satisfied",
};

function StarPicker({
  value,
  hover,
  onRate,
  onHover,
  onLeave,
}: {
  value: number;
  hover: number;
  onRate: (n: number) => void;
  onHover: (n: number) => void;
  onLeave: () => void;
}) {
  const active = hover || value;
  return (
    <div className="flex items-center gap-2">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onRate(n)}
          onMouseEnter={() => onHover(n)}
          onMouseLeave={onLeave}
          className="focus:outline-none transition-transform hover:scale-110"
          aria-label={`Rate ${n} star${n > 1 ? "s" : ""}`}
        >
          <Star
            size={36}
            className={`transition-colors ${
              n <= active
                ? "fill-amber-400 text-amber-400"
                : "fill-gray-100 text-gray-300"
            }`}
          />
        </button>
      ))}
      {active > 0 && (
        <span className="ml-2 text-sm font-semibold text-gray-700">
          {RATING_LABELS[active]}
        </span>
      )}
    </div>
  );
}

export default function FeedbackPage() {
  const [searchParams] = useSearchParams();
  const complaintId = searchParams.get("id") ?? "";
  const customerId  = searchParams.get("cid") ?? "";

  const [rating, setRating]             = useState(0);
  const [hoverRating, setHoverRating]   = useState(0);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [feedbackText, setFeedbackText] = useState("");
  const [submitting, setSubmitting]     = useState(false);
  const [error, setError]               = useState<string | null>(null);
  const [submitted, setSubmitted]       = useState(false);

  function toggleTag(tag: string) {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (rating === 0) {
      setError("Please select a star rating before submitting.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.feedback.submitCustomer({
        complaint_id:  complaintId.trim().toUpperCase(),
        customer_id:   customerId.trim(),
        rating,
        issue_tags:    selectedTags,
        feedback_text: feedbackText.trim() || undefined,
      });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-lg mx-auto flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <span className="text-white font-bold text-xs">UBI</span>
          </div>
          <div>
            <p className="text-sm font-bold text-gray-900">Union Bank of India</p>
            <p className="text-xs text-gray-500">Customer Care</p>
          </div>
        </div>
      </header>

      {/* Card */}
      <main className="flex-1 flex items-start justify-center px-4 py-10">
        <div className="w-full max-w-lg">
          {submitted ? (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8 flex flex-col items-center gap-5 text-center">
              <div className="w-16 h-16 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                <CheckCircle size={32} className="text-emerald-500" />
              </div>
              <div>
                <p className="text-xl font-bold text-gray-900 mb-2">
                  Thank you for your feedback!
                </p>
                <p className="text-sm text-gray-500">
                  Your rating has been recorded. It helps us serve you better.
                </p>
              </div>
              <div className="text-xs text-gray-400 mt-2">
                Complaint reference: <span className="font-mono font-semibold text-gray-600">{complaintId}</span>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8">
              <div className="mb-6">
                <h1 className="text-xl font-bold text-gray-900">Rate Your Experience</h1>
                <p className="text-sm text-gray-500 mt-1">
                  Your complaint{" "}
                  <span className="font-mono font-semibold text-gray-700">{complaintId}</span>{" "}
                  has been resolved. Tell us how we did.
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-6">
                {/* Star Rating */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-3">
                    Overall Rating <span className="text-red-500">*</span>
                  </label>
                  <StarPicker
                    value={rating}
                    hover={hoverRating}
                    onRate={setRating}
                    onHover={setHoverRating}
                    onLeave={() => setHoverRating(0)}
                  />
                </div>

                {/* Issue Tags */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    What could we improve?{" "}
                    <span className="text-gray-400 font-normal">(optional)</span>
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {ISSUE_TAGS.map((tag) => {
                      const active = selectedTags.includes(tag.id);
                      return (
                        <button
                          key={tag.id}
                          type="button"
                          onClick={() => toggleTag(tag.id)}
                          className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-all ${
                            active
                              ? "bg-blue-100 border-blue-300 text-blue-700"
                              : "bg-gray-50 border-gray-200 text-gray-600 hover:border-blue-200 hover:text-blue-600"
                          }`}
                        >
                          {tag.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Free Text */}
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Additional Comments{" "}
                    <span className="text-gray-400 font-normal">(optional)</span>
                  </label>
                  <textarea
                    rows={4}
                    placeholder="Tell us more about your experience..."
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 transition-colors resize-none"
                  />
                </div>

                {error && (
                  <div className="flex items-center gap-2.5 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
                    <AlertTriangle size={14} className="text-red-500 flex-shrink-0" />
                    <p className="text-sm text-red-600">{error}</p>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full py-3 rounded-xl bg-blue-600 text-white font-bold text-sm hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {submitting ? (
                    <>
                      <Loader2 size={15} className="animate-spin" />
                      Submitting…
                    </>
                  ) : (
                    <>
                      <Send size={14} />
                      Submit Feedback
                    </>
                  )}
                </button>
              </form>
            </div>
          )}

          <p className="text-center text-xs text-gray-400 mt-6">
            For urgent assistance call{" "}
            <span className="font-semibold">1800-22-2244</span> (Toll Free)
          </p>
        </div>
      </main>
    </div>
  );
}
