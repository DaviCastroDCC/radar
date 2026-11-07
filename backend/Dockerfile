FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    TZ=America/Sao_Paulo

WORKDIR /app

# Instala só as dependências (camada fica em cache enquanto apenas o código muda).
COPY pyproject.toml ./
RUN mkdir radar && touch radar/__init__.py \
    && pip install ".[dev]" \
    && pip uninstall -y radar-concurso \
    && rm -rf radar build *.egg-info

COPY . .

CMD ["python", "-m", "radar.worker", "loop"]
