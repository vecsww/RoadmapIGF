# Derived image: same base (pinned by digest) + dedicated account-action tools.
# Reuses the exact deployed environment (Telethon 1.43.2, all deps) — only adds code.
# Patch must run as root: /app/src/server.py is root-owned in the base image; we
# chown the touched files back to appuser and drop privileges before runtime.
FROM ghcr.io/leshchenko1979/fast-mcp-telegram@sha256:293d3a6b6a181fd22cdbf68a7d50164357213c5558544e54ec5df6b494a71a4f
USER root
COPY account_actions.py /app/src/tools/account_actions.py
COPY patch_server.py /tmp/patch_server.py
RUN python /tmp/patch_server.py && rm -f /tmp/patch_server.py && python -c "import ast; ast.parse(open('/app/src/tools/account_actions.py').read())" && grep -q 'register_account_tools(mcp)' /app/src/server.py && chown appuser:appuser /app/src/tools/account_actions.py /app/src/server.py && echo 'fork build patch ok'
USER appuser
