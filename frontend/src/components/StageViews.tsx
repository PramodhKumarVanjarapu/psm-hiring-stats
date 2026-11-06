import { num, pct, ratio } from "../format";
import { STAGES, STAGE_LABELS, STAGE_NAMES, type PriorityRow, type Stage, type StageCounts, type StageStats } from "../types";
import { LabelChip, StageDot, Table, Td, Th } from "./ui";

export const countsOf = (stages: Record<Stage, StageStats>): StageCounts =>
  Object.fromEntries(STAGES.map((s) => [s, stages[s]?.unique ?? 0])) as StageCounts;

export const missingOf = (stages: Record<Stage, StageStats>): Stage[] => STAGES.filter((s) => stages[s] && !stages[s].present);

export function StageSummaryTable({ stages }: { stages: Record<Stage, StageStats> }) {
  return (
    <Table head={["Stage", <Th num>Unique</Th>, <Th num>Academy</Th>, <Th num>Intensive</Th>, <Th num>External</Th>,
      <Th num>Academy in bucket A–D</Th>, <Th num>TR cleared</Th>, <Th num>% of TA</Th>, <Th num>% of previous</Th>]}>
      {STAGES.map((s) => {
        const st = stages[s];
        return (
          <tr key={s}>
            <Td><span className="flex items-center gap-2"><StageDot stage={s} /><span className="font-medium">{s}</span><span className="hidden text-muted md:inline">{STAGE_NAMES[s]}</span></span></Td>
            <Td num className="font-semibold">{num(st.unique)}</Td>
            <Td num>{num(st.academy)}</Td>
            <Td num>{num(st.intensive)}</Td>
            <Td num>{num(st.external)}</Td>
            <Td num>{num(st.academy_in_bucket)}</Td>
            <Td num>{num(st.tr_cleared)}</Td>
            <Td num>{pct(st.pct_of_ta)}</Td>
            <Td num>{s === "TA" ? "–" : pct(st.pct_of_prev)}</Td>
          </tr>
        );
      })}
    </Table>
  );
}

/** Priority / status counts per stage. `split` (from a fresh analysis) adds the product breakdown. */
export function PriorityTables({ stages, split }: { stages: Record<Stage, StageStats>; split?: Partial<Record<Stage, PriorityRow[]>> }) {
  const codes = STAGES.filter((s) => STAGE_LABELS[s]);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {codes.map((s) => {
        const total = stages[s].unique;
        const labels = [...(STAGE_LABELS[s] || []), "Other / blank"];
        const rows = split?.[s];
        return (
          <div key={s}>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><StageDot stage={s} />{s}<span className="font-normal text-muted">{STAGE_NAMES[s]}</span></h3>
            <Table head={rows
              ? ["Value", <Th num>Candidates</Th>, <Th num>Academy</Th>, <Th num>Intensive</Th>, <Th num>External</Th>]
              : ["Value", <Th num>Candidates</Th>, <Th num>% of stage</Th>]}>
              {labels.map((l) => {
                const r = rows?.find((x) => x.label === l);
                const n = r ? r.candidates : stages[s].priority?.[l] ?? 0;
                return (
                  <tr key={l}>
                    <Td><LabelChip label={l} /></Td>
                    <Td num className="font-semibold">{num(n)}</Td>
                    {r ? (
                      <>
                        <Td num>{num(r.academy)}</Td>
                        <Td num>{num(r.intensive)}</Td>
                        <Td num>{num(r.external)}</Td>
                      </>
                    ) : (
                      <Td num>{pct(ratio(n, total))}</Td>
                    )}
                  </tr>
                );
              })}
            </Table>
          </div>
        );
      })}
    </div>
  );
}

const BUCKET_ROWS: [string, string][] = [["A", "Bucket A"], ["B", "Bucket B"], ["C", "Bucket C"], ["D", "Bucket D"],
  ["other", "Other bucket"], ["not_in_bucket", "Not in bucket"]];

export function BucketFunnelTable({ stages }: { stages: Record<Stage, StageStats> }) {
  return (
    <>
      <p className="mb-3 text-sm text-muted">Academy candidates only. Each column adds up to that stage's Academy total.</p>
      <Table head={["Bucket", ...STAGES.map((s) => <Th num key={s}>{s}</Th>), <Th num>SP % of TA</Th>, <Th num>TR cleared at SP</Th>]}>
        {BUCKET_ROWS.map(([key, label]) => {
          const c = (s: Stage) => stages[s]?.buckets?.[key]?.candidates ?? 0;
          return (
            <tr key={key}>
              <Td className="font-medium">{label}</Td>
              {STAGES.map((s) => <Td num key={s}>{num(c(s))}</Td>)}
              <Td num className="font-semibold">{pct(ratio(c("SP"), c("TA")))}</Td>
              <Td num>{num(stages.SP?.buckets?.[key]?.tr_cleared ?? 0)}</Td>
            </tr>
          );
        })}
      </Table>
    </>
  );
}
