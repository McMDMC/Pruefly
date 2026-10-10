FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# WeasyPrint needs pango; DejaVu gives full German glyph coverage.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY pruefly ./pruefly
COPY web ./web
RUN pip install -e .   # editable: keeps web/ and sheet.css next to the code
RUN useradd -m app
USER app
ENV PORT=8080
CMD ["sh", "-c", "uvicorn pruefly.main:app_factory --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
