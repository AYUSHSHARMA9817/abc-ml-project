#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ABC_BIN="${ABC_BIN:-$ROOT_DIR/abc}"
BLIF_DIR="${BLIF_DIR:-$ROOT_DIR/blif}"
GENLIB_FILE="${GENLIB_FILE:-$ROOT_DIR/genlib.genlib}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/results}"
MODES_STRING="${MODES:-0 1 2 3}"

read -r -a MODES_ARRAY <<< "$MODES_STRING"
if [[ ${#MODES_ARRAY[@]} -eq 0 ]]; then
    echo "No modes provided. Set MODES, for example: MODES=\"0 1 2 3\"" >&2
    exit 1
fi

mode_suffix="$(IFS=_; echo "${MODES_ARRAY[*]}")"
LOG_FILE="${1:-$OUT_DIR/blif_modes_${mode_suffix}.log}"

mkdir -p "$OUT_DIR"

if [[ ! -x "$ABC_BIN" ]]; then
    echo "Missing executable: $ABC_BIN" >&2
    exit 1
fi

if [[ ! -f "$GENLIB_FILE" ]]; then
    echo "Missing genlib file: $GENLIB_FILE" >&2
    exit 1
fi

shopt -s nullglob
blif_files=("$BLIF_DIR"/*.blif)
shopt -u nullglob

if [[ ${#blif_files[@]} -eq 0 ]]; then
    echo "No BLIF files found in $BLIF_DIR" >&2
    exit 1
fi

: > "$LOG_FILE"

for blif_file in "${blif_files[@]}"; do
    bench_name="$(basename "$blif_file")"
    for mode in "${MODES_ARRAY[@]}"; do
        echo "RUN benchmark=$bench_name g_mode=$mode file=$blif_file" | tee -a "$LOG_FILE"
        ML_MODE="$mode" "$ABC_BIN" -c "read_library $GENLIB_FILE; read_blif $blif_file; strash; map;" 2>&1 | tee -a "$LOG_FILE"
        echo | tee -a "$LOG_FILE"
    done
done

echo "Saved log to $LOG_FILE"
