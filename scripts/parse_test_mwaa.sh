#!/usr/bin/env bash
# =============================================================================
# parse_test_mwaa.sh  —  one-command reproduction of the ADR-005 Condition P5 gate
# =============================================================================
# PURPOSE
#   Parse-test airflow/dags/ against an MWAA-FAITHFUL Airflow runtime
#   (Apache Airflow 2.10.3 / Python 3.11 via aws-mwaa-local-runner), the way the
#   AWS MWAA service actually loads DAGs — NOT the local .venv (which runs an
#   unpinned Airflow 3.x / py3.12, the WRONG target: `default_args={"sla": ...}`
#   was removed in Airflow 3.0, so a 3.x venv parse is a false signal).
#   This is the gate that must pass before any MWAA spike (ADR-005 P5, P5-before-P4).
#
# COST / SAFETY
#   $0 — LOCAL ONLY. aws-mwaa-local-runner is a Docker image running MWAA's base
#   on localhost; it never calls an AWS API. No AWS creds are read: this script
#   does NOT mount .env / ~/.aws into the container. A ONE-SHOT DagBag import is
#   run (no long-lived webserver/scheduler). The DAGs dir is mounted READ-ONLY.
#   Disk budget: ~5 GB for the image + layers; first build ~26 min (cached after).
#
# MARIADB-MIRROR GOTCHA (read this if the BUILD step fails)
#   The upstream aws-mwaa-local-runner `docker/script/bootstrap.sh` wgets MariaDB
#   RPMs from `mirror.mariadb.org`, which is DNS-unresolvable in some sandboxes
#   (incl. this Codespace). WORKAROUND (already proven 2026-06-18): in the CLONED
#   runner copy only, replace the mirror host with the archive host:
#       sed -i 's#mirror.mariadb.org#archive.mariadb.org#g' \
#         "$RUNNER_DIR"/docker/script/bootstrap.sh
#   We patch the /tmp clone, never this repo. This script applies the patch
#   automatically before building if the image is missing.
#
# USAGE
#   bash scripts/parse_test_mwaa.sh          # build-if-missing, then parse
#   AIRFLOW_VERSION=2.10.3 bash scripts/parse_test_mwaa.sh
#
# EXIT
#   0 = PASS (zero import errors)   non-zero = FAIL (import error or infra error)
# =============================================================================
set -euo pipefail

# ---- Parameters (override via env) ------------------------------------------
AIRFLOW_VERSION="${AIRFLOW_VERSION:-2.10.3}"
# aws-mwaa-local-runner branch matching the Airflow version (e.g. v2.10.3).
RUNNER_BRANCH="${RUNNER_BRANCH:-v${AIRFLOW_VERSION}}"
RUNNER_DIR="${RUNNER_DIR:-/tmp/aws-mwaa-local-runner}"
RUNNER_REPO="${RUNNER_REPO:-https://github.com/aws/aws-mwaa-local-runner.git}"
# Image tag uses underscores per upstream convention: 2.10.3 -> 2_10_3
IMAGE_TAG="${IMAGE_TAG:-amazon/mwaa-local:${AIRFLOW_VERSION//./_}}"

# Repo root = parent of scripts/ (this file lives at <repo>/scripts/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DAGS_DIR="$REPO_ROOT/airflow/dags"

echo "=== ADR-005 P5 parse gate ==="
echo "  Airflow version : $AIRFLOW_VERSION"
echo "  Runner branch   : $RUNNER_BRANCH"
echo "  Image           : $IMAGE_TAG"
echo "  DAGs dir (ro)   : $DAGS_DIR"
echo

# ---- 0. Sanity ---------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "FAIL: docker not found on PATH." >&2
  exit 2
fi
if [[ ! -d "$DAGS_DIR" ]]; then
  echo "FAIL: DAGs dir not found: $DAGS_DIR" >&2
  exit 2
fi

# ---- 1. Ensure the aws-mwaa-local-runner clone at the pinned branch ----------
if [[ ! -d "$RUNNER_DIR/.git" ]]; then
  echo "[1/3] Cloning aws-mwaa-local-runner ($RUNNER_BRANCH) -> $RUNNER_DIR"
  git clone --branch "$RUNNER_BRANCH" --depth 1 "$RUNNER_REPO" "$RUNNER_DIR"
else
  echo "[1/3] Reusing existing runner clone at $RUNNER_DIR"
fi

# ---- 2. Ensure the image exists (build if missing) ---------------------------
if docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
  echo "[2/3] Image $IMAGE_TAG already present — skipping ~26-min build."
else
  echo "[2/3] Image $IMAGE_TAG missing — patching MariaDB mirror + building."
  BOOTSTRAP="$RUNNER_DIR/docker/script/bootstrap.sh"
  if [[ -f "$BOOTSTRAP" ]]; then
    # Apply the archive.mariadb.org workaround to the /tmp clone ONLY.
    sed -i 's#mirror.mariadb.org#archive.mariadb.org#g' "$BOOTSTRAP"
  else
    echo "WARN: $BOOTSTRAP not found — cannot pre-apply MariaDB mirror patch." >&2
  fi
  # Upstream build helper; falls back to a direct docker build if absent.
  if [[ -x "$RUNNER_DIR/mwaa-local-env" ]]; then
    ( cd "$RUNNER_DIR" && ./mwaa-local-env build-image )
  else
    docker build -t "$IMAGE_TAG" "$RUNNER_DIR/docker"
  fi
fi

# ---- 3. One-shot DagBag import (read-only mount, no creds) --------------------
echo "[3/3] Running one-shot DagBag import (no webserver, read-only DAGs)..."
set +e
docker run --rm \
  -v "$DAGS_DIR":/usr/local/airflow/dags:ro \
  -e DAGS_FOLDER=/usr/local/airflow/dags \
  --entrypoint python3 \
  "$IMAGE_TAG" -c '
import sys
from airflow.models.dagbag import DagBag
db = DagBag("/usr/local/airflow/dags", include_examples=False)
print("DAGS:", sorted(db.dag_ids))
print("IMPORT_ERRORS:", db.import_errors)
sys.exit(1 if db.import_errors else 0)
'
rc=$?
set -e

echo
if [[ $rc -eq 0 ]]; then
  echo "PASS: airflow/dags parsed clean on MWAA Airflow $AIRFLOW_VERSION (zero import errors). [ADR-005 P5 GREEN]"
else
  echo "FAIL: import error(s) above on MWAA Airflow $AIRFLOW_VERSION — see IMPORT_ERRORS. [ADR-005 P5 RED]"
fi
exit $rc
