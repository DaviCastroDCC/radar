import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { GradeCarregando, GradeEditais } from "@/components/CartaoEdital";
import { FormBusca } from "@/components/FormBusca";
import { buscarEditais } from "@/lib/api";

export const metadata: Metadata = {
  title: "Concursos públicos com inscrições abertas",
  description: "Busque concursos por cargo, órgão, banca e estado. Dados extraídos dos diários oficiais e das bancas.",
};

const POR_PAGINA = 24;

type Filtros = { q: string; uf: string; abertos: boolean; pagina: number };

function lerFiltros(sp: Record<string, string | string[] | undefined>): Filtros {
  const texto = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
  const pagina = Number.parseInt(texto(sp.pagina), 10);
  return {
    q: texto(sp.q).slice(0, 100),
    uf: texto(sp.uf).toUpperCase().slice(0, 2),
    abertos: texto(sp.abertos) !== "" && texto(sp.abertos) !== "0",
    pagina: Number.isInteger(pagina) && pagina > 0 ? pagina : 1,
  };
}

export default function Concursos(props: PageProps<"/concursos">) {
  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4 pt-10">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Concursos públicos</h1>
        <p className="text-texto-suave">Editais lidos dos diários oficiais e dos sites das bancas, atualizados ao longo do dia.</p>
      </header>
      {/* searchParams é dado da requisição: fica dentro do Suspense para a casca da página ser estática. */}
      <Suspense fallback={<><FormBusca /><GradeCarregando /></>}>
        <Resultados searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}

async function Resultados({ searchParams }: Pick<PageProps<"/concursos">, "searchParams">) {
  const filtros = lerFiltros(await searchParams);
  const editais = await buscarEditais({ ...filtros, limite: POR_PAGINA });

  return (
    <>
      <FormBusca q={filtros.q} uf={filtros.uf} abertos={filtros.abertos} />
      <p className="text-sm text-texto-suave" aria-live="polite">
        {editais.length === 0
          ? "Nenhum concurso encontrado com esses filtros."
          : `${editais.length}${editais.length === POR_PAGINA ? "+" : ""} concursos${filtros.q ? ` para “${filtros.q}”` : ""}${filtros.uf ? ` em ${filtros.uf}` : ""}`}
      </p>
      {editais.length > 0 ? (
        <GradeEditais editais={editais} />
      ) : (
        <div className="rounded-2xl border border-dashed border-borda bg-superficie p-10 text-center text-texto-suave">
          Tente outro termo, outro estado ou desmarque “Só inscrições abertas”.
        </div>
      )}
      <Paginacao filtros={filtros} temMais={editais.length === POR_PAGINA} />
    </>
  );
}

function Paginacao({ filtros, temMais }: { filtros: Filtros; temMais: boolean }) {
  const link = (pagina: number) => {
    const p = new URLSearchParams();
    if (filtros.q) p.set("q", filtros.q);
    if (filtros.uf) p.set("uf", filtros.uf);
    if (filtros.abertos) p.set("abertos", "1");
    if (pagina > 1) p.set("pagina", String(pagina));
    return `/concursos${p.size ? `?${p}` : ""}`;
  };
  if (filtros.pagina === 1 && !temMais) return null;
  const botao = "rounded-xl border border-borda bg-superficie px-4 py-2 font-medium hover:border-marca";
  return (
    <nav className="flex items-center justify-center gap-3 pt-4 text-sm" aria-label="Paginação">
      {filtros.pagina > 1 && <Link className={botao} href={link(filtros.pagina - 1)}>← Anteriores</Link>}
      <span className="text-texto-suave">Página {filtros.pagina}</span>
      {temMais && <Link className={botao} href={link(filtros.pagina + 1)}>Próximos →</Link>}
    </nav>
  );
}
