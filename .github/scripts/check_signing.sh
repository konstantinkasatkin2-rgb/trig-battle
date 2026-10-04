#!/usr/bin/env bash
# Проверка подписи APK: ключ подписи не должен меняться от сборки к сборке.
#
# Зачем: пока ключ меняется, Android требует сначала удалить старую версию
# перед установкой новой, а Google Play считает приложение подозрительным.
# Сборка, которая сменила ключ, — это регресс, и его надо ловить сразу.
#
# Подпись бывает двух видов:
#   * v1 (JAR) — файл в META-INF (*.RSA / *.DSA / *.EC);
#   * v2/v3 — служебный блок перед центральным каталогом, магия
#     "APK Sig Block 42".
# Принимаем обе схемы, берём отпечаток того, что нашли, и сравниваем его
# с expected_cert.txt.
set -uo pipefail

# каталог этого скрипта — нужен, чтобы найти find_sig_block.py
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APK="${1:-}"
if [ -z "$APK" ]; then
    APK=$(ls -1 dist/*.apk 2>/dev/null | head -1)
fi
if [ -z "$APK" ] || [ ! -f "$APK" ]; then
    echo "ОШИБКА: APK не найден (укажите путь аргументом)"
    exit 1
fi
echo "APK: $APK"

if ! unzip -tq "$APK" >/dev/null 2>&1; then
    echo "ОШИБКА: APK повреждён (не проходит проверку целостности)"
    exit 1
fi

SIG=$(unzip -Z1 "$APK" | grep -E '^META-INF/.*\.(RSA|DSA|EC)$' | head -1)
if [ -n "$SIG" ]; then
    echo "подпись v1: $SIG"
    CERT=$(unzip -p "$APK" "$SIG" | sha256sum | cut -d' ' -f1)
else
    echo "подписи v1 нет — проверяем блок v2/v3"
    CERT=$(python3 "$SCRIPT_DIR/find_sig_block.py" "$APK")
fi

if [ -z "$CERT" ]; then
    echo "ОШИБКА: APK вообще не подписан — Android его не установит."
    echo "проверьте переменные P4A_RELEASE_KEYSTORE* при сборке."
    exit 1
fi
echo "хеш сертификата: $CERT"

EXPECTED="${EXPECTED_CERT_FILE:-expected_cert.txt}"
if [ ! -f "$EXPECTED" ]; then
    printf '%s\n' "$CERT" > "$EXPECTED"
    echo "сохранён в $EXPECTED; следующие сборки обязаны им подписываться,"
    echo "иначе обновление поверх старой версии перестанет работать."
else
    if grep -qF "$CERT" "$EXPECTED"; then
        echo "подпись совпадает с предыдущими сборками"
    else
        echo "ОШИБКА: APK подписан другим ключом, чем предыдущие сборки."
        echo "пользователь не сможет обновиться поверх старой версии."
        echo "ожидался: $(cat "$EXPECTED")"
        exit 1
    fi
fi
