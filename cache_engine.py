"""Neurix Hub Alpha 0.2 — offline immutable installer cache.

No remote calls, deletes of external files, registry edits or automatic installs.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DATA_HOME = Path(os.getenv('APPDATA') or Path.home()) / 'NeurixHub'
CACHE_DIR = DATA_HOME / 'installer_cache'
CATALOG = DATA_HOME / 'cache_catalog.json'
SETUP_RX = re.compile(r'(setup|installer|install)', re.I)
VER_RX = re.compile(r'(alpha|beta)[-_. ]*(\d+)[._-](\d+)(?:[._-](\d+))?', re.I)

class CacheError(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def identify(path: Path) -> tuple[str, str]:
    if path.suffix.lower() != '.exe' or not SETUP_RX.search(path.name):
        raise CacheError('Seuls les installateurs Windows Setup/Installer .exe sont acceptés.')
    m = VER_RX.search(path.stem)
    if not m:
        raise CacheError('Version Alpha/Beta introuvable dans le nom du fichier.')
    number = '.'.join(x for x in m.groups()[1:] if x is not None)
    return (m.group(1).capitalize(), number)


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, suffix='.tmp', delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        except Exception:
            temp.unlink(missing_ok=True)
            raise
    os.replace(temp, path)


class CacheEngine:
    def __init__(self, base: Path | None = None):
        self.base = base or DATA_HOME
        self.folder = self.base / 'installer_cache'
        self.index_path = self.base / 'cache_catalog.json'
        self.folder.mkdir(parents=True, exist_ok=True)
        self.entries = self._read()

    def _read(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        try:
            data = json.loads(self.index_path.read_text(encoding='utf-8'))
            if data.get('schema') != 1 or not isinstance(data.get('installers'), list):
                raise ValueError('bad schema')
            return [entry for entry in data['installers'] if isinstance(entry, dict)]
        except (OSError, ValueError, TypeError) as exc:
            raise CacheError('Catalogue du cache illisible. Aucun fichier ne sera modifié.') from exc

    def _save(self):
        _atomic_json(self.index_path, {'schema': 1, 'installers': self.entries})

    def add(self, path: Path) -> dict:
        path = path.resolve(strict=True)
        if not path.is_file():
            raise CacheError('Le fichier sélectionné est introuvable.')
        family, version = identify(path)
        digest = sha256_file(path)
        for record in self.entries:
            if record.get('sha256') == digest:
                self.verify(record)
                return record
        # Content-addressed filenames avoid collisions between versions/builds.
        filename = f'{family}-{version}-{digest[:24]}.exe'
        destination = self.folder / filename
        if destination.exists():
            if sha256_file(destination) != digest:
                raise CacheError('Collision dans le cache : fichier différent. Import annulé.')
        else:
            # Copy to temp then hash, avoid partial cached copies.
            with tempfile.NamedTemporaryFile(dir=self.folder, suffix='.partial', delete=False) as stream:
                tmp = Path(stream.name)
            try:
                shutil.copyfile(path, tmp)
                if sha256_file(tmp) != digest:
                    raise CacheError('Fichier modifié pendant la copie. Import annulé.')
                if destination.exists():
                    if sha256_file(destination) != digest:
                        raise CacheError('Le fichier de destination existe avec un contenu différent.')
                    tmp.unlink(missing_ok=True)
                else:
                    tmp.replace(destination)
            finally:
                tmp.unlink(missing_ok=True)
        record = {'id': digest, 'family': family, 'version': version,
                  'name': path.name, 'cached_file': filename, 'sha256': digest,
                  'size': destination.stat().st_size, 'added': datetime.now(timezone.utc).isoformat()}
        self.entries.append(record)
        self._save()
        return record

    def verify(self, record: dict) -> Path:
        file_name = record.get('cached_file', '')
        if not isinstance(file_name, str) or Path(file_name).name != file_name or not file_name.endswith('.exe'):
            raise CacheError('Référence de cache non valide.')
        target = self.folder / file_name
        if not target.is_file() or target.is_symlink():
            raise CacheError('Installateur absent du cache.')
        if sha256_file(target) != record.get('sha256'):
            raise CacheError('Empreinte SHA-256 différente : installation bloquée.')
        return target

    def remove(self, record: dict):
        # Only delete files inside managed cache after verification.
        self.verify(record)
        if record not in self.entries:
            raise CacheError('Version non trouvée.')
        # Save catalog first, then remove managed file. External files untouched.
        self.entries.remove(record)
        try:
            self._save()
        except Exception:
            self.entries.append(record)
            raise
        (self.folder / record['cached_file']).unlink()

    def usage(self) -> int:
        return sum(p.stat().st_size for p in self.folder.glob('*.exe') if p.is_file())
