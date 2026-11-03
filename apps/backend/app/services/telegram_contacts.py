"""Validate manually supplied public handles; this is not Telegram account lookup."""
import re
from urllib.parse import urlsplit


def normalize_username(value):
    if value is None or not value.strip():
        return None
    name = value.strip()
    if name.startswith(('t.me/', 'telegram.me/')):
        name = 'https://' + name
    if '://' in name:
        url = urlsplit(name)
        if url.scheme != 'https' or url.netloc.lower() not in ('t.me', 'telegram.me') or url.query or url.fragment:
            raise ValueError('Enter a Telegram username or a public t.me/username link.')
        name = url.path.strip('/')
    if name.startswith('@'):
        name = name[1:]
    if not re.fullmatch(r'[A-Za-z0-9_]{3,32}', name) or name.isdigit() or name.lower() in {'share', 'login', 'joinchat', 'proxy', 'socks', 'contact', 'addstickers', 'addemoji', 'addlist', 'invoice'}:
        raise ValueError('Enter a valid Telegram username, for example @example_user.')
    return name
