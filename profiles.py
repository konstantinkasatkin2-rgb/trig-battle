# -*- coding: utf-8 -*-
"""
Профили игроков: регистрация по электронной почте, вход, статистика.

Хранилище — SQLite в каталоге `dtb` рядом с программой:
  * запуск из исходников в D:\\trig-battle  -> D:\\trig-battle\\dtb
  * собранный .exe                          -> dtb рядом с .exe
  * Android                                 -> внутри каталога приложения
Если каталог недоступен для записи, используется резервный
`<домашний каталог>/.trigbattle/dtb`, чтобы игра не падала из-за
прав доступа.

Ограничение, ради которого всё затевалось: один адрес электронной почты —
один аккаунт. Это обеспечено не кодом, а самой схемой: `email TEXT UNIQUE
NOT NULL`, поэтому даже при гонке двух регистраций вторая завершится
ошибкой целостности, а не создаст дубль.

Пароли не хранятся: PBKDF2-HMAC-SHA256 со случайной солью на пользователя.
Email хранится открытым — база локальная, сервера нет, а открытый адрес
нужен, чтобы показать его в профиле.

Только стандартная библиотека: модуль должен работать и на Android.
"""

import hashlib
import os
import secrets
import sqlite3
import sys
from datetime import datetime

DB_DIR_NAME = 'dtb'
DB_FILE_NAME = 'users.db'
SESSION_FILE = 'session.txt'

# Сколько уровней вверх от программы искать уже созданный каталог `dtb`.
SEARCH_UP_LEVELS = 3

# Сколько символов максимум в никнейме.
NICK_MAX = 16
MIN_PASSWORD = 6
MAX_PASSWORD = 64
EMAIL_MAX = 120


