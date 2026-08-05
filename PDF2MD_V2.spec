# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ
from PyInstaller.utils.hooks import collect_all

project_root = Path.cwd()
icon_path = project_root / "icone.ico"
model_cache = Path.home() / ".paddlex" / "official_models"

datas = []
binaries = []
hiddenimports = []

for package in ("customtkinter", "tkinterdnd2", "paddleocr", "paddlex", "paddle", "pymupdf", "pymupdf4llm"):
    pkg_datas, pkg_bins, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_bins
    hiddenimports += pkg_hidden

for resource_name in ("config.json", "historico_projetos.json", "icone.ico", "logo.png"):
    resource_path = project_root / resource_name
    if resource_path.exists():
        datas.append((str(resource_path), "."))

if model_cache.exists():
    datas.append((str(model_cache), "assets/paddlex/official_models"))


a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["tkinterdnd2"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDF2MD_V2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="PDF2MD_V2",
)
