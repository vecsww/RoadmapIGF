"""Build-time patch: insert register_account_tools(mcp) into server.py right after
register_tools(mcp). Idempotent; fails the build if the anchor line is missing."""

import sys

PATH = "/app/src/server.py"

src = open(PATH, encoding="utf-8").read()
if "register_account_tools" in src:
    print("server.py already patched")
    sys.exit(0)

out = []
patched = False
for line in src.splitlines(keepends=True):
    out.append(line)
    if line.strip() == "register_tools(mcp)":
        indent = line[: len(line) - len(line.lstrip())]
        out.append(indent + "from src.tools.account_actions import register_account_tools\n")
        out.append(indent + "register_account_tools(mcp)\n")
        patched = True

if not patched:
    print("ERROR: anchor line 'register_tools(mcp)' not found in server.py", file=sys.stderr)
    sys.exit(1)

open(PATH, "w", encoding="utf-8").write("".join(out))
print("patched server.py: register_account_tools(mcp) inserted")
