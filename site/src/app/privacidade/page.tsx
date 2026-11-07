import type { Metadata } from "next";

import { BotaoTelegram } from "@/components/BotaoTelegram";
import { site } from "@/config/site";

export const metadata: Metadata = {
  title: "Privacidade",
  description: `Como o ${site.nome} trata seus dados pessoais, conforme a LGPD.`,
};

export default function Privacidade() {
  return (
    <article className="mx-auto max-w-3xl space-y-6 px-4 pt-10 leading-relaxed">
      <h1 className="text-3xl font-bold tracking-tight">Privacidade</h1>
      <p className="text-texto-suave">
        Resumo em linguagem simples. A versão completa é a mesma exibida pelo comando <code>/privacidade</code> no bot.
      </p>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">O que guardamos</h2>
        <p className="text-texto-suave">
          Apenas o identificador da sua conversa no Telegram (não seu nome nem telefone), os filtros que você criar,
          os concursos que acompanhar e os alertas que enviamos.
        </p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Para quê</h2>
        <p className="text-texto-suave">Exclusivamente para enviar alertas de concursos. Não vendemos nem compartilhamos seus dados.</p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Seus direitos</h2>
        <ul className="list-disc space-y-1 pl-6 text-texto-suave">
          <li><code>/meusdados</code>: receba uma cópia de tudo o que guardamos.</li>
          <li><code>/apagar</code>: apague sua conta e todos os dados, na hora.</li>
          <li>Se você bloquear o bot ou pausar os alertas, apagamos tudo após 180 dias.</li>
        </ul>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Este site</h2>
        <p className="text-texto-suave">Navegar pelo site não exige cadastro e não usamos cookies de rastreamento.</p>
      </section>
      <BotaoTelegram variante="contorno" />
    </article>
  );
}
