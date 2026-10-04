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

# (list) Какие файлы buildozer кладёт в приватный каталог, из которого
# p4a ставит проект. setup.py обязан быть здесь, иначе p4a не увидит проект.
source.include_patterns = *.py,*.pyc,*.png,*.jpg,*.jpeg,*.json,*.ttf,*.otf

# (str) Application versioning
# 0.2.1 — падал при старте (pygame не грузил display, см. рецепт pygame).
# 0.2.2 — это исправлено, игра запускается.
# 0.2.3 — профили (регистрация по почте, база в dtb) и игра по сети.
# 0.3.0 — новый режим «машинки против препятствий»: режимы в меню,
# альбомная ориентация по требованию, оба угла и обе точки P1/P2
# у каждого игрока.
# 0.4.0 — правила нового режима доведены: чужие фигуры видны только
# после столкновения, стены ставятся прямо в бою (только в свой ход
# и одна за ход) и только внутри круга, препятствие вращается,
# машинка крупнее и её ход видно плавно, на поле и в меню нового
# режима больше нет лишних тригонометрических подписей.
# 0.5.0 — сторона «защитник» и «нападающий» убрана совсем: каждый игрок
# и защитник, и нападающий. Свои машинки ставятся на поле СОПЕРНИКА,
# свои стены строятся на своём поле и только во время боя, в свой ход и
# одна за ход. Машинка размером примерно в клетку. Стена при сдвиге
# проверяет своё поле, а не левое (иначе по сети ходы расходились).
version = 0.5.0

# (list) Application requirements.
# pygame собирается python-for-android из исходников и требует SDL2-модулей.
# Версии НЕ фиксируем: старые архивы sdl2_* (2.0.2 и т.п.) удалены с GitHub
# и сборка падает с 404 — пусть python-for-android возьмёт свои актуальные.
#
# trigbattle_src — наш локальный рецепт (p4a-recipes/trigbattle_src): он
# кладёт main.py и trig_battle_pygame.py в site-packages. БЕЗ него APK
# собирается «успешно», но без кода игры: приложение стартует и сразу
# закрывается. Подробности — в p4a-recipes/trigbattle_src/__init__.py.
requirements = python3,pygame,sdl2_ttf,sdl2_image,sdl2_mixer,trigbattle_src

# (str) Supported orientation — игра рассчитана на альбомную
orientation = landscape

# (bool) Fullscreen. Внутри можно переключить по F11.
# Поставьте 1, если хотите чистый полноэкранный режим без панели задач.
fullscreen = 0

# (list) Permissions. INTERNET обязателен для игры по сети: без него
# Android запрещает ЛЮБУЮ работу с сокетами, и создание игры падает с
# «[Errno 1] Operation not permitted» — ровно так и случилось в 0.2.3.
# Это обычное разрешение, диалога при установке не показывает.
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE

# (int) Target / minimum Android API
#android.api = 33
android.minapi = 21

# (str) Только arm64-v8a: все современные телефоны, APK вдвое меньше
# и собирается вдвое быстрее. 32-битный armeabi-v7a на свежих NDK
# дополнительно ломается на grpmodule.c, так что он не нужен.
android.archs = arm64-v8a

# (bool) Automatically accept Android SDK licenses (нужно для CI)
android.accept_sdk_license = True

# --- ПОДПИСЬ ---
# Ключ лежит в репозитории намеренно: пока им подписан только этот
# проект, а без него каждая сборка получает новый ключ, Google Play
# считает приложение подозрительным, а обновление поверх старой версии
# невозможно — приходится удалять старую и ставить заново.
android.keystore = ./trigbattle.keystore
android.keyalias = trigbattle
android.storepassword = trigbattle
android.keypassword = trigbattle
# release-сборка подписывается этим ключом; и APK, и AAB — APK нужен,
# потому что ставится напрямую с телефона, без Google Play.
android.release_artifact = apk
android.debug_artifact = apk

# (str) Ветка python-for-android.
# ВАЖНО: нельзя ставить develop — там python3 = 3.14, а рецепт pygame
# зафиксирован на pygame 2.1.0, чей C-код использует longintrepr.h
# (удалён в Python 3.12+) -> падает компиляция sdl2.c.
# В теге v2024.01.21 python3 = 3.11.5, и pygame 2.1.0 собирается нормально.
p4a.branch = v2024.01.21

# Нужен SDL2 (pygame 2.x не собирается под SDL1)
p4a.bootstrap = sdl2

# (bool) КРИТИЧНО: установить проект через setup.py.
# По умолчанию buildozer передаёт p4a флаг --ignore-setup-py, а p4a кладёт
# файлы проекта в APK ТОЛЬКО через setup.py. С этим флагом в бандл попадает
# Python с pygame, но БЕЗ main.py — приложение стартует и сразу закрывается.
# Нужен файл setup.py рядом с main.py (он есть) и эта опция = True.
p4a.setup_py = True

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