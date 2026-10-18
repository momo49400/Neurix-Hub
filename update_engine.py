"""Neurix Hub Alpha 0.4 - non-invasive update comparison.

A cached installer is NOT proof of an installed application version.
"""
from __future__ import annotations
import re

_NUM = re.compile(r"^\d+(?:\.\d+){1,3}$")
_RANK = {"alpha": 0, "beta": 1, "stable": 2}


def release_key(channel: str, version: str):
    if not isinstance(channel, str) or channel.lower() not in _RANK:
        raise ValueError("Canal inconnu")
    if not isinstance(version, str) or not _NUM.fullmatch(version):
        raise ValueError("Numero de version invalide")
    return (*[int(x) for x in version.split('.')], *([0] * (4 - len(version.split('.')))), _RANK[channel.lower()])


def cached_hashes(cache_entries: list[dict]) -> set[str]:
    return {x.get('sha256','').lower() for x in cache_entries if isinstance(x,dict) and isinstance(x.get('sha256'),str)}


def newest_remote(releases: list[dict]):
    return max(releases, key=lambda r: release_key(r['channel'], r['version']), default=None)


def newest_cached(cache_entries: list[dict]):
    good = []
    for item in cache_entries:
        if not isinstance(item, dict):
            continue
        try:
            release_key(str(item.get('family','')).lower(), str(item.get('version','')))
            good.append(item)
        except ValueError:
            continue
    return max(good, key=lambda r: release_key(r['family'].lower(), r['version']), default=None)


def update_summary(releases: list[dict], cache_entries: list[dict]) -> dict:
    if not releases:
        return {'state':'empty','latest':None,'cached':None}
    latest=newest_remote(releases)
    local=newest_cached(cache_entries)
    if latest['sha256'].lower() in cached_hashes(cache_entries):
        state='cached'
    elif not local:
        state='available'
    elif release_key(latest['channel'],latest['version']) > release_key(local['family'].lower(),local['version']):
        state='newer'
    else:
        state='different'
    return {'state':state,'latest':latest,'cached':local}
