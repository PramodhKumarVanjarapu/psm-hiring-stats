import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { FunnelStrip } from "../components/FunnelStrip";
import { BucketFunnelTable, PriorityTables, StageSummaryTable, countsOf, missingOf } from "../components/StageViews";
import { Button, ErrorNote, Field, Input, Loading, Note, PageHeader, Section, Select, Table, Tabs, Td, Th } from "../components/ui";
import { date, num, pct } from "../format";
import { STAGES, STAGE_NAMES, type Analysis, type SaveResult, type Stage } from "../types";

function CopyEmail({ email }: { email: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="font-medium text-primary hover:underline"
      onClick={() => navigator.clipboard.writeText(email).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); })}
    >
      {done ? "Copied" : email}
    </button>
  );
}

function StartForm() {
  const nav = useNavigate();
  const setup = useQuery({ queryKey: ["analysis-setup"], queryFn: () => api<{ service_account_email: string }>("/api/v1/analyses/setup") });
  const recent = useQuery({ queryKey: ["analyses"], queryFn: () => api<Analysis[]>("/api/v1/analyses") });
  const [f, setF] = useState({ job_id: "", sheet_url: "", company: "", role: "" });
  const start = useMutation({
    mutationFn: () => api<Analysis>("/api/v1/analyses", { method: "POST", body: f }),
    onSuccess: (a) => nav(`/analyses/${a.id}`),
  });
  const submit = (e: FormEvent) => { e.preventDefault(); start.mutate(); };
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  return (
    <>
      <PageHeader title="New analysis" sub="Reads the job's internal sheet (tabs TA, RS, SC, AS, SP) and shows the stats before you save." />
      <form onSubmit={submit} className="mb-10 grid max-w-3xl gap-4 sm:grid-cols-2">
        <Field label="Job ID"><Input required value={f.job_id} onChange={set("job_id")} placeholder="e.g. NUB-0425" /></Field>
        <Field label="Internal sheet link" className="sm:col-span-2" hint={setup.data?.service_account_email
          ? <>Share the sheet with <CopyEmail email={setup.data.service_account_email} /> as Viewer first.</>
          : "Share the sheet with the service account as Viewer first."}>
          <Input required type="url" value={f.sheet_url} onChange={set("sheet_url")} placeholder="https://docs.google.com/spreadsheets/d/…" />
        </Field>
        <Field label="Company" hint="Optional, but needed for company-level stats."><Input value={f.company} onChange={set("company")} placeholder="e.g. Nubra" /></Field>
        <Field label="Role" hint="Optional."><Input value={f.role} onChange={set("role")} placeholder="e.g. Product Intern" /></Field>
        <div className="sm:col-span-2">
          {start.error && <div className="mb-3"><ErrorNote error={start.error} /></div>}
          <Button type="submit" variant="primary" disabled={start.isPending}>{start.isPending ? "Starting…" : "Run analysis"}</Button>
        </div>
      </form>

      <Section title="Recent analyses">
        {recent.isLoading ? <Loading /> : !recent.data?.length ? <p className="text-sm text-muted">None yet.</p> : (
          <Table head={["Job", "Company", "Status", "Started by", "Started"]}>
            {recent.data.map((a) => (
              <tr key={a.id}>
                <Td><Link className="font-medium text-primary hover:underline" to={`/analyses/${a.id}`}>{a.job_id}</Link></Td>
                <Td>{a.company || <span className="text-faint">–</span>}</Td>
                <Td><StatusText a={a} /></Td>
                <Td className="text-muted">{a.created_by}</Td>
                <Td className="whitespace-nowrap text-muted">{date(a.created_at, true)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Section>
    </>
  );
}

function StatusText({ a }: { a: Analysis }) {
  const map = {
    queued: ["Waiting", "text-muted"], running: ["Running", "text-primary"], done: ["Ready to save", "text-warn"],
    failed: ["Failed", "text-bad"], saved: ["Saved", "text-good"]
  } as const;
  const [t, c] = map[a.status];
  return <span className={`font-medium ${c}`}>{t}</span>;
}

function SaveSummary({ r }: { r: SaveResult }) {
  return (
    <Note tone={r.status === "saved" ? "good" : "info"}>
      {r.status === "saved" ? (
        <>
          <strong>Saved.</strong> Students: {num(r.students_created)} new, {num(r.students_updated)} updated, {num(r.students_merged)} merged.
          {" "}Applications: {num(r.applications)}{r.applications_removed ? ` (${num(r.applications_removed)} removed from the earlier run)` : ""}.
          {" "}Identity conflicts: {num(r.identity_conflicts)}.{r.master_sheet === "appended" ? " Master sheet updated." : ""}
        </>
      ) : "This run was already saved. Nothing was duplicated."}
    </Note>
  );
}

function Preview({ a }: { a: Analysis }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState<"summary" | "priority" | "buckets" | "products" | "checks">("summary");
  const [prodStage, setProdStage] = useState<Stage>("TA");
  const save = useMutation({
    mutationFn: () => api<SaveResult>(`/api/v1/analyses/${a.id}/save`, { method: "POST" }),
    onSuccess: () => { qc.invalidateQueries(); },
  });
  const p = a.preview!;
  const result = save.data || a.save_result;
  const saved = a.status === "saved" || !!save.data;

  return (
    <>
      {p.warnings.length > 0 && <div className="mb-6 space-y-2">{p.warnings.map((w, i) => <Note key={i} tone="warn">{w}</Note>)}</div>}

      <div className="mb-8 flex flex-wrap items-center gap-3">
        {!saved && can("editor") && (
          <Button variant="primary" disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? "Saving… (a sleeping server can take a minute)" : "Save to database"}
          </Button>
        )}
        {saved && <Link to={`/jobs/${encodeURIComponent(a.job_id)}`}><Button variant="primary">Open the job</Button></Link>}
        <Link to="/analyses/new"><Button>Run another analysis</Button></Link>
      </div>
      {save.error && <div className="mb-6"><ErrorNote error={save.error} /></div>}
      {result && <div className="mb-6 space-y-2"><SaveSummary r={result} />{result.warnings?.map((w, i) => <Note key={i} tone="warn">{w}</Note>)}</div>}

      <Section title="Funnel"><FunnelStrip counts={countsOf(p.stages)} missing={missingOf(p.stages)} /></Section>

      <Tabs value={tab} onChange={setTab} items={[
        { id: "summary", label: "Stage summary" }, { id: "priority", label: "Priority / status" },
        { id: "buckets", label: "Buckets A–D" }, { id: "products", label: "Products" }, { id: "checks", label: "Data checks" },
      ]} />
      {tab === "summary" && <StageSummaryTable stages={p.stages} />}
      {tab === "priority" && <PriorityTables stages={p.stages} split={p.priority_tables} />}
      {tab === "buckets" && <BucketFunnelTable stages={p.stages} />}
      {tab === "products" && (
        <>
          <Field label="Stage" className="mb-4 max-w-xs">
            <Select value={prodStage} onChange={(e) => setProdStage(e.target.value as Stage)}>
              {STAGES.map((s) => <option key={s} value={s}>{s} – {STAGE_NAMES[s]}</option>)}
            </Select>
          </Field>
          <Table head={["Product category", <Th num>Candidates</Th>, <Th num>TR cleared</Th>, <Th num>TR cleared %</Th>]}>
            {p.product_tables[prodStage].map((r) => (
              <tr key={r.category}><Td>{r.category}</Td><Td num>{num(r.candidates)}</Td><Td num>{num(r.tr_cleared)}</Td><Td num>{pct(r.tr_cleared_pct)}</Td></tr>
            ))}
          </Table>
        </>
      )}
      {tab === "checks" && (
        <div className="space-y-6 text-sm">
          <Table head={["Stage", "Tabs used", "Name column", "Priority / status column", <Th num>Rows</Th>, <Th num>Unique</Th>]}>
            {STAGES.map((s) => (
              <tr key={s}>
                <Td className="font-medium">{s}</Td>
                <Td>{p.checks.tabs_used[s].join(", ") || <span className="text-faint">No tab found</span>}</Td>
                <Td>{!p.checks.tabs_used[s].length ? <span className="text-faint">–</span> : p.checks.name_columns?.[s]?.join(", ") || <span className="text-warn">None found</span>}</Td>
                <Td>{s === "TA" ? <span className="text-faint">–</span> : p.checks.priority_columns[s].join(", ") || <span className="text-warn">None found</span>}</Td>
                <Td num>{num(p.checks.row_counts[s].rows)}</Td>
                <Td num>{num(p.checks.row_counts[s].unique)}</Td>
              </tr>
            ))}
          </Table>
          <div>
            <h3 className="mb-1 font-semibold">Tabs used for product mapping</h3>
            {p.checks.product_tabs.length ? <ul className="list-disc pl-5 text-muted">{p.checks.product_tabs.map((t) => <li key={t}>{t}</li>)}</ul> : <p className="text-muted">None</p>}
          </div>
          <div>
            <h3 className="mb-1 font-semibold">Tabs used for names</h3>
            {p.checks.name_tabs?.length ? <ul className="list-disc pl-5 text-muted">{p.checks.name_tabs.map((t) => <li key={t}>{t}</li>)}</ul> : <p className="text-muted">None</p>}
          </div>
          {p.checks.skipped.length > 0 && (
            <div>
              <h3 className="mb-1 font-semibold">Tabs skipped</h3>
              <ul className="list-disc pl-5 text-muted">{p.checks.skipped.map((t) => <li key={t}>{t}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </>
  );
}

function AnalysisView({ id }: { id: string }) {
  const q = useQuery({
    queryKey: ["analysis", id],
    queryFn: () => api<Analysis>(`/api/v1/analyses/${id}`),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "queued" || s === "running" ? 1500 : false;
    },
  });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const a = q.data!;
  const title = <>{a.job_id}{a.company && <span className="font-normal text-muted"> at {a.company}</span>}</>;

  return (
    <>
      <PageHeader title={title} sub={a.preview?.sheet_title ? `Sheet: ${a.preview.sheet_title}` : <a className="text-primary hover:underline" href={a.sheet_url} target="_blank" rel="noreferrer">Open sheet</a>} />
      {(a.status === "queued" || a.status === "running") && (
        <div className="rounded-lg border border-line bg-surface px-5 py-6" aria-live="polite">
          <div className="mb-3 h-1.5 overflow-hidden rounded bg-sunken"><div className="h-full w-1/3 animate-pulse rounded bg-primary" /></div>
          <p className="font-medium">Reading the sheet…</p>
          <p className="text-sm text-muted">{a.message}</p>
        </div>
      )}
      {a.status === "failed" && (
        <div className="space-y-4">
          <Note tone="bad">{a.message}</Note>
          <Link to="/analyses/new"><Button>Try again</Button></Link>
        </div>
      )}
      {(a.status === "done" || a.status === "saved") && a.preview && <Preview a={a} />}
    </>
  );
}

export function NewAnalysisPage() {
  const { id } = useParams();
  return id ? <AnalysisView key={id} id={id} /> : <StartForm />;
}
