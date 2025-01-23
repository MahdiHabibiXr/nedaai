FROM python:3.11-slim AS py-base

WORKDIR /app

COPY requirements.txt requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt 

RUN adduser --disabled-password --gecos '' user && \
    mkdir /app/logs && chown -R user:user /app/logs && \
    mkdir -p /app/sessions && chown -R user:user /app/sessions

FROM py-base AS py-pod

USER user
COPY --chown=user:user . .

CMD ["sh", "-c", "python config.py && python main.py"]