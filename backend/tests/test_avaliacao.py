"""Ferramenta de avaliação da IA: corpus, execução retomável, planilha e pontuação."""

import csv
import json
from datetime import date

import pytest

from radar import avaliacao
from radar.collectors.base import PublicacaoColetada
from tests.fakes import extraido_exemplo
from tests.fixtures.textos import EDITAL_ABERTURA, PREGAO


class ColetorFalso:
    fonte = "dodf"

    def __init__(self, publicacoes):
        self.publicacoes = publicacoes
        self.consultados: list[str] = []

    def coletar(self, dia, ja_conhecido):
        for pub in self.publicacoes:
            self.consultados.append(pub.id_externo)
            if not ja_conhecido(pub.id_externo):
                yield pub


def _pub(id_externo: str, texto: str) -> PublicacaoColetada:
    return PublicacaoColetada(
        fonte="dodf", id_externo=id_externo, data_publicacao=date(2026, 11, 6), texto=texto, titulo="EDITAL"
    )


def test_dias_uteis_pula_fim_de_semana():
    assert list(avaliacao.dias_uteis(date(2026, 11, 6), date(2026, 11, 9))) == [
        date(2026, 11, 6),
        date(2026, 11, 9),
    ]


def test_corpus_guarda_so_o_que_iria_para_a_ia_e_nao_repete(tmp_path):
    coletor = ColetorFalso([_pub("1", EDITAL_ABERTURA), _pub("2", PREGAO)])

    assert avaliacao.coletar_corpus(coletor, [date(2026, 11, 6)], tmp_path) == 1
    assert avaliacao.coletar_corpus(coletor, [date(2026, 11, 6)], tmp_path) == 0  # já está no corpus

    [item] = avaliacao.ler_corpus(tmp_path)
    assert (item["id_externo"], item["data_publicacao"]) == ("1", "2026-11-06")
    assert item["score_detector"] >= 6


def test_rodar_e_retomavel_e_registra_falhas(tmp_path):
    corpus = [
        {"fonte": "dodf", "id_externo": str(i), "data_publicacao": "2026-11-06", "titulo": "E", "texto": "x"}
        for i in range(3)
    ]
    chamadas = []

    def extrair(**kwargs):
        chamadas.append(kwargs)
        if len(chamadas) == 2:
            raise TimeoutError("API lenta")
        return extraido_exemplo()

    saida = tmp_path / "r.jsonl"
    assert avaliacao.rodar(extrair, "claude-haiku-5-5", corpus[:2], saida) == 2
    assert avaliacao.rodar(extrair, "claude-haiku-5-5", corpus, saida) == 1  # só o novo

    linhas = [json.loads(linha) for linha in saida.read_text(encoding="utf-8").splitlines()]
    assert [linha["ok"] for linha in linhas] == [True, False, True]
    assert linhas[1]["erro"] == "TimeoutError: API lenta"
    assert linhas[0]["extraido"]["banca"] == "Cebraspe"


def _resultado(tmp_path):
    saida = tmp_path / "r.jsonl"
    linhas = [
        {"id": "dodf-1", "ok": True, "extraido": extraido_exemplo().model_dump(mode="json"), "url": "u"},
        {"id": "dodf-2", "ok": False, "erro": "Timeout"},
    ]
    saida.write_text("\n".join(json.dumps(linha) for linha in linhas), encoding="utf-8")
    return saida


def test_planilha_abre_no_excel_brasileiro(tmp_path):
    planilha = tmp_path / "p.csv"
    assert avaliacao.gerar_planilha(_resultado(tmp_path), planilha) == 2

    bruto = planilha.read_bytes()
    assert bruto.startswith(b"\xef\xbb\xbf")  # BOM: Excel reconhece UTF-8 e os acentos
    with planilha.open(encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    assert linhas[0]["salario_max"] == "5.800,50"
    assert linhas[0]["cargos"] == "Professor (superior, 100 vagas, R$ 5.800,50)"
    assert linhas[1]["erro"] == "Timeout"
    assert all(linhas[0][c] == "" for c in avaliacao.CRITERIOS)  # revisão começa em branco


def _revisar(planilha, marcas: list[dict[str, str]]):
    with planilha.open(encoding="utf-8-sig", newline="") as f:
        leitor = csv.DictReader(f, delimiter=";")
        campos, linhas = leitor.fieldnames, list(leitor)
    for linha, marca in zip(linhas, marcas, strict=True):
        linha.update(marca)
    with planilha.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)


def test_pontuacao_ignora_na_e_branco(tmp_path):
    planilha = tmp_path / "p.csv"
    avaliacao.gerar_planilha(_resultado(tmp_path), planilha)
    _revisar(
        planilha,
        [
            {"ok_classificacao": "S", "ok_datas": "s", "ok_taxa": "NA"},
            {"ok_classificacao": "N", "ok_datas": "S"},
        ],
    )

    p = avaliacao.pontuar(planilha)

    assert p["revisadas"] == 2
    assert p["por_criterio"]["ok_classificacao"]["taxa"] == 0.5
    assert p["por_criterio"]["ok_datas"]["taxa"] == 1.0
    assert p["por_criterio"]["ok_taxa"]["revisados"] == 0
    assert p["sem_nenhum_erro"] == 1


@pytest.mark.parametrize(
    ("acertos", "total", "baixo", "alto"),
    [(45, 50, 0.79, 0.96), (50, 50, 0.93, 1.0), (0, 0, 0.0, 0.0)],
)
def test_intervalo_de_wilson(acertos, total, baixo, alto):
    ic = avaliacao.intervalo_wilson(acertos, total)
    assert ic == pytest.approx((baixo, alto), abs=0.01)
