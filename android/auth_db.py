"""
База аккаунтов пользователей (регистрация по email).
Только стандартная библиотека: PBKDF2-HMAC-SHA256 для паролей,
SHA-256(email) — как ключ поиска (Fernet-шифрование даёт каждый раз
разный шифротекст, из-за чего вход по email был невозможен).
"""
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime


class AuthDatabase:
    """Хранилище пользователей: email (sha256), хеш пароля, соль, ник."""

    def __init__(self, db_path="users.db", key_file="db_key.key"):
        self.db_path = db_path
        # key_file сохранён для совместимости сигнатуры, не используется
        self._init_database()

    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    nickname TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            ''')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_email ON users(email)')
            conn.commit()

    @staticmethod
    def _email_key(email: str) -> str:
        return hashlib.sha256(email.encode('utf-8')).hexdigest()

    def _hash_password(self, password: str, salt: bytes = None) -> tuple:
        if salt is None:
            salt = secrets.token_bytes(16)
        if isinstance(salt, str):
            salt = bytes.fromhex(salt)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                                     salt, 100000)
        return digest.hex(), salt

    def _verify_password(self, password: str, password_hash: str,
                         salt) -> bool:
        try:
            computed, _ = self._hash_password(password, salt)
            return secrets.compare_digest(computed, password_hash)
        except Exception:
            return False

    def register_user(self, email: str, password: str,
                      nickname: str = None) -> dict:
        email = email.lower().strip()

        if not email or '@' not in email:
            return {'success': False, 'error': 'Неверный email'}

        if len(password) < 6:
            return {'success': False,
                    'error': 'Пароль должен быть минимум 6 символов'}

        if nickname and len(nickname) > 12:
            return {'success': False, 'error': 'Никнейм не длиннее 12 символов'}

        try:
            with sqlite3.connect(self.db_path) as conn:
                key = self._email_key(email)
                cursor = conn.execute(
                    'SELECT id FROM users WHERE email = ?', (key,))
                if cursor.fetchone():
                    return {'success': False,
                            'error': 'Этот email уже зарегистрирован'}

                salt = secrets.token_bytes(16)
                password_hash, _ = self._hash_password(password, salt)

                cursor = conn.execute('''
                    INSERT INTO users (email, password_hash, salt, nickname)
                    VALUES (?, ?, ?, ?)
                ''', (key, password_hash, salt.hex(), nickname or ''))
                conn.commit()

                return {'success': True, 'user_id': cursor.lastrowid,
                        'message': 'Регистрация успешна'}
        except sqlite3.IntegrityError:
            return {'success': False,
                    'error': 'Этот email уже зарегистрирован'}
        except Exception as e:
            return {'success': False,
                    'error': f'Ошибка регистрации: {str(e)}'}

    def login_user(self, email: str, password: str) -> dict:
        email = email.lower().strip()

        try:
            with sqlite3.connect(self.db_path) as conn:
                key = self._email_key(email)
                cursor = conn.execute(
                    'SELECT id, password_hash, salt, nickname FROM users '
                    'WHERE email = ? AND is_active = 1', (key,))
                row = cursor.fetchone()

                if not row:
                    return {'success': False,
                            'error': 'Неверный email или пароль'}

                user_id, password_hash, salt, nickname = row

                if not self._verify_password(password, password_hash, salt):
                    return {'success': False,
                            'error': 'Неверный email или пароль'}

                conn.execute(
                    'UPDATE users SET last_login = ? WHERE id = ?',
                    (datetime.now(), user_id))
                conn.commit()

                return {'success': True, 'user_id': user_id,
                        'nickname': nickname or 'Игрок', 'email': email}
        except Exception as e:
            return {'success': False, 'error': f'Ошибка входа: {str(e)}'}

    def update_nickname(self, user_id: int, nickname: str) -> dict:
        if len(nickname) > 12:
            return {'success': False, 'error': 'Никнейм не длиннее 12 символов'}

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('UPDATE users SET nickname = ? WHERE id = ?',
                             (nickname[:12], user_id))
                conn.commit()
                return {'success': True, 'message': 'Никнейм обновлен'}
        except Exception as e:
            return {'success': False, 'error': f'Ошибка: {str(e)}'}

    def get_user(self, user_id: int) -> dict:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT id, email, nickname, created_at, last_login '
                    'FROM users WHERE id = ?', (user_id,))
                row = cursor.fetchone()
                if row:
                    return {'id': row[0], 'email': row[1],
                            'nickname': row[2], 'created_at': row[3],
                            'last_login': row[4]}
                return None
        except Exception:
            return None


# Global instance
auth_db = AuthDatabase()
