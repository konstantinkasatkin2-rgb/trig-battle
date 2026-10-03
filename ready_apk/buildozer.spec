[app]

# (str) Title of your application
title = Тригонометрический морской бой

# (str) Package name / domain
package.name = trigbattlepg
package.domain = org.kasatkin

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,jpeg,ttf,otf,json

# (str) Application versioning
version = 0.1.0

# (list) Application requirements.
# pygame собирается python-for-android из исходников и требует SDL2-модулей;
# версии зафиксированы (так предписывает recipe pygame).
requirements = python3,pygame,sdl2_ttf==2.0.15,sdl2_image==2.0.2,sdl2_mixer==2.0.0

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

# (list) Только ARM — APK заметно меньше и собирается быстрее
android.archs = arm64-v8a, armeabi-v7a

# (bool) Automatically accept Android SDK licenses (нужно для CI)
android.accept_sdk_license = True

# (str) python-for-android branch с актуальными рецептами pygame
p4a.branch = develop

# Нужен SDL2 (pygame 2.x не собирается под SDL1)
p4a.bootstrap = sdl2

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