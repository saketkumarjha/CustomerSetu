import { useState, useEffect, useCallback } from "react";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "../../lib/api";
import type { CustomerCard as CustomerCardType } from "../../types";
import { CustomerCard } from "./CustomerCard";
import { Customer360Modal } from "./Customer360Modal";

const STATUS_OPTIONS = ["", "Open", "In Progress", "Pending", "Resolved", "Escalated"];
const CHANNEL_OPTIONS = ["", "web", "email", "whatsapp", "branch", "ivr"];

export function CustomerViewTab() {
  const [customers, setCustomers] = useState<CustomerCardType[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [selectedCif, setSelectedCif] = useState<string | null>(null);
  const PAGE_SIZE = 12;

  const load = useCallback(() => {
    setLoading(true);
    api.customers.list({ page, page_size: PAGE_SIZE, search, status: statusFilter, channel: channelFilter })
      .then((res) => {
        setCustomers(res.customers);
        setTotal(res.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, search, statusFilter, channelFilter]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  }

  function handleFilterChange(setter: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLSelectElement>) => {
      setter(e.target.value);
      setPage(1);
    };
  }

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-slate-800">360° Customer View</h1>
        <p className="text-sm text-slate-400 mt-0.5">Complete customer history across all channels</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-[200px]">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by name, email, phone, CIF…"
              className="w-full pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-ub-blue/30"
            />
          </div>
          <button type="submit" className="px-4 py-2 bg-ub-blue text-white text-sm rounded-lg hover:bg-ub-blue/90 transition-colors">
            Search
          </button>
        </form>

        <select
          value={statusFilter}
          onChange={handleFilterChange(setStatusFilter)}
          className="px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-ub-blue/30 bg-white"
        >
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.filter(Boolean).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          value={channelFilter}
          onChange={handleFilterChange(setChannelFilter)}
          className="px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-ub-blue/30 bg-white"
        >
          <option value="">All Channels</option>
          {CHANNEL_OPTIONS.filter(Boolean).map((c) => (
            <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
          ))}
        </select>

        <span className="text-xs text-slate-400 ml-auto">{total} customer{total !== 1 ? "s" : ""}</span>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: PAGE_SIZE }).map((_, i) => (
            <div key={i} className="h-48 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : customers.length === 0 ? (
        <div className="text-center py-16 text-slate-400">
          <p className="text-base font-medium">No customers found</p>
          <p className="text-sm mt-1">Try adjusting your search or filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {customers.map((c) => (
            <CustomerCard key={c.cif_id} customer={c} onClick={() => setSelectedCif(c.cif_id)} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-sm text-slate-600">
            Page <span className="font-semibold">{page}</span> of <span className="font-semibold">{totalPages}</span>
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}

      {/* Detail modal */}
      {selectedCif && (
        <Customer360Modal
          cifId={selectedCif}
          onClose={() => setSelectedCif(null)}
        />
      )}
    </div>
  );
}
