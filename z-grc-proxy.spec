# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['zgrc/proxy.main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'zgrc',
        'zgrc.proxy',
        'zgrc.proxy.handlers',
        'zgrc.policy',
        'zgrc.policy.pre_checker',
        'zgrc.policy.post_checker',
        'zgrc.policy.Quota',
        'zgrc.client',
        'zgrc.client.api_client',
        'zgrc.auth',
        'zgrc.context',
        'zgrc.utils',
        'zgrc.utils.exceptions',
        'mitmproxy',
        'mitmproxy.tools.dump',
        'mitmproxy.options',
        'mitmproxy.http',
        'mitmproxy.proxy',
        'mitmproxy.proxy.mode_servers',
        'mitmproxy.proxy.server',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='z-grc-proxy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
