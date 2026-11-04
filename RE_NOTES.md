# LoG4 reverse-engineering notes

All offsets are ROM file offsets unless written as 0x08xxxxxx (GBA bus address).
"Verified" = checked against emulator RAM or on-screen output. "Inferred" = read from code only.

## Buu's Fury (USA) — the base ROM
SHA1 f1c4b07554d2a3b1ad2f325307051e775ce68087, 8 MB, code BG3E, last data 0x7B89A6.

### Compression "WFZ" (verified)
- Container: u32 type (0 = stored, 1/2 = compressed), u32 decompressed size, then a bitstream of 32-bit LE words read MSB-first.
- aPLib-like LZ with Webfoot extensions (7/8-bit literal modes with base, adjustable offset width, raw 256-byte blocks).
- Game copies the decoder from ROM 0x7B79A4 to IWRAM 0x03000000; the entry point is 0x03000040. Caller 0x0803D944.
- Python port: tools/wfz.py. First 55 KB of text bank 0 match emulator RAM byte-for-byte.
- Whole-ROM scan (tools/scan_wfz.py): about 13,180 WFZ blocks hold most of the ROM (5.2 MB compressed, 27.8 MB decompressed).

### Text (verified)
- Dialogue: 7 WFZ banks, pointer table at 0x7B5B64: 0x79BF2C, 0x7A04F0, 0x7A46C8, 0x7A8AD8, 0x7AD118, 0x7B1558, 0x7B5AA0. About 196k UTF-16 chars, no terminators. Dumped to dump/text/bank*.txt.
- String reference = packed u32: bank = bits 0-5, char offset = bits 6-20, length = bits 21-31. Loader 0x08012230 / 0x080122B4 decompresses the whole bank into a 64 KB heap buffer.
- Control codes: 0x08 NN = color (07 highlight, 02 normal, 05 label, 03 value ...), 0x0B = page break, %s/%d printf.
- UI strings: 1,534 UTF-16 strings via the pointer list at 0x6BCE8 (index-based). Dumped to dump/text/ui_strings.json.

### Script VM (verified by runtime log)
- Interpreter loop at 0x08004064; opcode table at 0x080554C0 (31 opcodes).
  00 push u8 | 01 push varint (7-bit groups, MSB-first, low bit = sign) | 02 call native[u8] | 03 set var[u8] = pop
  04 AND 05 OR 06 NEG 07 ADD 08 SUB 09 MUL 0A DIV 1E MOD | 0B EQ 0C NE 0D GT 0E GE 0F LT 10 LE
  11 END | 12 JMP s16 (big-endian, relative) | 13 JZ s16 | 14 POP | 15-1A inc/dec variants on var[u8]
  1B push loop counter | 1C loop back u16 | 1D push N varints
- Native functions: 248 at 0x08055098; settable vars: 18 at 0x08055478. Observed: 0x72/0x73 = load scene/area
  (world, area, ...) via 0x08009030; 0x88 = wait frames; 0x23 = music(?); 0x6B = camera pan(?);
  0x1F/0x21 = area-related; 0x7A/0x7B/0x78/0x79 = fades(?); 0xB2 = place actor(?). Names are inferred.
- Scripts and events are stored raw (uncompressed), e.g. the intro at 0x77CAD7 and Other World events at ~0x7804F4.
- Event step record: u16 step id, u8 type; type 5 = dialogue (u8 speaker id, u32 string ref); type 0 = inline bytecode up to 0x11.
  Speaker ids seen: 0x02 Goku, 0x57 King Kai, 0x00 narrator.
- The intro movie is ordinary scripts plus scene loads with real maps and sprites, so an epilogue cutscene can be authored the same way.

### Areas
- AreaEntry table 0x08E2E0: 452 entries x 56 bytes. Byte 0 = world (0x00-0x16), byte 1 = area. Includes a music(?) field and pointers to script/event lists (0x0807xxxx-0x0808xxxx).
- Lookup routine 0x080089FC. 184 area names among the UI strings.

