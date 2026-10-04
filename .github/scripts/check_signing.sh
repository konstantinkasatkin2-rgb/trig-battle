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

# keytool есть в PATH у любого CI с JDK, но не обязательно на машине
# разработчика, поэтому ищем и в типовых местах.
find_keytool() {
    command -v keytool 2>/dev/null && return 0
    for c in /usr/bin/keytool /usr/libexec/java_home/bin/keytool \
             "$HOME"/.buildozer/android/platform/android-sdk/*/*/keytool \
             "/c/Program Files/Java"/*/bin/keytool.exe \
             "/c/Program Files (x86)/Java"/*/bin/keytool.exe; do
        if [ -x "$c" ]; then echo "$c"; return 0; fi
    done
    for c in /usr/lib/jvm/*/bin/keytool; do
        if [ -x "$c" ]; then echo "$c"; return 0; fi
    done
    return 0
}
KEYTOOL=$(find_keytool)

# Отпечаток сертификата через apksigner — запасной путь для подписи
# схемы v2/v3, где файла в META-INF нет.
apksigner_cert_fallback() {
    local signer
    signer=$(ls -d "$ANDROID_HOME"/build-tools/*/apksigner \
                  "$HOME"/.buildozer/android/platform/android-sdk/build-tools/*/apksigner \
                  2>/dev/null | sort -V | tail -1)
    [ -z "$signer" ] && return 0
    "$signer" verify --print-certs "$1" 2>/dev/null \
        | grep -m1 -i 'SHA-256 digest' \
        | sed 's/.*digest: *//' | tr -d ' \r' | tr 'A-F' 'a-f'
}

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
    # Отпечаток САМОГО сертификата, а не хеш всего блока подписи:
    # в блоке есть время подписи, поэтому он меняется от сборки к сборке
    # даже при одном и том же ключе.
    CERT=""
    if [ -n "$KEYTOOL" ]; then
        CERT=$("$KEYTOOL" -printcert -jarfile "$APK" 2>/dev/null \
               | grep -m1 'SHA256:' | sed 's/.*SHA256: *//' \
               | tr -d ' :\r' | tr 'A-F' 'a-f')
    else
        echo "keytool не найден — ищу через apksigner"
    fi
    [ -z "$CERT" ] && CERT=$(apksigner_cert_fallback "$APK")
else
    echo "подписи v1 нет — проверяем блок v2/v3"
    CERT=$(apksigner_cert_fallback "$APK")
    [ -z "$CERT" ] && CERT=$(python3 "$SCRIPT_DIR/find_sig_block.py" "$APK")
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
