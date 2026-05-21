import { Component, type ReactNode } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import LandingPage from "./components/home/LandingPage";
import { MainApp } from "./components/home/MainApp";
import FeedbackPage from "./components/feedback/FeedbackPage";

interface EBState {
  error: Error | null;
}

class ErrorBoundary extends Component<{ children: ReactNode }, EBState> {
  state: EBState = { error: null };
  static getDerivedStateFromError(e: Error): EBState {
    return { error: e };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-slate-50 p-8">
          <div className="max-w-xl w-full bg-white rounded-2xl border border-red-200 shadow-sm p-6 space-y-3">
            <h1 className="text-base font-bold text-red-700">
              Something went wrong
            </h1>
            <p className="text-sm text-slate-600 font-mono bg-slate-50 rounded-lg p-3 border border-slate-200 break-all">
              {this.state.error.message}
            </p>
            <p className="text-xs text-slate-400 font-mono whitespace-pre-wrap">
              {this.state.error.stack?.split("\n").slice(0, 6).join("\n")}
            </p>
            <button
              onClick={() => {
                this.setState({ error: null });
                window.location.reload();
              }}
              className="px-4 py-2 rounded-lg bg-ub-blue text-white text-sm font-semibold hover:opacity-90"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/complaint" element={<MainApp />} />
          <Route path="/feedback" element={<FeedbackPage />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
