"""Copy the project's shareable files into a clone of smh4004/Gero-legacy-tools (then commit and push from there).
Allowlist only: code, the mod's own data, docs, and the cleaned LoG4 art. Never ROMs, ROM-extracted data, builds,
or the game's text (text goes as log4/text_edits.json deltas: tools/text_edits.py make).
usage: python3 tools/sync_repo.py <project root> <repo clone>"""
import os, shutil, sys, fnmatch

SKIP_TOOLS = {'bf_actor_colors.json', 'bf_objpal.json', 'bf_ui_obj_colors.json'}    # palettes dumped from the ROM
SKIP_DIRS = {'out', 'text', '__pycache__', 'raw', 'portraits64', 'alternates'}


def main(src, dst):
    n = 0
    def cp(p):
        nonlocal n
        d = os.path.join(dst, p); os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(os.path.join(src, p), d); n += 1
    for f in ('HANDOFF.md', 'RE_NOTES.md', 'PROMPT_buusfury_disassembly.md', 'lz.py'):
        if os.path.exists(os.path.join(src, f)): cp(f)
    for f in sorted(os.listdir(os.path.join(src, 'tools'))):
        p = 'tools/' + f
        if os.path.isfile(os.path.join(src, p)) and (f.endswith(('.py', '.c')) or f == 'refs_ok.json') and f not in SKIP_TOOLS:
            cp(p)
    for root, dirs, files in os.walk(os.path.join(src, 'log4')):
        rel = os.path.relpath(root, src)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = os.path.join(rel, f)
            if rel.startswith('log4/asm') and f.endswith(('.s', '.md', '.bin')): cp(p)
            elif rel == 'log4/art/clean' and f.endswith('.png') and not fnmatch.fnmatch(f, 'review_*'): cp(p)
            elif f.endswith(('.py', '.json', '.scene', '.md', '.txt')): cp(p)
    print('%d files copied into %s' % (n, dst))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
