import { num, pct, ratio } from "../format";
import { STAGES, STAGE_NAMES, type Stage, type StageCounts } from "../types";
import { STAGE_BG, cx } from "./ui";

/**
 * The signature element: the five hiring stages as a centred, stepped funnel.
 * Bar width = share of total applications. Between steps: how many moved on from the
 * last stage that exists (a missing tab is skipped, not counted as 0).
 */
export function FunnelStrip({ counts, missing = [] }: { counts: StageCounts; missing?: Stage[] }) {
  const ta = counts.TA || 0;
  let last: { stage: Stage; n: number } | null = null;

  const rows = STAGES.map((s, i) => {
    const n = counts[s] || 0;
    const isMissing = missing.includes(s);
    let step: string | null = null;
    if (!isMissing && last && last.n > 0) {
      const from = last.stage !== STAGES[i - 1] ? ` from ${last.stage}` : "";
      step = n > last.n
        ? `More than ${last.stage}: some jobs have no ${last.stage} tab`
        : `${pct(ratio(n, last.n))} moved on${from}`;
    }
    if (!isMissing) last = { stage: s, n };
    const width = ta ? Math.max((100 * n) / ta, n ? 1.5 : 0) : 0;

    return (
      <li key={s}>
        {step && <p className="num py-1 text-center text-xs text-muted sm:pl-[12rem] sm:pr-[7.5rem]">{step}</p>}
        {!step && i > 0 && <p aria-hidden className="py-1 text-xs">&nbsp;</p>}
        <div className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5 py-0.5 sm:grid-cols-[12rem_1fr_7.5rem]">
          <div className="min-w-0">
            <span className="text-sm font-semibold text-ink">{s}</span>
            <span className="ml-2 text-xs text-muted sm:ml-0 sm:block sm:truncate">{STAGE_NAMES[s]}</span>
          </div>
          <div className="col-span-2 row-start-2 flex h-6 items-center justify-center rounded bg-sunken/60 sm:col-span-1 sm:row-start-auto sm:h-7">
            {isMissing ? (
              <span className="text-xs text-faint">No tab in sheet</span>
            ) : (
              <div className={cx("h-full rounded transition-[width] duration-500", STAGE_BG[s])} style={{ width: `${width}%` }} />
            )}
          </div>
          <div className="text-right">
            <div className="num text-base font-semibold text-ink">{isMissing ? "–" : num(n)}</div>
            {s !== "TA" && !isMissing && <div className="num text-xs text-muted">{ta ? `${pct(ratio(n, ta))} of TA` : "–"}</div>}
          </div>
        </div>
      </li>
    );
  });

  return (
    <figure aria-label="Hiring funnel" className="rounded-lg border border-line bg-surface px-4 py-4 sm:px-6">
      <ol>{rows}</ol>
    </figure>
  );
}
