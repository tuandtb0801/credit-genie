import type { Applicant, Product } from "../types";

export function ApplicantPicker({
  applicants,
  selectedId,
  product,
  onSelect,
  onProductChange,
}: {
  applicants: Applicant[];
  selectedId: string | null;
  product: Product;
  onSelect: (id: string) => void;
  onProductChange: (p: Product) => void;
}) {
  const selected = applicants.find((a) => a.applicant_id === selectedId);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        {applicants.map((a) => (
          <button
            key={a.applicant_id}
            onClick={() => onSelect(a.applicant_id)}
            className={`rounded-sm border px-3 py-2 text-left transition-colors ${
              a.applicant_id === selectedId ? "border-accent bg-accent-soft" : "border-border bg-surface hover:bg-surface-2"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-semibold">{a.display_name}</span>
              <span className="font-mono text-[10px] text-ink-muted">{a.products.join(" / ")}</span>
            </div>
            <p className="mt-0.5 text-[11.5px] leading-snug text-ink-muted">{a.persona_note}</p>
          </button>
        ))}
      </div>

      {selected && (
        <div className="flex items-center gap-1 rounded-sm border border-border bg-surface-2 p-1">
          {selected.products.map((p) => (
            <button
              key={p}
              onClick={() => onProductChange(p)}
              className={`flex-1 rounded-sm px-2 py-1.5 font-mono text-[11px] uppercase tracking-wide ${
                product === p ? "bg-surface text-accent shadow-sm" : "text-ink-muted"
              }`}
            >
              {p === "personal_loan" ? "Personal Loan" : "BNPL"}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
