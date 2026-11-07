import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { BotaoTelegram } from "@/components/BotaoTelegram";
import { Prazo } from "@/components/Prazo";
import { buscarEdital, type EditalDetalhe } from "@/lib/api";
import { dataBR, ESCOLARIDADE, FONTES, idDaUrl, numero, periodo, reais } from "@/lib/formato";

async function carregar(params: PageProps<"/concursos/[id]">["params"]): Promise<EditalDetalhe | null> {
  const id = idDaUrl((await params).id);
  return id ? buscarEdital(id) : null;
}

export async function generateMetadata(props: PageProps<"/concursos/[id]">): Promise<Metadata> {
  const edital = await carregar(props.params);
  if (!edital) return { title: "Concurso não encontrado", robots: { index: false } };
  const partes = [
    edital.vagas_total && `${numero(edital.vagas_total)} vagas`,
    edital.salario_max && `salário até ${reais(edital.salario_max)}`,
    edital.inscricao_fim && `inscrições até ${dataBR(edital.inscricao_fim)}`,
  ].filter(Boolean);
  const titulo = edital.titulo ?? edital.orgao ?? "Concurso público";
  return {
    title: titulo,
    description: `${titulo}${partes.length ? `: ${partes.join(", ")}` : ""}. ${edital.resumo ?? ""}`.slice(0, 300),
    openGraph: { title: titulo, type: "article" },
  };
}

export default function PaginaEdital(props: PageProps<"/concursos/[id]">) {
  return (
    <div className="mx-auto max-w-6xl px-4 pt-8">
      <nav className="text-sm text-texto-suave" aria-label="Você está em">
        <Link href="/" className="hover:text-marca">Início</Link>
        <span className="px-2">/</span>
        <Link href="/concursos" className="hover:text-marca">Concursos</Link>
      </nav>
      <Suspense fallback={<Carregando />}>
        <Detalhe params={props.params} />
      </Suspense>
    </div>
  );
}

async function Detalhe({ params }: Pick<PageProps<"/concursos/[id]">, "params">) {
  const edital = await carregar(params);
  if (!edital) return <NaoEncontrado />;

  const fatos: [string, string | null][] = [
    ["Vagas", numero(edital.vagas_total)],
    ["Salário até", reais(edital.salario_max)],
    ["Inscrições", periodo(edital.inscricao_inicio, edital.inscricao_fim)],
    ["Data da prova", dataBR(edital.data_prova)],
    ["Taxa de inscrição", reais(edital.taxa_inscricao)],
    ["Banca", edital.banca],
  ];

  return (
    <article className="mt-6 grid gap-8 lg:grid-cols-[1fr_320px]">
      <div className="space-y-8">
        <header className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Prazo fim={edital.inscricao_fim} />
            {edital.uf && <span className="rounded-md bg-marca-suave px-2 py-1 text-xs font-bold text-marca">{edital.uf}</span>}
            {edital.numero_edital && <span className="text-xs text-texto-suave">{edital.numero_edital}</span>}
          </div>
          <h1 className="text-3xl leading-tight font-bold tracking-tight sm:text-4xl">
            {edital.titulo ?? edital.orgao ?? "Concurso público"}
          </h1>
          {edital.orgao && <p className="text-lg text-texto-suave">{edital.orgao}</p>}
        </header>

        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-borda bg-borda sm:grid-cols-3">
          {fatos.map(([rotulo, valor]) => (
            <div key={rotulo} className="bg-superficie p-4">
              <dt className="text-xs text-texto-suave">{rotulo}</dt>
              <dd className="mt-1 font-semibold">{valor ?? <span className="font-normal text-texto-suave">ver edital</span>}</dd>
            </div>
          ))}
        </dl>

        {edital.resumo && (
          <section className="space-y-2">
            <h2 className="text-xl font-bold">Resumo</h2>
            <p className="leading-relaxed text-texto-suave">{edital.resumo}</p>
          </section>
        )}

        {edital.cargos.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-xl font-bold">Cargos ({edital.cargos.length})</h2>
            <div className="overflow-x-auto rounded-2xl border border-borda bg-superficie">
              <table className="w-full min-w-[540px] text-left text-sm">
                <thead className="bg-superficie-2 text-xs text-texto-suave uppercase">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Cargo</th>
                    <th className="px-4 py-3 font-semibold">Escolaridade</th>
                    <th className="px-4 py-3 text-right font-semibold">Vagas</th>
                    <th className="px-4 py-3 text-right font-semibold">Salário</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borda">
                  {edital.cargos.map((cargo, i) => (
                    <tr key={`${cargo.nome}-${i}`}>
                      <td className="px-4 py-3 font-medium">{cargo.nome}</td>
                      <td className="px-4 py-3 text-texto-suave">{ESCOLARIDADE[cargo.escolaridade] ?? cargo.escolaridade}</td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {numero(cargo.vagas) ?? "—"}
                        {cargo.cadastro_reserva && <span className="ml-1 text-xs text-texto-suave">+ CR</span>}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold tabular-nums">{reais(cargo.salario) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-texto-suave">CR = cadastro de reserva.</p>
          </section>
        )}
      </div>

      <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
        <div className="space-y-3 rounded-2xl border border-borda bg-superficie p-5">
          <h2 className="font-semibold">Não perca nenhuma mudança</h2>
          <p className="text-sm text-texto-suave">Receba no Telegram as retificações e prorrogações deste concurso.</p>
          <BotaoTelegram texto="Acompanhar este concurso" parametroStart={`edital_${edital.id}`} className="w-full" />
        </div>
        <div className="space-y-2 rounded-2xl border border-borda bg-superficie p-5 text-sm">
          {edital.link_inscricao && (
            <a href={edital.link_inscricao} target="_blank" rel="noopener noreferrer nofollow" className="block rounded-xl bg-aberto px-4 py-3 text-center font-semibold text-white hover:opacity-90">
              Fazer inscrição ↗
            </a>
          )}
          {edital.url_publicacao && (
            <a href={edital.url_publicacao} target="_blank" rel="noopener noreferrer nofollow" className="block rounded-xl border border-borda px-4 py-3 text-center font-semibold hover:border-marca">
              Ver publicação oficial ↗
            </a>
          )}
          <p className="pt-2 text-xs text-texto-suave">
            Fonte: {FONTES[edital.fonte] ?? edital.fonte}, publicado em {dataBR(edital.data_publicacao)}.
            Dados extraídos automaticamente: confira sempre o edital oficial.
          </p>
        </div>
      </aside>
    </article>
  );
}

function Carregando() {
  return (
    <div className="mt-6 space-y-4" aria-busy="true">
      <div className="h-8 w-40 animate-pulse rounded-full bg-superficie-2" />
      <div className="h-10 w-3/4 animate-pulse rounded-xl bg-superficie-2" />
      <div className="h-40 animate-pulse rounded-2xl bg-superficie-2" />
    </div>
  );
}

function NaoEncontrado() {
  return (
    <div className="mt-10 rounded-2xl border border-dashed border-borda bg-superficie p-10 text-center">
      <h1 className="text-2xl font-bold">Concurso não encontrado</h1>
      <p className="mt-2 text-texto-suave">O link pode estar errado ou o edital foi removido.</p>
      <Link href="/concursos" className="mt-6 inline-block font-semibold text-marca hover:underline">Ver concursos →</Link>
    </div>
  );
}
