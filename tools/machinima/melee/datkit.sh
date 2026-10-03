#!/bin/sh
# datkit.sh ARGS...: run the HSD .dat tool (builds it on first use). Needs the .NET 8 SDK (~/.dotnet or DOTNET_ROOT).
D="$(cd "$(dirname "$0")/datkit" && pwd)"
export DOTNET_ROOT="${DOTNET_ROOT:-$HOME/.dotnet}"
export PATH="$DOTNET_ROOT:$PATH"
if [ ! -x "$D/bin/rel/datkit" ] || [ -n "$(find "$D" -maxdepth 1 -name '*.cs' -newer "$D/bin/rel/datkit")" ]; then
  dotnet build -c Release -o "$D/bin/rel" "$D" >/dev/null || { dotnet build -c Release -o "$D/bin/rel" "$D" | grep -E 'error' ; exit 1; }
fi
exec "$D/bin/rel/datkit" "$@"
