"""Avaliação da extração por IA com publicações reais (humano no circuito).

Fluxo (detalhes em backend/avaliacao/README.md):

    python -m radar.avaliacao coletar --de 2026-09-01 --ate 2026-11-06   # sem custo
    python -m radar.avaliacao rodar                                     # chama a IA
    python -m radar.avaliacao planilha                                  # gera CSV p/ revisão
    python -m radar.avaliacao pontuar avaliacao/revisoes/<arquivo>.csv  # taxa de acerto

O corpus (texto integral) e os resultados brutos ficam fora do git: publicações podem
conter nomes de candidatos. Só a planilha revisada (dados extraídos + marcações) é versionada.
"""

import argparse
import csv
import json
import logging
import math
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from radar.collectors.base import Coletor
from radar.pipeline.detector import detectar

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent / "avaliacao"
CORPUS = RAIZ / "corpus"
RESULTADOS = RAIZ / "resultados"
REVISOES = RAIZ / "revisoes"

# Colunas que o revisor preenche com S (certo), N (errado) ou NA (não se aplica).
CRITERIOS = {
    "ok_classificacao": "É concurso? E o tipo (abertura, retificação...) está certo?",
    "ok_orgao_banca": "Órgão e banca corretos?",
    "ok_cargos": "Lista de cargos completa e com escolaridade certa?",
    "ok_salario": "Salários corretos?",
    "ok_vagas": "Número de vagas correto?",
    "ok_datas": "Datas de inscrição e prova corretas?",
    "ok_taxa": "Taxa de inscrição correta?",
}


# ---------------------------------------------------------------------------
# 1. Corpus
# ---------------------------------------------------------------------------
def dias_uteis(de: date, ate: date) -> Iterator[date]:
    dia = de
    while dia <= ate:
        if dia.weekday() < 5:
            yield dia
        dia += timedelta(days=1)


def _arquivo(pasta: Path, fonte: str, id_externo: str) -> Path:
    return pasta / f"{fonte}-{id_externo}.json"


