"""Durable per-board actionable-block alert outbox and bounded retry delivery."""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

BACKOFF = (60, 300, 900)

def _root(board: str) -> Path:
    safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in board) or 'default'
    return Path.home() / '.hermes' / 'ginflow' / safe

def _store(board: str):
    root = _root(board); root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'outbox.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX)
    path = root / 'outbox.json'
    try: data = json.loads(path.read_text()) if path.exists() else {'alerts': {}}
    except (ValueError, OSError): data = {'alerts': {}}
    return root, lock, path, data

def _save(path: Path, data: dict) -> None:
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.outbox-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, sort_keys=True); f.flush(); os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)

def enqueue(board: str, card: str, action: str, message: str, send) -> bool:
    key = card + ':' + hashlib.sha256(action.encode()).hexdigest()[:16]
    root, lock, path, data = _store(board)
    try:
        alerts = data['alerts']; now = time.time()
        if key in alerts and alerts[key]['state'] in ('pending', 'delivered'): return False
        alerts[key] = {'card': card, 'action': action, 'message': message, 'state': 'pending',
                       'attempts': 0, 'next_attempt': now, 'updated': now}
        _save(path, data)
    finally: lock.close()
    attempt(board, key, send)
    return True

def attempt(board: str, key: str, send) -> bool:
    root, lock, path, data = _store(board)
    try:
        row = data['alerts'].get(key)
        if not row or row['state'] != 'pending' or row['next_attempt'] > time.time(): return False
        row['attempts'] += 1; row['next_attempt'] = time.time() + BACKOFF[min(row['attempts'] - 1, len(BACKOFF)-1)]
        row['updated'] = time.time(); _save(path, data)
        message, card = row['message'], row['card']
    finally: lock.close()
    sent = bool(send(message))
    root, lock, path, data = _store(board)
    try:
        row = data['alerts'].get(key)
        if row and row['state'] == 'pending' and sent:
            row['state'] = 'delivered'; row['updated'] = time.time(); _save(path, data)
    finally: lock.close()
    return sent

def retry(board: str, send, is_blocked) -> None:
    root, lock, path, data = _store(board)
    try:
        due = [(key, row.copy()) for key, row in data['alerts'].items() if row['state'] == 'pending' and row['next_attempt'] <= time.time()]
    finally: lock.close()
    for key, row in due:
        if not is_blocked(row['card']):
            root, lock, path, data = _store(board)
            try:
                if key in data['alerts']: data['alerts'][key]['state'] = 'cancelled'; data['alerts'][key]['updated'] = time.time(); _save(path, data)
            finally: lock.close()
        else: attempt(board, key, send)
