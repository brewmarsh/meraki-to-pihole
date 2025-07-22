# build stage
FROM python:3.10-slim-buster as builder

WORKDIR /app

RUN pip install poetry

COPY . .

RUN poetry config virtualenvs.create false && poetry install --only main

# final stage
FROM python:3.10-slim-buster

WORKDIR /app

RUN pip install poetry

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root
COPY app/ /app/app/

ARG FLASK_PORT=8000
EXPOSE ${FLASK_PORT}

CMD ["poetry", "run", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "${FLASK_PORT}"]
