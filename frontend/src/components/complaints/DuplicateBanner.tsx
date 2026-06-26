import { useEffect, useState } from "react";
import { api } from "../../lib/api";


interface MergeModalProps {
  primaryId: string;
  secondaryId: string;
  primaryChannel?: string;
  secondaryChannel?: string;
  primaryText?: string;
  secondaryText?: string;
  primaryCif?: string | null;
  secondaryCif?: string | null;
  onClose: () => void;
  onMerged: () => void;
}

export function MergeModal({
  primaryId, secondaryId,
  primaryChannel, secondaryChannel,
  primaryText, secondaryText,
  primaryCif, secondaryCif,
  onClose, onMerged,
}: MergeModalProps) {
  const [merging, setMerging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chosenPrimary, setChosenPrimary] = useState<"left" | "right" | null>(null);

  const doMerge = async (primId: string, secId: string) => {
    setMerging(true);
    setError(null);
    try {
      await api.duplicates.merge(primId, secId);
      onMerged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Merge failed");
    } finally {
      setMerging(false);
    }
  };

  const sides = [
    { id: primaryId, channel: primaryChannel, text: primaryText, cif: primaryCif, side: "left" as const },
    { id: secondaryId, channel: secondaryChannel, text: secondaryText, cif: secondaryCif, side: "right" as const },
  ];

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl mx-4 p-6">
        <h2 className="text-sm font-semibold text-gray-800 mb-1">Merge duplicate complaints</h2>
        <p className="text-xs text-gray-500 mb-4">Pick which complaint becomes the primary. The other will be soft-hidden (merged into the primary).</p>
        {error && (
          <div className="mb-3 rounded bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-700">{error}</div>
        )}
        <div className="grid grid-cols-2 gap-4">
          {sides.map((s) => (
            <div key={s.id} className="border rounded-lg p-3 space-y-1">
              <p className="text-xs font-mono text-gray-500">{s.id}</p>
              <p className="text-xs text-gray-400">Channel: <span className="font-medium text-gray-600">{s.channel ?? "—"}</span></p>
              {s.cif && <p className="text-xs text-gray-400">CIF: <span className="font-mono">{s.cif.slice(0, 8)}…</span></p>}
              <p className="text-xs text-gray-700 line-clamp-4 mt-1">{s.text || "—"}</p>
              <button
                disabled={merging}
                onClick={() => {
                  setChosenPrimary(s.side);
                  const other = sides.find((x) => x.side !== s.side)!;
                  doMerge(s.id, other.id);
                }}
                className="mt-2 w-full text-xs px-3 py-1.5 rounded bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50"
              >
                {merging && chosenPrimary === s.side ? "Merging…" : "Make Primary"}
              </button>
            </div>
          ))}
        </div>
        <button onClick={onClose} className="mt-4 text-xs text-gray-400 hover:text-gray-600">Cancel</button>
      </div>
    </div>
  );
}


interface DuplicateBannerProps {
  complaintId: string;
  duplicateStatus: 'possible_duplicate' | 'confirmed_duplicate' | 'merged';
  duplicateOf: string[];
  ownCifId?: string | null;
  ownChannel?: string;
  ownText?: string;
  onActionComplete: () => void;
}

export function DuplicateBanner({
  complaintId, duplicateStatus, duplicateOf, ownCifId, ownChannel, ownText, onActionComplete,
}: DuplicateBannerProps) {
  const [relatedMap, setRelatedMap] = useState<Record<string, { channel?: string; cif_id?: string | null; text?: string }>>({});
  const [loadedIds, setLoadedIds] = useState<Set<string>>(new Set());
  const [showMerge, setShowMerge] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!duplicateOf.length) return;
    setLoadedIds(new Set());
    duplicateOf.forEach((id) => {
      api.complaints.get(id).then((c) => {
        setRelatedMap((prev) => ({
          ...prev,
          [id]: { channel: c.channel, cif_id: c.cif_id, text: c.masked_text ?? c.original_text },
        }));
        setLoadedIds((prev) => new Set([...prev, id]));
      }).catch(() => {
        setLoadedIds((prev) => new Set([...prev, id]));
      });
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [duplicateOf.join(",")]);

  const allLoaded = duplicateOf.every((id) => loadedIds.has(id));
  const allSameCif = allLoaded && duplicateOf.every((id) => relatedMap[id]?.cif_id === ownCifId);
  const canMerge = allLoaded && (duplicateStatus === 'confirmed_duplicate' || allSameCif);

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      await api.duplicates.confirmSamePerson(complaintId);
      onActionComplete();
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 space-y-2">
      <p className="text-xs font-semibold text-amber-800">
        Possible duplicate complaint{duplicateOf.length > 1 ? "s" : ""} detected
      </p>
      <div className="space-y-1.5">
        {duplicateOf.map((id) => {
          const r = relatedMap[id];
          const loaded = loadedIds.has(id);
          const diffCif = loaded && r?.cif_id !== ownCifId;
          return (
            <div key={id} className="flex flex-wrap items-center gap-2 text-xs text-amber-700">
              <span className="font-mono">{id}</span>
              {r?.channel && <span className="text-amber-500">· {r.channel}</span>}
              {diffCif && r?.cif_id && (
                <span className="font-mono text-red-600 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded">
                  Different CIF
                </span>
              )}
              {canMerge && (
                <button
                  onClick={() => setShowMerge(id)}
                  className="text-xs px-2 py-0.5 rounded bg-amber-500 text-white hover:bg-amber-600"
                >
                  Merge
                </button>
              )}
              {!allLoaded && (
                <span className="text-xs text-amber-400 italic">loading…</span>
              )}
              {allLoaded && !canMerge && (
                <span className="text-xs text-amber-400 italic">confirm same person first</span>
              )}
            </div>
          );
        })}
      </div>
      {allLoaded && !allSameCif && duplicateStatus === 'possible_duplicate' && (
        <button
          onClick={handleConfirm}
          disabled={confirming}
          className="text-xs px-2 py-1 rounded border border-amber-500 text-amber-800 hover:bg-amber-100 disabled:opacity-50"
        >
          {confirming ? "Confirming…" : "Confirm same person — unlock merge"}
        </button>
      )}
      {showMerge && (
        <MergeModal
          primaryId={complaintId}
          secondaryId={showMerge}
          primaryChannel={ownChannel}
          secondaryChannel={relatedMap[showMerge]?.channel}
          primaryText={ownText}
          secondaryText={relatedMap[showMerge]?.text}
          primaryCif={ownCifId}
          secondaryCif={relatedMap[showMerge]?.cif_id}
          onClose={() => setShowMerge(null)}
          onMerged={() => { setShowMerge(null); onActionComplete(); }}
        />
      )}
    </div>
  );
}
