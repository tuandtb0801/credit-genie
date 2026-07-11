import { useState } from "react";
import { Dashboard } from "./pages/Dashboard";
import { PolicyEditor } from "./pages/PolicyEditor";

type Tab = "dashboard" | "policy";

function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-surface px-6 py-3">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-[15px] font-bold tracking-tight">Credit Genie</h1>
            <p className="font-mono text-[10.5px] text-ink-muted">Agentic credit decision engine</p>
          </div>
          <nav className="flex gap-1 rounded-sm border border-border bg-surface-2 p-1">
            {(["dashboard", "policy"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-sm px-3 py-1.5 font-mono text-[11px] uppercase tracking-wide ${
                  tab === t ? "bg-surface text-accent shadow-sm" : "text-ink-muted"
                }`}
              >
                {t === "dashboard" ? "Decision Dashboard" : "Policy Editor"}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">{tab === "dashboard" ? <Dashboard /> : <PolicyEditor />}</main>
    </div>
  );
}

export default App;
