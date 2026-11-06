import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Button, Dialog, ErrorNote, Field, Input, LabelChip, Loading, Note, PageHeader, Section, Select, StageDot, Table, Td } from "../components/ui";
import { date } from "../format";
import { STAGES, type Category, type Student, type StudentEdit } from "../types";

const FIELD_NAMES: Record<string, string> = {
  name: "Name", product: "Product", category: "Product category", bucket: "Bucket", tr_cleared: "TR cleared",
  mobile: "Mobile", emails: "Emails", user_ids: "User ids", unlocked: "Unlocked", merged: "Merged",
};

function Locked({ on }: { on: boolean }) {
  return on ? <span className="ml-2 rounded bg-sunken px-1.5 py-0.5 text-xs text-muted" title="Edited by hand. Sheet saves won't change it.">edited</span> : null;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[9rem_1fr] gap-3 border-b border-line py-2.5 text-sm last:border-0">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

function ListEditor({ label, values, onChange, placeholder }: { label: string; values: string[]; onChange: (v: string[]) => void; placeholder: string }) {
  const [draft, setDraft] = useState("");
  const add = () => { const v = draft.trim(); if (v && !values.includes(v)) onChange([...values, v]); setDraft(""); };
  return (
    <Field label={label}>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {values.map((v) => (
          <span key={v} className="inline-flex items-center gap-1 rounded bg-sunken px-2 py-0.5 text-sm">
            {v}
            <button type="button" aria-label={`Remove ${v}`} className="text-muted hover:text-bad" onClick={() => onChange(values.filter((x) => x !== v))}>×</button>
          </span>
        ))}
        {!values.length && <span className="text-sm text-faint">None</span>}
      </div>
      <div className="flex gap-2">
        <Input value={draft} placeholder={placeholder} onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
        <Button type="button" onClick={add}>Add</Button>
      </div>
    </Field>
  );
}

function EditForm({ s, onDone }: { s: Student; onDone: () => void }) {
  const qc = useQueryClient();
  const [f, setF] = useState({
    name: s.name || "", product: s.product || "", category: (s.category || "External") as Category,
    bucket: s.bucket || "", tr_cleared: !!s.tr_cleared, mobile: s.mobile || "", note: "",
  });
  const [emails, setEmails] = useState(s.emails);
  const [uids, setUids] = useState(s.user_ids);
  const [unlock, setUnlock] = useState<string[]>([]);

  const m = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { note: f.note || undefined };
      if (f.name !== (s.name || "")) body.name = f.name;
      if (f.product !== (s.product || "")) body.product = f.product;
      if (f.category !== s.category) body.category = f.category;
      if (f.bucket !== (s.bucket || "")) body.bucket = f.bucket || null;
      if (f.tr_cleared !== !!s.tr_cleared) body.tr_cleared = f.tr_cleared;
      if (f.mobile && f.mobile !== (s.mobile || "")) body.mobile = f.mobile;
      body.add_emails = emails.filter((e) => !s.emails.includes(e));
      body.remove_emails = s.emails.filter((e) => !emails.includes(e));
      body.add_user_ids = uids.filter((u) => !s.user_ids.includes(u));
      body.remove_user_ids = s.user_ids.filter((u) => !uids.includes(u));
      body.unlock = unlock;
      return api<Student>(`/api/v1/students/${s.student_id}`, { method: "PATCH", body });
    },
    onSuccess: () => { qc.invalidateQueries(); onDone(); },
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  return (
    <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="space-y-4">
      <p className="text-sm text-muted">Fields you change here are marked as edited. Later sheet saves won't overwrite them.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name"><Input value={f.name} onChange={set("name")} required /></Field>
        <Field label="Mobile"><Input value={f.mobile} onChange={set("mobile")} inputMode="tel" /></Field>
        <Field label="Product"><Input value={f.product} onChange={set("product")} /></Field>
        <Field label="Product category">
          <Select value={f.category} onChange={set("category")}><option>Academy</option><option>Intensive</option><option>External</option></Select>
        </Field>
        <Field label="Bucket">
          <Select value={f.bucket} onChange={set("bucket")}>
            <option value="">Not in a bucket</option>{["A", "B", "C", "D"].map((b) => <option key={b}>{b}</option>)}
            {f.bucket && !["A", "B", "C", "D"].includes(f.bucket) && <option>{f.bucket}</option>}
          </Select>
        </Field>
        <label className="mt-6 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={f.tr_cleared} onChange={(e) => setF({ ...f, tr_cleared: e.target.checked })} className="h-4 w-4 accent-[var(--primary)]" />
          TR cleared
        </label>
      </div>
      <ListEditor label="Emails" values={emails} onChange={setEmails} placeholder="name@example.com" />
      <ListEditor label="User ids" values={uids} onChange={setUids} placeholder="User id" />
      {s.locked_fields.length > 0 && (
        <fieldset>
          <legend className="mb-1 text-sm font-medium">Let sheet saves update these again</legend>
          <div className="flex flex-wrap gap-4">
            {s.locked_fields.map((l) => (
              <label key={l} className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4 accent-[var(--primary)]" checked={unlock.includes(l)}
                  onChange={(e) => setUnlock(e.target.checked ? [...unlock, l] : unlock.filter((x) => x !== l))} />
                {FIELD_NAMES[l] || l}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <Field label="Note" hint="Optional. Shown in the edit history."><Input value={f.note} onChange={set("note")} placeholder="Why this change?" /></Field>
      {m.error && <ErrorNote error={m.error} />}
      <div className="flex justify-end gap-2"><Button type="button" onClick={onDone}>Cancel</Button><Button type="submit" variant="primary" disabled={m.isPending}>Save changes</Button></div>
    </form>
  );
}

function MergeForm({ s, onDone }: { s: Student; onDone: () => void }) {
  const qc = useQueryClient();
  const [other, setOther] = useState("");
  const lookup = useQuery({
    queryKey: ["merge-lookup", other],
    queryFn: () => api<{ items: { student_id: string; name?: string; mobile?: string; emails: string[] }[] }>("/api/v1/students", { query: { q: other, limit: 5 } }),
    enabled: other.trim().length >= 3,
  });
  const m = useMutation({
    mutationFn: (mergeId: string) => api(`/api/v1/students/merge`, { method: "POST", body: { keep_id: s.student_id, merge_id: mergeId } }),
    onSuccess: () => { qc.invalidateQueries(); onDone(); },
  });
  const options = (lookup.data?.items || []).filter((x) => x.student_id !== s.student_id);
  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">Find the duplicate record. Its jobs, emails and user ids move into {s.name || "this student"}, and the duplicate is removed (a copy is kept).</p>
      <Field label="Search the duplicate"><Input value={other} onChange={(e) => setOther(e.target.value)} placeholder="Name, mobile or email" /></Field>
      {options.map((o) => (
        <div key={o.student_id} className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2 text-sm">
          <span><span className="font-medium">{o.name || "Unnamed"}</span> <span className="text-muted">{o.mobile || o.emails[0]}</span></span>
          <Button disabled={m.isPending} onClick={() => m.mutate(o.student_id)}>Merge into this student</Button>
        </div>
      ))}
      {other.trim().length >= 3 && lookup.isSuccess && !options.length && <p className="text-sm text-muted">No other student matches.</p>}
      {m.error && <ErrorNote error={m.error} />}
    </div>
  );
}

function describe(e: StudentEdit) {
  return Object.entries(e.changes).map(([k, v]) => {
    const fmt = (x: unknown) => Array.isArray(x) ? (x.length ? x.join(", ") : "none") : x === null || x === undefined || x === "" ? "empty" : String(x);
    if (k === "merged") return `Merged record ${fmt(v.from)} into this student`;
    if (k === "unlocked") return `Sheet saves may update again: ${fmt(v.to)}`;
    return `${FIELD_NAMES[k] || k}: ${fmt(v.from)} → ${fmt(v.to)}`;
  });
}

export function StudentPage() {
  const { id = "" } = useParams();
  const { can } = useAuth();
  const [dialog, setDialog] = useState<"" | "edit" | "merge">("");
  const q = useQuery({ queryKey: ["student", id], queryFn: () => api<Student>(`/api/v1/students/${id}`) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const s = q.data!;
  const lock = (f: string) => s.locked_fields.includes(f);
  const reachedSp = s.applications.filter((a) => a.stages.SP).length;

  return (
    <>
      <PageHeader
        title={s.name || "Unnamed student"}
        sub={`${s.applications.length} job${s.applications.length === 1 ? "" : "s"}, profiles shared in ${reachedSp}`}
        actions={can("editor") && <><Button onClick={() => setDialog("merge")}>Merge a duplicate</Button><Button variant="primary" onClick={() => setDialog("edit")}>Edit student</Button></>}
      />
      {s.student_id !== id && <div className="mb-6"><Note>This record was merged into the one shown here.</Note></div>}

      <div className="grid gap-8 xl:grid-cols-[minmax(0,22rem)_1fr]">
        <Section title="Details">
          <dl className="rounded-lg border border-line bg-surface px-4">
            <Row label="Name">{s.name || "–"}<Locked on={lock("name")} /></Row>
            <Row label="Mobile">{s.mobile || <span className="text-faint">–</span>}</Row>
            <Row label="Emails">{s.emails.length ? s.emails.join(", ") : <span className="text-faint">–</span>}</Row>
            <Row label="User ids">{s.user_ids.length ? s.user_ids.join(", ") : <span className="text-faint">–</span>}</Row>
            <Row label="Product">{s.product || <span className="text-faint">–</span>}<Locked on={lock("product")} /></Row>
            <Row label="Category">{s.category || "–"}<Locked on={lock("category")} /></Row>
            <Row label="Bucket">{s.bucket || <span className="text-faint">–</span>}<Locked on={lock("bucket")} /></Row>
            <Row label="TR cleared">{s.tr_cleared ? "Yes" : "No"}<Locked on={lock("tr_cleared")} /></Row>
            <Row label="Up to date as of">{date(s.profile_as_of, true)}</Row>
          </dl>
        </Section>

        <Section title="Jobs">
          {!s.applications.length ? <p className="text-sm text-muted">Not part of any saved job.</p> : (
            <Table head={["Job", "Company", ...STAGES, "Bucket then"]}>
              {s.applications.map((a) => (
                <tr key={a.job_id}>
                  <Td><Link className="font-medium text-primary hover:underline" to={`/jobs/${encodeURIComponent(a.job_id)}`}>{a.job_id}</Link><div className="text-xs text-muted">{date(a.run_at)}</div></Td>
                  <Td>{a.company || <span className="text-faint">–</span>}{a.role && <div className="text-xs text-muted">{a.role}</div>}</Td>
                  {STAGES.map((st) => (
                    <Td key={st}>{st === "TA" ? (a.stages.TA ? <StageDot stage="TA" /> : <span className="text-faint">–</span>) : <LabelChip label={a.stages[st]} />}</Td>
                  ))}
                  <Td>{a.bucket || <span className="text-faint">–</span>}</Td>
                </tr>
              ))}
            </Table>
          )}
        </Section>
      </div>

      <Section title="Edit history">
        {!s.edits?.length ? <p className="text-sm text-muted">No hand edits.</p> : (
          <ol className="space-y-3">
            {s.edits.map((e) => (
              <li key={e.id} className="rounded-lg border border-line bg-surface px-4 py-3 text-sm">
                <div className="mb-1 text-muted">{date(e.at, true)} by {e.by}</div>
                <ul className="list-disc pl-5">{describe(e).map((d, i) => <li key={i}>{d}</li>)}</ul>
                {e.note && <p className="mt-1 text-muted">Note: {e.note}</p>}
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Dialog wide open={dialog === "edit"} onClose={() => setDialog("")} title="Edit student"><EditForm s={s} onDone={() => setDialog("")} /></Dialog>
      <Dialog wide open={dialog === "merge"} onClose={() => setDialog("")} title="Merge a duplicate"><MergeForm s={s} onDone={() => setDialog("")} /></Dialog>
    </>
  );
}
