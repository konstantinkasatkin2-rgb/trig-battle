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

# buildozer называет файл package-version-arch-debug.apk — переименовываем
# в понятный вид <package>_<version>.apk
NAME=$(grep -E '^package\.name' buildozer.spec | head -1 | cut -d= -f2 | tr -d ' ')
VER=$(grep -E '^version' buildozer.spec | head -1 | cut -d= -f2 | tr -d ' ')
mkdir -p dist
if ls bin/*.apk >/dev/null 2>&1; then
  cp "$(ls bin/*.apk | head -1)" "dist/${NAME}_${VER}.apk"
  echo "Итоговый файл: dist/${NAME}_${VER}.apk"
  ls -lh "dist/${NAME}_${VER}.apk"
else
  echo "ВНИМАНИЕ: APK не найден в bin/"
fi

echo
echo "Установить на телефон:"
echo "  adb install -r dist/${NAME}_${VER}.apk"