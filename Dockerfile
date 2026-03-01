FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NOTES_CLI_HOME=/data

WORKDIR /app

RUN useradd --create-home --shell /usr/sbin/nologin appuser

COPY pyproject.toml README.md /app/
COPY notes_cli /app/notes_cli

RUN python -m pip install --upgrade pip && \
    python -m pip install .

RUN mkdir -p /data && chown -R appuser:appuser /data

VOLUME ["/data"]

USER appuser

ENTRYPOINT ["notes"]
CMD ["--help"]
