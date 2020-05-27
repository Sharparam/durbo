FROM python:3.8.3-slim-buster

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=1.0.5 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry'

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        curl \
    && apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python -u \
    && poetry --version

WORKDIR /app
COPY ./pyproject.toml ./poetry.lock /app/

RUN poetry install --no-dev --no-interaction --no-ansi \
    && rm -rf "$POETRY_CACHE_DIR"

COPY docker-entrypoint.sh ./
RUN chmod +x 'docker-entrypoint.sh' \
    && groupadd -r durbo && useradd -d /app -r -g durbo durbo \
    && chown durbo:durbo -R /app

USER durbo

ENTRYPOINT ["./docker-entrypoint.sh"]
