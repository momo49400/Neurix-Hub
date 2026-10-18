"""Neurix Hub Alpha 0.4 — local cache, rollback and public catalogue.

Python 3.10+; PySide6-Essentials. HTTPS catalogue reads and consent-based downloads; no elevated privileges or hidden installs.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QObject, Signal, QThread, QTimer
from cache_engine import CacheEngine, CacheError
from distribution_engine import fetch_catalog, download_verified, DistributionError
from update_engine import update_summary, cached_hashes, newest_remote
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QListWidget, QListWidgetItem, QStackedWidget,
    QTextEdit, QLineEdit, QFrame, QScrollArea, QProgressBar, QFormLayout
)

APP_VERSION = "0.4"
SETUP_HINT = re.compile(r"(setup|installer|install|installation)", re.I)
VER_RE = re.compile(r"(?:beta|alpha)[-_ .]*(\d+)[._-](\d+)(?:[._-](\d+))?", re.I)
DATA_HOME = (Path(os.getenv("APPDATA", str(Path.home()))) / "NeurixHub")
DB_PATH = DATA_HOME / "library.json"
STYLES = """
QMainWindow, QWidget#root { background: #10131a; color: #e8eaf2; }
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: #e8eaf2; }
QFrame#sidebar { background: #151a25; border-right: 1px solid #252d40; }
QFrame#card { background: #1b2230; border: 1px solid #2a354a; border-radius: 15px; }
QLabel#hero { font-size: 31px; font-weight: 700; }
QLabel#section { font-size: 19px; font-weight: 700; }
QLabel#muted { color: #aab5c8; }
QPushButton { background: #273248; color: #f5f7fc; border: 1px solid #35425b; border-radius: 9px; padding: 10px 15px; }
QPushButton:hover { background: #354663; }
QPushButton#primary { background: #347de9; border: 1px solid #438afd; font-weight: 600; }
QPushButton#primary:hover { background: #458bff; }
QPushButton:disabled { color: #707b91; background: #242a35; }
QListWidget { background: #131824; border: 1px solid #2a354a; border-radius: 10px; padding: 5px; outline: 0; }
QListWidget::item { padding: 14px; border-radius: 8px; }
QListWidget::item:selected { background: #29436c; }
QLineEdit, QTextEdit { background: #131824; border: 1px solid #303a50; border-radius: 8px; padding: 10px; }
QProgressBar { background: #252d3b; border: 0; border-radius: 5px; height: 8px; }
QProgressBar::chunk { background: #418bf5; border-radius: 5px; }
"""


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_setup(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == '.exe' and bool(SETUP_HINT.search(path.stem))


def version_info(name: str) -> tuple[str, str]:
    match = VER_RE.search(name)
    if not match:
        return ('Inconnue', 'Version non détectée')
    family = 'Beta' if re.search('beta', name, re.I) else 'Alpha'
    number = '.'.join(p for p in match.groups() if p is not None)
    return (f'{family} {number}', f'Neurix AI {family} {number}')


def load_db() -> list[dict]:
    try:
        value = json.loads(DB_PATH.read_text(encoding='utf-8'))
        if isinstance(value, dict) and isinstance(value.get('installers'), list):
            return [x for x in value['installers'] if isinstance(x, dict)]
    except (OSError, ValueError):
        pass
    return []


def save_db(data: list[dict]) -> None:
    DATA_HOME.mkdir(parents=True, exist_ok=True)
    new = DB_PATH.with_suffix('.tmp')
    new.write_text(json.dumps({'schema': 1, 'installers': data}, indent=2, ensure_ascii=False), encoding='utf-8')
    new.replace(DB_PATH)


class RemoteWorker(QObject):
    progress = Signal(int)
    finished = Signal(str, object, str)
    def __init__(self, mode, entry=None):
        super().__init__()
        self.mode, self.entry = mode, entry
    def run(self):
        try:
            if self.mode == 'catalog':
                result = fetch_catalog()
            else:
                result = str(download_verified(self.entry, self.progress.emit))
            self.finished.emit(self.mode, result, '')
        except Exception as exc:
            self.finished.emit(self.mode, None, str(exc))

class HashWorker(QObject):
    completed = Signal(str, str, str)  # path, hash, error
    def __init__(self, path: str):
        super().__init__()
        self.path = path
    def run(self):
        try:
            h = digest_file(Path(self.path))
            self.completed.emit(self.path, h, '')
        except Exception as exc:
            self.completed.emit(self.path, '', str(exc))


def frame(title: str, text: str = '') -> QFrame:
    f = QFrame()
    f.setObjectName('card')
    v = QVBoxLayout(f)
    v.setContentsMargins(20, 18, 20, 18)
    t = QLabel(title)
    t.setObjectName('section')
    v.addWidget(t)
    if text:
        sub = QLabel(text)
        sub.setObjectName('muted')
        sub.setWordWrap(True)
        v.addWidget(sub)
    return f


class Hub(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Neurix Hub — Alpha 0.4')
        self.resize(1100, 710)
        self.setMinimumSize(780, 510)
        self.setStyleSheet(STYLES)
        self.entries = load_db()
        self.cache_engine = CacheEngine()
        self.active_path: Optional[str] = None
        self.hash_thread: Optional[QThread] = None
        self.hash_worker: Optional[HashWorker] = None
        self.remote_thread = None
        self.remote_worker = None
        self.remote_releases = []
        self._build_ui()
        self.refresh()
        self.refresh_cache()
        # Check on start in a worker thread; never download or install silently.
        QTimer.singleShot(900, self.refresh_remote)

    def _build_ui(self):
        root = QWidget()
        root.setObjectName('root')
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(205)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14,22,14,18)
        side.setSpacing(12)
        brand = QLabel('◈  NEURIX HUB')
        brand.setStyleSheet('font-size: 18px; font-weight: 700; color: #bbd2ff;')
        side.addWidget(brand)
        tagline = QLabel('Your AI. Your Rules.')
        tagline.setObjectName('muted')
        side.addWidget(tagline)
        side.addSpacing(25)
        btn_home = QPushButton('⌂   Accueil')
        btn_library = QPushButton('▦   Bibliothèque')
        btn_cache = QPushButton('↶   Versions en cache')
        btn_online = QPushButton('◎   Catalogue mondial')
        btn_guide = QPushButton('ⓘ   Guide')
        for button in (btn_home, btn_library, btn_cache, btn_online, btn_guide):
            side.addWidget(button)
        side.addStretch()
        side.addWidget(QLabel('Alpha 0.4 • Update Manager'))
        layout.addWidget(sidebar)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        self.home_page = QWidget()
        self.library_page = QWidget()
        self.guide_page = QWidget()
        self.cache_page = QWidget()
        self.online_page = QWidget()
        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.library_page)
        self.pages.addWidget(self.cache_page)
        self.pages.addWidget(self.online_page)
        self.pages.addWidget(self.guide_page)
        btn_home.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        btn_library.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        btn_cache.clicked.connect(lambda: (self.refresh_cache(), self.pages.setCurrentIndex(2)))
        btn_online.clicked.connect(lambda: (self.pages.setCurrentWidget(self.online_page), self.refresh_remote()))
        btn_guide.clicked.connect(lambda: self.pages.setCurrentWidget(self.guide_page))
        self._build_home()
        self._build_library()
        self._build_cache()
        self._build_guide()
        self._build_online()

    def _build_home(self):
        outer = QVBoxLayout(self.home_page)
        outer.setContentsMargins(32,30,32,25)
        outer.setSpacing(20)
        h = QLabel('Bienvenue dans Neurix Hub')
        h.setObjectName('hero')
        outer.addWidget(h)
        tip = QLabel('Toutes tes versions de Neurix AI, au même endroit. Sans terminal pour les installer.')
        tip.setObjectName('muted')
        tip.setWordWrap(True)
        outer.addWidget(tip)
        featured = frame('Neurix AI  •  Bibliothèque locale',
                         'Ajoute tes fichiers Setup.exe existants, sélectionne une version et lance son installateur.')
        v = featured.layout()
        self.home_count = QLabel('Aucun installateur référencé')
        self.home_count.setObjectName('muted')
        v.addWidget(self.home_count)
        row = QHBoxLayout()
        add = QPushButton('Ajouter un Setup.exe')
        add.setObjectName('primary')
        add.clicked.connect(self.add_file)
        scan = QPushButton('Rechercher dans un dossier')
        scan.clicked.connect(self.scan_folder)
        row.addWidget(add)
        row.addWidget(scan)
        row.addStretch()
        v.addLayout(row)
        outer.addWidget(featured)
        info = frame('Nouveau : cache local et retour arrière',
                     'Conserve les anciens installateurs, vérifie leur empreinte et ouvre un ancien Setup après confirmation. Catalogue GitHub facultatif.')
        outer.addWidget(info)
        outer.addStretch()

    def _build_library(self):
        outer = QVBoxLayout(self.library_page)
        outer.setContentsMargins(30,25,30,25)
        outer.setSpacing(14)
        header = QLabel('Bibliothèque des versions')
        header.setObjectName('hero')
        outer.addWidget(header)
        toolbar = QHBoxLayout()
        add = QPushButton('＋ Ajouter un installateur')
        add.setObjectName('primary')
        add.clicked.connect(self.add_file)
        scan = QPushButton('Scanner un dossier')
        scan.clicked.connect(self.scan_folder)
        refresh = QPushButton('Actualiser')
        refresh.clicked.connect(self.refresh)
        toolbar.addWidget(add)
        toolbar.addWidget(scan)
        toolbar.addWidget(refresh)
        toolbar.addStretch()
        outer.addLayout(toolbar)
        split = QHBoxLayout()
        self.listing = QListWidget()
        self.listing.setMinimumWidth(260)
        self.listing.currentItemChanged.connect(self.selection_changed)
        split.addWidget(self.listing, 2)
        details = frame('Détails de la version')
        form = QFormLayout()
        self.version_label = QLabel('Sélectionne un installateur')
        self.file_label = QLabel('—')
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.sha_label = QLabel('—')
        self.sha_label.setWordWrap(True)
        self.sha_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.state_label = QLabel('—')
        form.addRow('Version :', self.version_label)
        form.addRow('Chemin :', self.file_label)
        form.addRow('SHA-256 :', self.sha_label)
        form.addRow('État :', self.state_label)
        details.layout().addLayout(form)
        self.progress = QProgressBar()
        self.progress.setRange(0,0)
        self.progress.setVisible(False)
        details.layout().addWidget(self.progress)
        btns = QHBoxLayout()
        self.install_btn = QPushButton('Lancer le Setup')
        self.install_btn.setObjectName('primary')
        self.install_btn.clicked.connect(self.launch_setup)
        self.remove_btn = QPushButton('Retirer de la liste')
        self.remove_btn.clicked.connect(self.remove_selected)
        btns.addWidget(self.install_btn)
        btns.addWidget(self.remove_btn)
        self.cache_selected_btn = QPushButton('Mettre en cache')
        self.cache_selected_btn.clicked.connect(self.cache_selected_library)
        details.layout().addWidget(self.cache_selected_btn)
        details.layout().addLayout(btns)
        details.layout().addStretch()
        split.addWidget(details, 3)
        outer.addLayout(split,1)
        self.status = QLabel('Aucune installation automatique : confirmation systématique avant ouverture.')
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

    def _build_guide(self):
        outer = QVBoxLayout(self.guide_page)
        outer.setContentsMargins(30,30,30,30)
        h = QLabel('Guide et sécurité')
        h.setObjectName('hero')
        outer.addWidget(h)
        instructions = QLabel(
            '1. Ajoute un fichier NeurixAI-...-Setup.exe déjà créé avec Inno Setup.\n\n'
            '2. Ou clique « Scanner un dossier » et sélectionne tes Téléchargements ou ton dossier release.\n\n'
            '3. Sélectionne une version et vérifie son chemin, son nom et son empreinte SHA-256.\n\n'
            '4. Clique « Lancer le Setup ». Neurix Hub te demande confirmation avant d’ouvrir le programme.\n\n'
            '• Le launcher ne supprime aucun ancien fichier et ne désinstalle aucune version.\n'
            '• Ajouter un fichier calcule une empreinte mais ne garantit pas qu’il est sûr.\n'
            '• Neurix Hub ne désactive ni Smart App Control ni Microsoft Defender.\n'
            '• Alpha 0.4 : importe manuellement des Setup dans le cache pour les conserver.\n'
            '• Le rollback ouvre un ancien Setup, mais ne garantit pas que son installation rétrograde est compatible.\n'
            '• Sauvegarde tes données Neurix AI avant toute rétrogradation.\n'
            '• Aucune modification automatique des bases SQLite ou du registre Windows.\n'
            '• Les téléchargements en ligne et les mises à jour automatiques viendront plus tard.\n'
            '• Les installateurs précompilés ne sont PAS inclus dans cette archive.\n'
        )
        instructions.setWordWrap(True)
        instructions.setAlignment(Qt.AlignTop)
        instructions.setStyleSheet('font-size: 14px; line-height: 1.4;')
        outer.addWidget(instructions)
        outer.addStretch()


    def _build_online(self):
        outer = QVBoxLayout(self.online_page)
        outer.setContentsMargins(30, 25, 30, 25)
        heading = QLabel('Catalogue mondial — Neurix Group')
        heading.setObjectName('hero')
        outer.addWidget(heading)
        note = QLabel('Update Manager : recherche au demarrage et catalogue mondial. Aucune installation automatique. La comparaison porte sur les installateurs en cache, pas sur les applications installees.')
        note.setWordWrap(True)
        outer.addWidget(note)
        actions = QHBoxLayout()
        reload_btn = QPushButton('Actualiser depuis GitHub')
        reload_btn.clicked.connect(self.refresh_remote)
        actions.addWidget(reload_btn)
        actions.addStretch()
        outer.addLayout(actions)
        self.online_status = QLabel('Clique sur Actualiser pour consulter les versions publiees.')
        self.online_status.setWordWrap(True)
        outer.addWidget(self.online_status)
        self.update_status = QLabel('Recherche de mises a jour en attente...')
        self.update_status.setWordWrap(True)
        outer.addWidget(self.update_status)
        self.update_button = QPushButton('Voir la derniere version disponible')
        self.update_button.setEnabled(False)
        self.update_button.clicked.connect(self.select_latest_update)
        outer.addWidget(self.update_button)
        self.online_list = QListWidget()
        self.online_list.currentItemChanged.connect(self.remote_selected)
        outer.addWidget(self.online_list, 1)
        self.online_detail = QLabel('Selectionne une version pour voir ses informations.')
        self.online_detail.setWordWrap(True)
        outer.addWidget(self.online_detail)
        self.online_progress = QProgressBar()
        self.online_progress.setRange(0,100)
        self.online_progress.setValue(0)
        outer.addWidget(self.online_progress)
        self.online_download = QPushButton('Telecharger et verifier dans le cache')
        self.online_download.setObjectName('primary')
        self.online_download.setEnabled(False)
        self.online_download.clicked.connect(self.download_remote)
        outer.addWidget(self.online_download)

    def run_remote(self, mode, entry=None):
        if self.remote_thread is not None:
            return
        self.online_download.setEnabled(False)
        self.online_status.setText('Recherche des nouvelles versions...' if mode == 'catalog' else 'Telechargement en cours...')
        self.remote_thread = QThread(self)
        self.remote_worker = RemoteWorker(mode, entry)
        self.remote_worker.moveToThread(self.remote_thread)
        self.remote_thread.started.connect(self.remote_worker.run)
        self.remote_worker.progress.connect(self.online_progress.setValue)
        self.remote_worker.finished.connect(self.remote_finished)
        self.remote_worker.finished.connect(self.remote_thread.quit)
        self.remote_thread.finished.connect(self.remote_thread.deleteLater)
        self.remote_thread.finished.connect(self.remote_worker.deleteLater)
        self.remote_thread.finished.connect(self.remote_cleanup)
        self.remote_thread.start()

    def remote_cleanup(self):
        self.remote_thread = None
        self.remote_worker = None
        self.remote_selected(None, None)

    def refresh_remote(self):
        if self.remote_thread is not None:
            return
        self.online_progress.setValue(0)
        self.run_remote('catalog')

    def remote_finished(self, mode, value, error):
        if error:
            self.online_status.setText(error + ' — la bibliotheque locale reste disponible.')
            if mode == 'catalog': self.update_status.setText('Mode hors ligne : impossible de verifier les mises a jour.')
            return
        if mode == 'catalog':
            self.remote_releases = value
            self.online_list.clear()
            for i, release in enumerate(value):
                item = QListWidgetItem(f"Neurix AI {release['channel'].capitalize()} {release['version']}    •    {release['size_bytes']/1048576:.1f} Mio")
                item.setData(Qt.UserRole, i)
                self.online_list.addItem(item)
            self.online_status.setText(f'{len(value)} version(s) publique(s) disponible(s).' if value else 'Aucune version publique dans le catalogue.')
            self.show_update_summary()
        else:
            try:
                record = self.cache_engine.add(Path(value))
                self.refresh_cache()
                self.show_update_summary()
                self.online_status.setText('Telechargement verifie et copie dans le cache. Lance le Setup depuis Versions en cache apres confirmation.')
                QMessageBox.information(self, 'Telechargement verifie', f"Version {record['version']} ajoutee au cache local. Aucun installateur n'a ete lance.")
            except Exception as exc:
                self.online_status.setText('Erreur lors de la mise en cache : ' + str(exc))
            finally:
                Path(value).unlink(missing_ok=True)

    def remote_selected(self, current, previous):
        item = self.online_list.currentItem()
        if item is None:
            self.online_download.setEnabled(False)
            self.online_detail.setText('Aucune version selectionnee.')
            return
        index = item.data(Qt.UserRole)
        if not isinstance(index,int) or index >= len(self.remote_releases):
            return
        r = self.remote_releases[index]
        self.online_detail.setText(f"{r['filename']}  |  SHA-256: {r['sha256']}\n{r['notes']}")
        already = r['sha256'].lower() in cached_hashes(self.cache_engine.entries)
        self.online_download.setText('Deja dans le cache (verifie)' if already else 'Telecharger la mise a jour (SHA-256)')
        self.online_download.setEnabled(self.remote_thread is None and not already)

    def select_latest_update(self):
        latest = newest_remote(self.remote_releases)
        if latest is None:
            return
        for index, r in enumerate(self.remote_releases):
            if r is latest:
                self.online_list.setCurrentRow(index)
                return

    def show_update_summary(self):
        try:
            info = update_summary(self.remote_releases, self.cache_engine.entries)
        except ValueError as exc:
            self.update_status.setText('Comparaison impossible : ' + str(exc))
            return
        latest = info['latest']
        self.update_button.setEnabled(bool(latest))
        if not latest:
            self.update_status.setText('Aucune version publiee : rien a comparer.')
            return
        label = f"{latest['channel'].capitalize()} {latest['version']}"
        texts = {
            'cached': f'Derniere version publique {label} deja presente dans le cache.',
            'newer': f'MISE A JOUR DISPONIBLE : {label} est plus recente que le dernier installateur en cache.',
            'available': f'NOUVEAUTE : {label} peut etre telechargee (aucun installateur local reconnu).',
            'different': f'Version publique {label} disponible. Un installateur aussi recent ou plus recent est en cache.'
        }
        self.update_status.setText(texts[info['state']] + ' Ceci ne detecte pas la version reellement installee.')
        if info['state'] in ('newer','available') and not getattr(self,'_notified_version',None) == (latest['channel'], latest['version']):
            self._notified_version = (latest['channel'], latest['version'])
            self.statusBar().showMessage('Neurix AI ' + label + ' disponible dans Catalogue mondial.', 12000)

    def download_remote(self):
        item = self.online_list.currentItem()
        if item is None or self.remote_thread is not None:
            return
        entry = self.remote_releases[item.data(Qt.UserRole)]
        confirm = QMessageBox.question(self, 'Telecharger depuis GitHub ?',
            f"Telecharger {entry['filename']} ({entry['size_bytes']/1048576:.1f} Mio) ?\n\nLe fichier sera verifie par SHA-256 et conserve dans le cache. Aucun Setup ne sera lance.\n\nLes binaires publics doivent venir de sources fiables.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.online_progress.setValue(0)
            self.run_remote('download', entry)

    def _build_cache(self):
        outer = QVBoxLayout(self.cache_page)
        outer.setContentsMargins(30, 25, 30, 25)
        outer.setSpacing(14)
        title = QLabel('Cache et versions précédentes')
        title.setObjectName('hero')
        outer.addWidget(title)
        explain = QLabel('Les installateurs sont copiés dans %APPDATA%\\NeurixHub\\installer_cache. Les originaux restent intacts. Aucune connexion GitHub.')
        explain.setObjectName('muted')
        explain.setWordWrap(True)
        outer.addWidget(explain)
        tools = QHBoxLayout()
        a = QPushButton('＋ Importer un Setup dans le cache')
        a.setObjectName('primary')
        a.clicked.connect(self.import_to_cache)
        b = QPushButton('Actualiser le cache')
        b.clicked.connect(self.refresh_cache)
        tools.addWidget(a)
        tools.addWidget(b)
        tools.addStretch()
        outer.addLayout(tools)
        self.cache_list = QListWidget()
        self.cache_list.currentItemChanged.connect(self.cache_selection_changed)
        outer.addWidget(self.cache_list, 1)
        self.cache_summary = QLabel('—')
        self.cache_summary.setObjectName('muted')
        self.cache_summary.setWordWrap(True)
        outer.addWidget(self.cache_summary)
        self.cache_detail = QLabel('Choisis une version dans la liste.')
        self.cache_detail.setWordWrap(True)
        self.cache_detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.cache_detail)
        actions = QHBoxLayout()
        self.restore_btn = QPushButton('↶ Préparer un retour arrière')
        self.restore_btn.setObjectName('primary')
        self.restore_btn.clicked.connect(self.prepare_rollback)
        self.delcache_btn = QPushButton('Supprimer du cache')
        self.delcache_btn.clicked.connect(self.delete_cached)
        actions.addWidget(self.restore_btn)
        actions.addWidget(self.delcache_btn)
        actions.addStretch()
        outer.addLayout(actions)
        warning = QLabel('Important : le rollback n’est pas une restauration automatique. Hub vérifie le Setup puis l’ouvre uniquement après confirmation. Vérifie la compatibilité et sauvegarde les données Neurix AI avant de rétrograder.')
        warning.setObjectName('muted')
        warning.setWordWrap(True)
        outer.addWidget(warning)

    def cache_selected_library(self):
        entry = self.selected()
        if entry:
            self._cache_file(Path(entry['path']))

    def import_to_cache(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Importer un installateur dans le cache', str(Path.home() / 'Downloads'), 'Installateurs Windows (*.exe)')
        if path:
            self._cache_file(Path(path))

    def _cache_file(self, path: Path):
        if QMessageBox.question(self, 'Conserver cet installateur ?',
                                f'Copier {path.name} dans le cache local Neurix Hub ?\n\nLe fichier original ne sera pas modifié.',
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            record = self.cache_engine.add(path)
        except (CacheError, OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Import impossible', str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh_cache()
        QMessageBox.information(self, 'Version conservée', f"{record['family']} {record['version']} enregistrée dans le cache.\nEmpreinte : {record['sha256']}")

    def selected_cached(self):
        item = self.cache_list.currentItem()
        if item is None:
            return None
        return next((r for r in self.cache_engine.entries if r.get('id') == item.data(Qt.UserRole)), None)

    def refresh_cache(self):
        selected = self.selected_cached()
        previous = selected.get('id') if selected else None
        self.cache_list.blockSignals(True)
        self.cache_list.clear()
        for entry in sorted(self.cache_engine.entries, key=lambda e: e.get('added',''), reverse=True):
            label = f"{entry.get('family', '?')} {entry.get('version', '?')}  •  {entry.get('name', '?')}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry.get('id'))
            self.cache_list.addItem(item)
        self.cache_list.blockSignals(False)
        n = self.cache_engine.usage() / (1024 * 1024)
        self.cache_summary.setText(f'{len(self.cache_engine.entries)} version(s) conservée(s) · {n:.1f} Mo occupés')
        if hasattr(self,'update_status') and self.remote_releases:
            self.show_update_summary()
        if self.cache_list.count():
            select_index = next((i for i in range(self.cache_list.count()) if self.cache_list.item(i).data(Qt.UserRole) == previous), 0)
            self.cache_list.setCurrentRow(select_index)
        else:
            self.cache_selection_changed(None, None)
        self.home_count.setText(f'{len(self.entries)} installateur(s) référencé(s) · {len(self.cache_engine.entries)} en cache')

    def cache_selection_changed(self, current, previous):
        entry = self.selected_cached()
        self.restore_btn.setEnabled(bool(entry))
        self.delcache_btn.setEnabled(bool(entry))
        if not entry:
            self.cache_detail.setText('Aucune version en cache.')
            return
        self.cache_detail.setText(f"{entry.get('family')} {entry.get('version')}  ·  {entry.get('size', 0)/(1024*1024):.1f} Mo\nSHA-256 : {entry.get('sha256')}\nConservé le : {entry.get('added')}")

    def prepare_rollback(self):
        entry = self.selected_cached()
        if not entry:
            return
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            target = self.cache_engine.verify(entry)
        except (CacheError, OSError) as exc:
            QMessageBox.critical(self, 'Vérification échouée', str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
        text = (f"Préparer un retour à {entry['family']} {entry['version']} ?\n\n"
                f"Installateur vérifié : {target.name}\n\n"
                "ATTENTION : sauvegarde d'abord tes conversations, projets et bases SQLite Neurix AI. "
                "Une ancienne version peut ne pas comprendre les données d'une version récente.\n\n"
                "Hub ne désinstallera rien automatiquement et ne modifiera aucune base de données. "
                "Il ouvrira seulement l'ancien installateur, dont tu contrôleras les étapes.\n\n"
                "Continuer ?")
        if QMessageBox.question(self, 'Retour arrière — confirmation', text,
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            subprocess.Popen([str(target)], cwd=str(target.parent), close_fds=True)
            QMessageBox.information(self, 'Installateur ouvert', 'Le Setup a été lancé. Le retour arrière n’est pas encore confirmé : suis les étapes de l’installateur et teste l’application ensuite.')
        except OSError as exc:
            QMessageBox.critical(self, 'Lancement impossible', str(exc))

    def delete_cached(self):
        entry = self.selected_cached()
        if not entry:
            return
        if QMessageBox.question(self, 'Supprimer du cache ?',
                                f"Supprimer la copie en cache de {entry['family']} {entry['version']} ?\n\nL’installateur original ne sera pas touché.",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.cache_engine.remove(entry)
        except (CacheError, OSError) as exc:
            QMessageBox.warning(self, 'Suppression impossible', str(exc))
            return
        self.refresh_cache()

    def add_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Sélectionne un installateur Windows', str(Path.home()/'Downloads'), 'Installateurs Windows (*.exe)')
        if path:
            self._add_path(Path(path))

    def scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Choisis un dossier à scanner', str(Path.home()/'Downloads'))
        if not folder:
            return
        root = Path(folder)
        found = 0
        # Depth-bounded scan, no symlink following. Avoid surprising whole-disk traversal.
        todo = [(root, 0)]
        while todo:
            current, depth = todo.pop()
            try:
                for child in current.iterdir():
                    if child.is_symlink():
                        continue
                    if child.is_dir() and depth < 4 and child.name.lower() not in {'.venv', 'node_modules', 'build', '_internal'}:
                        todo.append((child, depth + 1))
                    elif is_setup(child):
                        if self._add_path(child, quiet=True):
                            found += 1
            except OSError:
                continue
        self.refresh()
        QMessageBox.information(self, 'Recherche terminée', f'{found} nouvel(s) installateur(s) ajouté(s).')

    def _add_path(self, path: Path, quiet=False) -> bool:
        if not is_setup(path):
            if not quiet:
                QMessageBox.warning(self, 'Fichier non reconnu', 'Choisis un fichier .exe dont le nom contient Setup, Installer ou Install.')
            return False
        resolved = str(path.resolve())
        if any(e.get('path', '').lower() == resolved.lower() for e in self.entries):
            if not quiet:
                QMessageBox.information(self, 'Déjà présent', 'Cet installateur est déjà dans la bibliothèque.')
            return False
        version, title = version_info(path.name)
        self.entries.append({'path': resolved, 'version': version, 'title': title,
                             'sha256': '', 'added': datetime.now().isoformat(timespec='seconds')})
        save_db(self.entries)
        if not quiet:
            self.refresh()
            self.select_path(resolved)
        return True

    def refresh(self):
        old = self.active_path
        self.listing.blockSignals(True)
        self.listing.clear()
        for entry in sorted(self.entries, key=lambda e: e.get('added', ''), reverse=True):
            path = Path(entry['path'])
            flag = '●' if path.is_file() else '○'
            name = f"{flag}  {entry.get('version', 'Inconnue')}  •  {path.name}"
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, entry['path'])
            self.listing.addItem(item)
        self.listing.blockSignals(False)
        self.home_count.setText(f'{len(self.entries)} installateur(s) référencé(s) · {len(self.cache_engine.entries)} en cache')
        if old:
            self.select_path(old)
        elif self.listing.count():
            self.listing.setCurrentRow(0)
        else:
            self.selection_changed(None, None)

    def select_path(self, path: str):
        for i in range(self.listing.count()):
            if self.listing.item(i).data(Qt.UserRole) == path:
                self.listing.setCurrentRow(i)
                return

    def selected(self) -> Optional[dict]:
        item = self.listing.currentItem()
        if not item:
            return None
        return next((e for e in self.entries if e['path'] == item.data(Qt.UserRole)), None)

    def selection_changed(self, current, previous):
        entry = self.selected()
        self.active_path = entry['path'] if entry else None
        self.version_label.setText(entry.get('version', 'Inconnue') if entry else '—')
        self.file_label.setText(entry['path'] if entry else '—')
        self.sha_label.setText(entry.get('sha256') or 'Calcul en cours…' if entry else '—')
        valid = bool(entry and Path(entry['path']).is_file())
        self.state_label.setText('Fichier présent' if valid else 'Fichier absent' if entry else '—')
        self.install_btn.setEnabled(valid and self.hash_thread is None)
        self.remove_btn.setEnabled(bool(entry))
        self.cache_selected_btn.setEnabled(valid)
        if valid and not entry.get('sha256') and self.hash_thread is None:
            self.hash_selected(entry['path'])

    def hash_selected(self, path: str):
        self.progress.show()
        self.status.setText('Calcul SHA-256 en cours…')
        self.install_btn.setEnabled(False)
        self.hash_thread = QThread(self)
        self.hash_worker = HashWorker(path)
        self.hash_worker.moveToThread(self.hash_thread)
        self.hash_thread.started.connect(self.hash_worker.run)
        self.hash_worker.completed.connect(self.hash_done)
        self.hash_worker.completed.connect(self.hash_thread.quit)
        self.hash_worker.completed.connect(self.hash_worker.deleteLater)
        self.hash_thread.finished.connect(self._thread_finished)
        self.hash_thread.finished.connect(self.hash_thread.deleteLater)
        self.hash_thread.start()

    def hash_done(self, path: str, value: str, error: str):
        entry = next((e for e in self.entries if e['path'] == path), None)
        if entry and value:
            entry['sha256'] = value
            save_db(self.entries)
        self.progress.hide()
        if path == self.active_path:
            self.sha_label.setText(value or 'Erreur de lecture')
        self.status.setText(f'Échec du calcul : {error}' if error else 'Empreinte calculée. Ce hash ne prouve pas à lui seul que le fichier est sûr.')

    def _thread_finished(self):
        self.hash_thread = None
        self.hash_worker = None
        self.install_btn.setEnabled(bool(self.selected() and Path(self.selected()['path']).is_file()))
        # A new selection may still require hashing.
        entry = self.selected()
        if entry and not entry.get('sha256') and Path(entry['path']).is_file():
            self.hash_selected(entry['path'])

    def remove_selected(self):
        entry = self.selected()
        if not entry:
            return
        if QMessageBox.question(self, 'Retirer de la bibliothèque',
            'Retirer cette entrée ? Le fichier sur le disque ne sera PAS supprimé.') != QMessageBox.Yes:
            return
        self.entries.remove(entry)
        self.active_path = None
        save_db(self.entries)
        self.refresh()

    def launch_setup(self):
        entry = self.selected()
        if not entry:
            return
        path = Path(entry['path'])
        if not is_setup(path):
            QMessageBox.warning(self, 'Installateur introuvable', 'Le fichier a été déplacé ou renommé.')
            return
        if self.hash_thread is not None:
            QMessageBox.information(self, 'Patiente', 'La vérification est en cours.')
            return
        self.status.setText('Vérification du fichier avant lancement…')
        QApplication.processEvents()
        try:
            actual = digest_file(path)
        except OSError as exc:
            QMessageBox.critical(self, 'Erreur de lecture', str(exc))
            return
        expected = entry.get('sha256', '')
        if expected and actual.lower() != expected.lower():
            QMessageBox.critical(self, 'Fichier modifié !',
                'Son empreinte SHA-256 a changé depuis son ajout. Retire-le puis vérifie son origine avant de l’ajouter à nouveau.')
            return
        if not expected:
            entry['sha256'] = actual
            save_db(self.entries)
        question = (
            f"Lancer cet installateur ?\n\n{path.name}\n\n"
            f"Version détectée : {entry.get('version')}\n"
            f"Emplacement : {path}\n\n"
            'Vérifie que tu connais et fais confiance à la provenance du fichier. '
            'Windows peut encore demander une confirmation ou bloquer l’application.'
        )
        if QMessageBox.question(self, 'Confirmer le lancement', question,
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            self.status.setText('Installation annulée.')
            return
        try:
            # Windows opens .exe directly; no shell, no privilege escalation or automatic UAC bypass.
            subprocess.Popen([str(path)], cwd=str(path.parent), close_fds=True)
            self.status.setText('Installateur ouvert. Suis les étapes Windows.')
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, 'Impossible de lancer', str(exc))
            self.status.setText('Lancement impossible.')


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Neurix Hub')
    app.setStyle('Fusion')
    w = Hub()
    w.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
