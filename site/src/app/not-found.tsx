import Link from "next/link";

export default function NaoEncontrada() {
  return (
    <div className="mx-auto max-w-xl px-4 pt-24 text-center">
      <p className="text-sm font-semibold text-marca">Erro 404</p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Página não encontrada</h1>
      <p className="mt-3 text-texto-suave">O endereço pode estar errado ou a página foi removida.</p>
      <Link href="/concursos" className="mt-8 inline-block rounded-xl bg-marca px-5 py-3 font-semibold text-white hover:bg-marca-forte">
        Ver concursos
      </Link>
    </div>
  );
}