def coletar_corpus(coletor: Coletor, dias: Iterable[date], pasta: Path = CORPUS) -> int:
    """Salva as publicações que o detector mandaria para a IA (a mesma entrada da produção)."""
    pasta.mkdir(parents=True, exist_ok=True)
    salvas = 0
    for dia in dias:

        def ja_tem(id_externo: str, _f=coletor.fonte) -> bool:
            return _arquivo(pasta, _f, id_externo).exists()

        for pub in coletor.coletar(dia, ja_conhecido=ja_tem):
            deteccao = detectar(pub.titulo or "", pub.texto)
            if not deteccao.candidato:
                continue
            registro = {**asdict(pub), "data_publicacao": pub.data_publicacao.isoformat()}
            registro["score_detector"] = deteccao.score
            _arquivo(pasta, pub.fonte, pub.id_externo).write_text(
                json.dumps(registro, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            salvas += 1
        log.info("corpus: dia processado", extra={"dia": dia, "total_salvas": salvas})
    return salvas


def ler_corpus(pasta: Path = CORPUS) -> list[dict[str, Any]]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(pasta.glob("*.json"))]


# ---------------------------------------------------------------------------
# 2. Execução da IA
# ---------------------------------------------------------------------------
Extrair = Callable[..., Any]  # Extrator.extrair


def rodar(extrair: Extrair, modelo: str, corpus: list[dict[str, Any]], saida: Path) -> int:
    """Roda a extração em cada item. Retomável: pula ids que já estão no arquivo de saída."""
    saida.parent.mkdir(parents=True, exist_ok=True)
    feitos = (
        {json.loads(linha)["id"] for linha in saida.read_text(encoding="utf-8").splitlines()}
        if saida.exists()
        else set()
    )
    novos = 0
    with saida.open("a", encoding="utf-8") as arquivo:
        for item in corpus:
            ident = f"{item['fonte']}-{item['id_externo']}"
            if ident in feitos:
                continue
            inicio = time.monotonic()
            registro: dict[str, Any] = {
                "id": ident,
                "fonte": item["fonte"],
                "titulo": item.get("titulo"),
                "url": item.get("url"),
                "modelo": modelo,
            }
            try:
                extraido = extrair(
                    fonte=item["fonte"],
                    data=date.fromisoformat(item["data_publicacao"]),
                    orgao=item.get("orgao"),
                    titulo=item.get("titulo"),
                    texto=item["texto"],
                )
                registro |= {"ok": True, "extraido": extraido.model_dump(mode="json")}
            except Exception as e:  # registrar e seguir: uma falha não invalida a rodada
                registro |= {"ok": False, "erro": f"{type(e).__name__}: {e}"}
            registro["segundos"] = round(time.monotonic() - inicio, 2)
            arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
            arquivo.flush()
            novos += 1
    return novos


# ---------------------------------------------------------------------------
# 3. Planilha de revisão
# ---------------------------------------------------------------------------
def _reais(valor: float | None) -> str:
    return "" if valor is None else f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cargos(cargos: list[dict[str, Any]], limite: int = 8) -> str:
    partes = [
        f"{c['nome']} ({c['escolaridade']}, {c.get('vagas') or '-'} vagas, R$ {_reais(c.get('salario')) or '?'})"
        for c in cargos[:limite]
    ]
    if len(cargos) > limite:
        partes.append(f"... +{len(cargos) - limite}")
    return " | ".join(partes)


def gerar_planilha(resultados: Path, saida: Path) -> int:
    """CSV para Excel/Google Sheets (separador ';', UTF-8 com BOM) com colunas de revisão em branco."""
    linhas = [json.loads(linha) for linha in resultados.read_text(encoding="utf-8").splitlines() if linha]
    saida.parent.mkdir(parents=True, exist_ok=True)
    colunas = [
        "id", "url", "titulo", "erro", "e_concurso", "tipo", "orgao", "banca", "uf", "qtd_cargos", "cargos",
        "vagas_total", "salario_max", "inscricao_inicio", "inscricao_fim", "data_prova", "taxa_inscricao",
        "resumo", *CRITERIOS, "observacoes",
    ]  # fmt: skip
    with saida.open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas, delimiter=";")
        escritor.writeheader()
        for r in linhas:
            ex = r.get("extraido") or {}
            cargos = ex.get("cargos") or []
            vagas = [c["vagas"] for c in cargos if c.get("vagas") is not None]
            salarios = [c["salario"] for c in cargos if c.get("salario") is not None]
            escritor.writerow(
                {
                    "id": r["id"],
                    "url": r.get("url") or "",
                    "titulo": r.get("titulo") or "",
                    "erro": r.get("erro") or "",
                    "e_concurso": {True: "sim", False: "não"}.get(ex.get("e_concurso"), ""),
                    "tipo": ex.get("tipo", ""),
                    "orgao": ex.get("orgao") or "",
                    "banca": ex.get("banca") or "",
                    "uf": ex.get("uf") or "",
                    "qtd_cargos": len(cargos) if ex else "",
                    "cargos": _cargos(cargos),
                    "vagas_total": sum(vagas) if vagas else "",
                    "salario_max": _reais(max(salarios)) if salarios else "",
                    "inscricao_inicio": ex.get("inscricao_inicio") or "",
                    "inscricao_fim": ex.get("inscricao_fim") or "",
                    "data_prova": ex.get("data_prova") or "",
                    "taxa_inscricao": _reais(ex.get("taxa_inscricao")),
                    "resumo": ex.get("resumo") or "",
                }
            )
    return len(linhas)


