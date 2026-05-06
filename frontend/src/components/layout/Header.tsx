import { Bell, ChevronDown, Menu, X } from 'lucide-react'

interface Props {
  sidebarOpen: boolean
  onMenuToggle: () => void
}

export function Header({ sidebarOpen, onMenuToggle }: Props) {
  return (
    <header className="flex items-center justify-between px-4 md:px-6 py-3 bg-ub-blue shadow-lg flex-shrink-0 z-30">
      <div className="flex items-center gap-3">
        {/* Hamburger — mobile only */}
        <button
          onClick={onMenuToggle}
          className="lg:hidden w-9 h-9 rounded-md flex items-center justify-center text-white hover:bg-white hover:bg-opacity-10 transition-colors flex-shrink-0"
          aria-label="Toggle navigation"
        >
          {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
        </button>

        {/* Logo mark */}
        <div className="w-9 h-9 rounded-md bg-white flex items-center justify-center font-bold text-xs text-ub-blue select-none flex-shrink-0">
          UB
        </div>

        {/* Brand text */}
        <div className="min-w-0">
          <div className="text-white font-bold text-sm tracking-wide whitespace-nowrap">Union Bank of India</div>
          <div className="text-blue-200/90 text-xs hidden sm:block truncate">
            Complaint intelligence workspace
          </div>
        </div>

        {/* Live badge — md+ only */}
        <div className="hidden md:flex items-center gap-2 ml-2 px-3 py-1 rounded-md text-xs bg-white/10 text-blue-100 border border-white/10 flex-shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400/90 inline-block animate-pulse-dot" />
          IDEA 2.0 · AI–CSPARC · Live Demo
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-4 flex-shrink-0">
        {/* Notifications */}
        <div className="relative cursor-pointer">
          <div className="w-9 h-9 rounded-md flex items-center justify-center text-white hover:bg-white hover:bg-opacity-10 transition-colors">
            <Bell size={18} />
          </div>
          <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-ub-red text-white text-xs flex items-center justify-center font-bold">
            3
          </span>
        </div>

        {/* User */}
        <div className="flex items-center gap-2 cursor-pointer group">
          <div className="w-9 h-9 rounded-md bg-white flex items-center justify-center text-xs font-bold text-ub-blue select-none">
            RM
          </div>
          <div className="text-xs leading-tight hidden md:block">
            <div className="text-white font-semibold">Rajiv Menon</div>
            <div className="text-blue-300">Sr. Relationship Manager</div>
          </div>
          <ChevronDown size={14} className="text-blue-300 group-hover:text-white transition-colors hidden md:block" />
        </div>
      </div>
    </header>
  )
}
