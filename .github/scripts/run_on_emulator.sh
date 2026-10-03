#!/usr/bin/env bash
# Запуск APK на эмуляторе Android и сбор диагностики.
#
# Зачем: приложение падало с пустым экраном, а причина была видна только
# в logcat. Этот скрипт запускает APK на эмуляторе, снимает скриншот,
# проверяет, жив ли процесс, и выгружает журналы — причину падения видно
# в логе прогона без телефона и без adb.
set -x

PKG=org.kasatkin.trigbattle
ACT=org.kivy.android.PythonActivity
OUT=out
APK=$(ls -1 apk/*.apk 2>/dev/null | head -1)

mkdir -p "$OUT"
if [ -z "$APK" ]; then
    echo "!! APK не найден в apk/" | tee "$OUT/result.txt"
    exit 1
fi
echo "APK: $APK" | tee "$OUT/result.txt"

adb wait-for-device
adb root >/dev/null 2>&1 || true
sleep 5
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true

echo "=== установка"
adb install -r -t "$APK" 2>&1 | tee "$OUT/install.txt"
adb logcat -c

echo "=== запуск activity"
adb shell am start -W -n "$PKG/$ACT" 2>&1 | tee "$OUT/start.txt"
sleep 45

echo "=== жив ли процесс (пусто = умер)"
adb shell pidof "$PKG" | tr -d '\r' > "$OUT/pid.txt" || true
cat "$OUT/pid.txt"
if [ -s "$OUT/pid.txt" ]; then
    echo "ИТОГ: процесс жив" | tee -a "$OUT/result.txt"
else
    echo "ИТОГ: процесс НЕ жив (приложение упало)" | tee -a "$OUT/result.txt"
fi

echo "=== что сейчас на экране / чем закончилась activity"
adb shell dumpsys activity activities 2>/dev/null \
    | grep -aiE "mResumedActivity|topResumedActivity|mFocusedApp" \
    > "$OUT/activity.txt" || true
cat "$OUT/activity.txt"

adb exec-out screencap -p > "$OUT/screen.png" 2>/dev/null || true

adb logcat -d -v time > "$OUT/logcat.txt" 2>/dev/null || true
adb logcat -d -b crash -v time > "$OUT/logcat-crash.txt" 2>/dev/null || true

# наш собственный журнал: сначала внешний каталог, потом internal (run-as)
adb shell cat "/sdcard/Android/data/$PKG/files/trigbattle.log" \
    > "$OUT/trigbattle.log" 2>/dev/null || true
if [ ! -s "$OUT/trigbattle.log" ]; then
    adb shell run-as "$PKG" cat files/trigbattle.log \
        > "$OUT/trigbattle.log" 2>/dev/null || true
fi

echo "===================== ИТОГ"
cat "$OUT/result.txt"
echo "===================== НАШ ЖУРНАЛ (trigbattle.log)"
if [ -s "$OUT/trigbattle.log" ]; then
    cat "$OUT/trigbattle.log"
else
    echo "(пусто — приложение не дошло до нашего кода)"
fi
echo "===================== ЛОГИ ПРИЛОЖЕНИЯ И SDL"
grep -aiE "trigbattle|pythonforandroid|kivy|pygame|SDL|PythonActivity" \
    "$OUT/logcat.txt" | tail -60 || true
echo "===================== ПАДЕНИЯ (AndroidRuntime / crash buffer)"
cat "$OUT/logcat-crash.txt" | tail -40
grep -aE "FATAL|AndroidRuntime|Died|signal|Force finishing|ANR in" \
    "$OUT/logcat.txt" | tail -40 || true
