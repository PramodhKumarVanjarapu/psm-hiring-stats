import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { month, num } from "../format";
import type { CategorySplit, StageCounts } from "../types";

const axis = { stroke: "var(--faint)", fontSize: 12, tickLine: false, axisLine: false } as const;
const tooltipStyle = {
  contentStyle: { background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)", fontSize: 13 },
  labelStyle: { color: "var(--muted)" },
};

export function CategoryBars({ ta, sp }: { ta: CategorySplit; sp: CategorySplit }) {
  const data = [
    { name: "Academy", TA: ta.academy, SP: sp.academy },
    { name: "Intensive", TA: ta.intensive, SP: sp.intensive },
    { name: "External", TA: ta.external, SP: sp.external },
  ];
  return (
    <div className="h-56">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <CartesianGrid horizontal={false} stroke="var(--line)" />
          <XAxis type="number" {...axis} tickFormatter={(v) => num(v)} />
          <YAxis type="category" dataKey="name" {...axis} width={72} />
          <Tooltip {...tooltipStyle} formatter={(v: number) => num(v)} cursor={{ fill: "var(--sunken)" }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="TA" name="Applied (TA)" fill="var(--st-ta)" radius={[0, 3, 3, 0]} />
          <Bar dataKey="SP" name="Shared (SP)" fill="var(--st-sp)" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MonthlyTrend({ rows }: { rows: ({ month: string } & StageCounts)[] }) {
  return (
    <div className="h-56">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ left: 8, right: 16, top: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--line)" />
          <XAxis dataKey="month" {...axis} tickFormatter={month} />
          <YAxis {...axis} tickFormatter={(v) => num(v)} width={48} />
          <Tooltip {...tooltipStyle} labelFormatter={(l) => month(String(l))} formatter={(v: number) => num(v)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line dataKey="TA" name="Applied (TA)" stroke="var(--st-ta)" strokeWidth={2} dot={false} />
          <Line dataKey="RS" name="Resume shortlisted" stroke="var(--st-rs)" strokeWidth={2} dot={false} />
          <Line dataKey="SP" name="Shared (SP)" stroke="var(--st-sp)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
