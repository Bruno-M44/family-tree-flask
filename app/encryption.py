#! /usr/bin/env python
"""Encrypted SQLAlchemy column types using Fernet (AES-128 + HMAC-SHA256)."""

from datetime import datetime

from cryptography.fernet import Fernet
from flask import current_app
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


class EncryptedString(TypeDecorator):
    """Stores a string encrypted in the database."""
    impl = String
    cache_ok = True

    def _fernet(self):
        key = current_app.config['ENCRYPTION_KEY']
        if isinstance(key, str):
            key = key.encode()
        return Fernet(key)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return self._fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self._fernet().decrypt(value.encode()).decode()


class EncryptedDateTime(TypeDecorator):
    """Stores a datetime encrypted as a string in the database."""
    impl = String
    cache_ok = True
    _fmt = "%Y-%m-%dT%H:%M:%S"

    def _fernet(self):
        key = current_app.config['ENCRYPTION_KEY']
        if isinstance(key, str):
            key = key.encode()
        return Fernet(key)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            value = value.strftime(self._fmt)
        return self._fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        decrypted = self._fernet().decrypt(value.encode()).decode()
        return datetime.strptime(decrypted, self._fmt)
