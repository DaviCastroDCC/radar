import Link from "next/link";

import { BotaoTelegram } from "@/components/BotaoTelegram";
import { GradeEditais } from "@/components/CartaoEdital";
import { FormBusca } from "@/components/FormBusca";
import { site } from "@/config/site";
import { buscarEditais, buscarMetricas } from "@/lib/api";
import { numero } from "@/lib/formato";

export default async function Inicio() {
  const [abertos, metricas] = await Promise.all([buscarEditais({ abertos: true, limite: 9 }), buscarMetricas()]);

  return (
    <>
      {/* Herói */}
      <section className="relative overflow-hidden border-b border-borda bg-gradient-to-b from-marca-suave to-fundo">
        <div className="mx-auto max-w-6xl px-4 pt-16 pb-12 sm:pt-24">
          <div className="max-w-3xl space-y-6">
            <p className="inline-flex rounded-full bg-superficie px-3 py-1 text-xs font-semibold text-marca ring-1 ring-borda">
              Diários oficiais e bancas, lidos todos os dias
            </p>
            <h1 className="text-4xl leading-tight font-bold tracking-tight text-texto sm:text-5xl">
              Saiu concurso para você?
              <span className="block text-marca">Você fica sabendo em minutos.</span>
            </h1>
            <p className="max-w-2xl text-lg text-texto-suave">
              Diga seu cargo, seu estado e o salário mínimo que você aceita. A gente lê os editais por você e
              avisa no Telegram, inclusive quando sai <strong className="text-texto">retificação</strong> do
              concurso que você acompanha.
            </p>
            <div className="flex flex-wrap gap-3">
              <BotaoTelegram />
              <Link
                href="/concursos?abertos=1"
                className="inline-flex items-center rounded-xl border border-borda bg-superficie px-5 py-3 font-semibold text-texto hover:border-marca"
              >
                Ver inscrições abertas →
              </Link>
            </div>
          </div>
          <div className="mt-10">
            <FormBusca destaque />
          </div>
        </div>
      </section>

      {/* Números (só aparecem quando existem: nada de métrica inventada) */}
      {metricas && metricas.publicacoes_candidatas_lidas > 0 && (
        <section className="border-b border-borda bg-superficie">
          <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-4 py-8 text-center sm:grid-cols-3">
            <Numero valor={metricas.publicacoes_candidatas_lidas} rotulo="publicações oficiais analisadas" />
            <Numero valor={metricas.editais_de_abertura} rotulo="editais de concurso encontrados" />
            <Numero valor={metricas.alertas_enviados} rotulo="alertas enviados" className="col-span-2 sm:col-span-1" />
          </dl>
        </section>
      )}

      {/* Inscrições abertas */}
      <section className="mx-auto max-w-6xl space-y-6 px-4 pt-14">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Inscrições abertas agora</h2>
            <p className="text-texto-suave">Os editais mais recentes, extraídos direto das fontes oficiais.</p>
          </div>
          <Link href="/concursos?abertos=1" className="hidden text-sm font-semibold text-marca hover:underline sm:block">
            Ver todos →
          </Link>
        </div>
        {abertos.length > 0 ? (
          <GradeEditais editais={abertos} />
        ) : (
          <div className="rounded-2xl border border-dashed border-borda bg-superficie p-10 text-center text-texto-suave">
            Estamos lendo os diários oficiais de hoje. Os concursos abertos aparecem aqui em instantes.
          </div>
        )}
      </section>

      {/* Como funciona */}
      <section id="como-funciona" className="mx-auto max-w-6xl scroll-mt-20 px-4 pt-20">
        <h2 className="text-2xl font-bold tracking-tight">Como funciona</h2>
        <ol className="mt-6 grid gap-4 md:grid-cols-3">
          <Passo n={1} titulo="Você diz o que procura">
            No Telegram, em uma mensagem: <code className="rounded bg-superficie-2 px-1">analista ti; uf=DF; salario=6000</code>
          </Passo>
          <Passo n={2} titulo="A gente lê tudo, todo dia">
            Diário Oficial da União, diários estaduais e sites das bancas. Uma IA lê cada edital e extrai cargos,
            vagas, salários e prazos.
          </Passo>
          <Passo n={3} titulo="Você recebe só o que importa">
            Um aviso direto, sem spam: cargo, salário, prazo e o link do edital oficial. E avisos de retificação
            do concurso que você acompanha.
          </Passo>
        </ol>
      </section>

      {/* Diferenciais */}
      <section className="mx-auto max-w-6xl px-4 pt-20">
        <div className="grid gap-4 md:grid-cols-3">
          <Diferencial titulo="Retificações">
            Edital mudou data, vagas ou requisitos? Você fica sabendo. É onde mais gente perde prazo.
          </Diferencial>
          <Diferencial titulo="Filtro por salário">
            Só concursos que pagam o mínimo que você definiu, no seu estado e na sua escolaridade.
          </Diferencial>
          <Diferencial titulo="Seus dados, suas regras">
            Guardamos só o necessário. Baixe ou apague tudo a qualquer momento, direto no bot.
          </Diferencial>
        </div>
      </section>

      {/* Chamada final */}
      <section className="mx-auto max-w-6xl px-4 pt-20">
        <div className="rounded-3xl bg-marca px-6 py-12 text-center text-white sm:px-12">
          <h2 className="text-3xl font-bold tracking-tight">Pare de garimpar edital em grupo de Telegram.</h2>
          <p className="mx-auto mt-3 max-w-2xl text-white/85">
            O {site.nome} é gratuito. Leva 30 segundos para configurar seu primeiro alerta.
          </p>
          <div className="mt-6 flex justify-center">
            <BotaoTelegram texto="Quero receber alertas" className="!bg-white !text-marca hover:!bg-marca-suave" />
          </div>
        </div>
      </section>
    </>
  );
}

function Numero({ valor, rotulo, className = "" }: { valor: number; rotulo: string; className?: string }) {
  return (
    <div className={`flex flex-col ${className}`}>
      <dt className="text-sm text-texto-suave">{rotulo}</dt>
      <dd className="order-first text-3xl font-bold tracking-tight text-marca">{numero(valor)}</dd>
    </div>
  );
}

function Passo({ n, titulo, children }: { n: number; titulo: string; children: React.ReactNode }) {
  return (
    <li className="rounded-2xl border border-borda bg-superficie p-6">
      <span className="flex size-9 items-center justify-center rounded-full bg-marca-suave font-bold text-marca">{n}</span>
      <h3 className="mt-4 font-semibold">{titulo}</h3>
      <p className="mt-2 text-sm text-texto-suave">{children}</p>
    </li>
  );
}

function Diferencial({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-superficie-2 p-6">
      <h3 className="font-semibold">{titulo}</h3>
      <p className="mt-2 text-sm text-texto-suave">{children}</p>
    </div>
  );
}
