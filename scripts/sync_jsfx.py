"""
Sync JSFX from source to REAPER install path, bust cache, verify ASCII.
Run after ANY JSFX edit.
"""
import os
import sys
import shutil
import hashlib

JSFX_SOURCE = r'C:\Dev\ReapNES-Studio\jsfx\ReapNES_Console.jsfx'
JSFX_INSTALLED = os.path.join(
    os.path.expanduser('~'),
    'AppData', 'Roaming', 'REAPER', 'Effects',
    'ReapNES Studio', 'ReapNES_Console.jsfx'
)


def check_ascii(path):
    with open(path, 'rb') as f:
        data = f.read()
    for i, b in enumerate(data):
        if b > 127:
            line = data[:i].count(b'\n') + 1
            return False, f'non-ASCII byte 0x{b:02x} at line {line}'
    return True, 'clean'


def main():
    if not os.path.exists(JSFX_SOURCE):
        print(f'ERROR: Source not found: {JSFX_SOURCE}')
        return False

    # 1. ASCII check
    clean, detail = check_ascii(JSFX_SOURCE)
    if not clean:
        print(f'ERROR: Source has Unicode: {detail}')
        return False
    print(f'[+] ASCII check: {detail}')

    # 2. Copy to install path
    os.makedirs(os.path.dirname(JSFX_INSTALLED), exist_ok=True)
    shutil.copy2(JSFX_SOURCE, JSFX_INSTALLED)
    print(f'[+] Copied to {JSFX_INSTALLED}')

    # 3. Cache bust (rename and back)
    temp = JSFX_INSTALLED + '.cachebust'
    os.rename(JSFX_INSTALLED, temp)
    os.rename(temp, JSFX_INSTALLED)
    print(f'[+] Cache busted')

    # 4. Verify hashes match
    src_hash = hashlib.sha256(open(JSFX_SOURCE, 'rb').read()).hexdigest()[:16]
    inst_hash = hashlib.sha256(open(JSFX_INSTALLED, 'rb').read()).hexdigest()[:16]
    if src_hash == inst_hash:
        print(f'[+] Hashes match: {src_hash}')
    else:
        print(f'[!] Hash mismatch: source={src_hash} installed={inst_hash}')
        return False

    print(f'\nJSFX sync complete.')
    return True


if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
