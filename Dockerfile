# Reuse the existing demo's CPU embedding runtime on the shared VM.
FROM us-east4-docker.pkg.dev/central-beach-194106/valuewholesale/valuewholesale-shopping-agent:latest
USER root
WORKDIR /app
RUN uv pip install --python /app/.venv/bin/python --no-cache google-genai==2.24.0 redis-agent-memory==0.2.0 redisvl==0.23.0
COPY valuetravel /app/valuetravel
COPY scripts /app/scripts
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
CMD ["/app/.venv/bin/uvicorn","valuetravel.api:app","--host","0.0.0.0","--port","8080"]
