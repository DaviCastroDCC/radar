import Link from "next/link";

import { Logo } from "@/components/Logo";
import { site } from "@/config/site";

export function Rodape() {
  return (
    <footer className="mt-16 border-t border-borda bg-superficie">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 text-sm text-texto-suave md:grid-cols-3">
        <div className="space-y-3">
          <Logo className="text-texto" />
          <p>{site.slogan}</p>
        </div>
        <div className="space-y-2">
          <p className="font-semibold text-texto">Navegação</p>
          <ul className="space-y-1">
            <li><Link href="/concursos?abertos=1" className="hover:text-marca">Inscrições abertas</Link></li>
            <li><Link href="/concursos" className="hover:text-marca">Todos os concursos</Link></li>
            <li><Link href="/privacidade" className="hover:text-marca">Privacidade</Link></li>
          </ul>
        </div>
        <div className="space-y-2">
          <p className="font-semibold text-texto">Importante</p>
          <p>
            As informações são extraídas automaticamente de diários oficiais e sites de bancas.
            Confira sempre o edital oficial antes de se inscrever.
          </p>
        </div>
      </div>
      <p className="border-t border-borda py-4 text-center text-xs text-texto-suave">
        © {site.nome}. Sem vínculo com órgãos públicos ou bancas organizadoras.
      </p>
    </footer>
  );
}
