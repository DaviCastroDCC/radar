"""Regras de usuários e LGPD (consentimento, acesso, eliminação e retenção)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from radar import db, usuarios
from radar.models import Acompanhamento, Alerta, Edital, Filtro, Usuario
from radar.pipeline.processor import processar_pendentes
from radar.relogio import agora
from tests.fakes import ExtratorFalso, criar_usuario, extraido_exemplo, publicar
from tests.fixtures.textos import EDITAL_ABERTURA

TITULO = "EDITAL NORMATIVO Nº 1 – SEEDF"
CHAT = 4242


def _novo_filtro(chat_id: int = CHAT, limite: int = 3) -> int:
    return usuarios.criar_filtro(
        chat_id,
        palavras="professor",
        ufs=["DF"],
        escolaridades=["superior"],
        salario_min=Decimal("5000"),
        limite_free=limite,
    )


def _contar(modelo) -> int:
    with db.session_scope() as s:
        return s.scalar(select(func.count()).select_from(modelo))


def _publicar_edital() -> int:
    fim = (date.today() + timedelta(days=10)).isoformat()
    publicar("1", TITULO, EDITAL_ABERTURA)
    processar_pendentes(ExtratorFalso({TITULO: extraido_exemplo(inscricao_fim=fim)}), max_tentativas=3)
    with db.session_scope() as s:
        return s.scalar(select(Edital.id))


# ------------------------------ consentimento ------------------------------
def test_registro_novo_exige_aceite(limpo):
    assert usuarios.registrar(CHAT) is False
    with pytest.raises(usuarios.TermosPendentes):
        _novo_filtro()


def test_aceite_grava_data_e_versao(limpo):
    usuarios.registrar(CHAT)
    usuarios.aceitar_termos(CHAT)
    assert usuarios.registrar(CHAT) is True
    with db.session_scope() as s:
        u = s.scalar(select(Usuario))
        assert u.termos_versao == usuarios.TERMOS_VERSAO
        assert u.termos_aceitos_em is not None


def test_comandos_sem_cadastro(limpo):
    with pytest.raises(usuarios.UsuarioNaoCadastrado):
        _novo_filtro()
    with pytest.raises(usuarios.UsuarioNaoCadastrado):
        usuarios.aceitar_termos(CHAT)
    assert usuarios.exportar_dados(CHAT) is None
    assert usuarios.apagar(CHAT) is False


def test_sem_aceite_nao_recebe_alertas(limpo):
    criar_usuario(1, aceitou_termos=False, palavras="professor")
    criar_usuario(2, palavras="professor")
    _publicar_edital()
    with db.session_scope() as s:
        destinatarios = s.scalars(select(Usuario.telegram_chat_id).join(Alerta)).all()
    assert destinatarios == [2]


def test_nova_versao_dos_termos_exige_novo_aceite(limpo, monkeypatch):
    criar_usuario(CHAT)
    monkeypatch.setattr(usuarios, "TERMOS_VERSAO", "2099-01-01")
    assert usuarios.registrar(CHAT) is False
    with pytest.raises(usuarios.TermosPendentes):
        _novo_filtro()


# ------------------------------ filtros ------------------------------
def test_limite_de_filtros_do_plano_gratuito(limpo):
    criar_usuario(CHAT)  # já tem 1 filtro
    _novo_filtro(limite=2)
    with pytest.raises(usuarios.LimiteDeFiltros) as erro:
        _novo_filtro(limite=2)
    assert erro.value.total == 2


def test_remover_filtro_apaga_de_verdade_e_so_do_dono(limpo):
    criar_usuario(CHAT)
    criar_usuario(999)
    filtro_id = _novo_filtro()
    assert usuarios.remover_filtro(999, filtro_id) is False  # não é dele
    assert usuarios.remover_filtro(CHAT, filtro_id) is True
    assert usuarios.remover_filtro(CHAT, filtro_id) is False
    with db.session_scope() as s:
        assert s.get(Filtro, filtro_id) is None


def test_listar_filtros(limpo):
    criar_usuario(CHAT, palavras="analista ti", ufs=["DF"])
    [f] = usuarios.listar_filtros(CHAT)
    assert (f.palavras, f.ufs) == ("analista ti", ["DF"])


def test_acompanhar_edital(limpo):
    criar_usuario(CHAT)
    edital_id = _publicar_edital()
    assert usuarios.acompanhar(CHAT, edital_id) is True
    assert usuarios.acompanhar(CHAT, edital_id) is True  # idempotente
    assert usuarios.acompanhar(CHAT, 999_999) is False
    assert _contar(Acompanhamento) == 1


# ------------------------------ direitos do titular ------------------------------
def test_exportar_dados_traz_tudo_e_e_serializavel(limpo):
    import json

    criar_usuario(CHAT, palavras="professor")
    edital_id = _publicar_edital()
    usuarios.acompanhar(CHAT, edital_id)

    dados = usuarios.exportar_dados(CHAT)

    json.dumps(dados)  # precisa virar arquivo sem erro
    assert dados["usuario"]["telegram_chat_id"] == CHAT
    assert dados["usuario"]["termos_versao"] == usuarios.TERMOS_VERSAO
    assert [f["palavras"] for f in dados["filtros"]] == ["professor"]
    assert [e["edital_id"] for e in dados["editais_acompanhados"]] == [edital_id]
    assert [a["motivo"] for a in dados["alertas_recebidos"]] == ["novo_edital"]


def test_apagar_remove_usuario_e_tudo_em_cascata(limpo):
    criar_usuario(CHAT, palavras="professor")
    outro = criar_usuario(7, palavras="professor")
    edital_id = _publicar_edital()
    usuarios.acompanhar(CHAT, edital_id)

    assert usuarios.apagar(CHAT) is True

    with db.session_scope() as s:
        assert s.scalars(select(Usuario.id)).all() == [outro]
        assert s.scalars(select(Filtro.usuario_id)).all() == [outro]
        assert s.scalars(select(Alerta.usuario_id)).all() == [outro]
        assert s.scalar(select(func.count()).select_from(Acompanhamento)) == 0
        assert s.get(Edital, edital_id) is not None  # dado público continua


# ------------------------------ retenção ------------------------------
def test_pausar_inicia_prazo_e_start_reativa(limpo):
    criar_usuario(CHAT)
    usuarios.pausar(CHAT)
    with db.session_scope() as s:
        u = s.scalar(select(Usuario))
        assert (u.ativo, u.desativado_em is not None) == (False, True)
    usuarios.registrar(CHAT)
    with db.session_scope() as s:
        u = s.scalar(select(Usuario))
        assert (u.ativo, u.desativado_em) == (True, None)


def test_retencao_apaga_so_inativos_ha_mais_de_180_dias(limpo):
    criar_usuario(1)
    criar_usuario(2)
    criar_usuario(3)  # continua ativo
    usuarios.pausar(1)
    usuarios.pausar(2)
    with db.session_scope() as s:
        antigo = s.scalar(select(Usuario).where(Usuario.telegram_chat_id == 1))
        antigo.desativado_em = agora() - timedelta(days=181)

    assert usuarios.purgar_inativos() == 1
    with db.session_scope() as s:
        assert sorted(s.scalars(select(Usuario.telegram_chat_id))) == [2, 3]
