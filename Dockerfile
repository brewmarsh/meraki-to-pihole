# build stage
FROM python:3.10-slim-buster as builder

WORKDIR /app

RUN pip install poetry

COPY . .

RUN poetry config virtualenvs.create false && poetry install --only main

# final stage
FROM python:3.10-slim-buster

# Create a non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /home/appuser/app

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /app /home/appuser/app

RUN chown -R appuser:appgroup /home/appuser/app

USER appuser

ENV PATH="/home/appuser/.local/bin:${PATH}"
ENV FLASK_PORT=8000
EXPOSE 8000

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]
