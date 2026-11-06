import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { Button, Empty, ErrorNote, Loading, PageHeader, Select, Table, Td, Th } from "../components/ui";
import { date, num } from "../format";
import type { Conflict, Paged } from "../types";

const KEY_NAMES = { email: "Email", user_id: "User id", mobile: "Mobile" };

export function ConflictsPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [resolved, setResolved] = useState("false");
  const q = useQuery({ queryKey: ["conflicts", resolved], queryFn: () => api<Paged<Conflict>>("/api/v1/identity-conflicts", { query: { resolved } }) });
  const resolve = useMutation({
    mutationFn: (id: string) => api(`/api/v1/identity-conflicts/${encodeURIComponent(id)}/resolve`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries(),
  });

  return (
    <>
      <PageHeader
        title="Identity conflicts"
        sub="Two different mobile numbers shared an email or user id, so they were kept as separate students. Check each one: if it's one person, open a student and merge; otherwise mark it as checked."
        actions={<Select value={resolved} onChange={(e) => setResolved(e.target.value)} aria-label="Show"><option value="false">To check</option><option value="true">Checked</option></Select>}
      />
      {resolve.error && <div className="mb-4"><ErrorNote error={resolve.error} /></div>}
      {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> : !q.data?.items.length ? (
        <Empty title={resolved === "false" ? "Nothing to check" : "No checked conflicts yet"} />
      ) : (
        <Table head={["Shared value", "Students", "Jobs", <Th num>Seen</Th>, "Last seen", ""]}>
          {q.data.items.map((c) => (
            <tr key={c.id}>
              <Td><div className="text-xs text-muted">{KEY_NAMES[c.key_type]}</div><div className="font-medium break-all">{c.key}</div></Td>
              <Td>
                <ul className="space-y-0.5">
                  {c.students.length ? c.students.map((s) => (
                    <li key={s.student_id}><Link className="text-primary hover:underline" to={`/students/${s.student_id}`}>{s.name || "Unnamed"}</Link> <span className="num text-muted">{s.mobile}</span></li>
                  )) : c.mobiles.map((m) => <li key={m} className="num text-muted">{m}</li>)}
                </ul>
              </Td>
              <Td className="text-muted">{c.job_ids.join(", ")}</Td>
              <Td num>{num(c.seen_count)}</Td>
              <Td className="whitespace-nowrap text-muted">{date(c.last_seen)}</Td>
              <Td>{!c.resolved && can("editor") && <Button disabled={resolve.isPending} onClick={() => resolve.mutate(c.id)}>Mark as checked</Button>}</Td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}
