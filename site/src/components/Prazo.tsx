"use client";

import { useSyncExternalStore } from "react";

import { dataBR, diasAte } from "@/lib/formato";

// "Hoje" só existe no navegador: no servidor (HTML em cache) o snapshot é null e o selo
// mostra só a data fixa; no navegador ele vira a contagem ("faltam 3 dias").
const semInscricao = () => () => {};
const hojeNoNavegador = () => new Date().toDateString(); // estável durante o dia
const hojeNoServidor = () => null;

export function Prazo({ fim }: { fim: string | null }) {
  const hoje = useSyncExternalStore(semInscricao, hojeNoNavegador, hojeNoServidor);

  if (!fim) return <Selo cor="neutro">Inscrições: ver edital</Selo>;
  const data = dataBR(fim);
  if (hoje === null) return <Selo cor="neutro">Inscrições até {data}</Selo>;

  const dias = diasAte(fim, new Date(hoje));
  if (dias < 0) return <Selo cor="urgente">Inscrições encerradas em {data}</Selo>;
  if (dias === 0) return <Selo cor="urgente">Último dia de inscrição!</Selo>;
  if (dias <= 5) return <Selo cor="alerta">{dias === 1 ? "Falta 1 dia" : `Faltam ${dias} dias`} · até {data}</Selo>;
  return <Selo cor="aberto">Inscrições abertas até {data}</Selo>;
}

const CORES = {
  neutro: "bg-superficie-2 text-texto-suave",
  aberto: "bg-aberto-suave text-aberto",
  alerta: "bg-alerta-suave text-alerta",
  urgente: "bg-urgente-suave text-urgente",
} as const;

function Selo({ cor, children }: { cor: keyof typeof CORES; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${CORES[cor]}`}>
      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
      {children}
    </span>
  );
}
