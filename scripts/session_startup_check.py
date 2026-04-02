"""
Session startup gate.
Validates environment before any extraction work begins.
Must pass before touching any game data.
"""
import os
import sys
import hashlib
import sqlite3
import json

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, 'data', 'pipeline.db')
JSFX_SOURCE = os.path.join(REPO_ROOT, 'studio', 'jsfx', 'ReapNES_Console.jsfx')
JSFX_ALT_SOURCE = r'C:\Dev\ReapNES-Studio\jsfx\ReapNES_Console.jsfx'
JSFX_INSTALLED = os.path.join(
    os.path.expanduser('~'),
    'AppData', 'Roaming', 'REAPER', 'Effects',
    'ReapNES Studio', 'ReapNES_Console.jsfx'
)


def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def check_ascii(path):
    if not os.path.exists(path):
        return False, 'file not found'
    with open(path, 'rb') as f:
        data = f.read()
    for i, b in enumerate(data):
        if b > 127:
            line = data[:i].count(b'\n') + 1
            return False, f'non-ASCII byte 0x{b:02x} at line {line}'
    return True, 'clean'


def run_checks(game_slug=None):
    results = []
    all_pass = True

    # A1. JSFX source exists
    source_path = JSFX_ALT_SOURCE if os.path.exists(JSFX_ALT_SOURCE) else JSFX_SOURCE
    if os.path.exists(source_path):
        results.append(('A1', 'PASS', f'JSFX source exists: {source_path}'))
    else:
        results.append(('A1', 'FAIL', f'JSFX source not found'))
        all_pass = False

    # A2. JSFX installed exists
    if os.path.exists(JSFX_INSTALLED):
        results.append(('A2', 'PASS', f'JSFX installed exists'))
    else:
        results.append(('A2', 'FAIL', f'JSFX not installed at {JSFX_INSTALLED}'))
        all_pass = False

    # A3. JSFX hashes match
    src_hash = file_hash(source_path) if os.path.exists(source_path) else None
    inst_hash = file_hash(JSFX_INSTALLED)
    if src_hash and inst_hash and src_hash == inst_hash:
        results.append(('A3', 'PASS', 'JSFX source and installed match'))
    elif src_hash and inst_hash:
        results.append(('A3', 'FAIL', 'JSFX source and installed DIFFER — need sync'))
        all_pass = False
    else:
        results.append(('A3', 'FAIL', 'Cannot compare JSFX hashes'))
        all_pass = False

    # A4. JSFX ASCII clean
    for label, path in [('source', source_path), ('installed', JSFX_INSTALLED)]:
        if os.path.exists(path):
            clean, detail = check_ascii(path)
            if clean:
                results.append(('A4', 'PASS', f'JSFX {label} ASCII clean'))
            else:
                results.append(('A4', 'FAIL', f'JSFX {label}: {detail}'))
                all_pass = False

    # A5. Database exists
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            conn.close()
            expected = {'games', 'source_files', 'captures', 'frame_states',
                        'validation_runs', 'track_names'}
            missing = expected - set(tables)
            if not missing:
                results.append(('A5', 'PASS', f'Database OK ({len(tables)} tables)'))
            else:
                results.append(('A5', 'FAIL', f'Missing tables: {missing}'))
                all_pass = False
        except Exception as e:
            results.append(('A5', 'FAIL', f'Database error: {e}'))
            all_pass = False
    else:
        results.append(('A5', 'FAIL', f'Database not found at {DB_PATH}'))
        all_pass = False

    # A6. Game-specific: track manifest exists
    if game_slug:
        manifest_paths = [
            os.path.join(REPO_ROOT, 'extraction', 'manifests', f'{game_slug}.json'),
            os.path.join(REPO_ROOT, 'specs', 'game_registry.json'),
        ]
        # Check track_names in DB
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            count = conn.execute(
                "SELECT COUNT(*) FROM track_names tn "
                "JOIN games g ON tn.game_id = g.id WHERE g.slug = ?",
                (game_slug,)
            ).fetchone()[0]
            conn.close()
            if count > 0:
                results.append(('A6', 'PASS', f'Track names in DB: {count} tracks'))
            else:
                results.append(('A6', 'WARN', f'No track names in DB for {game_slug}'))

    # Print results
    print(f"\n{'='*60}")
    print(f"SESSION STARTUP CHECK")
    if game_slug:
        print(f"Game: {game_slug}")
    print(f"{'='*60}")
    for check_id, status, detail in results:
        icon = {'PASS': '+', 'FAIL': '!', 'WARN': '?'}[status]
        print(f"  [{icon}] {check_id}: {status} — {detail}")
    print(f"{'='*60}")
    print(f"OVERALL: {'PASS' if all_pass else 'FAIL'}")
    print(f"{'='*60}\n")

    return all_pass


if __name__ == '__main__':
    game = sys.argv[1] if len(sys.argv) > 1 else None
    ok = run_checks(game)
    sys.exit(0 if ok else 1)
