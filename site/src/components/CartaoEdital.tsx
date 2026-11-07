import Link from "next/link";

import { Prazo } from "@/components/Prazo";
import type { EditalResumo } from "@/lib/api";
import { numero, reais, urlEdital } from "@/lib/formato";

export function CartaoEdital({ edital }: { edital: EditalResumo }) {
  const salario = reais(edital.salario_max);
  const vagas = numero(edital.vagas_total);
  return (
    <article className="group relative flex h-full flex-col gap-4 rounded-2xl border border-borda bg-superficie p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-marca/40 hover:shadow-md">
      <div className="flex flex-wrap items-center gap-2 text-xs font-medium text-texto-suave">
        {edital.uf && <span className="rounded-md bg-marca-suave px-2 py-0.5 font-bold text-marca">{edital.uf}</span>}
        {edital.banca && <span>{edital.banca}</span>}
      </div>

      <div className="space-y-1">
        <h3 className="text-base leading-snug font-semibold text-texto">
          <Link href={urlEdital(edital)} className="after:absolute after:inset-0">
            {edital.titulo ?? edital.orgao ?? "Concurso público"}
          </Link>
        </h3>
        {edital.orgao && edital.orgao !== edital.titulo && (
          <p className="line-clamp-2 text-sm text-texto-suave">{edital.orgao}</p>
        )}
      </div>

      <dl className="mt-auto grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-texto-suave">Salário até</dt>
          <dd className="font-semibold text-texto">{salario ?? "ver edital"}</dd>
        </div>
        <div>
          <dt className="text-xs text-texto-suave">Vagas</dt>
          <dd className="font-semibold text-texto">{vagas ?? "ver edital"}</dd>
        </div>
      </dl>

      <Prazo fim={edital.inscricao_fim} />
    </article>
  );
}

export function GradeEditais({ editais }: { editais: EditalResumo[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {editais.map((edital) => (
        <CartaoEdital key={edital.id} edital={edital} />
      ))}
    </div>
  );
}

export function GradeCarregando({ quantidade = 6 }: { quantidade?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-busy="true" aria-label="Carregando concursos">
      {Array.from({ length: quantidade }, (_, i) => (
        <div key={i} className="h-52 animate-pulse rounded-2xl border border-borda bg-superficie" />
      ))}
    </div>
  );
}
