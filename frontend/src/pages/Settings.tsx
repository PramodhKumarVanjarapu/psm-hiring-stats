import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Button, ErrorNote, Field, Input, Loading, Note, PageHeader, Section, Select, Table, Td } from "../components/ui";
import { date, num } from "../format";
import type { PoolInfo, Role, User } from "../types";

interface SettingsInfo { pools: Record<"bucket" | "tr", PoolInfo>; service_account_email: string; master_sheet_configured: boolean }

function PoolRow({ kind, p }: { kind: "bucket" | "tr"; p: PoolInfo }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const up = useMutation({
    mutationFn: (file: File) => { const fd = new FormData(); fd.append("file", file); return api(`/api/v1/settings/pools/${kind}`, { method: "POST", form: fd }); },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
  return (
    <tr>
      <Td className="font-medium">{p.title}</Td>
      <Td>
        {p.source === "uploaded" && <>{p.filename} <span className="text-muted">– {num(p.rows)} rows, uploaded {date(p.uploaded_at, true)} by {p.uploaded_by}</span></>}
        {p.source === "file" && <span className="text-muted">Using {p.filename} from the server folder</span>}
        {p.source === "missing" && <span className="text-bad">Missing – analyses can't run until it's uploaded</span>}
        {up.error && <div className="mt-2"><ErrorNote error={up.error} /></div>}
        {up.isSuccess && <div className="mt-1 text-sm text-good">Uploaded.</div>}
      </Td>
      <Td>
        {can("admin") && (
          <>
            <input ref={input} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) up.mutate(f); e.target.value = ""; }} />
            <Button disabled={up.isPending} onClick={() => input.current?.click()}>{up.isPending ? "Uploading…" : "Upload CSV"}</Button>
          </>
        )}
      </Td>
    </tr>
  );
}

function Users() {
  const qc = useQueryClient();
  const { user: me } = useAuth();
  const q = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/api/v1/users") });
  const [f, setF] = useState({ email: "", name: "", role: "viewer" as Role, password: "" });
  const add = useMutation({
    mutationFn: () => api<User>("/api/v1/users", { method: "POST", body: f }),
    onSuccess: () => { setF({ email: "", name: "", role: "viewer", password: "" }); qc.invalidateQueries({ queryKey: ["users"] }); },
  });
  const patch = useMutation({
    mutationFn: ({ email, body }: { email: string; body: Partial<User> & { password?: string } }) =>
      api<User>(`/api/v1/users/${encodeURIComponent(email)}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  return (
    <Section title="Users">
      {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> : (
        <Table head={["Name", "Email", "Role", "Status", "Last login", ""]}>
          {q.data!.map((u) => (
            <tr key={u.email}>
              <Td className="font-medium">{u.name}</Td>
              <Td className="text-muted">{u.email}</Td>
              <Td>
                <Select value={u.role} disabled={u.email === me?.email} aria-label={`Role of ${u.email}`}
                  onChange={(e) => patch.mutate({ email: u.email, body: { role: e.target.value as Role } })} className="w-28 py-1">
                  <option value="viewer">Viewer</option><option value="editor">Editor</option><option value="admin">Admin</option>
                </Select>
              </Td>
              <Td>{u.active === false ? <span className="text-bad">Disabled</span> : <span className="text-good">Active</span>}</Td>
              <Td className="whitespace-nowrap text-muted">{date(u.last_login, true)}</Td>
              <Td className="whitespace-nowrap">
                {u.email !== me?.email && (
                  <>
                    <Button variant="ghost" onClick={() => patch.mutate({ email: u.email, body: { active: u.active === false } })}>{u.active === false ? "Enable" : "Disable"}</Button>
                    <Button variant="ghost" onClick={() => { const p = prompt(`New password for ${u.email} (8+ characters)`); if (p) patch.mutate({ email: u.email, body: { password: p } }); }}>Reset password</Button>
                  </>
                )}
              </Td>
            </tr>
          ))}
        </Table>
      )}
      {patch.error && <div className="mt-3"><ErrorNote error={patch.error} /></div>}
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); add.mutate(); }} className="mt-6 grid gap-3 rounded-lg border border-line bg-surface p-4 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
        <Field label="Name"><Input required value={f.name} onChange={set("name")} /></Field>
        <Field label="Email"><Input required type="email" value={f.email} onChange={set("email")} /></Field>
        <Field label="Role"><Select value={f.role} onChange={set("role")}><option value="viewer">Viewer</option><option value="editor">Editor</option><option value="admin">Admin</option></Select></Field>
        <Field label="Password"><Input required minLength={8} type="password" autoComplete="new-password" value={f.password} onChange={set("password")} /></Field>
        <Button type="submit" variant="primary" disabled={add.isPending}>Add user</Button>
        {add.error && <div className="sm:col-span-2 lg:col-span-5"><ErrorNote error={add.error} /></div>}
      </form>
      <p className="mt-2 text-xs text-muted">Viewers can see everything. Editors can also run and save analyses and edit students. Admins can also manage users, upload pool files and delete jobs.</p>
    </Section>
  );
}

function MyPassword() {
  const { setSession } = useAuth();
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const m = useMutation({
    mutationFn: () => api<{ token: string; user: User }>("/api/v1/auth/change-password", { method: "POST", body: { current_password: cur, new_password: next } }),
    onSuccess: (r) => { setSession(r.token, r.user); setCur(""); setNext(""); },
  });
  return (
    <Section title="My password">
      <form onSubmit={(e) => { e.preventDefault(); m.mutate(); }} className="grid max-w-2xl gap-3 sm:grid-cols-3 sm:items-end">
        <Field label="Current password"><Input type="password" autoComplete="current-password" required value={cur} onChange={(e) => setCur(e.target.value)} /></Field>
        <Field label="New password"><Input type="password" autoComplete="new-password" minLength={8} required value={next} onChange={(e) => setNext(e.target.value)} /></Field>
        <Button type="submit" disabled={m.isPending}>Change password</Button>
      </form>
      {m.error && <div className="mt-3 max-w-2xl"><ErrorNote error={m.error} /></div>}
      {m.isSuccess && <div className="mt-3 max-w-2xl"><Note tone="good">Password changed. Other devices are logged out.</Note></div>}
    </Section>
  );
}

export function SettingsPage() {
  const { can } = useAuth();
  const q = useQuery({ queryKey: ["settings"], queryFn: () => api<SettingsInfo>("/api/v1/settings") });
  return (
    <>
      <PageHeader title="Settings" />
      <Section title="Lookup files" aside="Used to find each student's bucket and TR status.">
        {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> : (
          <Table head={["File", "Current", ""]}>
            <PoolRow kind="bucket" p={q.data!.pools.bucket} />
            <PoolRow kind="tr" p={q.data!.pools.tr} />
          </Table>
        )}
      </Section>
      {q.data && (
        <Section title="Google Sheets access">
          <p className="text-sm">
            {q.data.service_account_email
              ? <>Share each internal sheet with <strong className="break-all">{q.data.service_account_email}</strong> as Viewer.</>
              : <span className="text-bad">No service account key is set on the server (GOOGLE_SERVICE_ACCOUNT_JSON).</span>}
          </p>
          <p className="mt-1 text-sm text-muted">
            Master summary sheet: {q.data.master_sheet_configured ? "every saved run is also appended to it." : "not set up (optional)."}
          </p>
        </Section>
      )}
      {can("admin") && <Users />}
      <MyPassword />
    </>
  );
}
