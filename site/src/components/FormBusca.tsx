import { UFS } from "@/lib/formato";

type Props = {
  q?: string;
  uf?: string;
  abertos?: boolean;
  destaque?: boolean;
};

/** Formulário GET puro: funciona sem JavaScript e gera URLs compartilháveis/indexáveis. */
export function FormBusca({ q = "", uf = "", abertos = true, destaque = false }: Props) {
  const campo =
    "h-12 rounded-xl border border-borda bg-superficie px-4 text-texto placeholder:text-texto-suave/70 focus:border-marca focus:outline-none";
  return (
    <form
      action="/concursos"
      method="get"
      role="search"
      className={`flex flex-col gap-3 sm:flex-row sm:items-center ${destaque ? "rounded-2xl bg-superficie p-3 shadow-lg ring-1 ring-borda" : ""}`}
    >
      <label className="sr-only" htmlFor="busca-q">Cargo, órgão ou banca</label>
      <input
        id="busca-q"
        name="q"
        defaultValue={q}
        placeholder="Cargo, órgão ou banca (ex.: analista, PCDF, Cebraspe)"
        className={`${campo} flex-1`}
      />
      <label className="sr-only" htmlFor="busca-uf">Estado</label>
      <select id="busca-uf" name="uf" defaultValue={uf} className={`${campo} sm:w-40`}>
        <option value="">Todo o Brasil</option>
        {UFS.map((sigla) => (
          <option key={sigla} value={sigla}>{sigla}</option>
        ))}
      </select>
      <label className="flex items-center gap-2 px-1 text-sm whitespace-nowrap text-texto-suave">
        <input type="checkbox" name="abertos" value="1" defaultChecked={abertos} className="size-4 accent-marca" />
        Só inscrições abertas
      </label>
      <button type="submit" className="h-12 rounded-xl bg-marca px-6 font-semibold text-white transition-colors hover:bg-marca-forte">
        Buscar
      </button>
    </form>
  );
}