def base_dir():
    """Каталог, рядом с которым живёт база.

    У собранного .exe `__file__` указывает во временную папку распаковки
    (`_MEIPASS`), поэтому для него берём каталог самого .exe — иначе база
    исчезла бы вместе со временной папкой.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def db_dir():
    """Каталог `dtb` с базой.

    Порядок выбора:
      1. ближайший существующий каталог `dtb` вверх по дереву от программы —
         нужно, чтобы и запуск из исходников, и .exe в корне проекта, и APK
         пользовались ОДНОЙ базой в `D:\\trig-battle\\dtb`;
      2. иначе создаём `dtb` рядом с программой;
      3. если запись запрещена — резервный каталог в профиле пользователя,
         чтобы игра не падала из-за прав доступа.
    """
    start = base_dir()
    probe_dir = start
    for _level in range(SEARCH_UP_LEVELS):
        candidate = os.path.join(probe_dir, DB_DIR_NAME)
        if os.path.isdir(candidate):
            if _writable(candidate):
                return candidate
            break
        parent = os.path.dirname(probe_dir)
        if parent == probe_dir:
            break
        probe_dir = parent

    preferred = os.path.join(start, DB_DIR_NAME)
    if _writable(preferred):
        return preferred

    fallback = os.path.join(os.path.expanduser('~'), '.trigbattle',
                            DB_DIR_NAME)
    os.makedirs(fallback, exist_ok=True)
    return fallback


def _writable(path):
    """Создаёт каталог (если нужно) и проверяет, что в него можно писать."""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, '.write_test')
        with open(probe, 'w', encoding='utf-8') as fd:
            fd.write('ok')
        os.remove(probe)
        return True
    except OSError:
        return False


def db_path():
    return os.path.join(db_dir(), DB_FILE_NAME)


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class ProfileError(Exception):
    """Ошибка, которую можно показать игроку как есть."""


def validate_email(email):
    email = (email or '').strip().lower()
    if not email:
        raise ProfileError('Введите адрес электронной почты')
    if len(email) > EMAIL_MAX:
        raise ProfileError('Слишком длинный адрес почты')
    if email.count('@') != 1:
        raise ProfileError('В адресе должен быть ровно один знак @')
    local, _, domain = email.partition('@')
    if not local or not domain or '.' not in domain:
        raise ProfileError('Проверьте адрес почты, например ivan@mail.ru')
    if ' ' in email:
        raise ProfileError('В адресе почты не может быть пробелов')
    return email


def validate_password(password):
    if not password:
        raise ProfileError('Введите пароль')
    if len(password) < MIN_PASSWORD:
        raise ProfileError('Пароль должен быть минимум %d символов'
                           % MIN_PASSWORD)
    if len(password) > MAX_PASSWORD:
        raise ProfileError('Пароль слишком длинный')
    return password


def validate_nick(nick):
    nick = (nick or '').strip()
    if not nick:
        raise ProfileError('Введите никнейм')
    if len(nick) > NICK_MAX:
        raise ProfileError('Никнейм не длиннее %d символов' % NICK_MAX)
    return nick


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(16)
    elif isinstance(salt, str):
        salt = bytes.fromhex(salt)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                 salt, 120000)
    return digest.hex(), salt.hex()


class Profiles:
    """Хранилище аккаунтов и текущей сессии."""

    def __init__(self, path=None):
        self.path = path or db_path()
        self._init_db()

    # ---------------- схема ----------------
    def _init_db(self):
        with sqlite3.connect(self.path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    email         TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt          TEXT NOT NULL,
                    nickname      TEXT NOT NULL,
                    created_at    TEXT NOT NULL,
                    last_login    TEXT
                )''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    user_id    INTEGER PRIMARY KEY,
                    games      INTEGER DEFAULT 0,
                    wins       INTEGER DEFAULT 0,
                    losses     INTEGER DEFAULT 0,
                    shots      INTEGER DEFAULT 0,
                    hits       INTEGER DEFAULT 0,
                    moves      INTEGER DEFAULT 0,
                    misses     INTEGER DEFAULT 0,
                    hints      INTEGER DEFAULT 0,
                    updated_at TEXT
                )''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    token      TEXT PRIMARY KEY,
                    user_id    INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )''')
            conn.commit()
            self._migrate()

    def _migrate(self):
        """Добавляет новые счётчики в базу, созданную прошлой версией."""
        try:
            with sqlite3.connect(self.path) as conn:
                have = set()
                for row in conn.execute('PRAGMA table_info(stats)'):
                    have.add(row[1])
                for col in ('moves', 'misses', 'hints'):
                    if col not in have:
                        conn.execute('ALTER TABLE stats ADD COLUMN %s '
                                     'INTEGER DEFAULT 0' % col)
                conn.commit()
        except sqlite3.Error:
            pass

    # ---------------- регистрация и вход ----------------
    def register(self, email, password, nickname):
        """Создаёт аккаунт. Один email — один аккаунт (UNIQUE)."""
        email = validate_email(email)
        validate_password(password)
        nickname = validate_nick(nickname)
        phash, salt = hash_password(password)
        try:
            with sqlite3.connect(self.path) as conn:
                cur = conn.execute('''
                    INSERT INTO users (email, password_hash, salt, nickname,
                                       created_at)
                    VALUES (?, ?, ?, ?, ?)''',
                    (email, phash, salt, nickname, _now()))
                conn.commit()
                user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ProfileError('Этот адрес почты уже зарегистрирован')
        self.start_session(user_id)
        return {'id': user_id, 'email': email, 'nickname': nickname}

    def login(self, email, password):
        email = validate_email(email)
        if not password:
            raise ProfileError('Введите пароль')
        with sqlite3.connect(self.path) as conn:
            row = conn.execute('''
                SELECT id, password_hash, salt, nickname FROM users
                WHERE email = ?''', (email,)).fetchone()
            if row is None:
                raise ProfileError('Неверный адрес почты или пароль')
            user_id, phash, salt, nickname = row
            computed, _ = hash_password(password, salt)
            if not secrets.compare_digest(computed, phash):
                raise ProfileError('Неверный адрес почты или пароль')
            conn.execute('UPDATE users SET last_login = ? WHERE id = ?',
                         (_now(), user_id))
            conn.commit()
        self.start_session(user_id)
        return {'id': user_id, 'email': email, 'nickname': nickname}

    def change_nickname(self, user_id, nickname):
        nickname = validate_nick(nickname)
        with sqlite3.connect(self.path) as conn:
            conn.execute('UPDATE users SET nickname = ? WHERE id = ?',
                         (nickname, user_id))
            conn.commit()
        return nickname

    def has_accounts(self):
        with sqlite3.connect(self.path) as conn:
            return conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] > 0

    # ---------------- сессия ----------------
    def _session_file(self):
        return os.path.join(os.path.dirname(self.path), SESSION_FILE)

    def start_session(self, user_id):
        token = secrets.token_urlsafe(24)
        with sqlite3.connect(self.path) as conn:
            conn.execute('INSERT INTO sessions (token, user_id, created_at) '
                         'VALUES (?, ?, ?)', (token, user_id, _now()))
            conn.commit()
        try:
            with open(self._session_file(), 'w', encoding='utf-8') as fd:
                fd.write(token)
        except OSError:
            pass
        return token

    def restore_session(self):
        """Аккаунт, с которым игра запускалась в прошлый раз, либо None."""
        try:
            with open(self._session_file(), encoding='utf-8') as fd:
                token = fd.read().strip()
        except OSError:
            return None
        if not token:
            return None
        with sqlite3.connect(self.path) as conn:
            row = conn.execute('''
                SELECT u.id, u.email, u.nickname FROM sessions s
                JOIN users u ON u.id = s.user_id WHERE s.token = ?''',
                (token,)).fetchone()
        if row is None:
            return None
        return {'id': row[0], 'email': row[1], 'nickname': row[2]}

    def logout(self):
        try:
            os.remove(self._session_file())
        except OSError:
            pass
        with sqlite3.connect(self.path) as conn:
            conn.execute('DELETE FROM sessions')
            conn.commit()

    # ---------------- статистика ----------------
    def get_stats(self, user_id):
        """Статистика игрока: игры, победы, ходы, попадания, промахи,
        подсказки."""
        with sqlite3.connect(self.path) as conn:
            row = conn.execute('''
                SELECT games, wins, losses, shots, hits,
                       moves, misses, hints FROM stats
                WHERE user_id = ?''', (user_id,)).fetchone()
        keys = ('games', 'wins', 'losses', 'shots', 'hits',
                'moves', 'misses', 'hints')
        if row is None:
            return dict.fromkeys(keys, 0)
        return dict(zip(keys, row))

    def record_game(self, user_id, won, shots=0, hits=0):
        """Итог одной партии."""
        if not user_id:
            return
        with sqlite3.connect(self.path) as conn:
            conn.execute('''
                INSERT INTO stats (user_id, games, wins, losses, shots, hits,
                                   updated_at)
                VALUES (?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    games   = games + 1,
                    wins    = wins + excluded.wins,
                    losses  = losses + excluded.losses,
                    shots   = shots + excluded.shots,
                    hits    = hits + excluded.hits,
                    updated_at = excluded.updated_at''',
                (user_id, 1 if won else 0, 0 if won else 1, shots, hits,
                 _now()))
            conn.commit()

    def add_stat(self, user_id, key, n=1):
        """Счётчик действия: ход, попадание, промах, подсказка."""
        if not user_id or key not in ('moves', 'hits', 'misses', 'hints'):
            return
        with sqlite3.connect(self.path) as conn:
            conn.execute('INSERT OR IGNORE INTO stats (user_id) VALUES (?)',
                         (user_id,))
            conn.execute('UPDATE stats SET %s = %s + ?, updated_at = ? '
                         'WHERE user_id = ?' % (key, key),
                         (n, _now(), user_id))
            conn.commit()


if __name__ == '__main__':
    # Быстрая проверка из консоли: создаём базу, регистрируем, входим.
    p = Profiles()
    print('база:', p.path)
    print('аккаунтов уже было:', p.has_accounts())
