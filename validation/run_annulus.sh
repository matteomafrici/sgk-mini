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
#   CASE_DIR     OpenFOAM case to run
#                (default: validation/openfoam/annulus_cyclic)
#   BENCHMARK    physical record to validate against
#                (default: output/hollow-cylinder.physical-case.json)
#
# Extra arguments are passed to validate_annulus.py, e.g. --check.
#
set -eo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE="${CASE_DIR:-$REPO/validation/openfoam/annulus_cyclic}"
BENCH="${BENCHMARK:-$REPO/output/hollow-cylinder.physical-case.json}"

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

if [ ! -f "$BENCH" ]; then
    echo "Benchmark missing: $BENCH" >&2
    echo "Run the geometry stage first:" >&2
    echo "  dotnet run --project src/SGK.Geometry/ -- --auto-exit" >&2
    exit 1
fi

echo "== check inputs =="
"$PYTHON" "$REPO/validation/validate_annulus.py" \
    --case "$CASE" --benchmark "$BENCH" --check-inputs

echo "== clean stale artifacts =="
# A stale time directory from a previous mesh would be picked up as the latest
# result. Remove everything except the initial condition and rebuild the mesh.
find "$CASE" -maxdepth 1 -type d -regex '.*/[0-9.]+' ! -name 0 -exec rm -rf {} +
rm -rf "$CASE/constant/polyMesh" "$CASE/validation.json"

echo "== blockMesh =="
( cd "$CASE" && blockMesh > log.blockMesh 2>&1 )

echo "== checkMesh =="
( cd "$CASE" && checkMesh -allGeometry -allTopology > log.checkMesh 2>&1 )

echo "== simpleFoam =="
( cd "$CASE" && simpleFoam > log.simpleFoam 2>&1 )

echo "== writeCellCentres =="
( cd "$CASE" && postProcess -func writeCellCentres -latestTime > log.writeCellCentres 2>&1 )

echo "== writeCellVolumes =="
( cd "$CASE" && postProcess -func writeCellVolumes -latestTime > log.writeCellVolumes 2>&1 )

echo "== patch fluxes =="
( cd "$CASE" && {
    postProcess -func "flowRatePatch(name=cyclicLeft)" -latestTime
    postProcess -func "flowRatePatch(name=cyclicRight)" -latestTime
} > log.flux 2>&1 )

echo "== validate =="
"$PYTHON" "$REPO/validation/validate_annulus.py" \
    --case "$CASE" --benchmark "$BENCH" --json "$CASE/validation.json" "$@"

if [ "${SKIP_FIGURES:-0}" != "1" ]; then
    echo "== figures =="
    "$PYTHON" "$REPO/validation/plot_annulus.py" \
        --case "$CASE" --benchmark "$BENCH" --report "$CASE/validation.json"
fi
