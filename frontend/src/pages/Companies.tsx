import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { CategoryBars } from "../components/charts";
import { FunnelStrip } from "../components/FunnelStrip";
import { Empty, ErrorNote, Figure, Input, Loading, PageHeader, Panel, Section, Table, Td, Th } from "../components/ui";
import { date, num, pct, ratio } from "../format";
import { STAGES, type CompanySummary, type Paged } from "../types";

export function CompaniesPage() {
  const [search, setSearch] = useState("");
  const q = useQuery({ queryKey: ["companies"], queryFn: () => api<Paged<CompanySummary>>("/api/v1/companies") });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const rows = q.data!.items.filter((c) => c.company.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <>
      <PageHeader title="Companies" sub="Each company's jobs added up (latest run of every job)." />
      <Input className="mb-4 max-w-xs" type="search" placeholder="Search companies…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search companies" />
      {!rows.length ? <Empty title={search ? "No company matches" : "No companies yet"}>{!search && "Set a company when you run an analysis, or on a job's page."}</Empty> : (
        <Table head={["Company", <Th num>Jobs</Th>, ...STAGES.map((s) => <Th num key={s}>{s}</Th>), <Th num>RS % of TA</Th>, <Th num>SP % of TA</Th>, <Th num>SP % of RS</Th>, "Last run"]}>
          {rows.map((c) => (
            <tr key={c.company}>
              <Td><Link className={c.company === "Unassigned" ? "italic text-muted hover:underline" : "font-medium text-primary hover:underline"} to={`/companies/${encodeURIComponent(c.company)}`}>{c.company}</Link></Td>
              <Td num>{num(c.jobs)}</Td>
              {STAGES.map((s) => <Td num key={s}>{num(c.stages[s])}</Td>)}
              <Td num>{pct(c.rs_pct_of_ta)}</Td>
              <Td num className="font-semibold">{pct(c.sp_pct_of_ta)}</Td>
              <Td num>{pct(c.sp_pct_of_rs)}</Td>
              <Td className="whitespace-nowrap text-muted">{date(c.last_run_at)}</Td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}

export function CompanyPage() {
  const { name = "" } = useParams();
  const q = useQuery({ queryKey: ["company", name], queryFn: () => api<CompanySummary>(`/api/v1/companies/${encodeURIComponent(name)}`) });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const c = q.data!;

  return (
    <>
      <PageHeader title={c.company} sub={`${num(c.jobs)} job${c.jobs === 1 ? "" : "s"}, latest run of each.`} />
      <div className="mb-8 grid grid-cols-2 gap-6 sm:grid-cols-4">
        <Figure label="Applied (TA)" value={num(c.stages.TA)} />
        <Figure label="Profiles shared (SP)" value={num(c.stages.SP)} />
        <Figure label="SP % of TA" value={pct(c.sp_pct_of_ta)} />
        <Figure label="SP % of RS" value={pct(c.sp_pct_of_rs)} />
      </div>
      <Section title="Funnel"><FunnelStrip counts={c.stages} /></Section>
      <div className="grid gap-8 xl:grid-cols-2">
        <Section title="Applied vs shared, by product"><Panel className="p-4"><CategoryBars ta={c.category_ta} sp={c.category_sp} /></Panel></Section>
        <Section title="Academy buckets">
          <Table head={["Bucket", ...STAGES.map((s) => <Th num key={s}>{s}</Th>), <Th num>SP % of TA</Th>]}>
            {Object.entries(c.buckets).map(([b, counts]) => (
              <tr key={b}>
                <Td className="font-medium">Bucket {b}</Td>
                {STAGES.map((s) => <Td num key={s}>{num(counts[s])}</Td>)}
                <Td num className="font-semibold">{pct(ratio(counts.SP, counts.TA))}</Td>
              </tr>
            ))}
          </Table>
        </Section>
      </div>
      <Section title="Jobs">
        <Table head={["Job", "Role", ...STAGES.map((s) => <Th num key={s}>{s}</Th>), <Th num>SP % of TA</Th>, "Last run"]}>
          {c.job_list!.map((j) => (
            <tr key={j.job_id}>
              <Td><Link className="font-medium text-primary hover:underline" to={`/jobs/${encodeURIComponent(j.job_id)}`}>{j.job_id}</Link></Td>
              <Td className="text-muted">{j.role || "–"}</Td>
              {STAGES.map((s) => <Td num key={s}>{num(j.stages[s])}</Td>)}
              <Td num className="font-semibold">{pct(j.sp_pct_of_ta)}</Td>
              <Td className="whitespace-nowrap text-muted">{date(j.run_at)}</Td>
            </tr>
          ))}
        </Table>
      </Section>
    </>
  );
}