### Maps (decoded; same format in BF and LoG2; render verified pixel-aligned against a live Snake Way screen)
- Count: BF 188 map records (tools/find_maps.py), LoG2 112. Area link: AreaEntry +0x2C -> area struct, whose +0 = map pointer P.
  Area name = AreaEntry +0x0C (u16 UI string index; BF names 521-596, LoG2 ASCII string table at slice 0xE28F8).
  BF: 186 area entries link to maps (45 location names); LoG2: 111 (28 names, including Dr. Gero's Lab x5, Capsule Corp, New Namek).
- Map record. The code's object pointer is P; tools use M = P - 4. Offsets below are from M:
  +0x04 blend: low 16 = BLDCNT, high 16 = BLDALPHA (e.g. Gero's Lab 0x10091E41 = BG0 additive light over BG1-3)
  +0x10 animated-tile count, +0x14 list -> def {u8 frames, u8 tiles, u16 dest tile slot, frame ptrs}; frame = {u32 duration, raw WFZ stream}
  +0x18..+0x24 layer headers BG0-BG3 (0 = unused)
  +0x38 walkable floor mask, +0x3C play-area/air mask: WFZ 8 KB, 1 bit per 8x8 tile, rows 256 bits (LSB first)
  +0x4C tile list (WFZ u16 deltas: id[i] = id[i-1] + v + 1). High byte = page from +0x50 table (WFZ 256-tile 8bpp pages), low byte = tile.
- Layer header: +0 handler fn ptr, +4/+8 parallax X/Y (0x400 = 1.0), +0x14 dims (byte0 = chunks wide, byte1 = chunks high), +0x18 chunk ptrs row-major.
  Chunk = WFZ 32x32 u16: bits 0-9 tile slot, 10 hflip, 11 vflip. Slots past the static list are animated tiles.
- Palette: one global master palette per game, 24-bit RGB (BF ROM 0x701B0, 512 entries BG+OBJ; LoG2 slice 0x3ECD1C),
  faded in by 0x08007074. The 512 shared colors are the budget for anything imported from LoG2.
- tools/maprender.py (single map) and tools/render_all.py (all maps -> maps_out/). The gallery is in atlas/ (published as "LoG4 Location Atlas").
- Not modeled in renders: parallax backdrop scroll positions; animation frames beyond frame 0.

### Progression / items
- EXP table: u32 x 151 at 0x6B7084 (0, 10, 40, 100, 200 ... 50,410,227). Code at 0x080135D2 returns level = index + 50, and equipment level requirements also look biased by 50. UNVERIFIED in-game.
- Stats: STR, POW, END, SPD (LoG2 has STR, POW, END). Currency is Zenie. There is a skills menu.
- Equipment: 162 records x 44 bytes at 0x6F82EC. Fields: +0 name idx, +2 desc idx, +0x0C icon ptr, +0x10 slot (0 body, 1 hands, 2 feet, 3 accessory), +0x11 req level(?), +0x14.. stat bonuses, +0x1C price (s32).
- Dojo/multiplayer roster names (UI 158-173): Goku, Gohan, Goten, Trunks, Vegeta, Gotenks, Vegito, Gogeta, Android 18, Hercule, Krillin, Piccolo, Pikkon, Tien, Videl, Yamcha. Forms list at UI 116-147.

### Sprites (verified visually)
- Character frames = individual WFZ blocks of 8bpp 8x8 tiles (1-4 KB). OAM uses 8bpp objects with one shared 256-color OBJ palette.
- Frame/animation tables (CharacterData) not yet located.

## LoG2 (slice 0x800000 of the LoG I&II combo cart)
- Same WFZ compression (about 13,170 blocks) and the same 8bpp frame format. It uses a different palette, so frames need a palette remap to move into Buu's Fury.
- Combo SHA1 f02d179accbeb9b68bcaef8720eb0ae426dde6ee. LoG2 pointers are rebased to 0x0880xxxx. Script function table is at slice 0x3B5DD8. Dialogue is ASCII inline.

## Text pipeline (working)
- tools/find_refs.py + tile_refs.py find 2,415 dialogue lines with their reference sites (event step type 5). Kept only refs that
  sit end to end with neighbors on both sides (82-96% of each bank). Saved in tools/refs_ok.json.
- tools/text_tool.py export/build. Edited lines go into new stored (type 0) banks at 0x800000+ in a ROM expanded to 16 MB.
  The bank table moves there and the literal at 0x123CC is repointed. UI strings are repointed through the list at 0x6BCE8.
- log4/build.py: clean ROM (SHA-1 checked) -> out/LoG4.gba + out/LoG4.bps. Verified with our applier and with Flips (identical SHA-1).
- Verified in emulator: intro lines and title-menu label changed; untouched lines still load from the original banks.

## Tools (tools/)
- harness: headless mGBA (script of frames/keys, shot, dump, save/load state)
- tracer: single-step; watch a 16-bit value or break at a PC (pXXXXXXXX)
- scriptlog: logs script entries and native calls with stack args
- wfz.py / scan_wfz.py: decompressor and ROM scanner

## Open
- Map/tileset/collision format; CharacterData (animation tables, hitboxes); native function names (248);
  enemy stat tables; character base stats and growth; verify level+50 bias; OAM layering for visible equipment.

## Actors and animations (BF, decoded 2026-10-31; tools/anims.py, actor_sheet.py, actor_detail.py)
- Actor list: 298 pointers at ROM 0x6B6BD8 (actor id = index; no direct code reference found yet; probably indexed relative to it).
- Actor record P: +0 u32 flags (low byte = number of animation slots N; high byte = class: 0x04 players and enemies, 0x10 bosses,
  0x02 NPCs, 0x08/0x01/0x00 misc/effects), +0x14..+0x50 four (x, y, w, h) s32 boxes (one per direction), +0x54 N animation pointers (0 = empty).
- Animation: u32 frame_count, then frame_count x 4 frame pointers, frame-major; directions 0 down, 1 up, 2 side, 3 other side
  (dir 3 reuses dir-2 art with the OAM h-flip bit, so new art needs 3 directions).
- Frame: u32 piece_count, pieces of 16 bytes [s8 x, s8 y, u8 w, u8 h][u32 box2][u32 OAM attr][u32 tile container ptr].
- Tile containers load through 0x0803D96E (type 0 stored = copy; 1/2 = WFZ), so new sprites can be inserted UNCOMPRESSED.
- Playables (class 0x04, 20-22 slots, 120-160 frames): 98-105 Gohan forms (102 Great Saiyaman), 106 Goku, 109 SS Goku, 111 SS3 Goku,
  114/115 Goten, 117/120/121 Gotenks forms; second group 260-276 (Vegeta/Trunks/Vegito, to confirm).
- Player slot template (frames per direction, Goku/Gohan; labels are visual reads, confirm in-game):
  0 idle 2 | 1 walk 4 | 2 run 4 | 3 guard/block 3 | 4-6 melee combo hits 4/4/4 | 7 hurt 1 | 8 signature beam 11 | 9 ki blast 3 |
  10 transform (SS) 11 | 11 costume/form change out 4-9 | 12 victory 2 | 13 power-up / item (arms up) 2 | 14 kick/jump 3 |
  15 FLY (horizontal flight; the world map plays it, checked in RAM 2026-11-02) 4 | 16 spin knock-back + world-map turn (RAM-checked) 4 | 17 knockdown 4 | 18 recover 3 | 19 costume change in / teleport 3-10 | 20 throw 1-3 | 21 second special 11
- Great Saiyaman's slots 11/19 are a white-flash costume change: the model for LoG4's outfit swap.

## LoG2 actors
- Frame record = 12 bytes [bbox][OAM attr][tile ptr] (one piece, no count). Actor record (e.g. Android 17 at slice 0x1E680C, referenced from 0x3B4F48):
  u32 flags (0x100D0400), u32 anim count (8), u32 0, 4 boxes (16 bytes each), then each animation = 4 direction pointers to frame-record runs.
  Android 17: 8 animations (idle 2, walk 4, attacks 3-4, hit/KO 4), against BF's 22-slot player template.
- Actor list: slice 0x3B4F30, 154 pointers (tools/sprites.py log2_rec: "rN" = entry N). Big actors use 64x64 frames.
  Useful entries (by eye, likely): 51 = one-armed Super Saiyan Future Gohan (cutscene actor from LoG2's Trunks prologue:
  0 idle, 1 walk, 2 a back-facing look (other directions empty), 3 fall: SSJ standing, falling, lying with black hair,
  lying + sparkles; 5 a front-facing raised-hand pose; no attacks); 153 = Future Gohan with both arms, sleeveless orange
  gi (0 idle 2, 1 walk 4, 2 hurt 4, 3 KO 4 shared by three directions, 4 power-up 4, 5 ki blast 3, 6/7 punch combo 4);
  125 = Future Trunks (Capsule Corp jacket, sword on his back), 131 its SSJ version, 132 Trunks without the sword;
  126/129 Trunks in Saiyan armour, 127/130 SSJ; 57 Gohan orange gi, 58 SSJ; 50/52-54 Gohan (Cell saga outfits).
  Direction order: down, up, left, right; right is the left frames with the OAM h-flip bit (0x10000000).
- LoG2 player animation tables (no record header, 4 pointers per animation): Future Trunks 0x35bd5c / 0x3682b8 / 0x3b43dc
  (10 animations, sword at 8), SSJ Trunks 0x373cac, Goku 0x2c1f0c, SSJ Goku 0x2cef50, Vegeta 0x391e4c, Piccolo 0x3127c4,
  kid Gohan 0x2853b0 (purple gi) / 0x2a15ec (green overalls), SSJ Gohan 0x2ab6d4, Hercule 0x2de780.
- tools/onearm.py edits LoG2 frames before conversion (actors.json "log2_edit"): remove_arm (front/back: skin and
  wristband beyond the torso on one side; side: near-arm skin over the torso repainted gi, trailing skin removed; the
  right-facing view is the mirrored left one, so it shows the other arm) and ssj_hair (black hair -> SSJ gold).

## Dialogue portraits (decoded and verified in-game 2026-10-31; tools/portrait_backdrops.py, tools/portraits.py)
- Format: 64x64 8bpp **linear** bitmap (not tiles), 4096 bytes in a WFZ container; uses the global OBJ palette. The image
  includes the gold frame (4 px, transparent rounded corners) and a coloured backdrop; the face window is 56x56 at (4,4).
  Shown as one 64x64 OBJ at (168,88) next to the text box.
- BF table: ROM 0x6F393C, u32 pointer per **speaker id** (the u8 in a type-5 event step). 0 = narrator and 7 = none; 1-6 =
  party slots resolved through the current form (code 0x08012118: per-slot form table, then table[form value]); 8-162 = fixed
  characters (155 portraits, ROM 0x6F395C onward). Single code reference: literal at ROM 0x12194. King Kai = 0x57, Goku = form value 57.
- Stored (type 0) containers work for portraits. The build moves the table to 0xA00000 (256 entries) and appends new portraits;
  ids 163+ are new speakers, listed in log4/art/speakers.json. Verified: King Kai and Goku still show; speaker 163 (Lapis) and 192
  (Android 17 from LoG2) show in the real dialogue box with correct colours.
- New OBJ colours must also be written to the master palette (ROM 0x701B0 + (256+slot)*3). The build does that from
  palette_alloc.json. In savestates made earlier, the old palette stays in PAL RAM; the .ss file holds OBJ PAL RAM at byte 2560.
- BF portrait inventory (likely IDs, by eye): Android 18 (#1, possibly #74/#113), adult and teen Gohan forms (#28-46, Great
  Saiyaman #39), Goku forms (#47-53), Goten/Trunks/Gotenks, Vegeta forms (#136-142), Piccolo (#104), Krillin (#82), Tien (#127),
  Yamcha (#151?), Trunks (#128-133), Buu forms, Hercule, Bulma, Chi-Chi, Videl, Roshi, and others. No 16, 17, Gero, 19 or Cell.
- LoG2 portrait table: slice 0x3ECB6C, 107 pointers, same 64x64 linear format with a 3 px silver frame (the first 18 are
  party portraits shown here with the wrong palette). It has Android 16 (#18), 17 (#20), 18 (#21), 19 (#22), Gero (#23, #24),
  Cell imperfect/semi/perfect (#30-32), Future Trunks variants (#90-95), Tien (#87), Krillin (#65), Yamcha (#105), teen Gohan (#48).
  The build imports them (log4/art/portrait_imports.json, `--log2 <combo cart>`): window [4:60] mapped to BF colours with CIE94
  (worst dE 6.8), reframed in BF's gold frame.

## Palette loading and per-world palettes (verified 2026-10-31)
- 0x08007074 is the routine that writes PAL RAM: it copies all 512 master colours (ROM 0x701B0, only reference = literal at
  ROM 0x7164), scaled toward a fade colour (r0,r1,r2 = target RGB, r3 = amount 0..256). It runs on fades and when returning
  from menus.
- Current AreaEntry pointer: IWRAM 0x03001980 (first byte = world id). Snake Way = world 1, area 1.
- LoG4 hook (log4/asm/fadepal.s at ROM 0x9F0000, bx-pc veneer at 0x7074): same body, source = WORLDPAL[world] or the master
  palette when 0. Verified: with world 1 overriding OBJ colour 1, outlines turn red after leaving the status menu on Snake
  Way; with no overrides the game looks unchanged and boots normally. Overrides go in log4/palettes.json.
- Level bias VERIFIED: the status screen shows Goku LVL 60, XP 2200, next 675 = EXP table[10] = 2200, table[11] = 2875,
  so level = table index + 50.

## OBJ palette budget (measured 2026-10-31)
- Colours used: actors 239, BF portraits ~200, HUD/dialogue-box OBJs 44 (tools/bf_ui_obj_colors.json, from emulator dumps).
  The old "11 free slots" list was wrong: slot 6 is drawn by the HUD bar, 102/231 by portraits, 233 by an actor.
  Truly free (nothing uses them): 8, 9, 103, 193, 217, 218, 223, 224, 225, 236.
- Colours are heavily shared: dropping every Buu-saga actor frees at most 3 slots.
- Per-act plan (tools/palette_plan.py + log4/acts.json): act1 27, act2 12, act3 9, secret 27 slots, plus the global 10.
  artclean plans each act's new colours jointly over all its sheets (weighted k-means on badly matched pixels).
- Menus are BG layers (no OBJ colours); the HUD and the dialogue box are OBJs.

## Cross-game map import (verified 2026-10-31; tools/mapimport.py)
- The map record is 21 words: +0 pre-struct ptr (0x18 bytes: 2 function ptrs + a rect), +0x28 count / +0x2C 0x18-byte
  region records / +0x30 WFZ mask (doors: LoG2 lab room 61's door region draws as a closed orange door in BF), +0x34 size,
  +0x48 self pointer (= M). The area struct's first word is M+4.
- Code pointers LoG2 -> BF: 0x0880C2A3 -> 0x08007675, 0x0880DA33 -> 0x080072CD, 0x0880D91F -> 0x0800776D,
  layer handler 0x088056D9 -> 0x08008087 (matched by frequency over all map records).
- Tile ids in the tile list index a game-wide page table (high byte = page). The importer keeps only the pages and tiles the
  map uses, renumbers them, remaps BG colours LoG2 -> BF (CIE94 nearest) and stores pages/list uncompressed.
- Verified: LoG2 Dr. Gero's Lab room 61 shows in BF in the emulator (intro scenes repointed to it). Every VRAM tile slot matched
  the imported pages and every layer landed on the right BG. The offline render matches LoG2 closely.
- Animated tiles (done 2026-10-31): +0x10 count, +0x14 -> list of def pointers; def = {u8 frames, u8 ntiles, u16 dest VRAM
  slot, frame ptrs}; frame = {u32 duration, raw WFZ stream of ntiles*64 bytes}. The importer keeps the static tile list the
  same length, so dest slots stay valid; frames are decoded, colour-remapped and re-encoded with wfz.compress_literal
  (8-bit-literal stream: special 001 + mode change, then 1+8 bits per byte, control 000 end). Verified: the tank in room 62.
- LoG2 lab = LoG2 world 8, areas 60-65 (entries 256-261 of the table at slice 0x409470). 62/64 and 63/65 are the same rooms
  before/after the story beat (doors pick one by flag condition params 0x2008x/0x1008x).
- Savestates: run3/pre_load.ss = intro just before area (0,4) loads (advance with A); play1 = Snake Way (1,1).

## Spawning and new actors (verified in the emulator 2026-10-31; tools/sprites.py, log4/actors.json)
- Area struct (AreaEntry+0x2C): word 0 = map (M+4), then spawn records. NPC record (9 words):
  [0x0800A223][0x00030032][0x08017DA3 behaviour][0x00020002][y<<16|x][script ptr][actor idx][1][next ptr].
  actor idx = actor id + 9 (game code: [list+4 + 4*idx - 0x28]). Snake Way: King Kai idx 161 (actor 152), Bubbles 40 (31),
  Gregory 135 (126).
- The actor list has two code references, literals at ROM 0x3C0 and 0x1715C (both = list+4). The build moves the list to
  0xC00000 and appends new actors (ids 298+, log4/art/actor_ids.json), cloning a template record and replacing animation slots.
- New frames are stored uncompressed and packed into the smallest OBJ pieces covering the art (tools/sprites.py cover()).
- Character/NPC actors get about **1 KB of OBJ VRAM per frame** (no class 2/4 actor in BF exceeds 1024 bytes/frame). A 32x64
  Android 16 overwrote another new actor's graphics, while 32x32 frames work side by side. So character art must fit
  1024 bytes per frame (32x32 or equivalent); bosses (class 0x10) use up to 4096.
- Verified: Gevo and Android 16 spawned in Snake Way through its records (fresh area load from preA2 + A presses),
  with correct colours (act1 palette written to the master palette for the test).
- Correction (2026-10-31): character/NPC (class 2/4) frames are always ONE piece, 32x32 or 16x32 (checked across all BF
  characters). A frame with a second piece only draws the first one (Gevo/16 appeared cut in half), and a 32x64 piece
  overwrote another actor's VRAM. tools/sprites.py now emits single-piece frames; artclean shrinks oversized poses into the cell
  instead of cropping (portraits still crop at the bottom).

## Events and the scene compiler (verified 2026-10-31; tools/scenes.py, log4/scenes/*.scene)
- An event is a 0-terminated list of u32 step pointers. Step = [u16 id (1.. in list order)][u8 type][payload]:
  0 = bytecode until END, 5 = dialogue [u8 speaker][u32 text ref], 4 = data blob (kept as is), 7 = run another step list [u8 pad][u32 list ptr at +4]
  (the intro's last step 0x13 at ROM 0x77CBE8 starts the opening list 0x780550). Global script pointer table around ROM 0x79B77C.
- Natives identified from the opening: 56 begin_moves, 96 move(actor idx, x, y) (map pixels; idx = actor id + 9),
  58 wait_moves, 90 face(idx, dir), 31 journal/flag(id), 35 music(id)?, 115 = 0x73 load scene, 47 end cutscene?.
- Bytecode assembler matches the original encoding byte for byte (varint = 7-bit groups MSB-first, low bit = sign).
- The build compiles every log4/scenes/*.scene: new dialogue lines go into new text banks (text_tool EXTRA_REFS), kept
  steps are copied and renumbered, and every pointer to the replaced list is repointed. Verified: the Act 1 opening plays
  in full (more lines than the original, Gero/Gevo portraits and expressions, scripted Gevo movement, journal entry), then
  control returns to the player.
- Player character: in Other World the player is one of BF actors 106-108 (Goku variants; idx 115-117). Replacing their
  idle/walk/run slots with LoG2 Dr. Gero's animations (LoG2 actor table slice 0x3B4F30, 154 records; Gero 0x1FA96C /
  0x2019C0 / 0x2032C8, 17 0x1E680C, 18 0x1EE210) makes Gero the player: verified walking around the imported lab with the
  camera following and LoG2 walls respected. A `move <player idx>` at the end of the scene sets his position.
- Bug fixed 2026-10-31: palette index 0 had slipped into the "usable colours" list (palette_plan's protected set includes 0),
  so near-black pixels were mapped to 0 = transparent and the portrait backdrop showed through hair and outlines. The registry
  usable() list now always drops 0. This affected portraits, new sprites and LoG2 imports; all were rebuilt.
- Halos: actor record +0x50 is a pointer to per-slot attachment offset tables (halo). When it is non-zero the draw code
  (0x0800F094..) adds a halo above the actor. King Kai (152) and in-Other-World Goku (108) have one; living NPCs and 106/107
  have 0. New/replaced actors now get 0 unless actors.json says "halo": true.

## Area transitions, exits and starting stats (verified 2026-10-31)
- Natives 114 and 115 = load area (world, area, room, cam x, cam y) -> 0x08009030(ctx, world, area, room, &xy, ...).
  "room" picks the map: area struct word [room-1] (0x080089CC); room 0 = run entry +0x28 script, or 1 if none (0x080089A0).
  x/y only place the CAMERA (0x080094F0 clamps them to the map size); the player keeps its position. So script doors are
  for cutscenes (BF's own uses fade 120 / load / fade 121 around them). Entry +0x30 = on-enter script, +0x34 = on-exit
  script (old area's, run before the switch).
- Walking doors are warp exit objects: [0x08007675][0x0800776D][rect u16 x0,y0,x1,y1][dest][arrival y<<16 | x].
  Decoded from the constructor 0x08007674 and the trigger 0x080075AC: dest byte 0 low nibble = the key the player must
  hold while inside the rect (0 DOWN, 1 UP, 2 LEFT, 3 RIGHT; table 0x080707D8 -> key bits 0x80/0x40/0x20/0x10);
  byte 0 high nibble = arrival facing + 1 (0 = face the key direction); byte 1 = world; byte 2 = area; byte 3 = room
  index in that area (passed to load_area; 1 = the first room, 0 = default, others crash). On arrival the player walks
  ~14 px in the facing direction. The map record's 0x18-byte pre-struct (+0) is the same object.
  Pitfalls found the hard way: overlapping exit rects hide each other; holding the key through the warp can walk the
  player straight into the arrival room's own door and back; arrival spots that the engine thinks are inside
  collision freeze the player. tools/clipcheck.py plays every door and arrival in the emulator (it is part of the build).
- Player position (EWRAM, address varies per area load; 0x0202FA84 in lab room 63): u32 x<<8, u32 y<<8.
- AreaEntry word 0 = world | area<<8 | 1<<16 | exit count<<24 (exits at +0x10 are {u32 condition param, u32 object} x count).
- Area table relocation: lookup 0x080089FC searches the count from 0x080125E0 (movs r0,#0xff; adds r0,#imm; max 510) and reads
  the table from literal 0x8A58 (the only reference; the count function has one caller). tools/areas.py "new_areas" copies the
  table to free space, appends cloned entries and patches both. Verified: new areas 1:62-65 (LoG2 lab rooms 62-65).
- AreaEntry+0x10 -> {u32 param, u32 exit object}. Exit objects: door = [0x08007387][0x080071A7][x0,y0,x1,y1 as u16][ptr to
  inline bytecode] (Goku's House); trigger = [0x0800742D][0x080077DF or 0x0800770D][rect][step list ptr] (Snake Way).
  areas.json "doors" builds a door whose action is assembled script code; verified: walking into the lab door fades to (4,22).
- Exit param (the u32 before each exit object) = condition: 0 = always; 0x1xxxx / 0x2xxxx = flag forms (likely set / clear);
  otherwise a pointer to bytecode that must leave true, e.g. 0x087E18 'push 176; call 28; push 177; call 28; and' (natives
  27/28 = flag set / clear tests). Verified 2026-10-31: conditions are checked only when the area loads, so an exit enabled
  by a condition stays as it was until the next load; reloading in place with load_area (114) loses the player, so don't.
  areas.json door key "when" writes such a condition. Exit class 0x0800742D (with any getter, incl. the A+facing stubs) runs
  a step list: areas.json door key "event": <scene list name>. The lab's drone terminal uses it (toggle code + one line).
- AreaEntry+0x14 -> object pointer list (NPC spawn objects; entries point at the behaviour-fn word of each record).
  Putting a door object in that list blacks out the area (not the right place for it).
- Starting stats: ROM 0x6FDA4C, 9 records x 18 bytes [u16 level][u16 HP][u16 EP][u8 STR,POW,END,SPD][8 bytes]; record 0 =
  Goku. Levels are stored absolute and the EXP table starts at level 50 (EXP = table[level-50], code 0x080135BC).
  log4/stats.json + tools/stats.py; verified Gero at LVL 50, HP 60, EP 40.

## Clipping check (tools/clipcheck.py, runs at the end of every build; 2026-10-31)
- Field sprites use OBJ priority 3; BG0/BG1 are priority 1 (foreground: drawn over characters), BG2/BG3 priority 3.
- harness "lshot name mask" draws one frame with only some layers (bit0-3 BG0-3, bit4 OBJ) by writing DISPCNT with
  busWrite16 at scanline 0 (the game rewrites it every vblank; rawWrite16 cannot write I/O, and the installed libmgba's
  enableVideoLayer slot does not match the headers - it crashes).
- Per placement: full / sprites-only / backgrounds-only / blank frames + OAM. Hidden pixel = sprite pixel where the full
  frame equals the backgrounds-only frame. Camera = FFT registration of the backgrounds-only frame against a map render
  from the built ROM (maprender renders are uncropped 512x512 in map coordinates; maps_out/ PNGs are cropped).
- Floor mask +0x38: 1 = walkable, props and walls are holes (matches the game, e.g. the barrel under the lab door).
  Spawn origin (x, y) -> sprite x-1..x+14, feet y+8. Door arrival (x, y) -> feet (x+8, y+8) + 14 px in the facing direction.
- Booting: power-on, START/A presses through title, new game and the whole opening (~13,000 frames, 5 s), then a test
  warp added to 1:1 sends the player anywhere (dest/arrival patched per case in a copy of the ROM).
- Verified it catches: an NPC inside a barrel, an NPC inside a cylinder, a door arrival on a console, NPCs blocking a door.

## Party, characters and forms (decoded 2026-10-31)
- Game struct G at IWRAM 0x03001068 (ROM literal 0x08072890 / [0x08054FBC+0x14]). G[0] = current character index.
- Character records: 9 x 0x68 bytes at G+0x4F8 (index = character = starting-stats record 0x6FDA4C). +0 status bits
  (bit0 = in the party; new game writes 2 for everyone, 0x080133F6-0x08013444), +0x0C count + list (forms/skills?),
  +0x14 current form, +0x16/0x18 HP/max, +0x1A/0x1C EP/max. Displayed level = stored + 48.
- Form table ROM 0x6B82EC, 24-byte records: +0 flags, +2 name (UI, e.g. 158 "Gero"), +4 status-screen name (174),
  +0xC character index, +0xE actor idx (actor id + 9), +0x10..+0x15 portrait (speaker) ids, +0x16 transform target.
  Character 0 (Goku -> Gero) forms 0-8 (Gero = form 2, actor 108), Gohan 9-18, Goten 19-20 (actors 114/115), Trunks 21-25,
  Vegeta 26-30, Gotenks 31-33.
- Natives: 149(c) make character c the player (sets G[0], reloads the player); 150(c) push "c is in party"; 151(c) join;
  152(c) leave; 153/154(c) set/clear status bit1; 155 push current form's flags; 156(c) push c's actor idx;
  157(c, actor idx) change c's form to the first form whose +0xE = actor idx (actor id + 9); 21 push current character; 83(c, n) queue an action/emote for c; 183(a, b, c) chapter card
  (opening: 516, 1450 "Chapter 1", 1451 title). Chapter titles UI 1450-1473, per-chapter saga names UI 602-613.
- LoG4: character slot 2 (Goten) is the Red Ribbon combat drone (actors 114/115 drawn with LoG2's drone, stats record 2,
  portrait slots 62-64 -> a portrait generated from the drone sprite, names UI 129/130/160/176/1190/1191).
  Verified: 151 2; 149 2 makes the drone the player (flies, attacks, uses doors, Status shows RR DRONE).

## Intro, logo and chapter card (2026-10-31)
- Intro = step list 0x77CBF0 (log4/scenes/intro.scene replaces it): scene areas 0:1-0:7, the logo (area 0:98 room 1, map
  0x29B934: BG3 wordmark, BG2 + first word, BG1 full logo, revealed in turn by the type-4 step), then the opening list.
  tools/logo.py redraws the subtitle via tools/mapedit.py (decode map layers -> pixels -> re-tile into a new map record).
- Chapter card: background map + chapter title drawn as OBJ text from UI strings (183 native).
- Title screen (inserted 2026-10-31, tools/title.py): a linear 240x160 8bpp bitmap in a WFZ container (0x3BE3D4, 0x9600
  bytes; literals 0x5414, 0x1E744, 0x1E9E0), decompressed to EWRAM 0x02034738 and cut into 600 BG1 tiles by IWRAM
  0x030003BC. The other full-screen bitmaps (0x9600 containers) are the legal text 0x55620, Atari 0x6F9EC8, FUNimation
  0x6FA398, Webfoot 0x6FABF4 and multiplayer screens. Palette: 0x080053CC copies literal 0x5458 (0x5652C, shared) into
  the BG and OBJ palettes; the title gets its own copy with 155 new colours in slots no other front-end screen or the
  menu uses. Menu items (0x080060A8) are placed by immediates (START/OPTIONS 0x524A/0x5256/0x5284/0x5294, STORY/VERSUS
  0x1E4EE/0x1E502/0x1E52E/0x1E53E = x, y per item). The darkened menu box is drawn into the EWRAM bitmap through an
  index lookup table (0x56A2C; literals 0x5418, 0x1E748, 0x1E9E4; IWRAM 0x0300031C); the title now uses an identity table.

## Exit conditions (decoded 2026-10-31)
- Script exits [0x08007387][getter][rect][bytecode ptr]: the getter returns a shared condition object in IWRAM.
  0x080071A7 -> 0x03001918 (class 0x0804ACF4, key mask 0x40): fires while UP is held inside the rect.
  0x0800774F -> 0x0300193C (class 0x0804C12C, facing 1): fires when the player presses A (interact) facing up.
  Same class, other facings, no getter in ROM: 0x03001944 (0 down), 0x0300194C (2 left), 0x03001954 (3 right);
  tools/areas.py writes 8-byte getters (ldr r0,[pc]; bx lr) for them ('examine': 'down'/'left'/'right').
  Class tables hold self-relative method offsets (entry k at T+4k: target = T + 4k + value).
- Bytecode jumps: 0x12 jmp / 0x13 jz take a u16 big-endian offset relative to the operand's own address.
- Verified: the room 61 drone terminal (examine right / up) runs a jz-branching toggle between characters 0 and 2.

## Scouter map (SELECT in the field; decoded 2026-10-31, tools/scouter.py)
- Header ROM 0x74CA24: [u32 count 0x37][u32 -> table 0x74C948 of map-struct pointers]. The map shown is the one whose
  area records contain the current (world, area); 0x08004A88 sets the record's visited bit.
- Map struct: [tileset ptr (WFZ container; tile ids index it directly, loaded for BG2)][0][count2][ptr][ptr][u32 n]
  [n area-record ptrs]. Area record: [u8 world][u8 area][u16 visited bit][rect x0,y0,x1,y1 as u32 x4, twice]
  [w*h u16 tile map, not-visited look][w*h u16 tile map, visited look] (w = x1-x0, h = y1-y0, screen tiles).
  Snake Way (map 31) colours: visited fill 96 / outline 7, not visited fill 114 / outline 117. Frame tiles are 879+.
- LoG4: map 31 is replaced by a Gero's Lab schematic (rooms 61 -> 62 -> 63; 64/65 share 62/63's boxes and bits).
  Verified: room 61 alone at first, 62 appears after visiting it, the red dot follows the player.

## Map door regions (decoded 2026-10-31)
- Map record +0x28 = count, +0x2C = 0x18-byte records [x0, y0, x1, y1 (u32)][u32 OAM attr0 | attr1<<16][u32 attr2<<16],
  +0x30 = WFZ graphic (8bpp tiles, 1D, OBJ palette). Drawn as OBJ above every character (that's why the lab door covered
  Gero). LoG2 lab doors: 32x64 (attr 0xC000A000), one frame (the closed door, bottom 40 rows); BF's are mostly 32x32 props.
  BF's warp door code (0x08007675) never animates them. 80 BF maps and 58 LoG2 maps have regions.
- Natives: 136 (0x88) = wait n frames; 90 = face(actor idx, dir).
- NPC actor template 152 (King Kai): flags 0x0400000D (13 slots; idle 2 frames/dir, walk), boxes at +0x14 + 16*dir.

## Form table, full (BF original)
- Forms 0-8 char 0 (Goku 106-112), 9-18 char 1 (Gohan 97-105; 14 = Great Saiyaman, actor 102), 19-20 char 2 (Goten
  114/115), 21-25 char 3 (Trunks 260-262), 26-30 char 4 (Vegeta 270-274), 31-38 char 5 (Gotenks 117-121), 39-40 char 6
  (Vegito 275/276), 41-44 char 7 (Gogeta 93-96), 45-47 char 8 guest (none / Android 18 actor 7 / Hercule actor 129).
  Flags 0x10 = normal form, 0x51/0x52 = Super Saiyan levels, 0x1c/0x34/0x5d/0x5e/0x14/0x55 = fusion forms.
- LoG4 use: char 0 = Gero (Act 1), 2 = combat drone, 1 = Lapis (Act 2; Act 3 17 form should point at a NEW actor via
  form +0xE, not repaint 97-105), 3 = Lazuli (same for 18).

## Harness additions (2026-10-31)
- "rec name n keys" pipes frames to ffmpeg (lossless name.mkv) and appends sound to name.pcm (s16 stereo 48 kHz);
  "arec" = sound only. The master volume must be set (config "volume" 0x100) or the sound is silent.
- LoG2's opening story plays "Era of Darkness" (matched against the user's MP3).

## Animated doors (tools/doors.py, verified in the emulator 2026-11-01)
- Every warp door whose rect overlaps a map door region is converted automatically: the region is dropped, its art
  becomes door-panel NPC actors (<= 1024 px each: 32x40 -> panels of 8 and 32 rows), the doorway floor above the
  walk-in target is made solid (collision mask +0x38 rewritten as a stored container), and a trigger exit (class
  0x0800742D, UP-held getter 0x080071A7) just below the warp rect runs: nudge panels 1 px sideways (side frames = half
  open), 1 px up (up frames = open, collision box 0), then move the current player (call 21; call 156) into the doorway.
- Engine facts learned on the way:
  - Native 90 face(idx, dir) does NOT redraw an NPC while an event runs; moving does (an actor turns to its direction of
    travel). One-frame NPC animations never re-read their frame, so door panels use two identical frames per state.
  - Every NPC spawn gets a 16x8 shadow at its origin (actor class and record word 2 don't turn it off). Door panels put
    their origin inside the dark doorway (art hangs below the origin via the inserter's origin_dy), with upper panels
    2 px higher so their shadows sort under the panel below.
  - A UP warp fires when the player, inside the rect and holding the key, is stopped by a wall (walking on through a
    tall walkable doorway only fires at its far end), so the solid floor makes doors fire as soon as he's in.
  - An exit whose getter is "key held" fires every frame the key is held inside it: a trigger must move the player out.
  - Region graphics are BF OBJ indices already (mapimport copies them raw); use them unchanged.
- tools/clipcheck.py now replays every door's walk-in and samples each 3rd frame with harness "pshot" (all layers,
  backgrounds, sprites, OAM, OBJ VRAM and palette of ONE frame). Fails if another sprite drawn ahead of the player covers
  > 6 of his opaque pixels (counted through the fade too: the old overlay door hid him mid-fade), or the map hides
  > 6 (only while the palette is >= half bright). Verified it fails the old overlay doors (204/204/371 px covered).

## Story scenes in the field: chapter card -> field (decoded 2026-11-01 from the Act 1 opening's call log)
- 183(516, chapter UI, title UI) runs the card's own script 0x0879B007: load card scene 0:96 (115), music 37, draw the
  two lines (178), 121(100) fade in, wait 250, 120(100) fade out. Afterwards the game sits in 0:96 until a script loads
  something else; 'end cutscene' (47) does NOT bring the field back.
- Back to the field = what the opening does after its card: 115(0,2,0,0,0) (blank scene), 121(1), 165(0,20), then
  120(1); 119(world, area, room, x, y) = load a FIELD area with the player placed at (x, y) (spawn coordinates);
  121(n) fade in over n frames. Then the event's dialogue plays over the field, and 47; 51(0) hand control back with HUD.
  (114/115 load SCENE areas: the camera only, no player - that's why script-loaded areas showed no player.)
- 120(n) fade out over n frames, 121(n) fade in. 122(n) / 123(n) = the same to and from WHITE (classes 0x0804BBD4 /
  0x0804C5B8; both wait until done; verified 2026-11-03: a white strobe = call 122 6; call 123 6). 165(0, 20): part of the field return (meaning unknown).
- Event step type 4 = packed bytecode: the engine unpacks it into RAM (e.g. 0x02035420) and runs it. The opening's
  step 3 is the field load above plus NPC placement (93(idx, x, y)?) and camera (50, 74).
- Flags: 27(n) push "flag n set", 28(n) push "flag n clear", 29(n) set flag n. BF uses ids up to 387 (gap 283-360).
  Storage: IWRAM bitfield, flag n = byte 0x030010BD + n/8, bit n%8 (found by running the ch5 opening with 29(300) vs
  29(301); likely the whole range). LoG4 flags: 300 ch5 opening seen, 301 fence quest, 302 Hercule met, 303 ch5 ended, 304 ch6 opening
  seen, 305 crossroads ambush done, 306 conversion done (= outfit swap unlocked, once the 17/18 forms exist), 307 police chase running,
  308 chase done (lost the cop in the park).
- Code-step flow control (verified 2026-11-01): a type-0 step that ends with a value v left on the stack makes the list
  continue at the step AFTER id v (jump to v, then advance), so a jump to the k-th step leaves k-1; v >= the last id
  stops. tools/scenes.py: label / goto / stop / if_flag / unless_flag / set_flag / run compile to this. Type-7 steps
  ("run") run another list and come back. Test talk lists with tools/talktest.py (A-press trigger + flag presets).
- areas.json "doors_append" adds exits after an existing area's own (West City keeps all of BF's doors).
- West City arrival used by BF (0:92 -> 4:1): (268, 296) facing down.

## Save points and the team swap (verified 2026-11-01)
- A save point is an exit of class 0x08007499 (getter 0x0800770D, last word 0x0800742D), e.g. West City's Capsule pad
  (rect 128,560-177,609). Press A on it: "Save" (UI 7 "Save Game" screen) and, with 2+ party members, "Switch
  Characters" (UI 12) -> a picker of the party's field sprites -> the chosen character becomes the player. This is BF's
  team swap ("you can switch your characters in save points"); verified Lapis <-> Lazuli. 40 such exits in BF.
- The picker screen loads the master palette itself and writes its UI colours into OBJ slots {2,8,9,103,193,217,218,
  223,224,225,236}: tools/artclean.py MENU_SLOTS keeps those out of every act's free colours (FIXED 2026-11-01: the
  twins now use master colours only and look right in both places). fadepal remembers the last field world at EWRAM
  0x0203FF00 (LASTWORLD) because menus put a non-area pointer at 0x03001980.
- Not save-related: 182(id, item) = collectible (sets its flag), 214 = area teleport with set vars, 215(511, n) /
  216(507, dx, dy) = travel / push currents; window-frame drawing at 0x08020CF4 uses piece ids 0-12 (not UI strings).
- West City (4:1) objects: 0 Vegeta (270), 1 actor 27, 2 woman 172, 3 blond kid 252, 4 woman 171, 5 man 285, 6 old man
  195, 7-9 police 60. Exits: 0 BF chapter-card trigger (183 515 1232 1200), 1 save pad, 2 flag-197 scene.
  areas.json supports "drop_objects", "object_talk" (index -> talk list) and "drop_exits" (with "doors_append").
- East District 439 (2:11): 4 enemies (0x0800FD55 objects, types 8 and 15: bomb-throwing green-helmet soldiers).
  Verified a fight there as Lapis: melee, throw, getting hit, damage numbers - all her slots play. (World 2 isn't on the
  act2 palette yet; before adding it, the act2 keep list in acts.json must include these enemies' actors.)

## Map layer origin offsets (verified 2026-11-01)
- Map layer header +0xC / +0x10 (X / Y): (value >> 16) * 64 px = that layer's origin offset; the content sits that much
  up/left in world space (West City BG1-3: 64 / 128 / 192). tools/maprender.py rolls each layer by it; without it the
  West City render didn't register against screenshots (clipcheck "could not register").
- Story triggers in tests: clipcheck's make_test_rom points every conditional 0x0800742D exit (param = condition
  bytecode) at a never-true condition, so placement checks see the area and not a cutscene (keep_story=True keeps them).

## Exit condition getters (verified 2026-11-01 unless marked likely)
- Getter = exit object word 1; each returns a condition object (most live in IWRAM). From a survey of all 452 BF areas:
  0x0800776D (0x0300195C) key held + stopped by a wall (warp doors); 0x080071A7 / 71AB / 71B1 / 71B7 (0x03001918 +0/8/16/24)
  key-held conditions (71A7 = UP, used by the animated doors; the other three likely DOWN/LEFT/RIGHT, unconfirmed);
  0x0800774F / 7753 / 775F / 7759 = press A facing up / down / left / right (EXAMINE in tools/areas.py);
  0x0800770D = press A (save pads, 0x08007499); 0x080077DF (0x03001960) = walk into the rect: fires on arrival inside it
  AND when the player walks in (chapter 5 opening, chapter 6 crossroads); 0x08007791 builds a per-exit object whose
  check is true once per frame tick (also fires on walking in; BF uses it 40 times).
- Testing story triggers: clipcheck's make_test_rom disables conditional 0x0800742D exits, so tools/talktest.py runs
  with STORY=1 for anything that must fire a story trigger.

## Night areas and new-area options (verified 2026-11-01)
- areas.json new area {"night": true}: build.py gives its world a moonlit BG palette (tools/worldpal.night_bg): only the
  BG colours the map's tiles use are changed (55% toward grey, x(0.40, 0.48, 0.80) + 18 blue), so BG UI keeps its colours.
  OBJ colours are untouched (sprites and map OBJ regions such as West City's crossroads pad stay bright).
- Palettes are per WORLD, so a night copy needs its own world id: West City at night = 16:1 (world 16 is unused by BF;
  BF uses 0-15 and 18-22). The fade hook accepts worlds 0-31.
- "map_from" may name another new area listed earlier (or any BF area). "exits_from": [[w, a, i]] copies exit i of an
  existing area (16:1 copies West City's Capsule pad save point). Spawns take "actor" (LoG4 name) or "actor_id" (BF id).
- NPC scripting needs one actor per NPC that a script moves (move(idx) = actor id + 9): the three night drones are
  copies of drone_l2 (drone_night_a/b/c). Player actors work as NPCs (Gero 106 and Lazuli 260 in the tank room 1:66).
- Player position (EWRAM, per area load): 0x0202E4F4 in 16:1 (u32 x<<8, y<<8); walking speed ~1 px per frame.
- An event that moves any actor (begin_moves ... wait_moves) leaves the game in cutscene mode: it must end with
  47; 51(0) or the player stays locked. Moving the PLAYER (21/156/96) also detaches the camera for good (47/51 free the
  player but the camera stays put), so talk events only move NPCs; events that move the player end by loading an area
  (door triggers, the chapter 6 ambush).
- Exit conditions are read only at area load, so a trigger that should work only in a mid-visit state (e.g. the park
  hide during the chase) is left enabled and its step list checks the flags itself (unless_flag 307 -> stop).
- West City's crossroads "pad" (an OBJ map region, ~(400-450, 330-365)) blocks walking and scripted moves: a move whose
  path crosses it never finishes and wait_moves hangs the event. Script moves in West City use the lane at y = 400.
- A player placed (119 / warp arrival) where his collision box overlaps a wall is stuck for good: no movement at all
  (looks like an event lock). LoG2-imported masks are approximate, so put arrivals well inside open floor (chapter 2:
  (200,470) on the Northern Wastelands path edge froze the drone, (160,420) works).
- A-press exits that load an area: use a plain bytecode exit (class 0x08007387 + getter, as BF's own: 120; 119; 121)
  and put the dialogue in a walk-in event at the arrival point.
- Field enemy record (decomp-confirmed 2026-11-01): 8 words [0x0800FD55][condition][type = stats row][y<<16|x]
  [character = sprite, actor id + 9][0x080555A0][1][0x080716EC]; condition 0 / 0x1NNNN flag set / 0x2NNNN clear /
  script pointer. The character picks the sprite (verified: same type with character 187 shows the Mechanoid).
  Stats: gEnemyStats 0x711274, 150 x 28 bytes (exp, hp, id08, level+50, str, pow, end, phys/ki taken, on_defeat,
  death script). Row 34 (level byte 1) is not damageable; row 30 is a clean unused row.
- OBJ VRAM is the limit for big enemies: two animated door panels + an NPC + a large enemy + ki-blast effects garbled
  sprite tiles in the bunker tank room. Put big enemies in rooms without door panels/NPCs.
- Map record +0x44 (verified 2026-11-01): LoG2 Northern Wastelands 3:7 has 5 there and hangs BF on load (black screen,
  HUD too); 1 loads fine. BF uses 0-6 and 14 (6:10 has 5). Likely an ambient effect id; mapimport forces 1 for anything
  but 0/1. The map's pre-struct is a warp object (its built-in door) with LoG2 world/area numbers: 3:7's sits on the
  left cave mouth (160-177, 168-193).

## TCRF findings (reviewed 2026-11-01; LoG1, BF, BF prototype, LoG2 prototype pages; the LoG2 main page is robots-blocked)
- BF prototype debug menu (title: L L R R Up Down Left Right) is NOT in retail: tested in the emulator, and the key
  sequence isn't in the ROM. What it reached partly survives in retail: area 0:99 = combat test room (holds nearly every
  enemy: a quick place to check enemy types/characters), 0:14 = unused map (floating landmarks), 3:23 = 8-bit "Mr. Satan
  vs Cell" placeholder map (has Cell; candidate for an easter egg / the secret Cell chapter).
- Super Android 13 spawns from the prototype's "Super Janemba" debug option (Prototype D) - its sprite is in that build
  only. Retail keeps only text: UI 1050-1057 = Android #13/#14/#15/Super #13 names + descriptions ("An evil Android
  created by Dr. Gero's computer"; Super 13 "after absorbing the broken parts of #14 and #15").
- Retail also has "Android #20's Hat" (Hercule exhibit item text) and Uub / Mud Man scouter text.
- CodeBreaker notes: 0x0202D0B8 = player sprite address (swap to scan cutscene-only NPCs); the prototype sound test had
  unused tracks 2 and 52 (Faulconer-style) - worth checking whether they exist in retail as music for new chapters.
- LoG2 prototype page: only early portraits (Goku, Gohan, Trunks...); nothing usable.

## Prototype D (Buu's Fury prototype, DBZ3_cart27.GBA, SHA-1 4594e2d524e2d77cdf0e58ae7512e1052cc5bc02; user's file, kept private as rom/protoD.gba)
- Same engine formats as retail. Actor list 0x6A1BBC (280 actors; character table 0x6A1B98), records/animations/frames/WFZ
  tile blocks identical in layout to retail. Master palette at 0xA2504 = retail 0x701B0 byte for byte, so colour indices
  carry over unchanged. Portrait table 0x6E39C4 (163 entries, retail layout).
- Actor 230 = Super Android 13: 24 slots (0-7, 9, 17-23 used), class 0x10 (boss class, like retail 231), 236 frames,
  100 WFZ blocks, every frame one piece up to 64x64. Slot 17 = absorbing parts (sparks), 20 = flex/power-up, 21 = aura rise.
  Its colours avoid every act3 repaint slot (act1/secret repaint 152/164/175, so keep him in Act 3).
- Imported by tools/sprites.proto_actor (build `--proto <file>`; actors.json "super13": {"proto_actor": 230}) -> actor 307,
  character 316 (= actor + 9). Verified in the emulator as an enemy (stats row 30 test): walks, punches, takes damage, dies,
  death script runs.
- Portraits not in retail: #1 Android 13, #2 Android 14, #3 Android 15 (likely, by eye), #47/48/50 Future/SSJ Gohan
  variants, #150/151 Vegito variants; the rest are sketches or a cat placeholder. 13/14/15 imported (log4/art/proto_portraits.json)
  -> speakers proto_android13/14/15 = 209/210/211.
- Other prototype-only actors: 106/172/246 Mud Men; 176/177/217/219 ninjas, 178/252/263 vampires, 3/146/170/184/209/273
  small misc (palette/layout variants of retail enemies, likely). No field sprites for 13, 14 or 15 anywhere.

## Skills and the outfit swap (decoded 2026-11-01)
- Character record +0x0C = skill count, +0x0D.. = skill ids, +0x15 = selected skill (L cycles it; B uses it). Starting
  lists are in the stats records (0x6FDA4C, 18 bytes: +0xB count, +0xC.. ids). Gohan/Lapis [7, 20, 6, 17], Trunks/Lazuli
  [7, 20, 4, 11]: 20 = Super Saiyan, so ch5_start removes it from both twins.
- Skill table 0x71DB04, 24-byte records [u16 name UI, u16 desc UI][fn usable][fn use][u32][icon ptr][icon ptr]; name UI =
  1312 + 2*(id-1). 18 = Saiyaman (use = 0x0801A464), 20 = Super Saiyan.
- Natives 164/165/166 (0xA4-0xA6) = add / remove / replace a skill (c, id[, new]). The "165 0 20" in BF's opening idiom
  removes Super Saiyan from character 0.
- Saiyaman use: current form's +0x16 != 0xFF -> costume-in action (slot 19, finish sub_0801C5CE: form <- 14), else
  costume-out (slot 11, finish sub_0801C2AE: form <- 10). Both hard-coded; tools/outfit.py + log4/asm/outfit.s hook them
  (long calls from 0x1C5F2 / 0x1C2D2 to 0x08F7E000): forms >= 21 toggle 21 <-> 23 (Lazuli/18), else 10 <-> 14 (Lapis/17).
  Verified in the emulator both ways for both twins (2026-11-01).
- LoG4: form 14 = Android 17 (actor 102, names UI 164/180 "Android 17", portrait L2 17 = speaker 192), form 23 =
  Android 18 (actor 262, names 166/182, speaker 193); log4/forms.json. Skill 18 renamed "Outfit" (UI 1346/1347).
- Native 157(c, actor idx) sets c's form to the first form whose +0xE = actor idx (actor id + 9): 157 1 111 -> form 14,
  157 3 271 -> form 23. A wrong value hits the "Unable to find sprite index in character state data" assert.

## Map import notes (2026-11-01)
- LoG2 8:60 (map 0x54261C, unnamed: the pod room with pods 16/17/18) has no pre-struct (word 0 = 0x84400000): mapimport
  writes an empty-rect warp door instead. Its layers have empty chunks (pointer 0): kept as 0, BF draws them as empty.
- LoG2 8:37 (0x55EA78, the switch cave): the opening on the left is wall in the imported collision.

## Enemy rows and boss fights (2026-11-01, chapter 8)
- Enemy stats row 26 (Majin Buu) creates the enemy object but it never activates (frozen, invisible, garbled tiles):
  likely hard-coded Buu handling. Rows 70 and 136 (Majin Vegeta), 18 (Dabura) and 30 work for new bosses.
- BF's NPC actors for Tien (255) and Yamcha (293) have only idle/walk (and 157 Krillin a punch + KO): as enemies Tien
  runs away. Krillin 157, Vegeta 270 and Piccolo 213 work as bosses with the generic enemy behaviour (0x080555A0).
- An enemy death script can load the next area (call 29 flag; heal; call 120; call 119 ...): verified, the level-up
  pages show first, then the new area's arrival trigger runs.
- Boss HP field = enemy object + 0x28C (value << 10); position = HP field - 0xEC ([0x02050810][x << 8][y << 8]).
- (2026-11-03) Enemy objects start with the word 0x0804C484 (likely their class / vtable) and hold 0x03001BA4 at +0x18:
  that finds every enemy, the big machines included (Prototype 12, the Security Unit, the Collector). The word before
  the position (+0x19C) is a flags word, not a class: 0x02050810 on most, 0x050C1020 or 0x00001040 / 0x051C1040 on
  others, so it can't identify enemies. The player's position record has 0x02050810 there and no 0x0804C484 header.
  The played character's live HP is its character record's +0x16 for c = G[0] (0x03001068), not a fixed slot.
  tools/fightbot.py fights a boss closed-loop from a save state (finds both structs) for balance tests.
- 'heal' in scenes/death scripts = call max_hp; set hp; call max_ki; set ki (the Senzu Bean's own code).

## Characters, levels and scripted forms (2026-11-01, secret chapter)
- Character record (IWRAM 0x03001560 + 0x68*c): +0x14 form, +0x16/+0x18 HP/max, +0x1A/+0x1C EP/max, +0x24 u32 EXP,
  +0x28..+0x2B STR/POW/END/SPD, +0x0C skill count + ids. A character that never joined has HP 0 until healed (the
  heal pseudo-op only works on the active player after the area load, not straight after natives 151/149).
- Level is derived from EXP (exp table, index = level - 50). On a level-up BF rewrites STR/POW/END/HP/EP from the
  character's own growth (character 6 = Vegito went 40 -> 20 STR, 440 -> 234 HP at level 64), not from the start
  stats table plus gains. Kill EXP is scaled by the level gap: a level-75 Cell got negative EXP from a Cyborg (EXP
  40325 -> 5900). LoG4 gives the secret chapter's enemies 0 EXP.
- Native 157 to a Super Saiyan form (form flags 0x5x, e.g. Vegito's form 40) by script left the next journal box stuck
  open; base forms (0x10) are fine. The larva therefore uses another character (4) in a base form.
- Native 115 (world, area, room, camX, camY) mid-game: loads the area and its NPCs and points the camera, the player
  keeps its coordinates (so it can be left off screen): used for the epilogue and closing narrations.
- Text boxes don't show while the screen is faded out (native 120): narrate before the fade or after a fade-in.
- Enemy behaviour class (row +8): 0x8A fighter; BF row 17 Cyborg (character 72), 64 Laser Turret (167; shoots the
  player on arrival, which failed clipcheck), 72 Mechanoid (187).

## Music (decoded 2026-11-01, tools/music.py)
- BF and LoG2 share Webfoot's sequencer. Song table BF 0x083BB78C / LoG2 slice 0x1D4BE4, 20-byte entries [track list
  ptr][data start][sample bank][bank B][tempo | channels << 8]; native 35 (0x23) music(i) plays entry i. Data runs from
  start to the track list (absolute pointers into the data), which ends where the next song starts. Bank = 12-byte
  sample records [ptr][u32][rate << 16 | length]. BF song 45 = the startup song (intro + title).
- Porting a LoG2 song alone played nothing; keeping LoG2's layout bank B + song 0 + the song works (bank B is read past
  its 14 bytes). LoG2 song 7 = "Era of Darkness" (envelope match 0.97 vs the user's MP3). LoG4 puts it in slot 45 at
  0xF80000 (447,632 bytes incl. all LoG2 samples); 0xFED490-0x1000000 is free.
