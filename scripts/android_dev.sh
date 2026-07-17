#!/usr/bin/env bash
# Android クライアントのビルド・インストール・起動を自動化する。
# .tooling/ に JDK / Android SDK がある場合は自動で使う。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_DIR="$ROOT/clients/android"
TOOLING="$ROOT/.tooling"
APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"

usage() {
  cat <<'EOF'
Usage: scripts/android_dev.sh [options] [gradle-args...]

Options:
  --test          core ユニットテストのみ（:core:test）
  --install       ビルド後に adb install
  --launch        インストール後に MainActivity を起動（--install を含む）
  --port PORT     API ポート（未指定時は 8000 → 8001 の順で稼働中を自動検出）
  --api-url URL   BuildConfig.PMB_API_BASE_URL を直接指定（--port より優先）
  -h, --help      このヘルプ

環境変数:
  JAVA_HOME / ANDROID_HOME  … 未設定時は .tooling/ を参照
  PMB_API_PORT              … --port と同義

例:
  scripts/android_dev.sh --launch
  scripts/android_dev.sh --test
  scripts/android_dev.sh --port 8001 --install
EOF
}

resolve_java_home() {
  if [[ -n "${JAVA_HOME:-}" && -x "${JAVA_HOME}/bin/java" ]]; then
    return
  fi
  if [[ -d "$TOOLING/jdk" && -x "$TOOLING/jdk/bin/java" ]]; then
    export JAVA_HOME="$TOOLING/jdk"
    return
  fi
  echo "[android_dev] ERROR: JDK 17 が見つかりません。" >&2
  echo "  .tooling/jdk を用意するか JAVA_HOME を設定してください。" >&2
  exit 1
}

resolve_android_home() {
  if [[ -n "${ANDROID_HOME:-}" && -d "$ANDROID_HOME/platform-tools" ]]; then
    return
  fi
  if [[ -d "$TOOLING/android-sdk" ]]; then
    export ANDROID_HOME="$TOOLING/android-sdk"
    return
  fi
  echo "[android_dev] ERROR: Android SDK が見つかりません。" >&2
  echo "  .tooling/android-sdk を用意するか ANDROID_HOME を設定してください。" >&2
  exit 1
}

ensure_local_properties() {
  local props="$ANDROID_DIR/local.properties"
  if [[ ! -f "$props" ]]; then
    echo "sdk.dir=$ANDROID_HOME" >"$props"
    echo "[android_dev] wrote $props"
  fi
}

detect_api_port() {
  if [[ -n "${PMB_API_PORT:-}" ]]; then
    echo "$PMB_API_PORT"
    return
  fi
  python3 - <<'PY'
import urllib.request

for port in (8000, 8001):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/docs", timeout=1) as resp:
            if resp.status == 200:
                print(port)
                break
    except OSError:
        pass
else:
    print(8000)
PY
}

DO_TEST=0
DO_INSTALL=0
DO_LAUNCH=0
API_URL=""
API_PORT=""
GRADLE_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --test)
      DO_TEST=1
      shift
      ;;
    --install)
      DO_INSTALL=1
      shift
      ;;
    --launch)
      DO_INSTALL=1
      DO_LAUNCH=1
      shift
      ;;
    --port)
      API_PORT="${2:?--port requires a value}"
      shift 2
      ;;
    --api-url)
      API_URL="${2:?--api-url requires a value}"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      GRADLE_ARGS+=("$1")
      shift
      ;;
  esac
done

resolve_java_home
resolve_android_home
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"
ensure_local_properties

cd "$ANDROID_DIR"

if [[ "$DO_TEST" -eq 1 ]]; then
  echo "[android_dev] JAVA_HOME=$JAVA_HOME"
  echo "[android_dev] ANDROID_HOME=$ANDROID_HOME"
  ./gradlew :core:test --console=plain "${GRADLE_ARGS[@]}"
  exit 0
fi

if [[ -z "$API_URL" ]]; then
  if [[ -z "$API_PORT" ]]; then
    API_PORT="$(detect_api_port)"
  fi
  API_URL="http://10.0.2.2:${API_PORT}"
fi

echo "[android_dev] JAVA_HOME=$JAVA_HOME"
echo "[android_dev] ANDROID_HOME=$ANDROID_HOME"
echo "[android_dev] PMB_API_BASE_URL=$API_URL"

./gradlew :app:assembleDebug -PpmbApiBaseUrl="$API_URL" --console=plain "${GRADLE_ARGS[@]}"

if [[ "$DO_INSTALL" -eq 1 ]]; then
  if ! command -v adb >/dev/null 2>&1; then
    echo "[android_dev] ERROR: adb が見つかりません（ANDROID_HOME/platform-tools）" >&2
    exit 1
  fi
  device_count="$(adb devices | awk 'NR>1 && $2=="device" {c++} END {print c+0}')"
  if [[ "$device_count" -eq 0 ]]; then
    echo "[android_dev] ERROR: 接続中の Android デバイス/エミュレータがありません" >&2
    exit 1
  fi
  adb install -r "$APK"
  echo "[android_dev] installed $APK"
fi

if [[ "$DO_LAUNCH" -eq 1 ]]; then
  adb shell am start -n com.photomecha.battle/.MainActivity
  echo "[android_dev] launched MainActivity"
fi
