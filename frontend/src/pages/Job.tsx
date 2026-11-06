import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, download } from "../api";
import { useAuth } from "../auth";
import { FunnelStrip } from "../components/FunnelStrip";
import { BucketFunnelTable, PriorityTables, StageSummaryTable, countsOf, missingOf } from "../components/StageViews";
import { Button, CategoryTag, Dialog, Empty, ErrorNote, Field, Input, LabelChip, Loading, Note, PageHeader, Pager, Section, Select, Table, Tabs, Td, Th } from "../components/ui";
import { date, num } from "../format";
import { STAGES, STAGE_LABELS, type Candidate, type Job, type Paged, type RunStats, type Stage } from "../types";

const LIMIT = 100;

function Candidates({ jobId }: { jobId: string }) {
  const [f, setF] = useState({ stage: "", label: "", category: "", bucket: "", furthest_stage: "", q: "" });
  const [skip, setSkip] = useState(0);
  const [err, setErr] = useState<unknown>(null);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => {
    setF({ ...f, [k]: e.target.value, ...(k === "stage" ? { label: "" } : {}) });
    setSkip(0);
  };
  const q = useQuery({
    queryKey: ["candidates", jobId, f, skip],
    queryFn: () => api<Paged<Candidate>>(`/api/v1/jobs/${encodeURIComponent(jobId)}/candidates`, { query: { ...f, limit: LIMIT, skip } }),
    placeholderData: keepPreviousData,
  });
  const labels = f.stage ? STAGE_LABELS[f.stage as Stage] : undefined;

  return (
    <>
      <div className="mb-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-7">
        <Input className="sm:col-span-3 lg:col-span-2" type="search" placeholder="Name, mobile, email…" value={f.q} onChange={set("q")} aria-label="Search candidates" />
        <Select value={f.stage} onChange={set("stage")} aria-label="Stage">
          <option value="">Any stage</option>
          {STAGES.map((s) => <option key={s} value={s}>In {s}</option>)}
        </Select>
        <Select value={f.label} onChange={set("label")} disabled={!labels} aria-label="Priority or status">
          <option value="">{labels ? "Any value" : "Pick a stage first"}</option>
          {labels?.concat("Other / blank").map((l) => <option key={l}>{l}</option>)}
        </Select>
        <Select value={f.category} onChange={set("category")} aria-label="Category">
          <option value="">Any product</option><option>Academy</option><option>Intensive</option><option>External</option>
        </Select>
        <Select value={f.bucket} onChange={set("bucket")} aria-label="Bucket">
          <option value="">Any bucket</option>{["A", "B", "C", "D"].map((b) => <option key={b} value={b}>Bucket {b}</option>)}
        </Select>
        <Select value={f.furthest_stage} onChange={set("furthest_stage")} aria-label="Furthest stage">
          <option value="">Any furthest stage</option>
          {STAGES.map((s) => <option key={s} value={s}>Stopped at {s}</option>)}
        </Select>
      </div>
      <div className="mb-3 flex items-center justify-between">
        <span className="num text-sm text-muted">{q.data ? `${num(q.data.total)} candidates` : ""}</span>
        <Button onClick={() => download(`/api/v1/jobs/${encodeURIComponent(jobId)}/candidates.csv`, f).catch(setErr)}>Export CSV</Button>
      </div>
      {!!err && <div className="mb-3"><ErrorNote error={err} /></div>}
      {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> : !q.data?.items.length ? (
        <Empty title="No candidates match these filters" />
      ) : (
        <>
          <Table head={["Name", "Mobile", "Product", "Bucket", "TR", ...STAGES]}>
            {q.data.items.map((c) => (
              <tr key={c.student_id}>
                <Td><Link className="font-medium text-primary hover:underline" to={`/students/${c.student_id}`}>{c.name || "Unnamed"}</Link></Td>
                <Td className="num whitespace-nowrap">{c.mobile || c.emails[0] || "–"}</Td>
                <Td><CategoryTag category={c.category} /></Td>
                <Td>{c.bucket || <span className="text-faint">–</span>}</Td>
                <Td>{c.tr_cleared ? <span className="text-good">Cleared</span> : <span className="text-faint">No</span>}</Td>
                {STAGES.map((s) => <Td key={s}>{s === "TA" ? (c.stages.TA ? <span className="text-muted">Yes</span> : <span className="text-faint">–</span>) : <LabelChip label={c.stages[s]} />}</Td>)}
              </tr>
            ))}
          </Table>
          <Pager total={q.data.total} skip={skip} limit={LIMIT} onChange={setSkip} />
        </>
      )}
    </>
  );
}

