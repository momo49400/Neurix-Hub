"""Neurix Hub public GitHub catalogue client. No installer is run automatically."""
from __future__ import annotations
import hashlib
import json
import re
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit, unquote

CATALOG_URL = 'https://raw.githubusercontent.com/momo49400/Neurix-Group-Releases/main/catalog/versions.json'
MAX_CATALOG_BYTES = 512_000
MAX_DOWNLOAD_BYTES = 2_000_000_000
HEX64 = re.compile(r'^[0-9a-fA-F]{64}$')
FILENAME = re.compile(r'^[a-zA-Z0-9._-]+\.exe$')

class DistributionError(Exception):
    pass

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = urlsplit(newurl).hostname or ''
        if urlsplit(newurl).scheme != 'https' or not (host == 'github.com' or host == 'objects.githubusercontent.com' or host.endswith('.githubusercontent.com')):
            raise DistributionError('Redirection vers un domaine non approuvee.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)

OPENER = urllib.request.build_opener(SafeRedirect)

def validate_release(item):
    if not isinstance(item, dict):
        raise DistributionError('Entree de version invalide.')
    for key in ('version','channel','platform','filename','download_url','sha256','size_bytes','released_at','notes'):
        if key not in item:
            raise DistributionError(f'Champ catalogue manquant : {key}')
    if item['channel'] not in ('alpha','beta','stable') or item['platform'] != 'windows-x64':
        raise DistributionError('Plateforme ou canal non pris en charge.')
    if not isinstance(item['filename'], str) or not FILENAME.fullmatch(item['filename']) or '..' in item['filename']:
        raise DistributionError('Nom de fichier interdit.')
    if not isinstance(item['sha256'], str) or not HEX64.fullmatch(item['sha256']):
        raise DistributionError('SHA-256 invalide.')
    if type(item['size_bytes']) is not int or not 0 < item['size_bytes'] <= MAX_DOWNLOAD_BYTES:
        raise DistributionError('Taille invalide.')
    url = item['download_url']
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'github.com' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DistributionError('Le telechargement doit venir de GitHub Releases.')
    if not parsed.path.startswith('/momo49400/Neurix-Group-Releases/releases/download/') or unquote(parsed.path.rsplit('/',1)[-1]) != item['filename']:
        raise DistributionError('URL de release inattendue.')
    return item

def parse_catalog(data: bytes) -> list[dict]:
    if len(data) > MAX_CATALOG_BYTES:
        raise DistributionError('Catalogue trop volumineux.')
    try:
        doc = json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise DistributionError('JSON du catalogue illisible.') from exc
    if not isinstance(doc, dict) or doc.get('schema_version') != 1 or not isinstance(doc.get('applications'), list):
        raise DistributionError('Format de catalogue incompatible.')
    releases=[]
    for app in doc['applications']:
        if not isinstance(app, dict) or app.get('id') != 'neurix-ai':
            continue
        if not isinstance(app.get('releases'), list):
            raise DistributionError('Liste des releases invalide.')
        for item in app['releases']:
            releases.append(validate_release(item))
    return releases

def fetch_catalog() -> list[dict]:
    req=urllib.request.Request(CATALOG_URL, headers={'User-Agent':'NeurixHub/0.4','Accept':'application/json'})
    try:
        with OPENER.open(req,timeout=20) as response:
            data=response.read(MAX_CATALOG_BYTES+1)
    except Exception as exc:
        raise DistributionError(f'Catalogue inaccessible : {exc}') from exc
    return parse_catalog(data)

def download_verified(item: dict, progress=None, directory: Path | None = None) -> Path:
    """Returns verified temporary .exe. Caller imports it into CacheEngine then deletes temp."""
    validate_release(item)
    expected_size=item['size_bytes']
    base=directory or (Path(tempfile.gettempdir()) / 'NeurixHubDownloads')
    base.mkdir(parents=True, exist_ok=True)
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=base, suffix='.exe', prefix='neurix-',delete=False) as out:
            tmp=Path(out.name)
            h=hashlib.sha256()
            size=0
            req=urllib.request.Request(item['download_url'],headers={'User-Agent':'NeurixHub/0.4'})
            with OPENER.open(req,timeout=60) as response:
                for chunk in iter(lambda:response.read(256*1024),b''):
                    size+=len(chunk)
                    if size > expected_size:
                        raise DistributionError('Fichier plus grand que la taille attendue.')
                    out.write(chunk)
                    h.update(chunk)
                    if progress: progress(int(size * 100 / expected_size))
        if size != expected_size or h.hexdigest().lower() != item['sha256'].lower():
            raise DistributionError('Taille ou SHA-256 incorrect : telechargement rejete.')
        # CacheEngine identifies version based on the original installer filename.
        destination=base / item['filename']
        if destination.exists():
            raise DistributionError('Un fichier temporaire du meme nom existe deja : operation annulee.')
        tmp.rename(destination)
        return destination
    except Exception as exc:
        if tmp: tmp.unlink(missing_ok=True)
        if isinstance(exc,DistributionError): raise
        raise DistributionError(f'Telechargement impossible : {exc}') from exc
