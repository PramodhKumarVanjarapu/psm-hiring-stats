import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { CategoryBars, MonthlyTrend } from "../components/charts";
import { FunnelStrip } from "../components/FunnelStrip";
import { Button, Empty, ErrorNote, Figure, Loading, PageHeader, Panel, Section, Table, Td, Th } from "../components/ui";
import { date, num, pct } from "../format";
import type { CompanySummary, Dashboard } from "../types";

function CompanyTable({ rows }: { rows: CompanySummary[] }) {
  if (!rows.length) return <p className="text-sm text-muted">Not enough data yet (companies need at least 20 applications).</p>;
  return (
    <Table head={["Company", <Th num>Applied</Th>, <Th num>Shared</Th>, <Th num>Shared % of applied</Th>]}>
      {rows.map((c) => (
        <tr key={c.company}>
          <Td><Link className="text-primary hover:underline" to={`/companies/${encodeURIComponent(c.company)}`}>{c.company}</Link></Td>
          <Td num>{num(c.stages.TA)}</Td>
          <Td num>{num(c.stages.SP)}</Td>
          <Td num className="font-semibold">{pct(c.sp_pct_of_ta)}</Td>
        </tr>
      ))}
    </Table>
  );
}

export function OverviewPage() {
  const { can } = useAuth();
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/api/v1/dashboard") });
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorNote error={q.error} />;
  const d = q.data!;

  if (!d.jobs) {
    return (
      <>
        <PageHeader title="Overview" />
        <Empty title="No jobs saved yet">
          Run an analysis on a job's internal sheet and save it. The numbers show up here.
          {can("editor") && <div className="mt-4"><Link to="/analyses/new"><Button variant="primary">Start a new analysis</Button></Link></div>}
        </Empty>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Overview"
        sub="Latest saved run of every job, added up."
        actions={can("editor") && <Link to="/analyses/new"><Button variant="primary">New analysis</Button></Link>}
      />
      <div className="mb-8 grid grid-cols-2 gap-6 sm:grid-cols-4">
        <Figure label="Jobs" value={num(d.jobs)} />
        <Figure label="Companies" value={num(d.companies)} />
        <Figure label="Students" value={num(d.students)} />
        <Figure label="Shared % of applied" value={pct(d.sp_pct_of_ta)} />
      </div>

      <Section title="Funnel across all jobs">
        <FunnelStrip counts={d.funnel} />
      </Section>

      {d.open_conflicts > 0 && (
        <p className="-mt-4 mb-8 text-sm text-muted">
          {num(d.open_conflicts)} identity conflict{d.open_conflicts === 1 ? "" : "s"} to check.{" "}
          <Link className="text-primary hover:underline" to="/conflicts">Review them</Link>
        </p>
      )}

      <div className="grid gap-8 xl:grid-cols-2">
        <Section title="Best conversion"><CompanyTable rows={d.top_companies} /></Section>
        <Section title="Lowest conversion"><CompanyTable rows={d.bottom_companies} /></Section>
      </div>

      <div className="grid gap-8 xl:grid-cols-2">
        <Section title="Applied vs shared, by product">
          <Panel className="p-4"><CategoryBars ta={d.category_ta} sp={d.category_sp} /></Panel>
        </Section>
        <Section title="By month (date of the run)">
          <Panel className="p-4">
            {d.by_month.length > 1 ? <MonthlyTrend rows={d.by_month} /> : <p className="py-16 text-center text-sm text-muted">A trend appears once runs span two months.</p>}
          </Panel>
        </Section>
      </div>

      <Section title="Recently saved">
        <Table head={["Job", "Company", "Role", <Th num>Applied</Th>, <Th num>Shared</Th>, "Run date"]}>
          {d.recent_saves.map((r, i) => (
            <tr key={i}>
              <Td><Link className="font-medium text-primary hover:underline" to={`/jobs/${encodeURIComponent(r.job_id)}`}>{r.job_id}</Link></Td>
              <Td>{r.company || <span className="text-faint">Unassigned</span>}</Td>
              <Td className="text-muted">{r.role || "–"}</Td>
              <Td num>{num(r.TA)}</Td>
              <Td num>{num(r.SP)}</Td>
              <Td className="whitespace-nowrap text-muted">{date(r.run_at)}</Td>
            </tr>
          ))}
        </Table>
      </Section>
    </>
  );
}
