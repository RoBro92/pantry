FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/apps/api

ARG PANTRO_UID=10001
ARG PANTRO_GID=10001

WORKDIR /app/apps/api

COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN groupadd --system --gid "${PANTRO_GID}" pantro \
    && useradd --system --uid "${PANTRO_UID}" --gid "${PANTRO_GID}" --home-dir /nonexistent --shell /usr/sbin/nologin pantro \
    && mkdir -p /var/lib/pantro/imports /var/lib/pantro/backups /var/lib/pantry/imports /var/lib/pantry/backups \
    && chown -R "${PANTRO_UID}:${PANTRO_GID}" /app /var/lib/pantro /var/lib/pantry

COPY --chown=${PANTRO_UID}:${PANTRO_GID} VERSION /app/VERSION
COPY --chown=${PANTRO_UID}:${PANTRO_GID} apps/api /app/apps/api

EXPOSE 8000

USER ${PANTRO_UID}:${PANTRO_GID}

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
