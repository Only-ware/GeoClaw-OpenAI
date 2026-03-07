#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
export COPYFILE_DISABLE=1

cd "${ROOT_DIR}"

clean_metadata_artifacts() {
  # Clean macOS metadata artifacts that can confuse pip distribution discovery.
  find "${ROOT_DIR}/src" -maxdepth 1 -type f -name '._*.egg-info' -delete
}

clean_metadata_artifacts

USER_BIN="$(${PYTHON_BIN} - <<'PY'
import site
print(site.USER_BASE + '/bin')
PY
)"

GEOCLAW_OPENAI_PATH="${USER_BIN}/geoclaw-openai"
INSTALL_MODE="pip"

install_via_pip() {
  set +e
  "${PYTHON_BIN}" -m pip install --user --break-system-packages -e .
  local rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then
    return 0
  fi

  echo "Retrying install with --no-build-isolation ..."
  set +e
  "${PYTHON_BIN}" -m pip install --user --break-system-packages --no-build-isolation -e .
  rc=$?
  set -e
  return "$rc"
}

install_wrapper_fallback() {
  echo "pip editable install failed, creating local launcher fallback ..."
  if ! "${PYTHON_BIN}" - <<'PY'
import yaml  # noqa: F401
PY
  then
    echo "[ERROR] Missing dependency: pyyaml. Please install it and rerun."
    exit 1
  fi

  mkdir -p "${USER_BIN}"
  cat > "${GEOCLAW_OPENAI_PATH}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="\${PYTHON:-python3}"
export PYTHONPATH="${ROOT_DIR}/src:\${PYTHONPATH:-}"

exec "\${PYTHON_BIN}" -m geoclaw_qgis.cli.main "\$@"
EOF
  chmod +x "${GEOCLAW_OPENAI_PATH}"
  INSTALL_MODE="launcher"
}

if ! install_via_pip; then
  install_wrapper_fallback
fi

clean_metadata_artifacts

echo
if [ -x "${GEOCLAW_OPENAI_PATH}" ]; then
  echo "Installed geoclaw-openai at: ${GEOCLAW_OPENAI_PATH} (mode=${INSTALL_MODE})"
else
  echo "geoclaw-openai binary not found at ${GEOCLAW_OPENAI_PATH}, check pip output."
fi

echo
if [[ ":$PATH:" != *":${USER_BIN}:"* ]]; then
  echo "Add user bin to PATH (zsh):"
  echo "  echo 'export PATH=\"${USER_BIN}:\$PATH\"' >> ~/.zshrc"
  echo "  source ~/.zshrc"
fi

echo
cat <<'TXT'
Next steps:
1) geoclaw-openai onboard
2) source ~/.geoclaw-openai/env.sh
3) geoclaw-openai skill -- --list
TXT
