[app]

# (str) Title of your application
title = Тригонометрический морской бой

# (str) Package name / domain
package.name = trigbattle
package.domain = org.kasatkin

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,jpeg,ttf,otf,json

# (str) Application versioning
version = 0.2.0

# (list) Application requirements.
# pygame собирается python-for-android из исходников и требует SDL2-модулей.
# Версии НЕ фиксируем: старые архивы sdl2_* (2.0.2 и т.п.) удалены с GitHub
# и сборка падает с 404 — пусть python-for-android возьмёт свои актуальные.
requirements = python3,pygame,sdl2_ttf,sdl2_image,sdl2_mixer

# (str) Supported orientation — игра рассчитана на альбомную
orientation = landscape

# (bool) Fullscreen. Внутри можно переключить по F11.
# Поставьте 1, если хотите чистый полноэкранный режим без панели задач.
fullscreen = 0

# (list) Permissions — игре ничего не нужно (ни сети, ни геолокации)
android.permissions =

# (int) Target / minimum Android API
#android.api = 33
android.minapi = 21

# (str) Только arm64-v8a: все современные телефоны, APK вдвое меньше
# и собирается вдвое быстрее. 32-битный armeabi-v7a на свежих NDK
# дополнительно ломается на grpmodule.c, так что он не нужен.
android.archs = arm64-v8a

# (bool) Automatically accept Android SDK licenses (нужно для CI)
android.accept_sdk_license = True

# (str) Ветка python-for-android.
# ВАЖНО: нельзя ставить develop — там python3 = 3.14, а рецепт pygame
# зафиксирован на pygame 2.1.0, чей C-код использует longintrepr.h
# (удалён в Python 3.12+) -> падает компиляция sdl2.c.
# В теге v2024.01.21 python3 = 3.11.5, и pygame 2.1.0 собирается нормально.
p4a.branch = v2024.01.21

# Нужен SDL2 (pygame 2.x не собирается под SDL1)
p4a.bootstrap = sdl2

# Локальный рецепт pygame: выключает CYTHON_USE_PYLONG_INTERNALS,
# иначе pygame 2.1.0 не компилируется на Python 3.11+ (longintrepr.h).
p4a.local_recipes = ./p4a-recipes

# (str) Android NDK version to use
#android.ndk = 25b

# (bool) Use --private data storage
#android.private_storage = True

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 1

# (str) Path to build artifact storage, absolute or relative to spec file
build_dir = ./.buildozer

# (str) Path to build output (i.e. .apk, .aab, .ipa) storage
bin_dir = ./bin