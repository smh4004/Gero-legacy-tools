# Legacy of Goku 4: project handoff

Last updated 2026-11-02. Read this first, then `RE_NOTES.md` (all technical findings with ROM offsets).

## What this is
A personal, non-commercial ROM hack that turns **Dragon Ball Z: Buu's Fury (USA)** into a fan-made "Legacy of Goku 4". It merges
sprites, maps and systems from **Legacy of Goku 2** and tells a new story: a Dr. Gero / Red Ribbon prequel,
Lapis and Lazuli's human lives, then the androids' rampage in Future Trunks's timeline, with a Cell epilogue.
Output ships as a .bps patch.

## Live documents (source of truth; don't duplicate them here)
- **Code repo:** https://github.com/smh4004/Gero-legacy-tools (PUBLIC): tools, log4 sources, docs and the cleaned LoG4 art
  (log4/art/clean, generated for the mod); no ROMs, no extracted assets (text as log4/text_edits.json deltas). Re-sync
  after each work session: `python3 tools/text_edits.py make bf.gba; python3 tools/sync_repo.py . <clone>`, then commit/push.
- **Design doc:** https://claude.ai/artifact/9H8wAFjMVxj5rfHwpqV1pg (Claude Docs). Covers direction, base-ROM decision, story outline and
  every story decision (table under "Story decisions"), combat/progression, technical plan, engine findings, progress.
- **Art Needs & Prompt List:** https://claude.ai/artifact/6jcKFYbnE2pEdTFQZKtbWX (Claude Docs). Covers the sprite inventory,
  style rules, prompts P1-P12 / R1-R6 / E1-E7 / U1-U14, the generator checklist and open questions.
- **LoG4 Location Atlas:** https://claude.ai/artifact/9HqynEqfhpt1yNEWjYX8AC. A gallery of all 300 maps from both ROMs, with pins.
  Source: `atlas/` (index.html + data.json + img/). Republish needs >255 files, so it takes two publishes.

