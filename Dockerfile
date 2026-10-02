FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install the package.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .

# Run as an unprivileged user
RUN useradd --create-home --uid 1000 cygne
USER cygne

# Default command runs the Telegram bot; the dashboard service overrides it.
CMD ["python", "-m", "cygne.channels.telegram"]
