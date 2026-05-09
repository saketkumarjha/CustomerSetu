import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Menu,
  X,
  Bell,
  ChevronDown,
  ArrowRight,
  User,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DashboardProps {
  variant: "dashboard";
  sidebarOpen: boolean;
  onMenuToggle: () => void;
}

interface LandingProps {
  variant: "landing";
}

type Props = LandingProps | DashboardProps;

// ─── Nav links (landing only) ─────────────────────────────────────────────────

const NAV_LINKS = [
  { label: "Home", href: "#top", isRoute: false },
  { label: "Complaints", href: "/complaint", isRoute: true },
  { label: "Reach Out", href: "#pipeline", isRoute: false },
  { label: "Feedback", href: "#features", isRoute: false },
];

// ─── Component ────────────────────────────────────────────────────────────────

export function AppHeader(props: Props) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const isLanding = props.variant === "landing";

  const mobileMenuOpen =
    isLanding
      ? mobileOpen
      : (props as DashboardProps).sidebarOpen;

  function handleHamburger() {
    if (isLanding) {
      setMobileOpen((o) => !o);
    } else {
      (props as DashboardProps).onMenuToggle();
    }
  }

  return (
    <>
      <header
        className={`bg-white border-b border-gray-100 shadow-sm flex-shrink-0 z-50 ${
          isLanding ? "fixed top-0 left-0 right-0" : "relative"
        }`}
      >
        <div className="w-full px-4 md:px-6 flex items-center justify-between h-16">

          {/* ── Left ── */}
          <div className="flex items-center gap-3 min-w-0">
            {/* Hamburger */}
            <button
              onClick={handleHamburger}
              className="lg:hidden w-9 h-9 flex items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 transition-colors flex-shrink-0"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>

            {/* Logo — links to home */}
            <Link to="/" className="flex-shrink-0">
              <img
                src="/logo.jpeg"
                alt="Union Bank of India"
                className="h-10 w-auto object-contain"
              />
            </Link>

            {/* Dashboard: live badge */}
            {!isLanding && (
              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-md text-xs bg-ub-blue-light text-ub-blue border border-ub-blue/15 flex-shrink-0 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block animate-pulse flex-shrink-0" />
                IDEA 2.0 · AI–CSPARC · Live Demo
              </div>
            )}
          </div>

          {/* ── Center: landing nav links ── */}
          {isLanding && (
            <nav className="hidden lg:flex items-center gap-0.5">
              {NAV_LINKS.map((link) => {
                const isActive =
                  link.isRoute && location.pathname === link.href;
                return link.isRoute ? (
                  <Link
                    key={link.label}
                    to={link.href}
                    className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-ub-blue text-white"
                        : "text-gray-600 hover:text-ub-blue hover:bg-gray-50"
                    }`}
                  >
                    {link.label}
                  </Link>
                ) : (
                  <a
                    key={link.label}
                    href={link.href}
                    className="px-4 py-2 rounded-md text-sm font-medium text-gray-600 hover:text-ub-blue hover:bg-gray-50 transition-colors"
                  >
                    {link.label}
                  </a>
                );
              })}
            </nav>
          )}

          {/* ── Right ── */}
          <div className="flex items-center gap-2 md:gap-3 flex-shrink-0">

            {/* Bell — dashboard only */}
            {!isLanding && (
              <div className="relative cursor-pointer">
                <div className="w-9 h-9 rounded-md flex items-center justify-center text-gray-500 hover:bg-gray-100 transition-colors">
                  <Bell size={18} />
                </div>
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-ub-red text-white text-[10px] flex items-center justify-center font-bold leading-none">
                  3
                </span>
              </div>
            )}

            {/* User section */}
            {isLanding ? (
              /* Landing: Login button */
              <Link
                to="/complaint"
                className="flex items-center gap-2 px-4 py-2 rounded-lg border border-ub-blue/20 bg-white hover:bg-ub-blue-light transition-colors group"
              >
                <div className="w-7 h-7 rounded-full bg-ub-blue flex items-center justify-center flex-shrink-0">
                  <User size={13} className="text-white" />
                </div>
                <span className="text-sm font-semibold text-ub-blue hidden sm:block">
                  Login
                </span>
              </Link>
            ) : (
              /* Dashboard: user avatar */
              <div className="flex items-center gap-2.5 cursor-pointer group pl-1">
                <div className="w-9 h-9 rounded-full bg-ub-blue flex items-center justify-center text-xs font-bold text-white select-none flex-shrink-0 ring-2 ring-ub-blue/20">
                  RM
                </div>
                <div className="hidden md:block text-xs leading-tight">
                  <div className="text-gray-900 font-semibold">Rajiv Menon</div>
                  <div className="text-gray-400">Sr. Relationship Manager</div>
                </div>
                <ChevronDown
                  size={14}
                  className="text-gray-400 group-hover:text-gray-600 transition-colors hidden md:block"
                />
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ── Mobile drawer — landing only ── */}
      {isLanding && mobileOpen && (
        <div className="lg:hidden fixed top-16 left-0 right-0 z-40 bg-white border-t border-gray-100 shadow-lg">
          <div className="px-6 py-2">
            {NAV_LINKS.map((link) =>
              link.isRoute ? (
                <Link
                  key={link.label}
                  to={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="flex items-center py-3 text-sm font-semibold text-ub-blue border-b border-gray-50 last:border-0"
                >
                  {link.label}
                  <ArrowRight size={14} className="ml-auto" />
                </Link>
              ) : (
                <a
                  key={link.label}
                  href={link.href}
                  onClick={() => setMobileOpen(false)}
                  className="block py-3 text-sm font-medium border-b border-gray-50 last:border-0 text-gray-700 hover:text-ub-blue transition-colors"
                >
                  {link.label}
                </a>
              ),
            )}
            {/* Login row in mobile drawer */}
            <Link
              to="/complaint"
              onClick={() => setMobileOpen(false)}
              className="flex items-center gap-2 py-3 text-sm font-semibold text-ub-blue"
            >
              <User size={14} className="flex-shrink-0" />
              Login to Dashboard
              <ArrowRight size={14} className="ml-auto" />
            </Link>
          </div>
        </div>
      )}
    </>
  );
}