## Decompilations (user-provided 2026-11-01; clone read-only, keep private, never redistribute their extracted assets)
- https://github.com/smh4004/buusfury-decomp (cloned at /home/claude/smh4004/buusfury-decomp; `cp bf.gba baserom.gba;
  make extract` -> assets/tables/{enemies,spawns,scouter,areas,...}.csv, assets/scripts, maps, gfx). Key facts used:
  enemy stats gEnemyStats 0x711274 (150 x 28, row = enemy type); enemy actor record [0x0800FD55][condition][type][x,y]
  [character = actor id + 9][0x080555A0][1][0x080716EC]; condition 0x1NNNN flag set / 0x2NNNN clear / script ptr;
  docs/script_natives.md names all natives.
- https://github.com/smh4004/log2-decomp and https://github.com/smh4004/log1-decomp (cloned beside it): LoG2 events,
  maps (floor/play-area masks), enemies (109 types), sprites; LoG1 text/graphics.

## Inputs (NOT in the package; the user supplies them)
- `bf.gba` Buu's Fury USA, 8 MB, SHA-1 `f1c4b07554d2a3b1ad2f325307051e775ce68087`
- LoG I & II combo cart, 16 MB, SHA-1 `f02d179accbeb9b68bcaef8720eb0ae426dde6ee`.
  `log2.gba` = bytes 0x800000..end of it (LoG2 image; its pointers are rebased to 0x0880xxxx).
Put both in the project root (`rom/`). Many tools hard-code `/home/claude/rom/...` paths; adjust or recreate that layout.

## Environment setup (cloud container)
```
apt-get install -y libmgba-dev mgba-sdl libpng-dev
pip install --break-system-packages capstone numpy pillow
cd tools && gcc -O2 harness.c -o harness -lmgba -lpng && gcc -O2 tracer.c -o tracer -lmgba && gcc -O2 scriptlog.c -o scriptlog -lmgba && gcc -O2 pcsample.c -o pcsample -lmgba
```
Optional: build Flips from github.com/Alcaro/Flips (`make TARGET=cli`) to verify patches independently.
Regenerate derived data: `python3 tools/scan_wfz.py bf.gba run1/wfz_blocks.pkl` (and the same for log2), then
`tools/render_all.py` for map PNGs (`maps_out/`). The `run3/*.json` indexes are included, so most of this is optional.

## Package layout
| Path | What |
| --- | --- |
| `RE_NOTES.md` | Every reverse-engineering finding: compression, text, script VM, events, areas, maps, palette, sprites, items, EXP |
| `tools/wfz.py` | Webfoot "WFZ" decompressor (verified vs RAM). No compressor yet; stored type-0 containers work for text banks |
| `tools/text_tool.py` + `refs_ok.json` | Export and re-insert dialogue (2,415 lines) and UI strings (1,534) |
| `tools/maprender.py`, `render_all.py`, `find_maps.py` | Map decode and render (verified pixel-aligned vs live screen) |
| `tools/artclean.py` + `bf_objpal.json` | Image-generator art cleanup and quantize to the BF OBJ palette (tested; results in the art doc) |
| `tools/intake.py` | Batch intake: `python3 tools/intake.py <files or zips>` matches files to prompt IDs by name prefix (P1, R2, U4...), adds specs with per-prompt defaults, cleans them, and writes `log4/art/clean/review_*.png` + `report_all.json` |
| `tools/collect_frames.py`, `segment_sprites.py`, `seg_sheets.py`, `seg_detail.py`, `export_refs.py` | Sprite frame discovery, grouping, reference-sheet export |
| `tools/harness`, `tracer`, `scriptlog`, `pcsample` (+ .c) | Headless mGBA: scripted input, screenshots (`lshot` = chosen layers only) and dumps, PC/memory watch, script-VM call log, PC histogram (is it hung?) |
| `tools/clipcheck.py` | Build gate: plays every placement/door in the emulator; fails on clipping or broken doors |
| `tools/mapedit.py`, `tools/logo.py` | Decode a map to pixels and re-tile it into a new map record; the title-logo subtitle edit |
| `tools/bps.py` | BPS writer and applier (with RLE) |
| `log4/build.py` | One-command build: art stage, then text insertion, then out/LoG4.gba + LoG4.bps (SHA-1-checks the clean ROM) |
| `log4/text/dialogue.txt`, `ui.txt` | Editable game text (demo edits: new intro lines, renamed menu label) |
| `log4/art/` | `specs.json` (asset specs, target heights), `raw/` (drop generator output), `clean/` (output), README |
| `art_refs/` | 19 reference sheets of real in-game frames (also sent to the user as LoG4_art_reference_pack.zip) |
| `dump/text/` | Decompressed dialogue banks and ui_strings.json |
| `run3/*.json` | Frame lists, sprite segments, map records, area-to-map links for both games |

## State of the work
Done:
- Base ROM decision: Buu's Fury.
- WFZ decoding; text pipeline; build plus verified patch.
- Script VM opcodes (31) and the event format (step type 0 = bytecode, type 5 = dialogue).
- Full map format (layers, chunks, tile list, animated tiles, blending, collision, global palette); area-to-map links; atlas.
- Sprite inventory of both games; art prompt lists; art cleanup tool.

Not done: inserting any new sprites or maps into the ROM. No gameplay changes yet, only text.

### Music plan (user, 2026-11-01) - DEFERRED until every chapter is expanded
- Once all chapters are fleshed out (mostly finished product), make a comprehensive list of every track and where it
  plays (area music fields + scene music calls). The user then suggests swaps; mix LoG2 (44 songs, samples already in
  the ROM: tools/music.py, extra songs cost only their data) and BF tracks per moment instead of BF's original order.
  Don't build the list before then.

### Chapter expansion (user 2026-11-01: "an actual game, not an interactive movie", aim 5-8 hours total)
- Chapter 1 rebuilt (log4/gen_ch1.py writes the areas; log4/scenes/act1_ch1.scene): the drone terminal (lab_terminal)
  sends the drone to the Red Ribbon Proving Ground (UI 526, was "Barren Wasteland"): 1:90 Range Gate (BF 20:6, save
  pad copied from 20:6 exit 1, range sergeant), 1:91 Canyon Road (20:2), 1:92 Target Field (20:7, site A), 1:85 Fuel
  Depot (LoG2 3:10 cave, site B + item drums), 1:94 The Pit (20:4, item drum), 1:93 Bone Flats (20:5, site C; west gate
  opens when 353-355 are set), 1:84 Live-Fire Arena (LoG2 3:12, heavy tank boss row 127). Tank death -> lab 1:61
  (150,230) walk-in ch1_report (356 set, 309 clear) -> ch2_start. Flags 352-358, items 372-373.
- Enemy rows tuned for chapter 1: 64 laser turret, 72 training mechanoid, 127 heavy tank (500 HP; a no-dodge bot wins
  or loses narrowly from a fresh drone, so a levelled player should win). Drone stats raised (HP 220, STR 19, POW 15).
- Engine/tool facts learned: area count limit raised to 765 (count function now movs/lsls/adds, areas.area_count);
  map edge exits: down/right rects need ~28 px depth (the player position is the sprite origin), top exits get solid
  rows ("solid" key in areas.json, copies a BF map record first) so the player stops below the HUD; arrivals are checked
  as feet = origin + (8, 8) + 14 px in the facing; clipcheck now ignores the area-name banner rows and despawns field
  enemies in its test ROM (listtest keeps them); fightbot: ANYMARK=1 for vehicles (BF Tank has no 0x02050810 marker),
  RANGED=1 [RANGED_DY] for shooters, keys.txt to replay a fight for video. BF Tank's hitbox sits ~16 px below its
  position field.

- Ki recharge (log4/asm/kiregen.s, tools/kiregen.py, hook at 0x0800E21C, code at 0xF7E800): the drone (character 2)
  gets max/32 ki every 12 frames (~6 s full), Seventeen/Eighteen (characters 1/3 once flag 306 is set, either outfit)
  every 8 frames (~4 s). Humans keep BF's slow refill (~3% per 10 s; user: leave it). Imperfect Cell: the bunker
  Cyborg's death script (row 17) heals him 1/6 max HP and 1/4 max ki ("absorbs" the kill); one line in fs_wake.
- Chapter 2 rebuilt (log4/gen_ch2.py on log4/areagen.py; scenes act1_ch2.scene): lab at night -> drone terminal ->
  1:68 Ambush Ridge (no Gevo now) -> 1:96 Scorched Canyon (BF 20:3) -> 1:100 Fuel Dump (LoG2 3:13, Pvt. Kurz, cache
  379), 1:97 Dry Basin (BF 20:10) -> 1:102 Raider Cave (LoG2 3:8, Cpl. Mori), 1:101 Supply Yard (LoG2 3:14, Raider
  Chief = row 128 Thug boss, Sgt. Halden tied up, cache 328 with a Senzu Bean). Flags 314, 374-379, 328. With all three
  found (378) the canyon's east exit leads to 1:95 (Ridge with Gevo, ch2_gevo) instead of 1:68. Enemy rows 15/44/75/108
  tuned. A fresh level-50 drone bot nearly beats the chief (480 HP); a levelled player with items should win.
- Map notes: BF Diablo Desert maps (11:x) load black / reset the game in world 1 - don't use them. BF 20:1/20:8/20:9
  don't render in tools/maprender (parallax). areagen.Gen: edge exits with measured edge distance; door key
  "cover_ok" lets clipcheck accept a walk-in behind scenery (1:68's west bush); areas.json "effect" overrides map +0x44.

- Journal goals FIXED (user saw BF's "Go to King Yemma's Castle"): tools/goals.py + log4/goals.json. BF's goal table
  (0x720564, 40 x [u8 cat][u8][u16 UI][ptr hide-if][ptr done-if][ptr active-if]) is replaced by ours (count byte at
  0x14254, literal 0x1441C); goal texts are UI strings 1600+ (text/ui_goals.txt, generated). tools/text_tool.py now
  supports UI indices past 1534 (copies + extends the UI pointer table, repoints its 51 code literals). Finished
  chapters' goals hide when the next chapter starts (the screen lists hold 40 each). The scene "journal" op still only
  shows the popup - add a goals.json entry for every new objective. NOTE: native 31 is play_sfx, not a journal flag.
- Chapter 1 feedback fixes: target sites are now visible grounded sensor drones (NPC drone_l2, A to read) instead of
  invisible examine spots; the sergeant names where each is; one fewer enemy in 4 areas; rows 8/44/64/72/75 weaker;
  drone END 22. Fuel Depot: the site drone sat on the south-trail arrival point and trapped the player (NPCs are
  solid); moved to (200,178). Skills: drone keeps Energy Blast 7 + Energy Punch 8 (Goten's SS 20 / Kamekameha 16
  removed after 151 2 - joining resets a new member's list); Gero keeps Energy Blast only (Goku's 15 Kamehameha / 14
  Instant Transmission removed in the opening and at the terminal). The Pit (BF 20:4) drops its 3 map OBJ regions = BF
  level-140 gate graphics (areas.json "keep_regions"). clipcheck now fails any warp arrival within ~20 px of an NPC spawn.

- Chapter 3 rebuilt (log4/gen_ch3.py; act1_ch3.scene): the tank-room pod gives the blueprint core (316, no
  self-destruct there now); the lab's south corridor (1:69, when 316) -> 1:103/104/105 Munitions Lines A-C (BF airship
  factory maps 12:5/12:9/12:15, 32 px walk strip, looters; the looters' captain = row 47 Hooligan boss in Line C, death
  sets 284 = vault keycard) -> stairs -> 1:106 Archive Vault (12:12; blast door opens to 1:107 when 284) -> 1:107 Army
  Archive (BF Computer Room 4:22): the console (ch3_archive) wipes the files, arms the self-destruct (317, 285) and
  loads 1:71 (escape, existing). Caches 286 (Senzu) / 288. Flags 283-288 (BF's unused gap 283-299). Area name UI 1700
  "Red Ribbon Headquarters" (UI strings past 1534 work now). Drone bot beats the captain from a fresh drone.
  clipcheck: area key "clipcheck_periodic" skips the "player not found" arrival test on repeating maps (the factory).

- Chapter 4 rebuilt (log4/gen_ch4.py; act1_ch4.scene): ch4_start makes the drone the player (skills [7, 8]); bunker
  1:72 south corridor -> 1:108 Mountain Pass (LoG2 8:40, arrival talk ch4_pass 289) -> 1:109 Generator Cave (LoG2 8:36,
  relay 2 node = NPC drone_l2, cache 291) / 1:110 Old Mine (BF 1:16, relay 3 node, Prototype 9 = row 41 boss, death 290;
  cache 292). relay_3 refuses until Prototype 9 is down (290). All three relays -> ch4_power -> Prototype 12 in the
  incubator (verified 2026-11-02) -> Android 16 -> pod. Enemy row 48 (failed prototype). Area names "Northern
  Wilderness" (573).
- Chapter 5 expanded (log4/gen_ch5.py on areagen with world=4; scenes act2_ch5.scene + act2_siblings.scene): West City
  4:1 gets exits: west road -> 4:40 Circus Lot (BF Musuka Circus 3:14, street vendor ch5_vendor 293), south road ->
  4:41 Riverside (BF 2:9, arrive over the bridge; cache_river 297) -> 4:42 Docks (BF 2:8; barn door -> warehouse; dome
  door docks_dome 299) -> 4:43 Old Warehouse (LoG2 2:50 crates; ch5_den intro 389; boss Big Ox = row 12 Bruiser char 39,
  death 294; ch5_stash examine 295 = stash + the stolen goods), Z-Mart door -> 4:44 Z-Mart (LoG2 Big Mouth deli 4:42,
  clerk 388/298), city hall door -> 4:45 West City Museum (LoG2 Antiquities 4:43, curator 387/296, Red Ribbon exhibit
  lore). ch5_check now also needs 295. Red Fang enemy rows 97 punk (char 235) / 36 bruiser (char 122) / 12 Big Ox,
  tuned for the human twins (HP 70/65). Twins are human until chapter 6: ch5_start strips Lapis [7, 6, 17] and Lazuli
  [7, 4, 11] to Energy Punch (8); the procedure adds Energy Blast 7 + Power Blitz 6 (17) / Stun Shot 4 (18) back
  (UI 1322 "Electric Kamehameha" -> "Power Blitz", 1318 "Burning Attack" -> "Stun Shot", desc without "chrono").
- ROM layout change (2026-11-02): area data (imported maps + structs) moved from 0xE00000 to 0x880000-0xA00000; it
  had overflowed into the scene region at 0xF00000 (build asserts both ends now).
- LoG2 map pre-struct doors: every LoG2 import's built-in door (pre-struct warp with LoG2 world/area numbers) is now
  emptied by tools/areas.py (key "pre_door": "keep" to keep one). Found live in 1:85, 1:71, 1:102, 1:109, 1:64/65,
  1:83 (walking onto them would have warped into random BF areas); 4:44's crashed with "unable to find area".
- The level-up (Player_AddExp -> sub_08013678) adds random growth to max HP/EP and 3 stat points per level; it does
  not reset STR (so the twins' low human stats stay low until the procedure's +22 STR upgrade).
- Chapter 5 tests (2026-11-02): ch5_start leaves both twins with [8]; den intro fires on the warehouse arrival; stash
  examine (facing down above the SE crates) refuses until 294, then runs ch5_check -> ch5_end -> chapter 6 card; dome
  door event works. Fight bot: Gero-strength player (54 HP, STR 10) took Big Ox from 340 to 117 HP before dying with
  the room's other two Red Fangs joining in; Ox lowered to 300 HP (Lapis has STR 14 / 70 HP plus levels from ~13 Red
  Fangs on the way). Enemy HP fields of rows 12/36 sit behind marker 0x050C1020, not 0x02050810: fightbot needs ANYMARK=1.
  New area names UI 1701-1706. clipcheck: "shade_ok" area rects (LoG2 opaque shading layers, the museum) and cover_ok
  now also read doors_append.
- Chapter 6 expanded (log4/gen_ch6.py, scenes act2_ch6.scene; world 16 = night): 16:1 crossroads now only plays
  night_crossroads (337, a drone sweeps the street); south road -> 16:41 Riverside -> 16:42 Docks -> 16:43 Old Warehouse
  (all night copies; Gero's hunter drones = row 94 Power Mechandoid char 230; caches 335/336); ch6_home (333) then the
  Collector (row 76 Metal Hulk char 191, 520 HP) whose death loads 16:44 (same map, drones A/B/C as NPCs) where
  ch6_ambush now plays (drones close in, voice, flash, lab). Night palette: areas.NIGHT is now a list per world (every
  night map's colours are moonlit). clipcheck allows reg err 0.42 on night areas.
- Chapter 7 expanded (log4/gen_ch7.py): pod room 1:81 south passage -> 1:111 Security Wing (BF Dr. Brief's Lab 4:31
  map; prototypes row 48, turrets row 64; ch7_alarm 338, Gero's workbench 329) -> 1:112 Control Room (BF 4:22 map;
  Security Unit = row 20 Destroyer char 78, 3000 HP STR 30, death 339) -> console ch7_console (needs 339; the computer
  is building 13/14/15) loads the cave 1:82 as before.
- Chapter 8 expanded (log4/gen_ch8.py): 17:1 south road -> 17:34 Riverside -> 17:35 Docks -> 17:36 Old Warehouse (Age
  767): ch8_hideout (359) = the tin box, the photo strip, 18 says "Lapis". The fruit stall memory now needs 359
  (stall_early line before). Gero's old machines: rows 94 / 62 (Knight Destroyer char 164, 420 HP). Caches 382/369.
- Chapter 9 expanded (log4/gen_ch9.py): Bulma's scene now flies the twins to 17:37 Mountain Pass (1:108 map); the bunker
  door (west) is sealed (ch9_sealed, examine) until the Sentinel (row 100 Shadow Colossus char 240, 3200 HP, death 401)
  in 17:38 Generator Cave (1:109 map) is destroyed; 17:39 Old Mine (BF 1:16) optional (cache 402); 17:12's south
  corridor leads back to the pass. Flags 400-402 (the flag array 0x030010BD runs to 0x0300112C = 896 flags.
  BF's story uses flags up to 387, but BF's world map (area 0:50) also sets/reads 398-408 as "location visited"
  markers; LoG4 has no way onto the world map (only BF 6:5 has an exit to it, unreachable), so 400-403 are safe.
  Checked by unpacking every type-4 step record: nothing else touches 388-419. Prefer 409+ for new flags.)
- Chapter 10 expanded (log4/gen_ch10.py): ch10_start opens in 17:40 Circus Lot ruins (BF 3:14; resistance machines rows
  62/64/94; cache 403); its east edge -> 17:21's west road -> the crossroads (ch10_rain).
- Built-in map doors (2026-11-02): BF maps carry them too (map record pre-struct warp): West City's Z-Mart door -> BF
  0:92 (live in 16:1, every 17:x West City copy), the lab map's south door -> BF 8:48 (1:61/67/73, 17:27), BF 1:16's cave
  door -> 1:17 with a BF story scene (1:110 Old Mine!), Goku's house -> 2:5. tools/areas.py now empties the pre-door of
  every map a LoG4 area uses (new areas and in-place edits with doors); "pre_door": "keep" opts out.
- Balance (fightbot from the shoot ROM's t_* lists, which set up the party and warp into a boss room): fresh level-1
  Lapis narrowly loses to Big Ox (420 HP) and beats the Collector (520 HP) with 11 HP left; a fresh Seventeen shredded
  an 850/1800 HP Security Unit (androids hit very hard), so it is 3000 HP / STR 30 now (not re-run). fightbot's
  "already hit" fallback also accepts the 0x050C1020 marker.
- Secret chapter: fs_leave now goes through 17:41 Security Wing (Age 788, 4:31 map, four Cyborgs = row 17, each one
  absorbed) and its east door (fs_out) flies Cell to West City 17:28 (log4/gen_secret.py).
- Re-run from a fresh shoot build (2026-11-02): a fresh Seventeen beats the Security Unit (3000 HP) losing 117/300 and
  the Sentinel (3200 HP) losing ~150/300. Story hand-offs verified with listtest: ch7_console -> 1:82, ch9_bulma ->
  17:37 (+ ch9_pass), fs_leave -> 17:41, ch10_start -> 17:40, ch8_hideout text.
- Remaining: the epilogue is exposition (user: keep it light). Music pass after everything (deferred list).
- Bug pass (2026-11-02): static audit (scratchpad audit.py: list refs, flags set/read, warps, moves without release,
  text over fades) clean; every event rect touches floor; every enemy on floor; fixes: ch9 bunker greeting also fires at
  the south corridor (when 362 clear), ch8 goals reordered (hideout first, "Look around West City" done at the stall).
- Music list (2026-11-02): area music = AreaEntry +0x24 (BF song index; 255 = keep). LoG4 uses only BF 6 (West City),
  9 (Goku's house), 15 (Snake Way/Grand Kai, used for every lab), 19 (Northern Wilderness, the template 15:10 for every
  generated area, boss arenas included), 27 (Barren Wasteland); chapter cards BF 37; title = slot 45 (LoG2 7). No boss
  music anywhere. LoG2 area table = slice 0x409470 (from entry 2, same 56-byte layout, +0x24 music, +0xC name index into
  the pointer table at slice 0xE28F8). Previews: scratchpad mus2/prev.py puts BF song N (copy table entry) or LoG2 song N
  (music.port into a 32 MB test copy at 0x1000000) in slot 45, which plays from boot, and records 30 s with harness arec.
  LoG2 song 43 fails to port (track pointer outside the song). Plan page: Artifact "Gero's Legacy Music Plan"
  (scratchpad musicpage/music.html); areas.json "music" key sets an area's track.
- Music APPLIED (user picks 2026-11-02): log4/music.json -> tools/music.apply_plan (build, after the startup port):
  LoG2 songs share the samples/bank/bank B + song 0 that port() put at 0xF80000 for slot 45; music.add() places each
  further LoG2 song at 0xB00000+ (226 KB) into a BF slot only BF maps used (l2_slots); LoG2 song 0 reuses the copy after
  bank B (a relocated copy hung the game: black screen). Chapter cards: slot 37 <- BF 00's entry. Every LoG4 area's
  +0x24 is set (98 areas). Verified: IWRAM 0x030038B0 = pointer to the playing song's table entry; every area group
  plays its slot (scratchpad mus2/verify2.py), and every LoG2 slot makes sound.
- LEVEL-UP CRASH FIXED (user report 2026-11-02, assertion "Energy attack level requested for attack which doesn't
  exist for player!" after a kill): BF's level-up event checks two BF moves per character with native 0xEA, and the VM
  evaluates both sides of its `or`, so every level-up of a character without those moves asserted (all LoG4 characters
  since the skill clean-ups). tools/levelup.py (build step after the enemy rows) neutralises the 18 checks and NOPs the
  0xE9/0xEA asserts. Reproduced on the previous build (assert screen), fixed on the new one (level-up, stat points).
- SAVE-SLOT CHAPTER NAME FIXED (every save said "Red Ribbon Science"): the slot builder 0x08004BC0 runs the step list
  0x0877CCA4 (event 6) and stores its result (a UI index) as the slot's chapter name. BF's packed script returns
  602 + the number of BF story flags 13/43/54/73/76/119/121/125/137/147 set; LoG4 sets none. tools/saga.py writes an
  unpacked replacement at 0xAFFF00 that checks LoG4's chapter-start flags newest first (390 secret, 380, 360, 340,
  330, 304, 300, 320, 315, 310, else 602) and repoints the list. Verified on the save screen: Siblings (ch5),
  Activation, The Last Stand, First Steps. If a chapter is added, add its start flag there.
- PARTY TABS (Status / Inventory / Skills / Journal) read "17" / "18" after the conversion (flag 306): BF draws each
  tab with a fixed UI 158 + character (0x08014FE0-0x080150D4), so act 3 showed LAPIS / LAZULI next to "ANDROID 18".
  tools/tabname.py + log4/asm/tabname.s hook characters 1 and 3 (UI 1707 / 1708, at 0xAFFF80). Verified both ways.
- LoG2 MAP PROPS RECOLOURED (user screenshots 2026-11-02: pink/green blobs + grey X box in chapter 2): map OBJ
  regions (+0x28/+0x2C/+0x30) were copied with LoG2 OBJ palette indices; the two OBJ palettes match in 2 of 256 slots.
  mapimport.obj_remap (CIE94 nearest, skipping slots any act repaints) now recolours region graphics (stored type 0) and
  doors.regions uses it for door panels: boulders, signs, switches, chairs, gnome, pot, the lab doors and 17/18 pods
  (all were orange; now LoG2's teal). Verified 1:68 boulder, 1:1 door.
- 1:68/1:95 AMBUSH RIDGE fence (user: "north blocked by electric fence, no other paths"): areas.json keys
  "erase_tiles" [{layer, tiles [tx0,ty0,tx1,ty1]}] and "walkable" [[x0,y0,x1,y1]] (tools/areas.py) remove LoG2's fence
  (layer 1 + post feet on layer 2) and open its row beside the rock pillar; north edge exit [104,0,208,48] -> 1:96
  (arrival back at (104,80)). Verified walking north into the canyon.
- NO HIDDEN EXITS (user rule 2026-11-02: "make all entrances and exits clearly visible, no hidden ones unless the player
  can know"). Audit: scratchpad exits/audit.py (every warp exit, map crops + clipcheck approach frames). Changed: 1:68/1:95
  west corner exit removed; 1:97 Dry Basin is now LoG2 3:7 (BF 20:10 was a walled basin), its top-right cave mouth ->
  1:102 Raider Cave (cave mouth and east ramp lead back); 1:107 archive leaves by the east panel door (was the bottom
  wall); Docks (4:42/16:42/17:35) <-> Riverside by the pier (was the west edge behind trees); Old Mine (1:110/17:39) is
  reached through the hole atop the Generator Cave's east ramp (was a cliff behind a tree), its barred gate has an
  examine line (mine_gate). Rule for new areas: an exit must sit on a visible path end, doorway, cave mouth or pier.
- ACT 3 OPEN WORLD (2026-11-02, user: world map + side content, Act 3 only, era-accurate places). BF's Earth map (0:50,
  Mode 7) via tools/worldmap.py + log4/worldmap.json (written by log4/gen_world.py). 0:50's 35 exit records are copied
  and edited IN PLACE (same order/count; rebuilding the list from scratch broke landing): name records get LoG4 UI names
  (1709-1716), landing records LoG4 scripts (fade, era pick: Age 780 if flag 380, native 119, fade, release), unused
  places get empty rects. Landing = hold A over a place; Kami's Lookout = hold B (getter 0x0803436F). Take-off =
  native 118(0, 50, 0, x, y): talk to the Eighteen NPC (actor player_18) at every destination, walk off a map-edge path
  (walk-in strips, fly_* lists generated into scenes/act3_world_fly.scene), the hub's airship/hangar, Goku's door.
  Places: West City (772 hub 17:18 / 780 17:40), Mount Paozu 17:19, Kame House 17:20, Orange Star City 17:42 (BF 3:4,
  Hercule actor 129), Kami's Lookout 17:43 (BF 6:1), Papaya Island 17:44 (BF 7:1, announcer actor 9 likely), Diablo
  Desert 17:45 (BF 14:1, Prototype 11 = row 19/char 76, 5200 HP), Pilaf's Castle 17:46 (BF 13:1, ninja captain row
  82/char 202), Nataday Village 17:47 (BF 15:1, raider boss Butcher row 131/char 272). Side content in
  scenes/act3_world.scene: seven stone Dragon Balls (BF items 15-21, descriptions now "gone to grey stone"), flags
  409-428 (list in gen_world.py); all seven at the Lookout's palace door -> scene + Holy Water/Senzu/Dinosaur Milk.
  Verified: take-off from the hub, landing at all nine places, every content list plays (STORY=1 listtests),
  clipcheck 104 areas. maprender now skips special layers (BF 6:1's sky). Boss balance: a fresh 17 beat Prototype 11
  at 3800 HP (raised to 5200); captain/Butcher not bot-tested (fightbot couldn't find the player struct with the
  partner NPC next to it).
- DEBUG ROM (2026-11-02, user: "a separate debug mode ROM so I could skip through chapters at will"). `python3
  log4/build.py bf.gba --log2 log12.gba --proto protoD.gba --skip-art --debug` -> log4/out/LoG4_debug.gba/.bps +
  named_lists_debug.json; no clipcheck (its boot needs the real opening); release builds never see log4/debug/.
  log4/gen_debug.py writes log4/debug/{debug.scene, areas_debug.json, boot.json}: debug room 17:120 (copy of BF 6:1,
  UI 1717 "Debug Room"); build.py --debug names the opening scene act1_opening and inserts, after its setup step
  (keep 1), "unless flag 429: load 17:120 + help text, end" - so New Game opens the room; the chapter 1 NPC sets 429
  and runs act1_opening. NPC launchers (dbg_chN etc.) set every earlier chapter's flags (CH_FLAGS in gen_debug.py -
  keep it in step when chapters gain flags), set the party (Act 1 Gero / twins / androids with the outfit + upgrade),
  then `run chN_start` (chapter 6 copies ch5_end's second half). Extras: supplies, stone balls, credits, finale
  (memories set, so epilogue -> secret chapter), open world Age 772 / 780. tools/dbgtest.py boots the debug ROM and
  runs a dbg_* list through an added walk-in trigger. Room: arrival (208,296) on open floor (not the palace carpet: the
  canopy roof hides the player there); front row y 256, back row y 332. Verified: all 16 launchers end in the right area.
- Debug options (2026-11-02): bottom row of the debug room. Drone = All moves (flag 430), scientists = level 55/60/
  70/80/90/99 (flags 431-436, one at a time). gen_debug.py writes log4/debug/apply.json; build.py --debug appends
  those lines to each chapter start list (+ the opening, + dbg_ch6) so they run after the chapter's own setup.
  Moves: remove-then-add (native 164 appends without a duplicate check). Level: native 194 (0xC2) = Player_AddExp on
  the current character (BF level-up: HP/EP up + stat Points to spend + level-up page), native 200 (0xC8) pushes its
  level; the generated code adds EXP(T) - EXP(L) for the current level L; other party members via 149 swaps (151/152
  for one not in the party). Cell (6) is never levelled. BF's own selector: L cycles the selected skill, B uses it.
  Verified: ch5 at level 70 -> both twins LVL 70 with full move sets; ch4 at 60 -> drone level-up pages.
- Examine spots walked to in the emulator (tools/examtest.py: arrive, walk, press A; no added trigger). The open-world
  lists had only been run directly, so Kami's palace door (altar, 413) was UNREACHABLE (the player stops at the canopy
  ornament, below the old rect): rect now (280,252,360,308). Also: papaya_gate rect to y 104 + the announcer moved
  off the gate path (304,108); pilaf_safe rect to y 104; mine_gate (1:110 / 17:39) (76,96,172,176) - the drone /
  enemy in front of the gate pushes the player left. Lesson: test examine rects by walking to them, not via listtest.
- DIFFICULTY PASS (2026-11-02). Facts: a level-up raises HP/EP and gives 3 stat Points per level to spend on the
  Status screen ("Use Points"); STR/END etc. only change when points are spent. The android upgrade (165 x 240)
  survives level-ups (17 at level 70 keeps STR 36). Combat damage (decomp Combat_Damage 0x0800E9D8) ~
  ((a+100)a^2 >> 13 + a) x (221 - END) x move power, a = STR (POW for ki). Expected levels if every enemy is killed
  once (EXP x1): drone ~59 after ch1 / 62 / 64 by ch4; Lapis ~56 at Big Ox, 58 at the Collector; 17 carries Lapis's
  EXP into Act 3: ~60 at the Security Unit, 62 Vegeta, 63 Piccolo, 64 Super 13, 65 Gohan, 66 Sentinel, 67 Future
  Gohan, 68+ for the world-map bosses. Act 3 bosses had been tuned with fresh level-50 androids, so they were
  rescaled (stats.json "_balance": HP and hit damage each x sqrt(c), c = half the level correction): Security Unit
  3300/32, Vegeta 1100/19/17, Piccolo 1350/20/17, Super 13 1700/22/20, Gohan 1600/17/15, Sentinel 3700/33, Future
  Gohan 1850/18/17, Prototype 11 6150/40, ninja captain 3550/34, Butcher 4000/36. Bot-checked at the expected level
  with no points spent (shoot lists t_bal_su/veg/fg/p11 level 17 with native 194): Vegeta win, lost 50% of HP;
  Future Gohan win with 48/478 left; Prototype 11 win with 43/526 left; the Security Unit never touched the bot.
  The full correction (x1.4-1.8) made the bot lose to Future Gohan and Prototype 11, so it was halved. Acts 1-2 kept
  (Act 2 had fresh-level bot data: Big Ox / Collector get easier with levels but stay fair; Act 1's drone bosses
  only lack a human check).
- REACH AUDIT (2026-11-02): tools/reachaudit.py <rom> <outdir> [w:a ...] - every examine exit and every NPC whose talk
  list is a LoG4 named list gets a sentinel list (sets flag 437); the player is dropped nearby (story triggers and field
  enemies off), steps toward it pressing A every 6 frames ("sweep"), pass = flag set. Rect test point = the arrival-frame
  position (player object = arrival y - 16). OVR=<json> {name: [[x, y, face, 'seq', 'harness|lines']]} adds hand-made
  approaches. Result 114/115: fixed cache_yard (1:101, rect to y 262: the lower crate blocked it). Hand-verified:
  arena_locked (examtest shows the locked-gate text), mine_gate / ch9_sealed / ch10_cache (the walled pocket in 17:40
  is reached round the right-hand strip), zmart_clerk (talk from the left). BF's wandering West City townsfolk can
  fail when they walk off. Run it after any area change.
- Status-screen portraits (user screenshot 2026-11-02: green blotches on Lapis/Lazuli): the menus reload the OBJ
  palette from BF's RGB555 copy at ROM 0x5652C (16 references), not the RGB888 triples at 0x701B0, so LoG4's 10 new
  global OBJ colours (palette_alloc.json) fell back to BF's. tools/portraits.apply_palette now writes both.
- Tools for packed BF scripts: tools/unpack4.py runs BF's own ARM decompressor (0x08049120, via IWRAM code dumped to
  tools/iwram_code.bin) in unicorn (pip install unicorn) and returns the type-4 step payload; tools/watchrd(.c) logs
  Thumb/ARM loads from an address range with PC/LR and stack return addresses (how the saga script was found).

### Bug and lore pass (2026-11-01, user: "full pass of each chapter for these kinds of bugs and lore inconsistencies")
- Chapter 1: the opening no longer keeps BF step 3 (Snake Way's packed setup walked the player in from the map edge,
  through the rock wall); it loads 1:1 with Gero at (112,200). Gevo leaves: walks to the tank-room door, the door panels
  open (scripted moves of door_540fd4_0_0/_1), he walks into the doorway, fade, and the scene swaps to 1:61 (no Gevo).
  The opening now ENDS IN 1:61 (clipcheck/listtest test hook moved there).
- Chapter 1 -> 2: the drone terminal in 1:61 is chapter 1's goal (ch1_end, flag 309: calibration lines -> run ch2_start).
  The south corridor is no longer a door (A facing down: lift_talk). Chapter 2 happens in Gero's own lab at night: 1:67
  and 1:73 are now map_from 1:1 (were BF's Dr. Brief's Lab map, which the user recognised); the drone terminal spots
  are the console (same bytecode action). 1:62's back door has two complementary 'when' warps (1:61 before flag 310,
  1:67 after); tools/doors.py shares one set of panels per doorway, clipcheck walks only the first. Chapter 2's ending
  runs ch3_start directly (1:69's south corridor no longer leads to 1:73).
- Scrambled sprites when the drone fired (user screenshot): BF's attack code steps to fixed frame numbers; the drone's
  LoG2 animations had fewer frames (e.g. slot 10: BF 11, ours 2), the engine read past the frame list and its upload
  copied ~6 KB of EWRAM into OBJ VRAM (wrapping to tile 0). Fixed with "stretch": true on party_drone_114/115 and
  player_gero_106-108 (every slot keeps BF's frame count). Verified: no more VRAM writes past the end in 1:69 combat.
  Rule: any player/enemy actor built from LoG2 frames needs "stretch".
- Lore: Trunks's finale no longer mentions 18's marriage/daughter or 17 the ranger (he left the past right after the
  Cell Games); epilogue wording; Act 2 old man ("Not so many years ago"); Android 20 speaks with the L2 Gero portrait
  after the conversion; a16 scene no longer has Prototype 12's wreckage in the tank room.
- Checked by script: every scene "call 119" placement is on walkable floor. Story lists of ch3-ch10 replayed with
  tools/listtest.py (sheets in scratchpad c1/chk*).

## RESUME HERE (updated 2026-11-01)
Last good build (2026-11-01): `python3 log4/build.py bf.gba --log2 log12.gba --proto protoD.gba --skip-art` -> clipcheck 52/52, patch 1,338,338 bytes (Prototype D adds Super 13 + 13/14/15 portraits; see RE_NOTES). Older: -> clipcheck 19/19 pass, patch 868,870 bytes
(log4/out/LoG4.bps, sent 2026-11-01). Act 1 (chapters 1-4) and Act 2 (chapters 5-6) play start to end as one story; the
dev shortcuts are gone (to test Act 2 quickly, use a test ROM hook: tools/talktest.py / clipcheck make_test_rom).
Next: the 17/18 forms (outfit swap after the conversion, flag 306) and Act 3 (17/18 in Trunks's timeline); optional:
real prototype/drone boss fights (needs BF's boss/enemy definition table decoded), the epilogue and the secret Cell chapter.

### Done 2026-11-01: animated doors (user: "fix the door overlap and give it an animation, for every future door")
tools/doors.py, applied automatically by the build to every warp door that has a map door region; the clipping gate
checks the player stays visible while walking into every door (see RE_NOTES "Animated doors"). Lab doors 1:1, 1:61,
1:62 verified in the emulator: closed -> half slid up -> open, the player walks into the doorway in front of everything.

### Act 1, chapter 2 "An Enemy Bullet": playable (verified 2026-11-01, log4/scenes/act1_ch2.scene)
- Main lab south corridor -> command room 1:67 (BF Dr. Brief's Lab map, name "Control Room" UI 537). Arrival trigger
  (flag 310) -> card (UI 1452/1453) -> radio scene: Squad Seven ambushed in the Northern Wastelands; journal "Take control
  of a drone at the main console".
- Main console (A facing up at 200,140-280,176) = plain bytecode exit: if 310 set and 311 clear, the drone joins and
  becomes the player (151 2; 149 2) and the battlefield loads. Battlefield 1:68 = LoG2 Northern Wastelands 3:1
  (0x67542C, template 15:10 for combat flag/music, name "Northern Wilderness"): drone arrives at (160,420); arrival
  trigger ch2_field (flag 313) plays the radio lines; two BF green-helmet soldiers (type 8) on the path; Gevo by the
  fence. Reaching him (104,96-248,150, flag 311): reinforcements denied for "a boy called Goku", a single shot, fade,
  Gero back as the player in the command room: grief lines, journal "Goku.", flag 312.
- Drone stats raised (HP 160, END 18). Tested by running past the soldiers; a bot that stands and mashes attacks dies
  (soldiers lob bombs; each enemy object may spawn more than one soldier). Worth a human playtest for balance.
- Fixed on the way: side doors (walk LEFT/RIGHT) in clipcheck; map_from to BF maps in doors.plan; the frozen-player
  trap (arrival inside a wall); enemy param = definition id.

### Act 1, chapter 3 "The Boy Called Goku": playable (verified 2026-11-01, log4/scenes/act1_ch3.scene)
- Chapter 2's ending now loads the post-Gevo command room 1:73 (same map; left door -> 1:69).
- 1:69 main lab under attack (arrival trigger, flag 315: card UI 1454/1455, alarms, technician, journal "Recover the android
  blueprints"); two looting soldiers; the drone terminals still swap Gero/drone. Its tank-room door -> 1:70.
- 1:70 tank room under attack (two looters): the pod (A facing up, 112,176-168,212) gives the blueprints + self-destruct
  (flags 316/317) and RELOADS the room (exit conditions are only read on load) so the south corridor (when 317) opens
  -> 1:71 Northern Wastelands (LoG2 3:7): arrival lines (flag 319), two looters on the climb; the foot of the old
  bridge (144,300-224,340; the bridge itself isn't walkable in the imported collision) ends the chapter (flag 318):
  the oath to Goku, fade -> 1:72 the abandoned bunker (same lab map, empty), journal "Rebuild.", free control.
- Fixed on the way: LoG2 map +0x44 = 5 hung BF (mapimport forces 1); clipcheck judges only placed characters (BF
  enemies roam behind props) and walks conditional warp doors.

### Act 1, chapter 4 "The First Androids": playable (verified 2026-11-01, log4/scenes/act1_ch4.scene) - Act 1 complete
- Chapter 3's ending puts Gero in the bunker 1:72, where the arrival trigger (flag 320) plays the card (UI 1456/1457):
  "Years later", prototypes 1-15 failed, journal "Restore power: three relays".
- Relays (A-press events, flags 321-323): 1:72 old terminal spot (facing up), 1:74 bunker tank room's bottom-right machines
  (facing down), 1:76 bunker incubator's right wall (facing right). The third one runs ch4_power: generators back on
  (flag 324), journal "Activate Android 16".
- Boss fight (verified 2026-11-01): the third relay's ch4_power swaps to the drone and loads the bunker incubator 1:76,
  where Prototype 12 has broken out: enemy stats row 30 (unused in BF; tools/stats.apply_enemies, log4/stats.json
  "enemies") drawn as BF's Death Machine (character 76), HP 420, spawn condition script "324 set and 327 clear", death
  script "call 29 327". A bot with melee beats it at full HP (the drone levels up). Not in the tank room: its two door
  panels + Android 16 + this big sprite overflowed OBJ VRAM (ki blasts garbled tiles). BF row 34 (level byte 1) took
  no damage at all - use row 30 / 11 for new enemies.
- Android 16 (actor android16) stands in 1:74; talking to him once Prototype 12 is destroyed plays the scene (flag 325): Gevo's face and
  voice, refuses to destroy the drone, Gero shelves him ("Too gentle. Like him."), "I will carry it myself".
- The conversion pod in 1:76 (A facing up below it, 160,228-208,256): Gero converts himself (flag 326), reload into 1:78
  (LoG2 room 65, the split pod): "Android 20. I feel nothing at all. Good." -> "End of Act One." -> West City, where
  chapter 5's opening fires on arrival: Act 2 begins.
- Testing tip: tools/talktest.py-style hook + 'w8 30010e5 <bits>' presets flags 320-327 (bit n = flag 320+n).

### Androids 13, 14, 15 (2026-11-01, user request: "get Android 13/14/15 into the game, lore accurate")
- Recovered from retail BF: their scouter text only (UI 1050-1057). Every sprite frame in the ROM was checked against the
  actor table (decomp extraction: 7,240 frames, 1 orphan = a Kid Buu frame): no 13/14/15/Super 13 graphics survive (the
  Super 13 sprite is in the prototype build only, spawned by its "Super Janemba" debug option).
- In the game now: Act 1's failed prototypes are 1-12 (boss = Prototype 12); after the conversion, Android 20 orders the
  bunker computer to build designs 13, 14 and 15 to kill Goku (the film's lore). Verified in the emulator.
- Planned (design doc "Story decisions (Nov 1)"): Act 3, Trunks's timeline - Goku is dead, 17/18 kill Gero, so the computer
  sends 13/14/15 after the renegades; Super 13 is the boss. Art requested: P14-P17 enemy sets, R8 portraits, E10/E11
  effects (Art Needs list). Keep Super 13 frames within 48x48 (OBJ VRAM).

### Title menu, legal screen, teaser (2026-11-01)
- Title menu items re-centred in the art's bar (tools/title.py MENU_IMMS: x 86/166, y 150, both menus).
- Legal screen (front-end bitmap 0x55620, literal 0x4EFC): first line redrawn as "Dragon Ball Z: Gero's Legacy"
  (tools/title.py legal_bitmap: Liberation Sans 9.6 px + 1/4 px stroke at 4x, box-filtered to the screen's grey ramp).
- Credits name: SMH.
- Teaser v3 (scratchpad tz2/teaser3.py, ~63 s, Era of Darkness): footage from the --shoot ROM (log4/build.py --shoot
  adds log4/shoot/*.scene party/warp lists and writes out/LoG4_shoot.gba, never a release; tz2/shoot.py records with
  tools/listtest.py NAMED=out/named_lists_shoot.json) intercut with the project's art (U14a/b, U13, U9a/c, R1/R2/R5, U1).

### Credits (2026-11-01)
- log4/scenes/credits.scene, list "credits": run after Act 3's "The End" and after the secret chapter. Cards over
  native-115 backdrops (West City 17:32, Kame island 17:20), camera views chosen away from both possible player
  positions. Creator credit "smh4004" (edit the scene to change it). Verified in the emulator (tools/listtest.py).

### Epilogue "Another Timeline" + secret chapter "First Steps" (2026-11-01)
- Epilogue (end of log4/scenes/act3_ch10.scene, card UI 1470/1471): native 115 loads 17:32 (West City, Trunks by the
  Z-Mart) with the camera on him while the player stays off screen at the 17:24 arrival point (115 only moves the
  camera). Age 788: Trunks leaves the time machine ready; in the morning the machine is gone and so is he.
- Unlock: Eighteen's three memories (341 fruit stall, 370 Mt. Paozu, 371 Kame House) + the mother and son spared (344)
  -> "run fs_start"; otherwise "The End" with a hint. Secret chapter: log4/scenes/secret_first_steps.scene (card UI
  1472/1473), flags 390-397, areas 17:25-17:31 (+17:33 backdrop):
  17:25 incubator (Cell wakes) -> 17:26 tank room (16's pod) -> 17:27 main lab (one Cyborg, BF row 17; Gero's
  recording on the console; south corridor out) -> 17:28 West City Age 788 (Trunks) -> 17:29 arena (Super Saiyan
  Trunks, row 24, LoG2 actor 131) -> 17:30 aftermath (Trunks lying; Cell takes the machine) -> 17:31 Age 763, a clearing
  outside Gingertown (LoG2 10:16; the larva crawls onto the dug-up patch) -> narration over 17:33 (LoG2 10:10) -> end.
- Player: Imperfect Cell = character 6 (BF Vegito's slot, form 39, actor 275 = player_cell: P10 sheets re-cleaned to
  32x32 (P10s_*) + LoG2 Imperfect Cell actor 25 shrunk x0.625 for combat). Skills: Energy Blast, Kamehameha, Instant
  Transmission. The larva = character 4 (BF Vegeta's slot) in form 27 (actor 271 = player_larva, P11 sheets).
- Lessons (RE_NOTES has details): a never-used character starts at 0 HP (heal after the area load); BF recomputes a
  character's stats on level-up from its own growth (Cell dropped to 20 STR), so his enemies give 0 EXP; kill EXP is
  scaled by the level gap; switching to a Super Saiyan form (flags 0x5x) by script left the journal box stuck; text
  narrated over a faded-out screen is invisible (four old cases fixed: ch7 opening, Yamcha, ch10 "Five years later",
  the Act 3 closing lines).
- Bot playthrough of the whole secret chapter from a fresh boot (tools/listtest.py + scratchpad nav scripts): Cyborg,
  then Trunks 1700 HP (str 17 / pow 16, behaviour 0x8A): the bot wins with 143/440 HP at the lowest.
- tools/listtest.py: run any named list from a fresh boot (STORY=1 keeps arrival triggers). Savestates from older
  builds are useless after area/scene changes (the current AreaEntry pointer and running script pointers move).

### Future Gohan and Future Trunks sprites from LoG2 (2026-11-01)
- LoG2's actor list (slice 0x3B4F30) has entry 51 = one-armed Super Saiyan Future Gohan (a cutscene actor: idle, walk,
  a fall that ends with his hair turning black; no attacks) and entry 153 = Future Gohan with both arms (full fighter set).
- future_gohan (ch10 boss) = BF Gohan's record 97 with idle/walk/fall/get-up from LoG2 51, and attacks/hurt/ki from
  LoG2 153 with the left arm removed and the hair turned gold (tools/onearm.py, actors.json "log2_edit"). The P7 sheets
  are no longer used. Known limit: facing right shows the mirrored left-facing frame, so the visible arm swaps sides.
- gohan_774 (ch9 boss, 17:16) = LoG2 153 unedited (Age 774: he still has both arms; BF's purple-gi Gohan stays as
  gohan_bf for Age 767).
- trunks_future (17:24) = LoG2 125 as an NPC; gohan_fallen (17:23) = the last frame of LoG2 51's fall.
- Enemy row field +8 is the behaviour class (likely): BF row 21's 0x8A ("fighter") chases and attacks; row 22's 0x8B
  hardly fights back (the bot won losing ~20 HP). stats.json "ai" sets it. Row 14 (old Future Gohan row) grabs the
  player and both lock up on the first hit, with any sprite (also BF Gohan's): that was the "slot 18 freeze".
  Future Gohan moved to row 23. Bot results (player 395-421 HP, chapter 9 reached from end8 without Super 13's XP):
  Gohan 774 row 22, 0x8A, 1400 HP, str 15 / pow 14: bot wins, lowest HP 141. Future Gohan row 23, 0x8A, 1600 HP,
  str 16 / pow 15: bot wins, lowest HP 68 (17/16 lost once in the full chain at boss 260 HP; str 20 kills the bot). tools/fightbot.py now picks the HP copy that sits
  behind a position struct.
- tools/clipcheck.py pairs wide frames (someone lying down, 32 px) with their shadow too (tolerance ow/2-2).
- Verified 2026-11-01: chapter 9 Gohan -> chapter 10 rain, fight, aftermath (Gohan lying beside the player) and finale
  (Trunks standing at the crossroads) play through to flag 386 in the emulator.
- tools/sprites.py: log2_slots values may name another LoG2 actor ("r51:3@0:2"); slices may run backwards ("3@1:-5:-1");
  log2_record accepts "rN" (actor list entry N).

### Chapter 9 side content + chapter 10 "The Last Stand" (2026-11-01)
- Chapter 9 hub (Age 772): after Super 13, Capsule Corporation 17:18 is the twins' base. Optional visits: Bulma's
  airship (examine, left side of the path) -> Mt. Paozu 17:19 (Chi-Chi, BF actor 57, portrait #20: "every night I set
  his plate out"; 18's third memory, flag 370); the main building's hangar (examine up) -> Roshi's island 17:20 (LoG2
  11:4, BF actor 177, portrait #74: Krillin's name and the normal life he wanted, flag 371). 18 at the base comments on
  what was visited (ch9_hub18). The gate (walk-in) -> Age 774, Gohan. Flags 368 hub, 370, 371.
- Chapter 10 (log4/scenes/act3_ch10.scene, flags 380-386, areas 17:21-17:24): Age 780 rain, one-armed Super Saiyan
  Future Gohan (actor future_gohan, stats row 23; sprites from LoG2, see below) -> his death (17:23 shows him fallen,
  hair black again: gohan_fallen), "Stop counting them", 18 covers his face, Trunks finds him -> Age 785: Future Trunks
  (17:24, trunks_future = LoG2 actor 125, jacket and sword) tells them about the other timeline (18 + Krillin, 17 the park ranger); 18
  remembers their mother's name; the end, with a teaser for the Cell epilogue (an incubator still humming).
- tools/sprites.py slot specs: 'SHEET#a:b' = raw frames a..b-1 before the down/up/side split. Enemies in areas.json can
  name an actor ("actor": name). tools/mapimport.py now tolerates LoG2-only map door classes (empty-rect door instead).
- Boss balance: Super 13 (row 21) 1500 HP: bot wins with ~140/366 HP left. The two Gohan fights were retested
  2026-11-01 (see "Future Gohan and Future Trunks sprites" above).
- Next: a human playtest of Acts 1-3 and the secret chapter.

### Act 3 chapter 9 "Years of Terror" (verified 2026-11-01, log4/scenes/act3_ch9.scene, flags 360-367)
- Chapter 8's night scene runs into ch9_start (card UI 1466/1467). 17:11 Capsule Corporation (Age 768): Bulma (BF actor
  32) with baby Trunks; 18's second memory (a woman singing); the computer's broadcast "return to base".
- 17:12-17:15 Gero's Act 1 bunker (world 17 copies of 1:72/1:74/1:76, act3 palette): the computer's log shows 14/15's
  portraits ("parts harvested"); Android 16's empty pod (examine); Super 13 in the incubator: his speech sets flag 367 and
  reloads the room so he spawns (stats row 21, character 316; 2200 HP). Death -> 17:15: he comes apart, 17 smashes the
  console, "Years pass. Age 774."
- 17:16 West City ruins: Gohan (gohan_774 = LoG2 actor 153, Future Gohan with both arms; row 22; R4b portraits) -> 17:17: he
  escapes and loses his arm. "End of Chapter 9."
- Enemy rows that work: 18, 21, 22, 30, 70, 136. Rows 26 (Majin Buu) and 122 (Super Janemba) don't spawn usable enemies.
- tools/fightbot.py takes the arrival point as optional args (the player struct is found near it).
- Tests: scratchpad c8/ chain9b.py / chain9c.py (states inc_60 etc.).
- Next: chapter 10 "The Last Stand" (Age 780, one-armed Future Gohan from the P7 sheets as the boss; then Future Trunks
  returns, Age 785), the epilogue (Cell takes the time machine) and the secret Cell chapter. Optional chapter 9 side
  content: Chi-Chi/Ox-King (BF actor 57), Roshi at Kame House.

### Act 3 chapter 8 "The Massacre" (verified 2026-11-01, log4/scenes/act3_ch8.scene, flags 340-351)
- Chapter 7's end runs straight into ch8_start (card UI 1464/1465). West City, Age 767 = world 17 (BF West City map, act3
  palette), areas 17:1-17:10 + 16:2 (night). Scenes are driven by arrival triggers; boss death scripts (log4/stats.json)
  set the flag, heal, and load the next area.
- Flow: 17:1 the twins' old city (Z-Mart, townsfolk: a cop who almost recognises them; fruit stall = 18's first memory,
  flag 341) -> crossroads (needs 341) -> 17:2 the Z Fighters land (Piccolo, Vegeta, Krillin, Tien, Yamcha, Gohan) ->
  17:3 Vegeta fight (row 70) -> 17:4 his last words; optional mother and son (spare = flag 344, changes Krillin's and the
  night scene's lines); Tien's last stand (scene) -> 17:6 Yamcha (scene; Tien/Yamcha have no fighting sprites) -> 17:7
  Krillin fight as Eighteen (row 18) -> 17:8 aftermath + Piccolo/Gohan -> 17:9 Piccolo fight as Seventeen (row 136) ->
  17:10 "Gohan, RUN!" -> 16:2 night on the Z-Mart roof: counting, their mother's name, the radio. "End of Chapter 8."
- Android upgrade at the conversion: native 165(c, 240) (tools/outfit.py hook_rm) = STR/POW +22, END +18, SPD +12,
  HP +230, EP +70. Balance checked with tools/fightbot.py (a chasing bot wins all three fights with HP to spare: Vegeta
  ends ~185/300, Piccolo takes about twice as long). Human playtest still worthwhile.
- Tests: scratchpad c8/ (ch8a.py, p2.txt, toland.txt, chain.py).

### 17/18 outfit swap + Act 3 chapter 7 "Activation" (verified 2026-11-01)
- The conversion (end of chapter 6) adds skill 18 "Outfit" to both twins and switches them to forms 14/23 (Android 17 /
  18 sprites: P1/P2 sheets + LoG2 17/18 walk, melee, hurt, ki), reloading the tank room as 1:79 with Eighteen as an NPC.
  L selects Outfit, B toggles android clothes <-> old clothes (tools/outfit.py). Super Saiyan is removed from both twins
  at the start of chapter 5.
- Chapter 7 (log4/scenes/act3_ch7.scene, flags 330-332) runs straight on from the conversion: tests fail, they are shut
  down, card (UI 1462/1463), Age 767 in the pod room 1:80 (LoG2 8:60, pods 16/17/18): Gero wakes them, Seventeen kills
  him (reload as 1:81 without him), the bunker computer starts Units 13/14/15, journal "Leave Dr. Gero's hidden
  laboratory". 1:81 south passage -> cave 1:82 (LoG2 8:37) -> Northern Wilderness 1:83 (LoG2 8:35): arrival trigger
  ch7_end (flag 332), "End of Chapter 7", journal "Find a city".
- Tests: scratchpad o17/ (ch6c.py plays chapter 6 -> 7 from a ch5_end trigger; tog*.txt outfit toggles; end7.py).
  log4/out/named_lists.json (written by the build) has every named list address for test triggers.
- Next: chapter 9 "Years of Terror" (Bulma and kid Trunks, Gohan encounters, Super 13 in the Act 1 bunker). DECIDED (user, 2026-11-01): Androids 13/14/15 = Super 13 only.
  The computer can only finish one android without Gero, so it merges 14's and 15's cores into 13; Super 13 (actor
  super13, character 316) is a chapter 9 boss in Gero's Act 1 bunker (1:72-1:76 maps), lured there by the computer.
  14/15 portraits (speakers 210/211) can show on the computer screen; his lines use proto_android13 (209) until R8
  Super 13 portraits arrive (optional). P14-P16 and E10/E11 are dropped from the art list.

### Prototype D recovery (2026-11-01)
- Super Android 13 = actor `super13` (307, character 316), copied whole from Prototype D actor 230; works as an enemy.
- Portraits for Android 13/14/15 from the prototype = speakers 209/210/211. Art Needs: P17 dropped, R8 now Super 13 only,
  E11 optional. Still to draw: P14-P16 field sprites for 13/14/15, E10.

### Act 2, chapter 5 "Siblings": first playable slice WORKS (2026-11-01)
- Lapis = party character 1 (BF Gohan; actors 97-105), Lazuli = character 3 (BF Trunks; actors 260-262), all 22 player
  slots from the cleaned P3/P4 sheets; names, portraits (R1/R2), stats. West City (4:1) uses the act2 palette.
- Act 2 starts when Act 1's finale loads West City (ch4_pod -> 119 4 1 1 268 296; ch5_start fires on arrival). The dev
  shortcuts are removed; the lab's south corridor leads to the command room.
- West City trigger at the arrival point (flag 300 clear) runs ch5_start (log4/scenes/act2_siblings.scene): set flag,
  party swap (join 1, 3; make 1 player; Gero and drone leave), chapter card, field return (115/121/165, then 120(1);
  119(4,1,1,268,304); 121(60)), twins' dialogue, journal, 47; 51(0). Verified: card, West City fades in with Lapis
  at the Z-Mart door and the HUD, dialogue, then free control as Lapis with correct colours.
- Team swap = BF's save points (A on the Capsule pad -> Switch Characters); verified Lapis <-> Lazuli, picker colours
  fixed (MENU_SLOTS). Fight as Lapis verified in East District 2:11.
- West City cleaned (Vegeta, actor 27, blond kid dropped; BF's chapter-card and flag-197 exits dropped); townsfolk and
  police have new lines; Hercule (actor 129) added at (360,330).
- Chapter 5 quests (verified 2026-11-01 with tools/talktest.py, every branch): the fence (man, obj 5 -> list
  wc_man_green, flag 301) and Hercule (wc_hercule, flag 302); each runs ch5_check, which plays ch5_end once both are
  done (flag 303: Lazuli spots the coat man; journal "Hide out until nightfall"; next stop the old warehouse by the docks).
  Repeat talks give "done" lines. Fixed on the way: type-7 step pointer is at +4; jump values are label id - 1.
- Side job "Ditch the Patrol" (verified 2026-11-01): the patrol cop (patrol_cop = clone of BF police actor 60, at
  (540,400), list wc_cop_chase) -> taunt, he lunges, flag 307, journal "Lose the cop in the park"; walk into the park
  (trigger (40,420)-(200,540), list park_hide) -> the cop runs past and gives up, then the man in the long coat (Gero,
  actor 106, standing at (600,320), list wc_coat_man) walks over and writes something down; flag 308. Chapter 5 now ends
  when 301, 302 and 308 are all set (ch5_check).
- Chapter 6 "Taken" (verified 2026-11-01, whole chain from Hercule to the lab, flags 300-306): ch5_end runs the card
  (UI 1460/1461) and loads West City at night (16:1, BF map, moonlit BG palette, world 16) with the twins in the park;
  curfew police (actor 60), three drones; walking into the crossroads (392,336)-(456,470) runs ch6_ambush: the drones
  close in, a voice ("Subjects located. Seventeen and Eighteen."), a white flash, then the tank-room copy 1:66 with Gero
  (actor 106) and Lazuli (260) as NPCs: Gero's lines, fade, "The procedure took eleven days", flag 306, journal "Lapis
  and Lazuli are gone", free control in the lab (still in Lapis's sprite until the 17/18 forms exist).
Next for Act 2: optional drone fight before the capture (needs an enemy type for the drone: BF enemy table not decoded
yet); East District 439 has no Act 2 content yet (design doc lists it as an Act 2 map).

### Trailer v6 (2026-11-02, user: "new hype trailer, same music, completely new format, no dialogue, name features,
spoiler-free rundown, ominous tease, COMING SOON on a Gero's lab computer screen")
GerosLegacy_trailer_v6.mp4 (86 s, 1080p30) = tools/trailer6.py <Era of Darkness mp3> <out> (frames composed in numpy,
piped to ffmpeg). Footage: tools/trailer6_shoot.py records clips with listtest + harness `rec` from a --shoot ROM (new
shoot lists sh_w_* / sh_wc767 = Seventeen in the open-world places and Age 767 West City), plus the teaser-4 clips
(scratchpad tz4/). Cuts land on the music's onsets (19.75, 25.1, 28.0, 32.75, 38.75, 43.1, 46.75, 49.7, 53.45, 57.65,
61.6, 64.45). Call-outs are typed in VT323 (OFL, Google Fonts) in phosphor green: "BEFORE THE ANDROIDS...", "A
SCIENTIST. TWO RUNAWAYS.", "THREE ACTS.", the act names, then the features (drone, world map, side quests and hidden
memories, optional bosses, outfits, new boss fights, LoG2 maps / Buu's Fury engine). Tease: the humming incubator with
signal tearing, "SPECIMEN STATUS: ALIVE". Ending: Gero's terminal types the project load and COMING SOON, then the
CRT switches off. Crops skip the HUD and the area-name banner (start clips 3+ s in, or zoom off the bottom).

### Teaser v3 (made 2026-11-01 on request: "remake the teaser with the new stuff, 45-50 s")
log4/out/GerosLegacy_teaser_v3.mp4 (49.6 s) = tools/teaser.py <mp3> <out> <footage dir> (old script: tools/teaser_v2.py).
Shots: main lab (Gero, Gevo, drone) -> animated door -> tank room -> West City day (Lapis out of Z-Mart) -> the park
with the man in the long coat watching -> night streets with drones -> drones close in -> the lab with the twins and Gero
-> full-res 17 & 18 art -> logo. Lines in the game's own font: "A soldier that never tires...", "Years later.",
"Somebody else was watching.", "Subjects located.", "Your old names end tonight." Draft-3 style kept (letterboxed,
graded, dissolves, no cards); music = Era of Darkness from 0 s (swell at 20 s on the park shot).
Footage: scratchpad t3/ (*.mkv recorded with harness `rec` from save states; recorder scripts rec_act2.py / stage.py
there). Game font: tools/gamefont.py builds tools/gamefont_atlas.npz (51 glyphs) from fully typed dialogue pages in
footage + the scene scripts, and renders any text with it.

## 2026-11-03 (evening): second length pass, cleanups, Gero's moves (user: "Do step 3, then 4 ... then step 1")
- The music pass is DONE (user, 2026-11-03: "We already did step 2"): log4/music.json is the user's plan. New areas take
  their neighbour's track (added 2026-11-03: 1:113 <- 1:71, 1:114 <- 1:108, 4:46 <- 4:45, 16:46/16:47 <- 16:1,
  1:115/1:117 <- 1:81, 1:116 <- 1:111, 17:48/17:49 <- 17:40). Ask the user before changing any pick.
- New content (log4/gen_more.py ch1_jobs / ch2_jobs / ch6_jobs / ch7_quarters; scenes in the chapter files):
  ch1 "Rogue Targets" (Range Sergeant; rows 3/4/5 re-statted as training mechanoids, char 187, ai 359; flags 496 job,
  497-499 kills, 500 reward); ch2 "The Squad Radio" (Cpl. Mori's sb_again; parts radio_antenna 1:100, radio_battery
  1:101, radio_handset 1:68; flags 501-505) -> the raider sniper on the Scorched Canyon's east rim (row 46, char 247,
  ai 533; 506); ch6 "Mrs. Oda" (Riverside NPC actor 183, her bag on the Docks fence; 531-533); ch7 Gero's Quarters
  1:117 (BF Chi-Chi's room 2:5, UI 1727) through the misty passage on the right of the hidden lab's cave 1:82: diary
  538, Gevo's photograph -> key 535, the wall safe 536 wakes Gero's sentry (row 58, char 142, ai 249; 537), the spare
  shutdown remote + blueprints 539. Free flags left: 442-449, 453-454, 458-459, 468-469, 475-479, 487-489, 507-509,
  540-543 (544-551 = Super 17's byte).
- Journal goals: 65 now; the table moved from 0xF7EA00 (1.5 KB, overflowed) to 0xF3C000 (after the ki effects).
- Cleanups: the Research Archive's LoG2 save pad (map OBJ region 1) is dropped: areas.py 'keep_regions' now works on
  LoG2 imports too. The five older reachaudit failures were real and are fixed through gen_more.reach_fixes (MOD_DOOR /
  MOD_SPAWN edit the generators' own entries): arena gate 1:93 and bunker door 17:37 (examine strips at the map edge too
  narrow to stand in, widened), relay node 3 moved off the mine gate's approach, the Z-Mart clerk moved out of the
  corner between a wall, plants and a table, the ch10 cache moved clear of the fly-away zone (its text now matches the
  trampled patch where the stall stood).
- Gero's moves (user: "make Gero's kamehameha replaced with the full power energy wave as well, keep instant
  transmission"): only the debug all-moves option gives Gero skills; gen_debug MOVES[0] = [7, 6, 14]. Checked in the
  emulator (shoot list t_gero_moves): the wave fires green from Gero's own hand-beam frame; Instant Transmission (hold
  B, release, then a direction) charges with BF's yellow aura on Gero's sprite and fades him next to an enemy: no Goku
  frames anywhere, nothing to fix.
- Bosses bot-tested (shoot lists t_bal_rogue / t_bal_sniper / t_bal_sentry, scratchpad bosses2/run.py): rogue
  mechanoid 340 won (fresh drone); sniper 520 and 380 beat the melee-only bot (it can't catch a kiter) -> 300, wants a
  human check; sentry 1700 too easy -> 2400 / 26 (bot down to 195 of 415 HP before winning).
- Checks: clipcheck 0 failing; reachaudit of every touched area passes (34 + 6 re-checked); full storyrun (242 lists):
  14 CHECKs, all explained - branches that need items or kills first (surv_b 505, mrs_oda 533, quarters_safe 539,
  wc_hercule 462, ch5_check 460, ch5_rest 467, and the older zmart_clerk / museum_curator / ch8_stall / lookout_door /
  fs_wake), test artifacts (breaker_doors: storyrun drops flags a list itself clears, so the wrong-order branch runs;
  ch7_archive: verified directly, 480 is set; file_range: the injected trigger lands in the Fuel Depot's exit - the
  list sets 510 from the lab, and the real spot passes reachaudit). Each new side job's payoff branch was run with
  its prerequisite flags preset: 500, 505, 533, 539 all set. Length report: 4.9 h (story 4.3 h).
- The third rogue mechanoid moved from the Fuel Depot (cramped, on the army file's approach) to the Target Field.

## 2026-11-03 (later): length pass ("all five options, plus more lore and side content"), Super 17 changes
- log4/gen_more.py writes the new areas and patches the doors/spawns/enemies of the areas they hang off (entries tagged
  _more=1; re-running replaces them). `python3 log4/gen_more.py --preview <dir>` draws every new/patched area with doors
  (red), events (yellow), NPCs (cyan), enemies (magenta) and arrival points (green). tools/mapview.py renders any map
  (bf:w:a, l2:0xPTR, out:w:a) with a 16 px grid and the floor tinted; LoG2 floor masks are read straight from log2.gba
  (areagen kind 'l2raw'), so placing things on a new LoG2 map no longer needs a build first.
- New areas: 1:113 Supply Depot (LoG2 Warlord's Domain cave 0x606dc4), 1:114 Prototype Graveyard (BF 15:18), 4:46 Museum
  Storeroom (BF 14:3), 16:46 Old House (BF 3:6), 16:47 Rooftops (LoG2 CC roof 0x5d13c4), 1:115 Research Archive (LoG2
  0x5e3de4; a dead end: logs are read from the centre aisle, the shelf gaps are too narrow to walk), 1:116 Bio Wing
  (LoG2 0x5e6648; reached through the Security Wing's open bottom edge once 485 is set), 17:48 Burning District (LoG2 Sasebo 0x5f3bf4), 17:49 Resistance Shelter
  (map of 1:113). Area names UI 1718-1726. LoG2 map imports now spill into 0xDF8000-0xF00000 once the main region
  passes 0x9C0000 (tools/areas.py SPILL; build.py asserts the actors end before it).
- Chapter changes: ch3 escape: the old bridge is out (bridge_out); the east edge of 1:71 -> the depot; its tunnel
  (depot_tunnel, needs 451) runs ch3_end. ch4: graveyard off the Mountain Pass's bottom edge. ch5: the chapter no longer
  ends by itself: ch5_check sets 460, and the mattresses in the Old Warehouse (ch5_rest) end it (and stash the ruby).
  ch6: the crossroads cutscene is gone (its lines are in ch5_end, which sets 337); searchlight walk-ins (until 471) send
  the twins back to the park; the south road is blocked until 473. ch7: breakers CORE/LIGHTS/DOORS on the Security
  Wing consoles open the wing's lower corridor (bottom edge) to the bio wing; breaker_doors reloads 1:111 so the exit
  appears. (The archive's top "door" was dropped: it is a building seen through the window, not an exit.) ch10: 17:40 -> 17:48 -> 17:21 (the old 17:40 <-> 17:21 link removed).
- Flags: 450-452 depot, 455-457 graveyard, 460-467 ch5 (460 ready to end, 461 ruby heard, 462 Hercule's show, 463 ruby
  taken, 464/465 lost boy, 466 storeroom, 467 ruby stashed), 470-474 ch6, 480-486 ch7, 490-495 ch10, 510-516 army files,
  520-530 Gero's notes. The flag byte for 544-551 (0x03001101) holds Super 17's Strength bonus: don't use those flags.
- New enemy rows: 43 Quartermaster (char 136), 1 Prototype 3 (char 17), 95 rooftop hunter (char 230, death reloads the
  roof), 42 bio wing warden (char 133), 67 resistance fighter (char 171), 2 resistance captain (char 25, ai 0x8A).
- Checks: clipcheck 0 failing; storyrun of the 57 new lists OK (3 CHECKs explained: branch-only flags); reachaudit
  154/161 on the full ROM - every new spot passes; the failures are older spots in areas this pass didn't touch
  (arena_locked 1:93, mine_gate 1:110 where the relay node stands in front of the gate, zmart_clerk 4:44 across the
  counter, ch9_sealed 17:37, ch10_cache 17:40 - likely the audit's limits; worth a human look). Bosses bot-tested
  (results in stats.json _balance); the rooftop hunter and the Act 1 bosses want a human check.
- Items repurposed: 28 Ribbon Ruby (UI 806-809), 29 Army File (810-813), 31 Gero's Note (818-821). Army files are taken
  back at the end of Act One (ch4_pod, native 130 once per file read).
- Super 17 (user 2026-11-03): the gold-haired form 13 / actor player_17_supergold are removed (Outfit does nothing in
  Super 17). Strength x1.5: log4/asm/kiregen.s adds half of character 1's STR while his form is 15 and takes the same
  amount off when he leaves it (bonus kept in 0x03001101, saved with the flags). Verified: STR 36 -> 54, back to 36.
- Ki effects (user 2026-11-03; tools/kifx.py, build step after kiregen, ROM 0xF38000): 17/18's Energy Blast is blue
  (a recoloured copy of BF's blast frames 0x71300C-0x71370C + table; the player projectile constructor sub_080197B4
  is hooked at 0x080197F2 to use it when G[0] is character 1 or 3; Gero, the drone, Cell and enemy projectiles keep
  BF's yellow; the impact burst stays BF's). Skill 6 (BF Electric Kamehameha, was "Power Blitz") is now "Full Power
  Energy Wave" (UI 1322/1323), green: its tiles 0x721218-0x722318 are recoloured in place (only its own frame tables
  use them). Eighteen gets skill 6 too at the conversion (act2_siblings.scene, gen_debug ANDROIDS / MOVES). Recolours
  map onto existing OBJ colours only; kifx.IN_GAME_CHANGED lists the 20 OBJ slots whose in-game colour isn't BF's
  (measured from PRAM in Act 3) - never targets. Verified in the emulator: blue blast, green wave for both, all
  directions.

## CREDITS (user, 2026-11-03): hold the credits update until the game is complete. log4/credits_todo.md lists every
change to make; ADD A LINE THERE whenever a new asset, source, feature or character goes in (also a CLAUDE.md rule).

## 2026-11-03: alternate outfits, Super 17, Android 13 two-phase boss, fly slot, Eighteen's record fix
- User request: alternate skins for 17/18 from their reference sheets + a Super 17 form; Android 13 sprites (walk sheet,
  then combat frames as they draw them) with option 4 = a two-phase boss (13, then Super 13).
- FIX: player_18 (form 23) cloned BF actor 262, which has only 2 animation slots; the engine doesn't bounds-check the slot
  (sub_0800ECDA), so attacking in 18's android outfit read past the record. Now "template_orig": 260 (22 slots).
- BF slot 15 = FLYING (the world map plays it: obj+0x50 checked in RAM). 17/18 had LoG2 hurt frames there; now their
  hover fly sheets until flat Buu's Fury-style fly frames are drawn (prompt sent: scratchpad prompts/art_prompts.md).
- Recolour outfits: tools/recolor.py (actors.json "recolor": anchors neck/waist/waist_last/feet, rules from->to/ramp with
  where below/above/interior/not_near/touching). Existing palette colours only (palette rule). Preview any actor's frames
  with tools/skinpreview.py (sprites.FRAME_HOOK / CUR_ACTOR collect every frame build_actors makes).
  New actors (appended last, ids 317-323): player_17_casual/_jacket/_super/_supergold, player_18_redyellow/_redblack/_tracksuit.
- Forms (forms.json, tools/outfit.py now supports copy/actor/into/back): 11/12 = 17 casual/jacket, 22/24/25 = 18 outfits
  (copies of 14/23, +0x17 = 0xFF so skill 20 can't fire there), 15 = Super 17 and 13 = gold Super 17 (copies of BF SSJ
  Gohan form 16: flags 0x51, revert 14). Form 14 +0x16 = 15.
- log4/asm/outfit.s: both skill-18 hooks step to the next form from tables next_plain / next_all (next_all once flag 440).
  17: 10 -> 14 -> 11 -> 12 -> 10; 15 <-> 13. 18: 21 -> 23 -> 22 -> 24 -> 25 -> 21. Verified in the emulator (debug ROM).
- Skill 20 renamed "Super 17" (UI 1348/1349); BF Super Saiyan mechanics: needs [0x03001988] != 0 (set by an area-script
  native: combat areas only, so not in towns), drains EP and reverts when it runs out. Verified: transform, gold swap, revert.
- Unlocks: flag 440 = outfits (talk to Eighteen at the Age 772 hub, ch9_hub18); flag 441 + skill 20 for character 1 =
  Super 17 (Project 17-S chip in Prototype 11's field case, Diablo Desert, diablo_ball). Debug all-moves sets both.
- Android 13 = actor android13 (template_orig 97, P14 user art via tools/bandsheet.py: walk, idle, run, guard, punch, kick,
  hook, hurt; see the slot trace below), stats row 11 (BF unused; ai 0x8A), HP 700 / STR 16 / POW 15 / END 18
  (1000/19 lost to the fightbot at level 64; 700/16 won with 37% HP). 17:14: 13 spawns when 367 set and 438 clear; his
  death sets 438, heals, reloads; the arrival list ch9_thirteen2 (438 set, 439 clear) plays the absorption and sets 439;
  Super 13 spawns when 439 set and 363 clear. Verified in the emulator (STORY=1 listtest from shoot list t_bal_13 + 438).
- Android 13 slot trace (2026-11-03): each slot given its own animation copy in a test ROM, then bot fights and idle /
  kite / ki-spam / skill runs: he plays 0 idle, 1 walk, 4/5/6 melee, 7 hurt, 9 = reaction to a ki hit (red flash; NOT a
  ki attack). Never: 2, 3, 8, 10-18. Slot 9 now uses the hurt frame. All three melee hits are drawn (user art: punch E
  slot 4, kick H slot 5, hook K slot 6; commit 252ac69). Nothing else is needed for the fight; M absorb only for a cutscene. Prompts: scratchpad prompts/art_prompts.md (updated).
- FULL STORY RUN (plan step 3, 2026-11-03): tools/storyrun.py plays all 171 story lists in story order, each from a fresh
  boot at its own trigger with every earlier flag preset (+ trigger 'when' flags + boss death flags it checks), then
  checks flags, end area and the last screen (contact sheets). Result: no game bugs. All 32 first-pass CHECKs were test
  issues, fixed in the tools (presets were written after the warp; prerequisite if_flags were dropped; field enemies
  killed the idle tester -> BF's "You have died!" -> title; trigger rects off the map edge) or are branch-only flags
  (zmart_clerk 388 / museum_curator 387 are the "ask" branch, ch8_stall 341 needs the tin box 359 first,
  lookout_door 413 needs all seven balls). fs_wake doesn't fire from the injected trigger in 17:25 (test limitation)
  but runs fine from 1:1. listtest: presets before the warp, ONESHOT=1 (injected trigger fires once), NOENEMIES=1,
  BOOTFLAGS cache.
- Flags used: 438 13 beaten, 439 transformation seen, 440 outfits, 441 Super 17. Free from 442.
- BOSS BOT TESTS (plan step 1, 2026-11-03; shoot lists t_bal_13/s13/pic/g774/sent/capt/butch/kri, level = the level players
  reach, no stat points spent; scratchpad bosses/run.py drives listtest + fightbot). Results and changes:
  Android 13 700/16 win (37% left); Super 13 1700 -> 1500 win (21/471); Piccolo never hurt the bot (row 136's own
  behaviour 0x30F), now ai 0x8A: win with 121/455; Gohan 774 win, lost 39%; Sentinel 3700/33 -> 2600/30 win (90/471);
  ninja captain 3550/34 barely hits the bot -> 4000/38 (still an easy win: human check); Butcher + his raiders swarm the
  bot (it fights the group at once): 3200/32 still a bot loss, human check; Krillin (as Eighteen, now with a full record)
  easy win (431/476 lowest), left as is (story fight). Act 1 drone bosses: only tested at fresh level before (they get
  easier with levels), not re-run.
  fightbot: the player struct is now found by a RIGHT/LEFT probe when NPCs stand near the arrival point.
- tools/bandsheet.py: imports the generator's labelled magenta sheets (panels down/up/right, frames left to right):
  finds the pixel scale from a native height (30 with shadow), strips the shadow, writes a strip for tools/intake.py.

## STATUS AT END OF 2026-11-02 (read this first; the 2026-11-03 section above adds to it)
Latest deliveries: GerosLegacy_balance.bps (main game: everything below) and GerosLegacy_debug_v4.bps (debug ROM).
Repo: https://github.com/smh4004/Gero-legacy-tools is in sync (code, mod data, docs, cleaned art). Re-sync with
`python3 tools/text_edits.py make bf.gba; python3 tools/sync_repo.py . <clone>`, then commit and push.

WALKTHROUGH / 100% GUIDE (user 2026-11-02: keep it in step with every addition or removal, 100% accurate):
GUIDE.md (repo root) is GENERATED by tools/guide.py from the built ROM (area names, exits, examine spots, NPCs,
enemies, boss stats), the scene lists (items, objectives, the secret chapter's flags) and the hand-written
log4/guide/walkthrough.md (tags {{A:w:a}} {{I:n}} {{B:row}} {{L:list}} {{C:list}} {{J:list}} {{X:list}}; area labels
in log4/guide/area_names.json). Every release build regenerates it and warns when the walkthrough misses something
(an item cache, a 1000+ HP enemy, a MUST_COVER list) or names something that no longer exists. Whenever content
changes: update walkthrough.md until `python3 tools/guide.py` says UP TO DATE, then sync it to the repo.

Done today (details in the sections below): debug ROM (debug room 17:120, chapter launchers, supplies, stone balls,
credits, open world, all-moves and level options); status-screen portrait colours (menus' RGB555 palette copy);
Kami's Lookout door reachable; reach audit of every examine and NPC (tools/reachaudit.py, 114/115, the last one
hand-verified); supply-yard crate fix; Act 3 boss rescale for real player levels (bot-checked); repo plus
tools/sync_repo.py; length report (tools/length_report.py).

The user's plan, in order. Each step is checked by the user before the next one starts:
1. DONE 2026-11-03 for Act 3 (results in the 2026-11-03 section; captain and Butcher still want a human check). Original note:
   Bot-test the bosses not yet tested at their current stats, at the level players reach:
   - Act 3: Piccolo, Super 13, Gohan 774, Sentinel, ninja captain, Butcher.
   - Act 1 drone bosses: tank r127, Raider Chief r128, looters' captain r47, Prototype 9 r41, Prototype 12 r30.
   How: add shoot.scene t_bal_* lists (party, then native-194 level code, then warp), build --shoot, create a state
   with listtest (place 1:1:112:200, NAMED=named_lists_shoot.json), then fightbot (ANYMARK=1 for some rows).
   For the captain and Butcher, fightbot needs a fix: it couldn't find the player next to the Eighteen partner NPC.
   Retune if a boss is a pushover or a wall. Estimate: ~1-1.5 h.
2. Fill the length gaps. Waiting for the user to pick from these:
   (1) ch6 night walk: drone patrols to sneak past or fight, the twins' old apartment (a memory scene), a rooftop chase (~15 min)
   (2) ch5: 1-2 more West City side jobs, e.g. for the fence, or a museum heist that pays off in ch8 (~10-15 min)
   (3) ch7: more of Gero's hidden lab: research logs (conversion, Androids 13-15), a locked wing with a power
       puzzle, a first look at the Cell incubator (~10 min)
   (4) ch3: a looted Red Ribbon depot; ch4: the Prototype 1-12 graveyard (~8 min each)
   (5) ch10: resistance encounters in the ruined city before the crossroads (~10 min)
3. Polish: the teaser with real 17/18 and open-world footage (1-2 h); credits update (~20 min); a full automated story
   run ch1 -> end plus fixes (2-3 h, the heavy part).
Batch fixes into few builds (each build takes ~10 min).

Length report (tools/length_report.py; story ~3.6 h confident to ~5.4 h first-time, +0.6-0.9 h open world; target 5-8 h):
ch1 20m, ch2 19m, ch3 15m, ch4 15m, ch5 18m, ch6 10m, ch7 12m, ch8 38m, ch9 34m, ch10 16m, secret 20m, open world 36m.
Thin spots: Act 2 (28 min total), ch7, ch3/4/10. Options 1-5 together add ~60-70 min (story ~4.5-6.5 h).

Still unverified by a human: Gero's Kamehameha and Instant Transmission with the debug all-moves option (no drawn
frames; may show Goku graphics); the debug options' on/off lines (the options themselves work); Act 1 boss feel.
The user is playtesting the debug ROM on mobile, so expect screenshots of bugs.

## Next steps (priority order) (older list, mostly done; see the status section above)
- Lab state 2026-10-31: 1:1 = main lab during the opening (with Gevo); every door back into the main lab leads to 1:61 (same
  map, no Gevo, technician + powered-down spare drone, talk scripts in log4/scenes/lab_talk.scene). Drone terminal = one
  step-list exit per spot (toggle code + one line); per-direction lines would need exits re-checked mid-room (see RE_NOTES).
0. **Teaser video (user request 2026-10-31, deferred):** make it only once 17/18 (Lapis/Lazuli) gameplay is in; Gero mainly
   as a tasteful closing hint at more characters. 30-40 s, real emulator footage (scripted inputs, 60 fps, nearest-neighbour
   upscale), caption cards, closing logo. Music: LoG2's "Era of Darkness" theme recorded from the user's LoG2 ROM (add audio
   capture to tools/harness.c). Deliver the .mp4 in chat only.
   Draft made 2026-10-31 (log4/out/GerosLegacy_teaser_draft.mp4, 38 s, script tools/teaser.py with scratch clip paths):
   harness "rec name n keys" pipes lossless clips to ffmpeg + sound to name.pcm, "arec" = sound only. Music = the user's
   Era of Darkness MP3 from 10.0 s (its swell at 20 s lands on the logo's first flash); verified it is the same song LoG2's
   opening story plays (envelope match r=0.98 with a cart recording). Cards: Poppins on a dark red glow.
   User feedback on draft 1: caption cards between shots looked AI-made and off-tone. Draft 2
   (log4/out/GerosLegacy_teaser_draft2.mp4, tools/teaser.py) = ominous and vague: no cards, letterboxed 240x128 strip
   (rows 24-151, HUD cropped) at 7x, darkened grade + vignette, dissolves / dips to black, three faint narration lines in
   the lower bar during the quiet part, swell on the walk through the lab door, 17/18 art then the logo at the end.
   Draft 3: text in the game's own dialogue font (glyphs lifted from intro narration frames, tools/teaser_fontmask.npy,
   4x nearest) and the 17/18 shot from the full-res U1_title.png (crop above its menu bar, slow bicubic push-in) instead of
   the 240x160 screen. The real teaser waits for more footage (17/18 gameplay).
1. **Decode CharacterData / animation tables** (BF frame record = 20 bytes `[OAM attr][ptr][count][bbox][bbox]`,
   LoG2 = 12 bytes `[attr][ptr][bbox]`). Needed to insert new sprites and to confirm the player-move slot counts in the art doc.
   Also check whether sprite frames load through the type-checking loader (0x0803D944), so stored type-0 frames work, or whether a WFZ compressor is needed.
2. ~~Portrait inventory~~ DONE: format, speaker table, insertion and LoG2 imports all verified in-game (RE_NOTES "Dialogue portraits").
   Build: `python3 log4/build.py bf.gba --log2 <LoG I&II cart> [--skip-art]`. New speaker ids are in log4/art/speakers.json.
3. **Cross-game map import proof:** move one LoG2 Dr. Gero's Lab room into the BF build and walk it in the emulator
   (palette remap into BF's 256 BG colors; tiles, chunks, collision, area entry).
4. Verify uncertain sprite IDs: Yamcha (unconfirmed), Krillin (BF seg #132?), Tien (LoG2 seg #62). Android 16 has no field sprite.
5. Name the 248 script natives (some known: 0x72/0x73 scene load, 0x88 wait, 0x6B camera, 0x23 music?); write a script decompiler and compiler.
6. ~~Verify the level +50 bias~~ VERIFIED (status screen). Still to find: character base stats and growth, enemy stat tables.
8. **Per-act palettes (in progress 2026-10-31):** hook in place (log4/asm/fadepal.s, tools/worldpal.py). log4/acts.json lists each act's
   kept BF actors/portraits; tools/palette_plan.py works out free OBJ slots (global 10; act1 27, act2 12, act3 9, secret 27).
   artclean keeps one registry per act (clean/palette_alloc_<act>.json) and plans each act's new colours from all its sheets
   at once. Per-world overrides are applied only once acts.json lists the act's world ids (filled in during level building).
   Findings: the old "11 free slots" list was wrong (slot 6 = HUD bar, 102/231 = portraits, 233 = an actor); portraits use ~200
   of the 256 OBJ colours, which is what limits the budget. Cutting Buu-saga actors frees almost nothing (colours are shared).
7. Find the reference mechanism for the ~4-18% of dialogue-bank text not covered by type-5 event steps (system messages).

## Engine milestones reached 2026-10-31 (all verified in the emulator)
- Dialogue portraits: new + LoG2-imported portraits as new speaker ids (163-207).
- Per-world palette hook; per-act colour planning in the art pipeline.
- LoG2 map import (Gero's Lab room 61 renders in BF).
- New actors: actor table relocated, new actors (Gevo 298, Android 16 299, LoG2 Android 17 300) spawned through area records.
- Area edits (log4/areas.json, tools/areas.py): new game now starts in LoG2 Gero's Lab room 61 with Gevo and 16 (test setup).
  AreaEntry lookup count is a constant (movs/adds at 0x080125E0 = 452, max 510 with that encoding); table literal at 0x8A58.
- Scene compiler (log4/scenes/act1_opening.scene): say/narrate/journal/keep/do (move, face, waits). The Act 1 opening plays.
- Playable Gero (test): BF Goku actors 106-108 redrawn with LoG2 Gero idle/walk/run (log4/actors.json player_gero_*).
  Halos removed (actor record +0x50 = halo table, zeroed). Status screen shows DR. GERO with his portrait
  (ui.txt 116/158/174/1188/1189; log4/portrait_overrides.json maps speaker slot 57 to young Gero). LoG2 scientist in the lab.
- Area exits work (lab door -> another area); starting stats editable (log4/stats.json).
- Clipping gate: every build ends with tools/clipcheck.py, which plays each NPC spawn, door arrival and door of the edited
  areas in the emulator and fails the build (no patch) on clipping (inside props/walls, hidden by the map, unusable door).
  Report + annotated frames: log4/out/clipcheck/. Sprite inserters refuse frames over the one-piece 32x32 budget.
- Gero's Lab is a real 4-room dungeon: AreaEntry table relocated and extended (new areas 1:62-65 from LoG2 lab rooms 62-65,
  1:1 = room 61), walking warp doors 61 <-> 62 <-> 63 with arrival points, animated tiles imported (tank, incubator).
  All rooms named "Dr. Gero's Lab" (ui 531, was Buu's House). 64/65 are the after-the-event versions (no doors yet).
  Doors: "warp" doors for walking ('dir' = key held to use it, 'face' = facing on arrival); script doors (native 114) only
  for cutscenes, since 114's x/y set the camera, not the player. See RE_NOTES "Area transitions" for the decoded format.
- Intro movie rewritten (log4/scenes/intro.scene: lab rooms + new narration); title logo subtitle redrawn as GERO'S LEGACY
  (tools/logo.py + tools/mapedit.py); chapter card / save names use the design doc's 12 chapter titles (UI 1450-1473,
  602-613).
- Gero: all 22 player slots drawn with LoG2 Gero (swipe, palm, hand beam; no Goku frames left).
- Combat drone = party character slot 2 (Goten's): LoG2 drone actors, stats, names, a portrait generated from its sprite.
  The drone terminal in room 61 (press A from its left or from below) toggles control Gero <-> drone (natives 151/149).
- Scouter map (SELECT) shows a Gero's Lab schematic instead of Snake Way (tools/scouter.py).
- Title art: U1_title = the user's own screenshot (log4/art/raw/U1_title.png; the generated one is in art/alternates).
  It still has to be inserted: the title image's storage in the ROM is not found yet.
Next: flag-conditional spawns (Gevo reappears in room 61 after leaving in the opening); a dialogue line when the terminal
switches; drone/Gero attack effects (still BF's ki blast); title screen insertion (art is ready; find where the title image is stored);
player setups for 17/18; lab NPC talk scripts; the lab exit to the outside (room 61's south corridor is a test door).

## Decisions since Oct 30 (details in the design doc's Story decisions table)
- Game title: Dragon Ball Z: Gero's Legacy. Buu-saga cast cut (kid Trunks sprite kept as Future kid Trunks).
- Kid Goku on screen in Act 1 with a full new set (art doc P13, R7, E8, E9). Act 2: generic NPCs + Hercule cameo.
  Act 3: Bulma + kid Trunks, Chi-Chi + Ox-King, Roshi + Kame House.
- User instruction: keep working without asking unless an error is unsolvable or a design decision is urgent.

## Working agreements with the user
- The user makes art with **image generators**. Whenever they send images, **run the cleanup step yourself**: match the asset to its
  prompt ID, add or adjust its `log4/art/specs.json` entry, run `log4/build.py` (or `tools/artclean.py`), inspect the preview and report,
  show the result next to the reference sheet, and say exactly what to change in the prompt if it needs regenerating.
- Story and design decisions go to the user as multiple-choice questions. Record answers in the design doc's
  "Story decisions" table.
- Keep both docs current after each work session (read `sinceRev` first; the user edits them too).
- Sprite identifications are visual and can be wrong (the "android18_bf_fighter" sheet was wrong and was removed). Label
  uncertain IDs "likely" and confirm before relying on them.
- Never ship patched ROMs; deliver .bps patches only. Don't redistribute ROM dumps.

## Gotchas
- Map record convention: the code's object pointer is P; tools use M = P - 4 (layers at M+0x18, tile list M+0x4C, pages M+0x50).
- Layer dims: byte0 = chunks wide, byte1 = chunks high. Animated-tile frames are `u32 duration` + **raw** WFZ stream (no header).
- One global palette per game (BF ROM 0x701B0, LoG2 slice 0x3ECD1C); only 11 BF OBJ slots are free (tracked in `art/clean/palette_alloc.json`).
- `harness` resolves `load/save <name>` relative to its output directory.
- The design doc has a stray user-typed "Fini" in the combat section ("New attack types"); it was flagged and left alone.

## Suggested skills
- `anthropic-skills:reverse-engineer-anything`: for further binary analysis (the REA server wasn't connected; shell tools plus mGBA were used instead).
- `anthropic-skills:docs`: required before editing the two Claude Docs (design doc, art doc).
- `artifact-design` (or the Artifact `quickstart`): when updating or republishing the Location Atlas or making new pages.
- `anthropic-skills:systematic-debugging` and `anthropic-skills:verification-before-completion`: the engine work is evidence-driven; verify in the emulator before claiming results.
- `anthropic-skills:handoff`: to refresh this document at the end of the next session.

- Emulator tip: a savestate holds RAM pointers into the ROM (area exits, objects). After any rebuild, regenerate states from
  one taken before the area loads (run8/door.txt from run7/preA2.ss), or exits point at stale data.
