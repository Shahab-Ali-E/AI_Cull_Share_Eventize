# ###############################################
# # Base Image
# ###############################################
# # FROM python:3.12-slim AS python-base
# FROM python:3.12-slim

# # ENV PYTHONUNBUFFERED=1 \
# #     PYTHONDONTWRITEBYTECODE=1 \
# #     PIP_NO_CACHE_DIR=off \
# #     PIP_DISABLE_PIP_VERSION_CHECK=on \
# #     PIP_DEFAULT_TIMEOUT=100 \
# #     POETRY_VERSION=1.8.3 \
# #     POETRY_HOME="/opt/poetry" \
# #     POETRY_VIRTUALENVS_IN_PROJECT=true \
# #     POETRY_NO_INTERACTION=1 \
# #     PYSETUP_PATH="/opt/pysetup" \
# #     VENV_PATH="/opt/pysetup/.venv"

# # # prepend poetry and venv to path
# # ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

# ###############################################
# # Builder Image
# ###############################################
# # FROM python-base AS builder-base
# RUN apt-get update \
#     && apt-get install --no-install-recommends -y \
#     curl \
#     build-essential \
#     gcc \
#     python3-dev

# # install poetry using pip to ensure version control
# RUN pip install "poetry==1.8.3"

# # copy project requirement files here to ensure they will be cached.
# # WORKDIR $PYSETUP_PATH
# WORKDIR /app
# COPY poetry.lock pyproject.toml ./app/

# # install runtime deps - uses $POETRY_VIRTUALENVS_IN_PROJECT internally
# RUN poetry install --no-root

# ###############################################
# # Production Image
# ###############################################
# # FROM python-base AS production
# # COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH
# COPY . ./app/

# CMD ["uvicorn", "src.main.main:app", "--host", "0.0.0.0", "--port", "8080"]

# #######################################

# Use official Python slim image
# Use official Python slim image
# FROM python:3.12-slim

# # Set environment variables for Poetry & Python
# ENV PYTHONUNBUFFERED=1 \
#     PYTHONDONTWRITEBYTECODE=1 \
#     PIP_NO_CACHE_DIR=off \
#     PIP_DISABLE_PIP_VERSION_CHECK=on \
#     PIP_DEFAULT_TIMEOUT=100 \
#     POETRY_VERSION=1.8.3 \
#     POETRY_HOME="/opt/poetry" \
#     POETRY_VIRTUALENVS_IN_PROJECT=true \
#     POETRY_NO_INTERACTION=1 \
#     VENV_PATH="/app/.venv"

# # Ensure Poetry & Virtual Env is in PATH
# ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

# # Install system dependencies
# RUN apt-get update && apt-get install --no-install-recommends -y \
#     curl \
#     build-essential \
#     gcc \
#     python3-dev \
#     supervisor \
#     && rm -rf /var/lib/apt/lists/*

# # Install Poetry
# RUN pip install "poetry==$POETRY_VERSION"

# # Set working directory
# WORKDIR /app

# # Copy dependency files
# COPY poetry.lock pyproject.toml ./ 

# # Install dependencies
# RUN poetry install --no-root --only main

# # Copy project files
# COPY . .

# # Copy supervisord config
# COPY supervisord.conf /etc/supervisord.conf

# # Expose port
# EXPOSE 7860

# # Use Supervisor to run both services
# CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]

FROM python:3.12

# Set environment variables for Poetry & Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=300 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    VENV_PATH="/app/.venv" \
    PATH="/opt/poetry/bin:/app/.venv/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    build-essential \
    libhdf5-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install "poetry==$POETRY_VERSION"

# Create a non-root user
# RUN useradd --create-home appuser

# # Switch to the non-root user
# USER appuser

# Set working directory
WORKDIR /app

# Copy dependency files
COPY poetry.lock pyproject.toml ./

# Configure pip to use a faster mirror (optional)
RUN pip config set global.index-url https://pypi.org/simple

# Install dependencies
RUN poetry install --no-root --only main

# Copy the rest of the app code
COPY . .

# Expose app port
EXPOSE 8000

CMD ["uvicorn", "src.main.main:app", "--host","0.0.0.0", "--port", "8000"]