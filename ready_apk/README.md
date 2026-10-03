# ready_apk — сборка APK из версии на pygame

Здесь лежит всё, что нужно, чтобы собрать `Тригонометрический морской бой`
(версия на pygame) в `.apk`. Папка самодостаточная: `buildozer.spec` указывает
на `source.dir = .`, то есть копируется только эта папка.

```
ready_apk/
├── trig_battle_pygame.py   игра ( pygame, без numpy/matplotlib )
├── main.py                 точка входа для buildozer
├── buildozer.spec          настройки сборки
├── p4a-recipes/pygame/     локальный рецепт p4a (pygame 2.1.3 вместо 2.1.0)
├── p4a-recipes/trigbattle_src/
│                           рецепт, который кладёт код игры в APK
├── setup.py                запасной путь доставки кода (установка в site-packages)
├── tools/verify_apk.py     проверка, что игра реально попала в APK
├── tools/verify_elf.py     проверка линковки .so (ловит падение dlopen)
├── tools/test_recipe.py    проверка рецепта (секунда, без сборки APK)
├── build_apk.sh            однокомандная сборка (Linux/WSL)
└── README.md               этот файл
```

## Как код игры попадает в APK — и почему раньше не попадал

Это главный грабли проекта, поэтому описано подробно.

Android запускает лаунчер, он делает `import main`. Если модуля `main` нет,
процесс умирает мгновенно, без окна и без сообщения — приложение «не
открывается» на любом телефоне. Сборка при этом **успешна**: APK получается,
подписывается, зелёный статус, ноль ошибок. В версии 0.2.0 внутри было
345 файлов (`modules/`, `site-packages/pygame`, `stdlib.zip`) и ни одного
файла игры.

Доставить код можно двумя путями, и оба оказались ненадёжными:

1. **Копирование по шаблонам.** В p4a v2024.01.21 такого механизма нет.
2. **Установка через `setup.py`.** Buildozer читает опцию `p4a.setup_py` и
   без неё передаёт p4a флаг `--ignore-setup-py`, при котором проект не
   устанавливается вообще. Если же опцию включить, p4a всё равно ничего не
   находит: buildozer копирует исходники в приватный каталог **на 16 секунд
   позже**, чем p4a проверяет наличие `setup.py`, и пишет
   `No Python modules and no setup.py to process, skipping` — после чего
   собирает бандл всё равно.

Поэтому код игры доставляет **рецепт `p4a-recipes/trigbattle_src`**: он
срабатывает на этапе сборки рецептов, то есть до сборки бандла, и читает
`main.py` / `trig_battle_pygame.py` прямо из рабочей копии репозитория
(`--local-recipes` указывает на каталог с рецептом, мимо приватной копии).
Файлы кладутся в `site-packages` рядом с pygame. Если файлов нет, рецепт
**падает**, а не собирает мёртвый APK.

Тонкости рецепта, на которые уходит время (обе уже учтены в коде):

* модуль обязан отдавать объект с именем `recipe` — p4a делает `mod.recipe`,
  иначе `AttributeError: has no attribute 'recipe'`;
* `prepare_build_dir` p4a вызывает со **строкой** (`arch.arch`), а
  `build_arch` — с **объектом** `Arch`, поэтому рецепт принимает обе формы.

Обе ошибки ловятся за секунду проверкой `python tools/test_recipe.py`, которая
запускается в CI **перед** девятиминутной сборкой.

## Второй грабли: pygame не собирается для Android (и это видно только на устройстве)

С версией 0.2.1 APK собирался и запускался, но падал при старте:

```
NotImplementedError: display module not available
(ImportError: dlopen failed: cannot locate symbol
 "alphablit_alpha_sse2_argb_surf_alpha" referenced by ".../pygame/surface.so")
```

Причина в шаблоне `buildconfig/Setup.Android.SDL2.in` (pygame 2.1.3):
расширение `surface` собирается из трёх файлов и **не включает**
`simd_blitters_sse2.c` / `simd_blitters_avx2.c`. При этом `alphablit.c`
вызывает `alphablit_alpha_sse2_argb_surf_alpha()` и `pg_has_avx2()`
безусловно, а на aarch64 сам `simd_blitters.h` включает
`#define PG_ENABLE_ARM_NEON 1` — вызовы компилируются, а определений в
сборке нет. На настольных платформах те же символы закрыты `__SSE2__`,
поэтому баг там не проявляется.

Рецепт `p4a-recipes/pygame` дописывает оба файла в строку `surface`
(`fix_surface_sources`). Сами файлы безопасны для ARM: SIMD-код внутри под
`#if __SSE2__` / `#if __AVX2__`, а `pg_has_avx2()` без AVX2 возвращает 0.
Проверка: `python tools/test_pygame_recipe.py` (тоже запускается в CI до
сборки).

