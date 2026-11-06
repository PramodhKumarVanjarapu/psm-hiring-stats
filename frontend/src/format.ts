const nf = new Intl.NumberFormat("en-IN");

export const num = (n?: number | null) => (n === undefined || n === null ? "–" : nf.format(n));
export const pct = (n?: number | null) => (n === undefined || n === null ? "–" : `${n.toFixed(1)}%`);
export const ratio = (a: number, b: number) => (b ? Math.round((1000 * a) / b) / 10 : 0);

export function date(iso?: string | null, withTime = false) {
  if (!iso) return "–";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "–";
  return d.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}),
  });
}

export function month(key: string) {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleString("en-IN", { month: "short", year: "2-digit" });
}
