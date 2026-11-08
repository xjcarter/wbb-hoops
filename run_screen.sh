#!/usr/bin/env bash
#
# WBB Screen — daily runner (snapshot + master append)
# ------------------------------------------------
# Runs once, produces an immutable dated snapshot, and appends the same
# rows to tracking_master.csv. Includes a failure guard.
#
# Usage:  ./run_screen.sh [days]
#         days defaults to 30
#
# Intended to be called from cron twice daily.

set -euo pipefail

# ---- Config ---------------------------------------------------------------
PROJECT_DIR="/wbb-screen"
ARCHIVE_DIR="${PROJECT_DIR}/archive"
MASTER_FILE="${PROJECT_DIR}/tracking_master.csv"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
SCRIPT="${PROJECT_DIR}/wbb_ranked_next_home.py"
DAYS="${1:-30}"
RUN_LABEL="${2:-run}"   # "am" or "pm" passed by cron

# ---- Sanity checks --------------------------------------------------------
if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[FATAL] Python venv not found at ${PYTHON_BIN}" >&2
  exit 1
fi
if [[ ! -f "${SCRIPT}" ]]; then
  echo "[FATAL] Script not found at ${SCRIPT}" >&2
  exit 1
fi

mkdir -p "${ARCHIVE_DIR}"

# ---- Timestamps -----------------------------------------------------------
TODAY_UTC="$(date -u +%Y-%m-%d)"
TIME_UTC="$(date -u +%H%M%S)"
SNAPSHOT="${ARCHIVE_DIR}/${TODAY_UTC}_${RUN_LABEL}_${TIME_UTC}.csv"
LOG="${ARCHIVE_DIR}/${TODAY_UTC}_${RUN_LABEL}_${TIME_UTC}.log"

# ---- Run the screen once --------------------------------------------------
cd "${PROJECT_DIR}"

if ! "${PYTHON_BIN}" "${SCRIPT}" --days "${DAYS}" --csv --csv-path "${SNAPSHOT}" \
      > "${LOG}" 2>&1; then
  echo "[ERROR] Screen run failed; see ${LOG}" >&2
  # Append a failure marker to the master log for visibility
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) FAILED ${RUN_LABEL} (log: ${LOG})" \
    >> "${ARCHIVE_DIR}/run_failures.log"
  exit 1
fi

# ---- Sanity: snapshot must exist and have >1 line -------------------------
LINES=$(wc -l < "${SNAPSHOT}" 2>/dev/null || echo 0)
if [[ "${LINES}" -le 1 ]]; then
  echo "[ERROR] Snapshot has no data rows: ${SNAPSHOT}" >&2
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) EMPTY ${RUN_LABEL} (snapshot: ${SNAPSHOT})" \
    >> "${ARCHIVE_DIR}/run_failures.log"
  exit 1
fi

# ---- Append to master (skip header if master already exists) --------------
if [[ ! -f "${MASTER_FILE}" ]]; then
  cp "${SNAPSHOT}" "${MASTER_FILE}"
else
  tail -n +2 "${SNAPSHOT}" >> "${MASTER_FILE}"
fi

# ---- Done -----------------------------------------------------------------
echo "[OK] ${RUN_LABEL} run: ${SNAPSHOT} (${LINES} lines, incl. header)"
echo "[OK] Master now has $(wc -l < "${MASTER_FILE}") lines"
