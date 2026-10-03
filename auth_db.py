"""
Encrypted authentication database for user registration.
Uses Fernet encryption for sensitive data.
"""
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json


class AuthDatabase:
    """Encrypted user database with email registration."""
    
    def __init__(self, db_path="users.db", key_file="db_key.key"):
        self.db_path = db_path
        self.key_file = key_file
        self._init_encryption()
        self._init_database()
    
    def _init_encryption(self):
        """Initialize or load encryption key."""
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                self.key = f.read()
        else:
            # Generate new key
            self.key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.key)
        self.cipher = Fernet(self.key)
    
    def _init_database(self):
        """Initialize database schema."""
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
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_email ON users(email)
            ''')
            conn.commit()
    
    def _hash_password(self, password: str, salt: bytes = None) -> tuple:
        """Hash password with salt."""
        if salt is None:
            salt = secrets.token_bytes(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key.decode(), salt
    
    def _verify_password(self, password: str, password_hash: str, salt: bytes) -> bool:
        """Verify password against hash."""
        try:
            computed_hash, _ = self._hash_password(password, salt)
            return secrets.compare_digest(computed_hash, password_hash)
        except:
            return False
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def register_user(self, email: str, password: str, nickname: str = None) -> dict:
        """Register new user with email and password."""
        email = email.lower().strip()
        
        if not email or '@' not in email:
            return {'success': False, 'error': 'Неверный email'}
        
        if len(password) < 6:
            return {'success': False, 'error': 'Пароль должен быть минимум 6 символов'}
        
        if nickname and len(nickname) > 12:
            return {'success': False, 'error': 'Никнейм не длиннее 12 символов'}
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if email exists
                cursor = conn.execute('SELECT id FROM users WHERE email = ?', (email,))
                if cursor.fetchone():
                    return {'success': False, 'error': 'Этот email уже зарегистрирован'}
                
                # Hash password
                salt = secrets.token_bytes(16)
                password_hash, _ = self._hash_password(password, salt)
                
                # Encrypt email for extra security
                encrypted_email = self.encrypt_data(email)
                
                # Insert user
                cursor = conn.execute('''
                    INSERT INTO users (email, password_hash, salt, nickname)
                    VALUES (?, ?, ?, ?)
                ''', (encrypted_email, password_hash, salt, nickname or ''))
                conn.commit()
                
                return {
                    'success': True, 
                    'user_id': cursor.lastrowid,
                    'message': 'Регистрация успешна'
                }
        except sqlite3.IntegrityError:
            return {'success': False, 'error': 'Этот email уже зарегистрирован'}
        except Exception as e:
            return {'success': False, 'error': f'Ошибка регистрации: {str(e)}'}
    
    def login_user(self, email: str, password: str) -> dict:
        """Authenticate user."""
        email = email.lower().strip()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Find user by encrypted email
                encrypted_email = self.encrypt_data(email)
                cursor = conn.execute(
                    'SELECT id, password_hash, salt, nickname FROM users WHERE email = ? AND is_active = 1',
                    (encrypted_email,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return {'success': False, 'error': 'Неверный email или пароль'}
                
                user_id, password_hash, salt, nickname = row
                
                if not self._verify_password(password, password_hash, salt):
                    return {'success': False, 'error': 'Неверный email или пароль'}
                
                # Update last login
                conn.execute(
                    'UPDATE users SET last_login = ? WHERE id = ?',
                    (datetime.now(), user_id)
                )
                conn.commit()
                
                return {
                    'success': True,
                    'user_id': user_id,
                    'nickname': nickname or 'Игрок',
                    'email': email
                }
        except Exception as e:
            return {'success': False, 'error': f'Ошибка входа: {str(e)}'}
    
    def update_nickname(self, user_id: int, nickname: str) -> dict:
        """Update user nickname."""
        if len(nickname) > 12:
            return {'success': False, 'error': 'Никнейм не длиннее 12 символов'}
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    'UPDATE users SET nickname = ? WHERE id = ?',
                    (nickname[:12], user_id)
                )
                conn.commit()
                return {'success': True, 'message': 'Никнейм обновлен'}
        except Exception as e:
            return {'success': False, 'error': f'Ошибка: {str(e)}'}
    
    def get_user(self, user_id: int) -> dict:
        """Get user info by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    'SELECT id, email, nickname, created_at, last_login FROM users WHERE id = ?',
                    (user_id,)
                )
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'email': self.decrypt_data(row[1]),
                        'nickname': row[2],
                        'created_at': row[3],
                        'last_login': row[4]
                    }
                return None
        except:
            return None


# Global instance
auth_db = AuthDatabase()