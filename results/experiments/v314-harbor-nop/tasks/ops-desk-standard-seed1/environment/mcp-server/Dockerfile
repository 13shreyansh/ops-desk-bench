FROM python:3.12-slim
RUN pip install --no-cache-dir "mcp==1.27.0"
WORKDIR /srv
COPY opsdesk /srv/opsdesk
ENV PORT=8000
CMD ["python", "-m", "opsdesk.mcp_server", "streamable-http"]
