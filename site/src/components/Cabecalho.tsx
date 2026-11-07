import Link from "next/link";

import { BotaoTelegram } from "@/components/BotaoTelegram";
import { Logo } from "@/components/Logo";

export function Cabecalho() {
  return (
    <header className="sticky top-0 z-20 border-b border-borda bg-superficie/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href="/" aria-label="Página inicial">
          <Logo />
        </Link>
        <nav className="flex items-center gap-1 text-sm font-medium sm:gap-4">
          <Link href="/concursos" className="rounded-lg px-3 py-2 text-texto-suave hover:bg-superficie-2 hover:text-texto">
            Concursos
          </Link>
          <Link
            href="/#como-funciona"
            className="hidden rounded-lg px-3 py-2 text-texto-suave hover:bg-superficie-2 hover:text-texto sm:block"
          >
            Como funciona
          </Link>
          <BotaoTelegram texto="Alertas" className="!px-4 !py-2 text-sm" />
        </nav>
      </div>
    </header>
  );
}
