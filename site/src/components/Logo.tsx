import { site } from "@/config/site";

/** Marca provisória: documento com sino de alerta. Troca junto com o nome em config/site.ts. */
export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-semibold tracking-tight ${className}`}>
      <svg viewBox="0 0 32 32" aria-hidden="true" className="size-8 shrink-0">
        <rect x="4" y="3" width="20" height="26" rx="4" className="fill-marca" />
        <path d="M9 10h10M9 15h10M9 20h6" stroke="white" strokeWidth="2" strokeLinecap="round" />
        <circle cx="24" cy="23" r="7" className="fill-aberto stroke-fundo" strokeWidth="2" />
        <path d="M24 19.5v4l2 1.5" stroke="white" strokeWidth="1.8" strokeLinecap="round" fill="none" />
      </svg>
      <span className="text-lg">{site.nome}</span>
    </span>
  );
}
