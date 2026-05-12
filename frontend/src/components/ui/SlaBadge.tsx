import { Badge } from "./Badge";

interface Props {
  breached: boolean;
  label: string;
}

export function SlaBadge({ breached, label }: Props) {
  if (!label || label === "—") {
    return <span className="text-xs text-slate-300">—</span>;
  }
  if (breached || label === "BREACHED" || label === "Breached") {
    return (
      <Badge variant="destructive" className="uppercase tracking-wide">
        Breached
      </Badge>
    );
  }
  return (
    <Badge variant="slaSafe" className="tabular-nums font-semibold">
      {label}
    </Badge>
  );
}
