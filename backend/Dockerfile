# Build context is the repository root (see docker/docker-compose.yml) so this image can
# also bundle the seed script and default tag map, which live outside backend/.
FROM python:3.11-slim

# python-snap7 3.x is a pure-Python S7 implementation (no libsnap7.so needed), and pymodbus
# is pure Python too, so this image needs no system packages beyond Python itself.
WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY database/seed ./database/seed
COPY config/plc_tags.yaml ./config/plc_tags.yaml

RUN pip install --no-cache-dir .

# Overridden by compose volume mounts in production; created here so a plain `docker run`
# (no compose, no volumes) still has somewhere to put the DB and backups on first boot.
RUN mkdir -p /app/data /app/backups

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz', timeout=3)" || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
