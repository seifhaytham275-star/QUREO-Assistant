"""Secure credential storage using the OS keyring (Windows Credential Manager).

Nothing here ever logs or prints a secret. If the keyring package or a
backend is unavailable, saving fails loudly instead of falling back to a file.
"""
SERVICE = "QUREO-Assistant"
_USER_KEY = "qureo-username"


def _kr():
    import keyring  # imported lazily so the app still starts without it
    return keyring


def available() -> bool:
    try:
        _kr()
        return True
    except Exception:
        return False


def save_qureo(username: str, password: str) -> None:
    kr = _kr()
    kr.set_password(SERVICE, _USER_KEY, username)
    kr.set_password(SERVICE, username, password)


def load_qureo():
    """Return (username, password) or (None, None)."""
    try:
        kr = _kr()
        user = kr.get_password(SERVICE, _USER_KEY)
        if not user:
            return None, None
        return user, kr.get_password(SERVICE, user)
    except Exception:
        return None, None


def clear_qureo() -> None:
    try:
        kr = _kr()
        user = kr.get_password(SERVICE, _USER_KEY)
        if user:
            try:
                kr.delete_password(SERVICE, user)
            except Exception:
                pass
        try:
            kr.delete_password(SERVICE, _USER_KEY)
        except Exception:
            pass
    except Exception:
        pass


def save_openrouter_key(key: str) -> None:
    _kr().set_password(SERVICE, "openrouter-key", key)


def load_openrouter_key():
    try:
        return _kr().get_password(SERVICE, "openrouter-key")
    except Exception:
        return None
