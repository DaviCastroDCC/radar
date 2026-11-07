FROM python:3.12-slim

# Desenvolvimento: EXTRAS=dev (pytest, ruff). Produção: vazio, imagem só com o necessário.
ARG EXTRAS=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app \
    TZ=America/Sao_Paulo

WORKDIR /app

# Instala só as dependências (camada fica em cache enquanto apenas o código muda).
COPY pyproject.toml ./
RUN mkdir radar && touch radar/__init__.py \
    && pip install --no-cache-dir ".${EXTRAS:+[$EXTRAS]}" \
    && pip uninstall -y radar-concurso \
    && rm -rf radar build *.egg-info

COPY . .

# Nunca rodar como root: se algo for explorado, o estrago fica contido no container.
RUN useradd --system --uid 10001 --no-create-home radar
USER radar

CMD ["python", "-m", "radar.worker", "loop"]
