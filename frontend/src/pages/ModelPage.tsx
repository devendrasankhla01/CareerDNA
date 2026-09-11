import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrainCircuit, CheckCircle2, Info, ShieldCheck } from "lucide-react";
import { api } from "../api/client";
import { fmt1 } from "../lib/format";
import { Badge, Card, Disclaimer, ErrorBox, Spinner, Table } from "../components/ui";

interface MetricRow { accuracy: number; precision: number; recall: number; f1: number; roc_auc: number; confusion_matrix: number[][] }
interface ModelInfo {
  status: string; available: boolean;
  model_version: string | null; model_name: string | null;
  metrics: Record<string, MetricRow>;
  selected_metrics: MetricRow;
  cv_f1: number | null;
  selection_rule: string | null;
  selection: Record<string, unknown>;
  feature_count: number;
  features: { name: string; label: string }[];
  feature_groups: Record<string, string[]>;
  global_importance?: Record<string, number>;
  disclaimer: string;
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function ModelPage() {
  const [technical, setTechnical] = useState(false);
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["model-info"],
    queryFn: () => api<ModelInfo>("/model/info"),
  });

  if (isLoading) return <Spinner label="Loading model information…" />;
  if (isError) return <ErrorBox message={(error as Error).message} onRetry={() => refetch()} />;
  if (!data) return null;

  if (!data.available || data.status === "model_unavailable") {
    return (
      <div className="space-y-5">
        <h1 className="text-xl font-semibold text-slate-900">How Readiness is Calculated</h1>
        <Card>
          <ErrorBox message="The readiness model is not deployed yet. Run scripts/train_model.py to build it." />
        </Card>
      </div>
    );
  }

  const selectedName = data.model_name || "selected model";
  const candidates = Object.keys(data.metrics);
  const cm = data.selected_metrics.confusion_matrix;
  const importance = Object.entries(data.global_importance || {})
    .map(([name, value]) => ({
      name,
      label: data.features.find((f) => f.name === name)?.label || name.replace(/_/g, " "),
      value,
    }))
    .sort((a, b) => b.value - a.value);
  const maxImp = importance[0]?.value || 1;
  const labelFor = (name: string) =>
    technical ? name : data.features.find((f) => f.name === name)?.label || name.replace(/_/g, " ");

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-xl font-semibold text-slate-900">How Readiness is Calculated</h1>
        <p className="mt-0.5 max-w-2xl text-[13px] text-slate-500">
          Everything on this page is read from the deployed model artifact — real training metrics,
          not estimates.
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Deployed model"
          actions={<Badge cls="bg-teal-50 text-teal-700 border-teal-200"><CheckCircle2 className="h-3 w-3" /> deployed</Badge>}>
          <dl className="space-y-2.5 text-[13px]">
            <div className="flex justify-between gap-4"><dt className="text-slate-500">Model</dt><dd className="font-medium text-slate-800">{data.model_name}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-slate-500">Version</dt><dd className="font-mono text-[12px] text-slate-700">{data.model_version}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-slate-500">Features</dt><dd className="font-medium tabular-nums text-slate-800">{data.feature_count}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-slate-500">Cross-validated F1</dt><dd className="font-medium tabular-nums text-slate-800">{data.cv_f1 != null ? data.cv_f1.toFixed(3) : "—"}</dd></div>
          </dl>
          {data.selection_rule && (
            <p className="mt-3 border-t border-slate-100 pt-3 text-[12px] leading-relaxed text-slate-500">
              <span className="font-semibold text-slate-600">Selection rule:</span> {data.selection_rule}
            </p>
          )}
        </Card>

        <Card title="Candidate comparison" subtitle="Held-out test split (n = 800)">
          <Table head={
            <tr><th>Model</th><th>Acc</th><th>Prec</th><th>Recall</th><th>F1</th><th>AUC</th></tr>
          }>
            {candidates.map((name) => {
              const m = data.metrics[name];
              const isSel = name === selectedName;
              return (
                <tr key={name} className={isSel ? "bg-teal-50/50" : ""}>
                  <td className={`text-[12.5px] ${isSel ? "font-semibold text-teal-800" : "text-slate-600"}`}>
                    {name}{isSel && <span className="ml-1.5 text-[10.5px] font-semibold uppercase text-teal-600">selected</span>}
                  </td>
                  <td className="tabular-nums text-slate-700">{pct(m.accuracy)}</td>
                  <td className="tabular-nums text-slate-700">{pct(m.precision)}</td>
                  <td className="tabular-nums text-slate-700">{pct(m.recall)}</td>
                  <td className="tabular-nums text-slate-700">{pct(m.f1)}</td>
                  <td className="tabular-nums text-slate-700">{m.roc_auc.toFixed(3)}</td>
                </tr>
              );
            })}
          </Table>
          {cm && cm.length >= 2 && (
            <div className="mt-4">
              <div className="label">Selected model confusion matrix</div>
              <div className="mt-2 grid grid-cols-3 gap-1 text-center text-[12px]">
                <div />
                <div className="text-slate-500">Predicted placed</div>
                <div className="text-slate-500">Predicted not</div>
                <div className="flex items-center justify-end pr-1 text-slate-500">Placed</div>
                <div className="rounded bg-teal-50 px-2 py-1.5 font-semibold tabular-nums text-teal-800">{cm[0][0]}</div>
                <div className="rounded bg-slate-50 px-2 py-1.5 tabular-nums text-slate-600">{cm[0][1]}</div>
                <div className="flex items-center justify-end pr-1 text-slate-500">Not placed</div>
                <div className="rounded bg-slate-50 px-2 py-1.5 tabular-nums text-slate-600">{cm[1][0]}</div>
                <div className="rounded bg-teal-50 px-2 py-1.5 font-semibold tabular-nums text-teal-800">{cm[1][1]}</div>
              </div>
            </div>
          )}
        </Card>

        <Card title="Terminology" subtitle="How to read these numbers">
          <ul className="space-y-3 text-[12.5px] leading-relaxed text-slate-600">
            <li className="flex gap-2">
              <BrainCircuit className="mt-0.5 h-4 w-4 shrink-0 text-navy-600" />
              <span><span className="font-semibold text-slate-800">Placement readiness</span> is a
              model-estimated 0–100 score for how placement-ready a student's verified profile looks.
              It is a readiness signal, not a placement outcome.</span>
            </li>
            <li className="flex gap-2">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-navy-600" />
              <span><span className="font-semibold text-slate-800">Readiness categories</span> use fixed
              institutional bands: &lt;60 Needs Training, 60–79.9 Near-Ready, ≥80 Ready.</span>
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-navy-600" />
              <span><span className="font-semibold text-slate-800">Explanations</span> come from the
              model's own linear coefficients (this model is a logistic regression), mapped to friendly
              labels. They describe association, not causation.</span>
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-navy-600" />
              <span><span className="font-semibold text-slate-800">Projections</span> (Path to Ready,
              intervention simulations) re-run this model on hypothetical features. They are
              model-based projections, never guarantees.</span>
            </li>
          </ul>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="What influences readiness most"
          subtitle="Global feature importance from the trained model (relative scale)"
          actions={
            <div className="flex rounded-lg border border-slate-200 p-0.5 text-[12px] font-medium">
              <button onClick={() => setTechnical(false)}
                className={`rounded-md px-2.5 py-1 ${!technical ? "bg-navy-800 text-white" : "text-slate-500"}`}>Friendly</button>
              <button onClick={() => setTechnical(true)}
                className={`rounded-md px-2.5 py-1 ${technical ? "bg-navy-800 text-white" : "text-slate-500"}`}>Technical</button>
            </div>
          }>
          <ol className="space-y-2.5">
            {importance.slice(0, 12).map((f, i) => (
              <li key={f.name}>
                <div className="flex items-center gap-2 text-[12.5px]">
                  <span className="w-4 text-right text-[11px] tabular-nums text-slate-400">{i + 1}</span>
                  <span className="w-44 truncate text-slate-700" title={f.name}>{labelFor(f.name)}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-navy-600" style={{ width: `${(f.value / maxImp) * 100}%` }} />
                  </div>
                  <span className="w-10 text-right tabular-nums text-slate-500">{f.value.toFixed(2)}</span>
                </div>
              </li>
            ))}
          </ol>
          <Disclaimer>
            Importance here means influence on the readiness score within this trained model —
            not a claim that changing the skill causes placement.
          </Disclaimer>
        </Card>

        <Card title={`Feature set (${data.feature_count})`}
          subtitle="The exact inputs the model uses. No identifiers, branch, or demographic fields are included.">
          <div className="space-y-3.5">
            {Object.entries(data.feature_groups).map(([group, names]) => (
              <div key={group}>
                <div className="label">{group}</div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {names.map((n) => (
                    <Badge key={n} cls="bg-slate-50 text-slate-600 border-slate-200">{labelFor(n)}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Disclaimer>{data.disclaimer}</Disclaimer>
    </div>
  );
}
