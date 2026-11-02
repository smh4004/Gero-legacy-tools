# LoG4 art pipeline

1. Generate art with the prompts in "LoG4 Art Needs & Prompt List" (attach the matching reference sheet).
2. Save the generator output, unedited, into `art/raw/` using the file name listed in `art/specs.json`
   (e.g. `P1_android17_dash.png`). Any size, any background, JPEG artifacts are fine.
3. Run `python3 build.py <clean Buu's Fury ROM>` - the art stage runs first and writes to `art/clean/`:
   - `<id>_NN.png`  one indexed PNG per frame (index 0 = transparent), already in the game's sprite palette
   - `<id>_preview.png`  4x preview of all frames (magenta = transparent)
   - `report.json`  detected pixel size, colours used, new palette slots, warnings
   - `palette_alloc.json`  which of the 11 free sprite-palette slots each asset claimed
4. Fix anything the report warns about (usually: regenerate, or tune the spec).

Spec fields: `kind` sprite | portrait | ui; `cell` [w,h] frame cell; `frames` {cols, rows} for a fixed grid
(omit to auto-split); `target_height` character height in game pixels (31 for 17/18, 32 Gero, 53 Cell);
`max_colors` (16 sprites, 32 portraits, 240 screens); `allow_new_colors` free palette slots this asset may claim;
`scale` force a known pixel size.
