#!/usr/bin/env bash

set -euo pipefail

ENV_NAME="${1:-ultimatetk}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
REQUIREMENTS_FILE="${PROJECT_ROOT}/requirements.txt"

if ! command -v conda >/dev/null 2>&1; then
  echo "Error: conda command not found. Install Miniconda/Anaconda first." >&2
  exit 1
fi

if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
  echo "Error: requirements file not found at ${REQUIREMENTS_FILE}" >&2
  exit 1
fi

if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  echo "Conda environment '${ENV_NAME}' already exists."
else
  echo "Creating conda environment '${ENV_NAME}' with Python ${PYTHON_VERSION}..."
  conda create -y -n "${ENV_NAME}" "python=${PYTHON_VERSION}" pip
fi

echo "Upgrading pip in '${ENV_NAME}'..."
conda run -n "${ENV_NAME}" python -m pip install --upgrade pip

echo "Installing pip requirements from requirements.txt..."
conda run -n "${ENV_NAME}" python -m pip install -r "${REQUIREMENTS_FILE}"

echo "Installing project in editable mode with extras [dev,pygame]..."
conda run -n "${ENV_NAME}" python -m pip install -e "${PROJECT_ROOT}[dev,pygame]"

echo
echo "Environment setup complete."
echo "Activate with: conda activate ${ENV_NAME}"
