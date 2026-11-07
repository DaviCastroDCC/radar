-- RadarConcurso - schema inicial (PostgreSQL 17 + pgvector)
-- Executado automaticamente pelo container do Postgres na primeira subida.

CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;   -- reservado para busca semântica de cargos

-- Configuração de busca textual em português que ignora acentos:
-- "Analista Judiciária" casa com "analista judiciario".
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'pt') THEN
        CREATE TEXT SEARCH CONFIGURATION pt (COPY = portuguese);
        ALTER TEXT SEARCH CONFIGURATION pt
            ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Publicações brutas coletadas dos diários. Também funciona como fila:
-- o worker pega as 'pendente' com FOR UPDATE SKIP LOCKED.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS publicacoes (
    id               BIGSERIAL PRIMARY KEY,
    fonte            TEXT        NOT NULL,             -- 'dodf', 'dou', ...
    id_externo       TEXT        NOT NULL,             -- id da matéria na fonte
    data_publicacao  DATE        NOT NULL,
    secao            TEXT,
    orgao            TEXT,
    tipo_ato         TEXT,
    titulo           TEXT,
    url              TEXT,
    texto            TEXT        NOT NULL,
    hash_texto       TEXT        NOT NULL,
    status           TEXT        NOT NULL DEFAULT 'pendente'
                     CHECK (status IN ('pendente', 'descartada', 'processada', 'erro')),
    score_detector   INTEGER,
    tentativas       INTEGER     NOT NULL DEFAULT 0,
    erro             TEXT,
    coletada_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    processada_em    TIMESTAMPTZ,
    UNIQUE (fonte, id_externo)
);
CREATE INDEX IF NOT EXISTS ix_publicacoes_pendentes ON publicacoes (id) WHERE status = 'pendente';
CREATE INDEX IF NOT EXISTS ix_publicacoes_data ON publicacoes (data_publicacao);

-- ---------------------------------------------------------------------------
-- Editais entendidos pela IA.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS editais (
    id                   BIGSERIAL PRIMARY KEY,
    publicacao_id        BIGINT      NOT NULL UNIQUE REFERENCES publicacoes (id),
    edital_pai_id        BIGINT      REFERENCES editais (id),   -- retificação -> edital original
    tipo                 TEXT        NOT NULL,
    orgao                TEXT,
    banca                TEXT,
    titulo               TEXT,
    numero_edital        TEXT,
    edital_referenciado  TEXT,
    uf                   TEXT,
    cidades              TEXT[]      NOT NULL DEFAULT '{}',
    inscricao_inicio     DATE,
    inscricao_fim        DATE,
    data_prova           DATE,
    taxa_inscricao       NUMERIC(10, 2),
    salario_max          NUMERIC(12, 2),
    vagas_total          INTEGER,
    link_inscricao       TEXT,
    resumo               TEXT,
    dados                JSONB       NOT NULL,                  -- saída completa da extração
    modelo               TEXT,
    criado_em            TIMESTAMPTZ NOT NULL DEFAULT now(),
    tsv                  TSVECTOR GENERATED ALWAYS AS (
        to_tsvector('pt'::regconfig,
            coalesce(titulo, '') || ' ' || coalesce(orgao, '') || ' ' ||
            coalesce(banca, '') || ' ' || coalesce(resumo, ''))
    ) STORED
);
CREATE INDEX IF NOT EXISTS ix_editais_tsv ON editais USING GIN (tsv);
CREATE INDEX IF NOT EXISTS ix_editais_uf ON editais (uf);
CREATE INDEX IF NOT EXISTS ix_editais_inscricao_fim ON editais (inscricao_fim);
CREATE INDEX IF NOT EXISTS ix_editais_numero ON editais (numero_edital);

CREATE TABLE IF NOT EXISTS cargos (
    id                BIGSERIAL PRIMARY KEY,
    edital_id         BIGINT      NOT NULL REFERENCES editais (id) ON DELETE CASCADE,
    nome              TEXT        NOT NULL,
    escolaridade      TEXT        NOT NULL,
    vagas             INTEGER,
    cadastro_reserva  BOOLEAN     NOT NULL DEFAULT false,
    salario           NUMERIC(12, 2),
    tsv               TSVECTOR GENERATED ALWAYS AS (to_tsvector('pt'::regconfig, nome)) STORED
);
CREATE INDEX IF NOT EXISTS ix_cargos_edital ON cargos (edital_id);
CREATE INDEX IF NOT EXISTS ix_cargos_tsv ON cargos USING GIN (tsv);

-- ---------------------------------------------------------------------------
-- Usuários, filtros e alertas.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id                BIGSERIAL PRIMARY KEY,
    telegram_chat_id  BIGINT      UNIQUE,
    nome              TEXT,
    email             TEXT        UNIQUE,
    plano             TEXT        NOT NULL DEFAULT 'free' CHECK (plano IN ('free', 'premium')),
    ativo             BOOLEAN     NOT NULL DEFAULT true,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS filtros (
    id             BIGSERIAL PRIMARY KEY,
    usuario_id     BIGINT      NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    palavras       TEXT        NOT NULL DEFAULT '',   -- ex.: "analista ti"
    ufs            TEXT[]      NOT NULL DEFAULT '{}', -- vazio = qualquer UF
    escolaridades  TEXT[]      NOT NULL DEFAULT '{}', -- vazio = qualquer
    salario_min    NUMERIC(12, 2),
    ativo          BOOLEAN     NOT NULL DEFAULT true,
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_filtros_ativos ON filtros (usuario_id) WHERE ativo;

-- Editais que o usuário segue para receber retificações.
CREATE TABLE IF NOT EXISTS acompanhamentos (
    usuario_id  BIGINT      NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    edital_id   BIGINT      NOT NULL REFERENCES editais (id) ON DELETE CASCADE,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (usuario_id, edital_id)
);

CREATE TABLE IF NOT EXISTS alertas (
    id          BIGSERIAL PRIMARY KEY,
    usuario_id  BIGINT      NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    edital_id   BIGINT      NOT NULL REFERENCES editais (id) ON DELETE CASCADE,
    motivo      TEXT        NOT NULL CHECK (motivo IN ('novo_edital', 'retificacao')),
    canal       TEXT        NOT NULL DEFAULT 'telegram',
    status      TEXT        NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'enviado', 'erro')),
    tentativas  INTEGER     NOT NULL DEFAULT 0,
    erro        TEXT,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    enviado_em  TIMESTAMPTZ,
    UNIQUE (usuario_id, edital_id)
);
CREATE INDEX IF NOT EXISTS ix_alertas_pendentes ON alertas (id) WHERE status = 'pendente';

-- ---------------------------------------------------------------------------
-- Registro de cada execução de coleta (métricas e depuração).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coletas (
    id             BIGSERIAL PRIMARY KEY,
    fonte          TEXT        NOT NULL,
    data_ref       DATE        NOT NULL,
    iniciada_em    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalizada_em  TIMESTAMPTZ,
    itens_lidos    INTEGER     NOT NULL DEFAULT 0,
    itens_novos    INTEGER     NOT NULL DEFAULT 0,
    erro           TEXT
);
