# LoG4 assembly patches

Our own code, assembled with GNU binutils (`arm-none-eabi-as`). The built `.bin` files are committed so the build
doesn't need the toolchain. Rebuild after editing a `.s` file:

    arm-none-eabi-as -mcpu=arm7tdmi -o fadepal.o fadepal.s
    arm-none-eabi-ld -Ttext=0x089F0000 -e fadepal -o fadepal.elf fadepal.o
    arm-none-eabi-objcopy -O binary fadepal.elf fadepal.bin
    arm-none-eabi-nm fadepal.elf | grep WORLDPAL     # must match WORLDPAL_OFF in tools/worldpal.py

| File | Placed at | What |
| --- | --- | --- |
| fadepal.s | ROM 0x9F0000 | Palette fade (0x08007074) reading a per-world palette; installed through a bx-pc veneer |
