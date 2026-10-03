# ready_apk — сборка APK из версии на pygame

Здесь лежит всё, что нужно, чтобы собрать `Тригонометрический морской бой`
(версия на pygame) в `.apk`. Папка самодостаточная: `buildozer.spec` указывает
на `source.dir = .`, то есть копируется только эта папка.

```
ready_apk/
├── trig_battle_pygame.py   игра ( pygame, без numpy/matplotlib )
├── main.py                 точка входа для buildozer
├── buildozer.spec          настройки сборки
├── build_apk.sh            однокомандная сборка (Linux/WSL)
└── README.md               этот файл
```

## Почему APK нельзя собрать прямо на Windows

buildozer/python-for-android работают **только на Linux и macOS**. На Windows
нужен WSL, а в WSL дополнительно скачиваются Android SDK (~1 ГБ) и
NDK (~2 ГБ). Первая сборка занимает 30–60 минут, последующие — 3–10 минут
за счёт кэша. Поэтому ниже два рабочих способа; первый не требует ничего
кроме интернета.

## Способ 1 — GitHub Actions (рекомендуется, бесплатно)

Воркфлоу уже добавлен: `.github/workflows/build-apk-pygame.yml`.

1. Создайте репозиторий на GitHub и загрузите проект:
   ```bash
   git init
   git add .
   git commit -m "Trigonometric battleship (pygame)"
   git remote add origin https://github.com/ВАШ_ЛОГИН/trig-battle.git
   git push -u origin master
   ```
2. Откройте вкладку **Actions** → workflow **Build APK (pygame)** →
   **Run workflow**.
3. Дождитесь окончания (в первый раз ~40–70 минут: качаются SDK/NDK и
   собирается pygame из исходников).
4. Скачайте артефакт **trig-battle-pygame-apk** — внутри лежит `*.apk`.
5. Перекиньте APK на телефон и установите (нужно разрешить установку из
   неизвестных источников).

Воркфлоу срабатывает и автоматически при `push`, если изменены файлы в
`ready_apk/`.

## Способ 2 — локально через WSL (Windows)

```powershell
wsl --install          # нужна перезагрузка и права администратора
```
После перезагрузки — в Ubuntu:
```bash
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk \
  autoconf libtool pkg-config zlib1g-dev libncurses-dev libffi-dev \
  libssl-dev cmake ccache
python3 -m pip install --user buildozer cython
cd /mnt/d/trig-battle/ready_apk
./build_apk.sh
```
APK появится в `ready_apk/bin/`. Установка: `adb install -r bin/*.apk`.

> Сборка только под ARM (`arm64-v8a`, `armeabi-v7a`) — APK получается
> заметно меньше и собирается быстрее. Если нужен x86_эмулятор, уберите
> строку `android.archs` из `buildozer.spec` и пересоберите.

## Что настроено в buildozer.spec

| Параметр | Значение | Зачем |
|---|---|---|
| `requirements` | `python3,pygame,sdl2_ttf,sdl2_image,sdl2_mixer` | pygame собирается из исходников и требует SDL2-модулей; версии зафиксированы по recipe pygame |
| `p4a.bootstrap` | `sdl2` | pygame 2.x не собирается под SDL1 |
| `p4a.branch` | `develop` | актуальные рецепты python-for-android |
| `orientation` | `landscape` | игра рассчитана на альбомную ориентацию |
| `android.permissions` | пусто | игре не нужны ни сеть, ни геолокация |
| `android.archs` | `arm64-v8a, armeabi-v7a` | реальные телефоны, меньший вес и быстрее сборка |
| `android.accept_sdk_license` | `True` | нужно для CI |

## Проверка до сборки

Игра не использует ничего, чего нет на Android: только стандартная
библиотека (`math`, `random`, `os`, `sys`, `glob`) и `pygame`. `numpy`,
`matplotlib`, `kivy` не требуются — APK будет небольшим.

Локально убедиться, что всё запускается:
```bash
pip install pygame
cd ready_apk
python main.py
```

## Полезные команды

```bash
buildozer android debug            # обычная сборка
buildozer android clean            # очистить кэш сборки
buildozer android logcat           # лог с телефона
buildozer --version                # версия buildozer
```