# build stage
FROM python:3.9-slim-buster as builder

WORKDIR /app

RUN pip install poetry

COPY . .

RUN poetry config virtualenvs.create false && poetry install --only main

# final stage
FROM python:3.9-slim-buster

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

COPY app/ /app/app/

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]
