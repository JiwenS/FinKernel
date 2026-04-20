FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN python -m pip install --upgrade pip setuptools wheel

COPY pyproject.toml README.md ./
COPY config ./config
COPY src ./src

RUN pip install --no-build-isolation .

EXPOSE 8000

CMD ["uvicorn", "finkernel.main:app", "--host", "0.0.0.0", "--port", "8000"]