function History({ jobId }: { jobId: string }) {
  const q = useQuery({ queryKey: ["runs", jobId], queryFn: () => api<RunStats[]>(`/api/v1/jobs/${encodeURIComponent(jobId)}/runs`) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  return (
    <Table head={["Run date", "Saved", ...STAGES.map((s) => <Th num key={s}>{s}</Th>), "Students", ""]}>
      {q.data!.map((r) => (
        <tr key={r.run_id}>
          <Td className="whitespace-nowrap">{date(r.run_at, true)}</Td>
          <Td className="whitespace-nowrap text-muted">{date(r.saved_at, true)}</Td>
          {STAGES.map((s) => <Td num key={s}>{num(r.stages[s]?.unique)}</Td>)}
          <Td className="whitespace-nowrap text-muted">{r.save_summary ? `${num(r.save_summary.students_created)} new, ${num(r.save_summary.students_merged)} merged` : "–"}</Td>
          <Td>{r.is_latest && <span className="rounded bg-good-bg px-1.5 py-0.5 text-xs font-medium text-good">Latest</span>}</Td>
        </tr>
      ))}
    </Table>
  );
}

function EditDetails({ job, onClose }: { job: Job; onClose: () => void }) {
  const qc = useQueryClient();
  const [company, setCompany] = useState(job.company || "");
  const [role, setRole] = useState(job.role || "");
  const m = useMutation({
    mutationFn: () => api<Job>(`/api/v1/jobs/${encodeURIComponent(job.job_id)}`, { method: "PATCH", body: { company, role } }),
    onSuccess: () => { qc.invalidateQueries(); onClose(); },
  });
  return (
    <div className="space-y-4">
      <Field label="Company"><Input value={company} onChange={(e) => setCompany(e.target.value)} /></Field>
      <Field label="Role"><Input value={role} onChange={(e) => setRole(e.target.value)} /></Field>
      {m.error && <ErrorNote error={m.error} />}
      <div className="flex justify-end gap-2"><Button onClick={onClose}>Cancel</Button><Button variant="primary" disabled={m.isPending} onClick={() => m.mutate()}>Save details</Button></div>
    </div>
  );
}

function DeleteJob({ job, onClose }: { job: Job; onClose: () => void }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [typed, setTyped] = useState("");
  const m = useMutation({
    mutationFn: () => api(`/api/v1/jobs/${encodeURIComponent(job.job_id)}`, { method: "DELETE", query: { confirm: true } }),
    onSuccess: () => { qc.invalidateQueries(); nav("/jobs"); },
  });
  return (
    <div className="space-y-4">
      <p className="text-sm">This removes the job, its {num(job.run_count)} saved run(s) and its student list. Students stay in the database.</p>
      <Field label={`Type ${job.job_id} to confirm`}><Input value={typed} onChange={(e) => setTyped(e.target.value)} /></Field>
      {m.error && <ErrorNote error={m.error} />}
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="danger" disabled={typed.trim() !== job.job_id || m.isPending} onClick={() => m.mutate()}>Delete job</Button>
      </div>
    </div>
  );
}

export function JobPage() {
  const { jobId = "" } = useParams();
  const { can } = useAuth();
  const [tab, setTab] = useState<"candidates" | "summary" | "priority" | "buckets" | "history">("candidates");
  const [dialog, setDialog] = useState<"" | "edit" | "delete">("");
  const q = useQuery({ queryKey: ["job", jobId], queryFn: () => api<Job>(`/api/v1/jobs/${encodeURIComponent(jobId)}`) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const job = q.data!;
  const st = job.latest_stats;

  return (
    <>
      <PageHeader
        title={job.job_id}
        sub={<>
          {job.company ? <Link className="text-primary hover:underline" to={`/companies/${encodeURIComponent(job.company)}`}>{job.company}</Link> : "No company set"}
          {job.role && <> – {job.role}</>}
          {st && <span className="ml-2 text-faint">Last run {date(st.run_at, true)}</span>}
        </>}
        actions={<>
          {job.sheet_url && <a href={job.sheet_url} target="_blank" rel="noreferrer"><Button>Open sheet</Button></a>}
          {can("editor") && <Button onClick={() => setDialog("edit")}>Edit details</Button>}
          {can("admin") && <Button variant="ghost" className="text-bad" onClick={() => setDialog("delete")}>Delete</Button>}
        </>}
      />
      {!job.company && can("editor") && <div className="mb-6"><Note tone="warn">Set the company so this job counts in company stats.</Note></div>}
      {st && <Section title="Funnel"><FunnelStrip counts={countsOf(st.stages)} missing={missingOf(st.stages)} /></Section>}

      <Tabs value={tab} onChange={setTab} items={[
        { id: "candidates", label: "Candidates" }, { id: "summary", label: "Stage summary" },
        { id: "priority", label: "Priority / status" }, { id: "buckets", label: "Buckets A–D" }, { id: "history", label: `History (${job.run_count})` },
      ]} />
      {tab === "candidates" && <Candidates jobId={job.job_id} />}
      {tab === "summary" && st && <StageSummaryTable stages={st.stages} />}
      {tab === "priority" && st && <PriorityTables stages={st.stages} />}
      {tab === "buckets" && st && <BucketFunnelTable stages={st.stages} />}
      {tab === "history" && <History jobId={job.job_id} />}

      <Dialog open={dialog === "edit"} onClose={() => setDialog("")} title="Edit job details"><EditDetails job={job} onClose={() => setDialog("")} /></Dialog>
      <Dialog open={dialog === "delete"} onClose={() => setDialog("")} title={`Delete ${job.job_id}?`}><DeleteJob job={job} onClose={() => setDialog("")} /></Dialog>
    </>
  );
}

