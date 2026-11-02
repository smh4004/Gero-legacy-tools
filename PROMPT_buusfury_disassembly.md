# Prompt: build a matching disassembly of Dragon Ball Z: Buu's Fury (GBA)

Copy everything below the line into a new Claude session. Attach:
(1) your own dump of **Dragon Ball Z - Buu's Fury (USA).gba**,
(2) **LoG4_project_handoff.zip** (from the earlier project: RE notes, tools, extracted indexes).

---

## Who I am and what I want

I'm making a personal, non-commercial ROM hack ("Legacy of Goku 4") on top of **Dragon Ball Z: Buu's Fury (USA)** for the Game Boy Advance.
In an earlier session we reverse-engineered its data formats: compression, text, script VM, maps, palettes, sprite storage.
That work is in the attached `LoG4_project_handoff.zip`. Read `HANDOFF.md` and `RE_NOTES.md` from it first.

Now I want a **matching disassembly project** for Buu's Fury, in the style of the pret projects (pokeemerald / pokefirered in their early
days). It's a source tree that rebuilds a **byte-identical ROM** from assembly plus extracted data, with code and data **labeled and
relocatable**. Deeper hacks (new mechanics, more content, moving data freely) then become source edits instead of hex surgery.
A full C decompilation is **not** the goal of this session. It's an optional later phase you should scope at the end.

Work autonomously in phases, keep a task list, and check in with me only at the decision points marked **[ASK]**.
Verify every claim by building and comparing. Never say something matches without checking the SHA-1.

## Inputs and facts you can rely on

- Base ROM: 8 MB, game code `BG3E`, SHA-1 `f1c4b07554d2a3b1ad2f325307051e775ce68087`. Refuse any other dump.
- Developer: Webfoot Technologies (published by Atari, 2004). Same engine as Legacy of Goku 2 (debug strings `T:\Source\ByteCodeInterpreter\...`,
  `GameData.cpp`, `AreaEntry.cpp`, `CharacterData.cpp`), so the game is **C++**.
- Toolchain hints to verify, not assume: Thumb-to-ARM veneers of the form `bx pc; nop; ldr pc,[pc,#-4]; .word target` at 0x08049120+
  (GNU ld interworking style), a division helper at 0x08046E58, and hot ARM routines copied to IWRAM (WFZ decompressor at
  ROM 0x7B79A4 -> 0x03000000). Identify the compiler and linker (GCC 2.9x/3.x via devkitadv vs ARM SDT/ADS) from prologues,
  literal-pool layout, veneers and libgcc/libc fingerprints. Report the evidence.
- Known addresses (bus addresses 0x08xxxxxx unless noted). Use them to seed symbols:
  - Script VM loop 0x08004064; opcode table 0x080554C0 (31 entries); native function table 0x08055098 (248); setter table 0x08055478 (18)
  - Script entry 0x08004038; WFZ container loader 0x0803D944; area lookup 0x080089FC; area table 0x0808E2E0 (452 x 56 bytes)
  - Text bank table 0x087B5B64 (7 WFZ banks); string loaders 0x08012230 / 0x080122B4; UI string pointer list 0x0806BCE8 (1534)
  - Global 24-bit master palette 0x080701B0 (512 entries), fade routine 0x08007074
  - Tile-upload loop 0x08009BD4; animated tiles 0x08009B12/0x08009B80; EXP table 0x086B7084 (151 x u32); equipment 0x086F82EC (162 x 44 bytes)
  - About 13,180 WFZ-compressed blocks (`tools/scan_wfz.py`); map records listed in `run3/maps_bf.json`; sprite frame records in `run3/frames_bf.json`
  - Format details for all of the above: `RE_NOTES.md`.

## Environment

