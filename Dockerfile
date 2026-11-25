FROM python:3.12.10-slim
WORKDIR /app
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt && useradd --create-home --uid 10001 bank \
    && install -d -o bank -g bank /app
COPY --chown=bank:bank . .
USER bank
