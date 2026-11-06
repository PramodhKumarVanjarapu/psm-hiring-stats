import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Empty, ErrorNote, Input, Loading, PageHeader, Pager, Select, Table, Td, Th } from "../components/ui";
import { date, num, pct, ratio } from "../format";
import { STAGES, type CompanySummary, type Job, type Paged } from "../types";

const LIMIT = 50;

export function JobsPage() {
  const [search, setSearch] = useState("");
  const [company, setCompany] = useState("");
  const [skip, setSkip] = useState(0);
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api<Paged<CompanySummary>>("/api/v1/companies") });
  const q = useQuery({
    queryKey: ["jobs", search, company, skip],
    queryFn: () => api<Paged<Job>>("/api/v1/jobs", { query: { search, company: company === "Unassigned" ? "" : company, limit: LIMIT, skip } }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader title="Jobs" sub="Latest saved run of each job." />
      <div className="mb-4 flex flex-wrap gap-3">
        <Input className="max-w-xs" type="search" placeholder="Search job ID, company, role…" value={search}
          onChange={(e) => { setSearch(e.target.value); setSkip(0); }} aria-label="Search jobs" />
        <Select className="max-w-[14rem]" value={company} onChange={(e) => { setCompany(e.target.value); setSkip(0); }} aria-label="Company">
          <option value="">All companies</option>
          {companies.data?.items.filter((c) => c.company !== "Unassigned").map((c) => <option key={c.company}>{c.company}</option>)}
        </Select>
      </div>
      {q.isLoading ? <Loading /> : q.error ? <ErrorNote error={q.error} /> : !q.data?.items.length ? (
        <Empty title={search || company ? "No jobs match these filters" : "No jobs saved yet"}>
          {search || company ? "Clear the search or pick another company." : "Saved analyses appear here."}
        </Empty>
      ) : (
        <>
          <Table head={["Job", "Company", "Role", ...STAGES.map((s) => <Th num key={s}>{s}</Th>), <Th num>SP % of TA</Th>, "Last run"]}>
            {q.data.items.map((j) => {
              const c = j.stage_counts!;
              return (
                <tr key={j.job_key}>
                  <Td><Link className="font-medium text-primary hover:underline" to={`/jobs/${encodeURIComponent(j.job_id)}`}>{j.job_id}</Link></Td>
                  <Td>{j.company || <span className="text-faint">Unassigned</span>}</Td>
                  <Td className="text-muted">{j.role || "–"}</Td>
                  {STAGES.map((s) => <Td num key={s}>{num(c[s])}</Td>)}
                  <Td num className="font-semibold">{pct(ratio(c.SP, c.TA))}</Td>
                  <Td className="whitespace-nowrap text-muted">{date(j.latest_run_at)}</Td>
                </tr>
              );
            })}
          </Table>
          <Pager total={q.data.total} skip={skip} limit={LIMIT} onChange={setSkip} />
        </>
      )}
    </>
  );
}