You're in a Linux cloud container (ephemeral: deliver work as files or a git repo regularly so nothing is lost).
- `apt-get install -y gcc-arm-none-eabi binutils-arm-none-eabi libmgba-dev mgba-sdl libpng-dev` (check what's available).
- `pip install --break-system-packages capstone numpy pillow`.
- Ghidra or other heavy tools: only if they install cleanly. Python + capstone + GNU binutils is enough.
- Build the headless mGBA harness from the handoff zip (`tools/harness.c`, `tracer.c`, `scriptlog.c`; see HANDOFF.md) for boot and smoke tests.
- Look for existing GBA disassembly tooling on GitHub and package registries before writing your own (e.g. pret's `gbadisasm`,
  Luvdis, agbcc-era Makefile patterns). Use what fits; write your own where it doesn't.

## Hard rules (legal and hygiene)

- **Never commit or distribute ROM bytes or extracted game assets.** Like pret projects, everything copyrighted is pulled at build
  time from the user's `baserom.gba` (checked by SHA-1): `incbin` ranges, extraction scripts, `.gitignore` for `baserom.gba` and all extracted
  files. The repo itself must contain only original code you write: assembly text that is mechanically derived is fine to keep
  locally, but flag before ever pushing it anywhere public **[ASK]**.
- Never claim "matching" without `sha1sum` of the built ROM equal to the base ROM.

## Phases

### Phase 0: Setup and reconnaissance
1. Verify the ROM SHA-1. Unzip the handoff, read HANDOFF.md and RE_NOTES.md.
2. Install the toolchain; confirm `arm-none-eabi-as/ld/objcopy` work.
3. Map the ROM: header, crt0/entry (0x080000C0), code regions vs data regions. Use the WFZ block scan, pointer-table scans and code
   discovery from the entry point plus all known function tables (VM tables, vtables, callbacks in area entries) to classify bytes.
4. Identify the compiler (see hints). Write `docs/toolchain.md` with evidence.
**Deliverable:** a region map (`docs/rom_map.md`, plus a machine-readable `config/regions.yaml`) covering 100% of the ROM as code, data,
compressed data, padding or unknown.

### Phase 1: Matching build (the core goal)
1. Create the repo skeleton: `Makefile`, `ld_script.ld`, `asm/`, `data/`, `include/`, `tools/`, `config/`, `docs/`, `README.md`.
2. Disassemble all code regions into GNU `as` syntax (Thumb and ARM, correct `.thumb_func`/`.arm` modes, literal pools emitted
   as data, alignment preserved). Non-code regions start as `incbin` from `baserom.gba`.
3. `make` -> `buusfury.gba`; `make compare` checks the SHA-1. Iterate until it **matches byte for byte**.
**Deliverable:** clean `make && make compare` from a fresh clone + baserom. Commit (local git) and send me a zip **[ASK: create a
private GitHub repo if a GitHub connection is available?]**.

### Phase 2: Labels and shiftability (what makes it useful)
1. Replace every absolute pointer (in code literal pools AND data tables) with a symbol. Find pointers by value range plus
   validation (target is a known function, a data label, or a WFZ block). Treat ambiguous values conservatively and list them.
2. Name known functions and tables from RE_NOTES (VM, loaders, palette, tables above). Use `sub_0800XXXX` / `gUnknown_0800XXXX`
   for the rest, consistently.
3. **Shift test:** insert padding (e.g. 0x100 bytes) early in the ROM, rebuild, and boot it in the headless mGBA harness through the
   title screen, a new game and the first area (scripts in the handoff: `tools/harness`). Compare screenshots with the matching build. Any crash
   = a missed pointer; find it with `tracer` and fix. Repeat until shifting is safe.
**Deliverable:** a shiftable build plus `docs/shifting.md` (method, known risks, the remaining unknown pointers).

### Phase 3: Data as editable assets
1. Split data into per-asset files: text banks, UI strings, script/event blocks, area table, map records, tile pages, chunks, collision,
   sprite frames, palettes, equipment, EXP table.
2. Extraction tools convert them to editable forms at build time: `.json`/`.csv` for tables, PNG (indexed) for graphics, text files
   for dialogue (reuse `tools/text_tool.py` logic), and keep the original compressed blobs for a matching build.
3. Write a **WFZ compressor** (format in RE_NOTES / `tools/wfz.py`) so edited assets recompress. Matching builds keep the original blobs;
   modified assets are recompressed and verified by decompress-roundtrip. Also confirm whether loaders accept stored (type 0) containers
   everywhere. Document where they do and where they don't.
4. Add a `make modern`-style path (or flag) that builds from the edited assets (non-matching allowed) and boots in the harness.
**Deliverable:** editing one dialogue line, one palette color and one map tile from source produces a working ROM.

### Phase 4: Scope the C decompilation (report only)
Using the identified toolchain, try to match 3-5 small functions in C/C++ (e.g. VM opcode handlers at 0x08003C74+, which are tiny).
Report: compiler and flags that match (or why none do yet), effort estimate, recommended workflow (decomp.me-style
per-function matching, objdiff), and whether it's worth it for my hack **[ASK]**.

## Working style
- Keep a running `docs/progress.md` (what's done, what's verified, open problems) and update `HANDOFF.md`-style notes at the end.
- Prefer small verified steps: after each change, rebuild and compare.
- When stuck, trace in the emulator rather than guessing.
- Report back in plain language: what works, what's verified and how, and what's next. No long logs in chat; put them in files.
- At the end, deliver: the repo as a zip (or GitHub repo), `docs/`, and a short summary of matching status, shiftability and editable assets.

## Later (don't do now, but keep the design compatible)
- Port my Legacy of Goku 4 build (text pipeline, art pipeline in `tools/artclean.py`, `log4/`) onto this disassembly.
- The same treatment for Legacy of Goku 2 (same engine; its image is the second half of the LoG I&II combo cart, rebased to 0x08800000).
