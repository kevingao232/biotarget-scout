# BioTarget Scout — API + static test UI (see README for env vars).
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY web ./web

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

# Default English model (small). For build-plan biomedical NER, add:
#   RUN pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_sm-0.5.4.tar.gz
RUN python -m spacy download en_core_web_sm

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "biotarget_scout.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
