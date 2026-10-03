# Тригонометрический морской бой

Игра «морской бой» на тригонометрической окружности: выстрел — это точка
пересечения tg и cos (P₁) либо ctg и sin (P₂).

## Версии

- **`trig_circle.py`** — настольная версия на matplotlib (Windows/Linux).
  Запуск: `python trig_circle.py`
- **`trig_battle_pygame.py`** — версия на **pygame**: работает и на ПК, и на
  Android (мышь + тач, экранная клавиатура для ввода sin/cos/tg/ctg).
  Запуск: `pip install pygame` → `python trig_battle_pygame.py`
  Сборка APK: `buildozer -c android-pygame/buildozer.spec android debug`
  (см. `android-pygame/`)
- **`android/main.py`** — мобильная версия на Kivy (также работает на ПК).
  Запуск: `python android/main.py`

## Как получить APK для Android

### Способ 1 — GitHub Actions (облако, бесплатно, рекомендуется)

1. Создайте репозиторий на GitHub (например, `trig-battle`).
2. Загрузите этот проект:
   ```bash
   git init
   git add .
   git commit -m "Trigonometric battleship"
   git remote add origin https://github.com/ВАШ_ЛОГИН/trig-battle.git
   git push -u origin master
   ```
3. Откройте вкладку **Actions** в репозитории — сборка запустится
   автоматически (первый раз ~30–50 минут: скачиваются Android SDK/NDK).
4. Когда сборка завершится, скачайте артефакт **trig-battle-apk**
   (в нём `*.apk`) на странице запуска.
5. Перекиньте APK на телефон и установите (разрешите установку
   из неизвестных источников).

### Способ 2 — локально через WSL (Windows)

```bash
wsl --install          # нужна перезагрузка, права администратора
# в Ubuntu:
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk \
  autoconf libtool pkg-config zlib1g-dev libncurses-dev libffi-dev \
  libssl-dev cmake python3-pip
pip install buildozer cython
cd /mnt/c/Users/makla/Downloads/PortableGit/android
buildozer android debug
# APK появится в android/bin/
```

## Управление (Android/ПК, сенсорное)

- **Стройка**: «Корабли»/«Самолёты» → размер 1–5 → тап по полю;
  ⟳ — повернуть, «Удалить» — убрать выбранный юнит.
- **Прицел**: тяните пальцем по полю (кнопка «Прицел ∠1/∠2» выбирает угол),
  или слайдеры, или ввод sin₁/cos₁/tg₂/ctg₂.
- **Выстрел**: «Огонь P₁/P₂» → «Совершить ход».
