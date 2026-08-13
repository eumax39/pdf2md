# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path
import sys

datas = [('icone.ico', '.'), ('logo.png', '.'), ('config.json', '.'), ('assets', 'assets')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('paddleocr')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('paddlepaddle')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('paddlex')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pymupdf')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pymupdf4llm')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

_extras_ocr_modulos = [
    'bs4',
    'einops',
    'ftfy',
    'jinja2',
    'latex2mathml',
    'lxml',
    'openpyxl',
    'premailer',
    'regex',
    'sklearn',
    'scipy',
    'sentencepiece',
    'tiktoken',
    'tokenizers',
    'pypdfium2',
    'cv2',
    'shapely',
    'pyclipper',
    'bidi',              # ✅ CORRETO (módulo importado)
    'python-bidi',       # ✅ OPCIONAL (por segurança)
    'skimage',
    'imgaug',
    'albumentations',
    'lmdb',
]

for _mod in _extras_ocr_modulos:
    try:
        _ret = collect_all(_mod)
        datas += _ret[0]; binaries += _ret[1]; hiddenimports += _ret[2]
    except Exception:
        # Alguns extras podem nao existir em ambientes antigos; o build segue.
        pass

# Inclui cache local de modelos Paddle quando disponível (build offline estável).
_paddlex_cache = Path.home() / '.paddlex' / 'official_models'
if _paddlex_cache.exists():
    datas.append((str(_paddlex_cache), 'assets/paddlex/official_models'))

# Inclui DLLs do Paddle manualmente para evitar falha de carregamento no runtime.
_python_dir = Path(sys.executable).resolve().parent
_site_packages = _python_dir / 'Lib' / 'site-packages'

_paddle_lib_dirs = [
    _site_packages / 'paddle' / 'libs',
    _site_packages / 'paddle' / 'fluid',
]

for _lib_dir in _paddle_lib_dirs:
    if _lib_dir.exists():
        for _dll in _lib_dir.glob('*.dll'):
            binaries.append((str(_dll), 'paddle/libs'))

# Inclui runtimes MSVC da instalação do Python (fallback para ambientes limpos).
for _pat in ('vcruntime*.dll', 'msvcp*.dll'):
    for _dll in _python_dir.glob(_pat):
        binaries.append((str(_dll), 'paddle/libs'))


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='PDF2MD_V2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icone.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PDF2MD_V2',
)
