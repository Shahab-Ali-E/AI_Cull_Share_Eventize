# The builder image, used to build the virtual environment
FROM python:3.12-slim AS builder

# Install required dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc 

RUN pip install poetry==1.8.3

WORKDIR /app

ENV POETRY_NO_INTERACTION=1\
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache


COPY pyproject.toml poetry.lock ./

RUN touch README.md

# Force install psycopg2 with pip to bypass PEP 517 error
# RUN poetry run pip install --no-cache-dir --no-build-isolation psycopg2==2.9.10

# Now install all dependencies
RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --no-root


# The runtime image, used to just run the code provided its virtual environment
FROM python:3.12-slim-bookworm AS runtime

# Install Poetry in runtime stage
RUN pip install poetry==1.8.3

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY src/ /app/src/

COPY Ml_Models/ /app/ML_Models/

COPY alembic/ /app/alembic/

COPY alembic.ini /app/alembic.ini

RUN mkdir -p /app/static

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "src.main.main:app", "--host", "0.0.0.0", "--port", "8000"]

