import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { CategoryTag, Empty, ErrorNote, Input, Loading, PageHeader, Pager, Select, Table, Td, Th } from "../components/ui";
import { num } from "../format";
import type { Paged, StudentRow } from "../types";

const LIMIT = 50;

export function StudentsPage() {
  const [f, setF] = useState({ q: "", category: "", bucket: "", edited: "" });
  const [skip, setSkip] = useState(0);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => { setF({ ...f, [k]: e.target.value }); setSkip(0); };
  const q = useQuery({
    queryKey: ["students", f, skip],
    queryFn: () => api<Paged<StudentRow>>("/api/v1/students", { query: { ...f, limit: LIMIT, skip } }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader title="Students" sub="Everyone seen in any saved job, one record per person." />
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Input className="sm:col-span-2" type="search" placeholder="Name, mobile, email or user id…" value={f.q} onChange={set("q")} aria-label="Search students" />
        <Select value={f.category} onChange={set("category")} aria-label="Product">
          <option value="">Any product</option><option>Academy</option><option>Intensive</option><option>External</option>
        </Select>
        <Select value={f.bucket} onChange={set("bucket")} aria-label="Bucket">
          <option value="">Any bucket</option>{["A", "B", "C", "D"].map((b) => <option key={b} value={b}>Bucket {b}</option>)}
        </Select>
        <Select value={f.edited} onChange={set("edited")} aria-label="Edited by hand">
          <option value="">Edited or not</option><option value="true">Edited by hand</option><option value="false">Never edited</option>
        </Select>
      </div>
      {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> : !q.data?.items.length ? (
        <Empty title="No students found">Try a different search, or save an analysis first.</Empty>
      ) : (
        <>
          <Table head={["Name", "Mobile", "Email", "Product", "Bucket", "TR", <Th num>Jobs</Th>, <Th num>Reached SP</Th>]}>
            {q.data.items.map((s) => (
              <tr key={s.student_id}>
                <Td>
                  <Link className="font-medium text-primary hover:underline" to={`/students/${s.student_id}`}>{s.name || "Unnamed"}</Link>
                  {s.locked_fields.length > 0 && <span className="ml-2 text-xs text-muted">edited</span>}
                </Td>
                <Td className="num whitespace-nowrap">{s.mobile || <span className="text-faint">–</span>}</Td>
                <Td className="max-w-[16rem] truncate text-muted">{s.emails[0] || "–"}</Td>
                <Td><CategoryTag category={s.category} /></Td>
                <Td>{s.bucket || <span className="text-faint">–</span>}</Td>
                <Td>{s.tr_cleared ? <span className="text-good">Cleared</span> : <span className="text-faint">No</span>}</Td>
                <Td num>{num(s.jobs)}</Td>
                <Td num className={s.reached_sp ? "font-semibold" : "text-faint"}>{num(s.reached_sp)}</Td>
              </tr>
            ))}
          </Table>
          <Pager total={q.data.total} skip={skip} limit={LIMIT} onChange={setSkip} />
        </>
      )}
    </>
  );
}