Убедиться, что правка доехала до готового APK, можно и без телефона —
`tools/verify_elf.py` разбирает секции ELF всех `.so` и ищет символы,
которых нет нигде в бандле:

```
$ python tools/verify_elf.py bin/trigbattle_0.2.1.apk      # тот, что падал
  ПРОБЛЕМА: символы без определения (1 .so):
    surface.so: alphablit_alpha_sse2_argb_surf_alpha, ... blit_blend_rgb_mul_sse2
$ python tools/verify_elf.py bin/trigbattle_0.2.2.apk      # с исправлением
  ОК: каждый символ, нужный .so, где-то определён — dlopen не должен падать
```

Символы вида `PyErr_SetString` или `SDL_*` проблемой не считаются: они
приходят из `libpython3.11.so` и `libSDL2.so`. Проверка запускается в CI
после сборки, так что «молчаливо сломанный» APK больше не уйдёт дальше.

## Как узнать причину падения на устройстве

`main.py` сообщает об ошибке тремя независимыми способами, потому что
прежний вариант (экран средствами pygame) не срабатывал, если SDL не смог
открыть окно:

1. файл-журнал `/sdcard/Android/data/org.kasatkin.trigbattle/files/trigbattle.log`;
2. нативный Toast поверх любых окон Android;
3. экран средствами pygame, если окно есть.

Всё печатается и в logcat: `adb logcat -s trigbattle python`.
Плюс есть воркфлоу `.github/workflows/test-emulator.yml`: он собирает APK
под x86_64, запускает его на эмуляторе Android и печатает в лог прогона
состояние процесса, скриншот, наш журнал и logcat — причину видно без
телефона.

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
4. Скачайте артефакт **trigbattle_0.2.1** — внутри лежит готовый
   `trigbattle_0.2.0.apk`.
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
Скрипт сам переименует результат: `ready_apk/dist/trigbattle_0.2.1.apk`
(buildozer по умолчанию даёт `trigbattle-0.2.0-arm64-v8a_armeabi-v7a-debug.apk`).
Установка: `adb install -r dist/trigbattle_0.2.1.apk`

> Сборка только под ARM (`arm64-v8a`, `armeabi-v7a`) — APK получается
> заметно меньше и собирается быстрее. Если нужен x86_эмулятор, уберите
> строку `android.archs` из `buildozer.spec` и пересоберите.

## Что настроено в buildozer.spec

| Параметр | Значение | Зачем |
|---|---|---|
| `requirements` | `python3,pygame,sdl2_ttf,sdl2_image,sdl2_mixer` | pygame собирается из исходников и требует SDL2-модулей; версии зафиксированы по recipe pygame |
| `p4a.bootstrap` | `sdl2` | pygame 2.x не собирается под SDL1 |
| `p4a.branch` | `v2024.01.21` | там python3 = 3.11.5; на `develop` (Python 3.14)
pygame 2.1.0 не собирается: его C-код использует `longintrepr.h`,
удалённый в Python 3.12+ |
| `orientation` | `landscape` | игра рассчитана на альбомную ориентацию |
| `android.permissions` | пусто | игре не нужны ни сеть, ни геолокация |
| `android.archs` | `arm64-v8a` | все современные телефоны; APK вдвое меньше и вдвое быстрее сборка. 32-битный armeabi-v7a на свежих NDK ломается на `grpmodule.c` |
| `p4a.local_recipes` | `./p4a-recipes` | свой рецепт pygame **2.1.3** вместо штатных 2.1.0: 2.1.0 несовместим с Python 3.11 (`longintrepr.h` переехал, `PyFrameObject` стал непрозрачным), а 2.1.3 — первая версия с поддержкой 3.11 и ещё с Android-шаблоном `Setup.Android.SDL2.in` |
| `version` / `package.name` | `0.2.1` / `trigbattle` | итоговый файл `trigbattle_0.2.1.apk` |
| `source.include_patterns` | `*.py,*.pyc,...` | **критично**: без этого p4a не кладёт файлы проекта в APK и приложение закрывается сразу после запуска |
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
## Если приложение не запускается

Версия 0.2.0 была собрана, но в APK не попали файлы игры: приложение
стартовало и мгновенно закрывалось (на любом телефоне). Причина —
buildozer передаёт python-for-android флаг `--ignore-setup-py`, а p4a
кладёт файлы проекта в APK **только** через `setup.py`. Лечится парой
`setup.py` + `p4a.setup_py = True` в `buildozer.spec`.

В 0.2.1 это исправлено, а в CI появилась проверка
`tools/verify_apk.py` — сборка падает, если внутри APK нет `main.py`.

Если вдруг приложение снова не откроется, снимите лог:
```bash
adb logcat -s trigbattle python
```
`main.py` печатает туда диагностику при старте, а при ошибке — полный
трейсбек и текст на экране ��а несколько секунд.
