#!/usr/bin/env bash
# Сборка APK версии на pygame.
# Запускать на Linux или в WSL (на Windows buildozer не работает).
#
#   cd ready_apk
#   ./build_apk.sh              # debug-сборка
#   ./build_apk.sh release      # release-сборка (нужен ключ, см. --help)
#
# Результат: ready_apk/bin/*.apk
set -euo pipefail

cd "$(dirname "$0")"

VARIANT="${1:-debug}"

echo "==> Проверка окружения"
command -v python3 >/dev/null || { echo "Нет python3"; exit 1; }
java -version 2>&1 | head -1 || true
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) echo "Внимание: сборка идёт внутри WSL/Linux, не в Git Bash" ;;
esac

echo "==> Установка buildozer"
python3 -m pip install --upgrade --user buildozer cython

echo "==> Сборка APK ($VARIANT)"
buildozer -v android "$VARIANT" || buildozer android "$VARIANT"

echo
echo "==> Готово. APK:"
ls -lh bin/*.apk 2>/dev/null || ls -lh bin/ 2>/dev/null || true
echo
echo "Установить на телефон:"
echo "  adb install -r bin/*.apk"