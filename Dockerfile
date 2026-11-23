FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY contracts ./contracts
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini ./
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