# ---------------------------------------------------------------------------
# 4. Pontuação
# ---------------------------------------------------------------------------
def intervalo_wilson(acertos: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confiança de 95% para uma proporção (robusto com amostras pequenas)."""
    if total == 0:
        return (0.0, 0.0)
    p = acertos / total
    centro = (p + z * z / (2 * total)) / (1 + z * z / total)
    margem = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return (max(0.0, centro - margem), min(1.0, centro + margem))


def _marca(valor: str | None) -> bool | None:
    v = (valor or "").strip().upper()
    if v in {"S", "SIM", "1", "OK"}:
        return True
    if v in {"N", "NAO", "NÃO", "0"}:
        return False
    return None  # vazio ou NA: não entra na conta


def pontuar(planilha: Path) -> dict[str, Any]:
    with planilha.open(encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo, delimiter=";"))

    por_criterio = {}
    for criterio in CRITERIOS:
        marcas = [m for m in (_marca(linha.get(criterio)) for linha in linhas) if m is not None]
        acertos = sum(marcas)
        baixo, alto = intervalo_wilson(acertos, len(marcas))
        por_criterio[criterio] = {
            "revisados": len(marcas),
            "acertos": acertos,
            "taxa": acertos / len(marcas) if marcas else None,
            "ic95": [round(baixo, 3), round(alto, 3)],
        }

    revisadas = [linha for linha in linhas if any(_marca(linha.get(c)) is not None for c in CRITERIOS)]
    perfeitas = [linha for linha in revisadas if all(_marca(linha.get(c)) is not False for c in CRITERIOS)]
    return {
        "planilha": planilha.name,
        "publicacoes": len(linhas),
        "revisadas": len(revisadas),
        "sem_nenhum_erro": len(perfeitas),
        "taxa_sem_nenhum_erro": len(perfeitas) / len(revisadas) if revisadas else None,
        "por_criterio": por_criterio,
    }


def imprimir_pontuacao(p: dict[str, Any]) -> None:
    print(f"Planilha: {p['planilha']}  |  revisadas: {p['revisadas']} de {p['publicacoes']}")
    for criterio, r in p["por_criterio"].items():
        if r["taxa"] is None:
            print(f"  {criterio:<18} sem revisão")
            continue
        baixo, alto = r["ic95"]
        print(
            f"  {criterio:<18} {r['taxa']:6.1%}  ({r['acertos']}/{r['revisados']})"
            f"  IC95%: {baixo:.0%}–{alto:.0%}"
        )
    if p["taxa_sem_nenhum_erro"] is not None:
        print(f"  {'edital 100% certo':<18} {p['taxa_sem_nenhum_erro']:6.1%}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from radar.config import get_settings

    settings = get_settings()
    parser = argparse.ArgumentParser(prog="radar.avaliacao")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("coletar", help="monta o corpus a partir do DODF (sem custo)")
    p.add_argument("--de", type=date.fromisoformat, required=True)
    p.add_argument("--ate", type=date.fromisoformat, required=True)

    p = sub.add_parser("rodar", help="roda a IA no corpus (tem custo)")
    p.add_argument("--saida", type=Path)

    p = sub.add_parser("planilha", help="gera a planilha de revisão a partir de um resultado")
    p.add_argument("resultado", type=Path, nargs="?")

    p = sub.add_parser("pontuar", help="calcula a taxa de acerto de uma planilha revisada")
    p.add_argument("planilha", type=Path)
    p.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.comando == "coletar":
        from radar.collectors.dodf import ColetorDODF

        n = coletar_corpus(ColetorDODF(settings), dias_uteis(args.de, args.ate))
        print(f"{n} publicações novas no corpus ({len(list(CORPUS.glob('*.json')))} no total)")
    elif args.comando == "rodar":
        from radar.pipeline.extractor import Extrator

        extrator = Extrator(settings)
        saida = args.saida or RESULTADOS / f"{settings.extractor_model}-{datetime.now():%Y%m%d-%H%M}.jsonl"
        n = rodar(extrator.extrair, settings.extractor_model, ler_corpus(), saida)
        print(f"{n} extrações gravadas em {saida}")
    elif args.comando == "planilha":
        resultado = args.resultado or max(RESULTADOS.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        saida = REVISOES / f"{resultado.stem}.csv"
        n = gerar_planilha(resultado, saida)
        print(f"Planilha com {n} linhas: {saida}")
    elif args.comando == "pontuar":
        resultado = pontuar(args.planilha)
        if args.json:
            print(json.dumps(resultado, ensure_ascii=False, indent=2))
        else:
            imprimir_pontuacao(resultado)


if __name__ == "__main__":
    main()
