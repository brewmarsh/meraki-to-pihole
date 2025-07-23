FROM python:3.10-slim-buster

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock* README.md ./

RUN poetry install --only main --no-root

COPY app ./app

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]
