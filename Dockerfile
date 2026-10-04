FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app
COPY pyproject.toml requirements.lock ./
RUN pip install --upgrade pip && pip install -c requirements.lock .
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
RUN mkdir -p /app/uploads && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]

FROM runtime AS test
USER root
RUN pip install -c requirements.lock -e ".[test]"
COPY tests ./tests
RUN chown -R app:app /app/tests
USER app
CMD ["pytest", "--cov=app", "--cov-report=term-missing"]

FROM runtime AS production
