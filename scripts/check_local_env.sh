#!/usr/bin/env bash
set -u

PASS=0
FAIL=0
WARN=0

print_ok() {
  echo "[OK] $1"
  PASS=$((PASS + 1))
}

print_fail() {
  echo "[FAIL] $1"
  FAIL=$((FAIL + 1))
}

print_warn() {
  echo "[WARN] $1"
  WARN=$((WARN + 1))
}

check_cmd() {
  local cmd="$1"
  local msg="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    print_ok "$msg: $(command -v "$cmd")"
    return 0
  fi
  print_fail "$msg: command not found ($cmd)"
  return 1
}

pick_qgis_process() {
  local candidates=(
    "qgis_process"
    "/Applications/QGIS.app/Contents/MacOS/bin/qgis_process"
    "/Applications/QGIS-LTR.app/Contents/MacOS/bin/qgis_process"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ "$candidate" == */* ]]; then
      if [ -x "$candidate" ]; then
        echo "$candidate"
        return 0
      fi
    else
      if command -v "$candidate" >/dev/null 2>&1; then
        command -v "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

echo "== GeoClaw-OpenAI Local Environment Check =="
echo "Date: $(date '+%Y-%m-%d %H:%M:%S %z')"
echo

check_cmd python3 "Python3"

QGIS_PROCESS_BIN=""
if QGIS_PROCESS_BIN=$(pick_qgis_process); then
  if [ "$QGIS_PROCESS_BIN" = "qgis_process" ] || [ "$QGIS_PROCESS_BIN" = "$(command -v qgis_process 2>/dev/null || true)" ]; then
    print_ok "qgis_process: $QGIS_PROCESS_BIN"
  else
    print_warn "qgis_process not in PATH, using detected path: $QGIS_PROCESS_BIN"
  fi

  QP_VER=$("$QGIS_PROCESS_BIN" --version 2>&1 | head -n 1)
  if [ -n "$QP_VER" ]; then
    print_ok "qgis_process version: $QP_VER"
  else
    print_warn "qgis_process exists but version output is empty"
  fi

  if "$QGIS_PROCESS_BIN" list >/dev/null 2>&1; then
    print_ok "qgis_process algorithm list callable"
  else
    print_warn "qgis_process list failed; check QGIS runtime config"
  fi
else
  print_fail "qgis_process not found (PATH or common macOS app locations)"
fi

if check_cmd gdalinfo "GDAL"; then
  GDAL_VER=$(gdalinfo --version 2>&1 | head -n 1)
  print_ok "GDAL version: $GDAL_VER"
fi

if check_cmd ogrinfo "OGR"; then
  OGR_VER=$(ogrinfo --version 2>&1 | head -n 1)
  print_ok "OGR version: $OGR_VER"
fi

if check_cmd proj "PROJ"; then
  PROJ_VER=$(proj 2>&1 | head -n 1)
  print_ok "PROJ version: $PROJ_VER"
fi

echo
if command -v python3 >/dev/null 2>&1; then
  echo "-- PyQGIS check --"
  if python3 scripts/check_pyqgis.py; then
    print_ok "PyQGIS import and init"
  else
    RC=$?
    if [ "$RC" -eq 2 ]; then
      print_warn "PyQGIS unavailable in current Python environment"
    else
      print_fail "PyQGIS check script failed with code $RC"
    fi
  fi
fi

if [ -x "/Applications/QGIS.app/Contents/MacOS/bin/python3" ]; then
  echo
  echo "-- PyQGIS check via QGIS bundled python --"
  if /Applications/QGIS.app/Contents/MacOS/bin/python3 scripts/check_pyqgis.py; then
    print_ok "QGIS bundled python can import PyQGIS"
  else
    RC=$?
    if [ "$RC" -eq 2 ]; then
      print_warn "QGIS bundled python cannot import PyQGIS"
    else
      print_fail "QGIS bundled python check failed with code $RC"
    fi
  fi
fi

echo
TOTAL=$((PASS + FAIL + WARN))
echo "== Summary =="
echo "Checks: $TOTAL | PASS: $PASS | WARN: $WARN | FAIL: $FAIL"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
