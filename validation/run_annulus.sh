#!/usr/bin/env bash
#
# Reproduce the annular Poiseuille CFD validation from a clean checkout.
#
#   validation/run_annulus.sh
#
# Environment overrides:
#   FOAM_BASHRC  path to OpenFOAM etc/bashrc
#                (default: ~/opt/OpenFOAM/OpenFOAM-v2606/etc/bashrc)
#   PYTHON       python interpreter with numpy
#                (default: ~/data/venvs/sgk-mini/bin/python if present,
#                 else python3)
#
set -eo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE="$REPO/validation/openfoam/annulus_cyclic"

FOAM_BASHRC="${FOAM_BASHRC:-$HOME/opt/OpenFOAM/OpenFOAM-v2606/etc/bashrc}"
if [ ! -f "$FOAM_BASHRC" ]; then
    echo "OpenFOAM bashrc not found: $FOAM_BASHRC" >&2
    echo "Set FOAM_BASHRC to your OpenFOAM etc/bashrc." >&2
    exit 1
fi
# shellcheck disable=SC1090
set +e
source "$FOAM_BASHRC"
set -e

if [ -n "${PYTHON:-}" ]; then
    :
elif [ -x "$HOME/data/venvs/sgk-mini/bin/python" ]; then
    PYTHON="$HOME/data/venvs/sgk-mini/bin/python"
else
    PYTHON="python3"
fi

if [ ! -f "$REPO/output/hollow-cylinder.physical-case.json" ]; then
    echo "Benchmark output/hollow-cylinder.physical-case.json missing." >&2
    echo "Run the geometry stage first:" >&2
    echo "  dotnet run --project src/SGK.Geometry/ -- --auto-exit" >&2
    exit 1
fi

echo "== blockMesh =="
( cd "$CASE" && blockMesh > log.blockMesh 2>&1 )
echo "== simpleFoam =="
( cd "$CASE" && simpleFoam > log.simpleFoam 2>&1 )
echo "== writeCellCentres =="
( cd "$CASE" && postProcess -func writeCellCentres -latestTime > log.writeCellCentres 2>&1 )
echo "== validate =="
"$PYTHON" "$REPO/validation/validate_annulus.py" "$@"
echo "== figures =="
"$PYTHON" "$REPO/validation/plot_annulus.py"
