# Dragon Ball Z: Gero's Legacy: Walkthrough and 100% Guide

This guide covers the whole game: the story chapters, every side job and optional area, every item cache, every boss, the four missable memories that unlock the secret chapter, and both endings.

It is regenerated from the game's own data whenever the game changes (`tools/guide.py`). Area names, items, boss stats, the checklist and the area atlas at the end always match the current build.

**Spoilers:** the walkthrough follows the story in order. The checklist, the boss table and the atlas at the end are reference sections.

## Basics
- **Controls:** A talks, examines and attacks up close. B uses your selected skill. L changes the selected skill. Start opens the Status, Journal and Inventory screens.
- **Examine spots:** walk up to the thing, face it, and press A. Caches only give their items once.
- **Journal:** your current objective is always the last Journal entry (Start, then L).
- **Levels:** levelling up raises HP and EP and gives 3 stat points. Spend them on the Status screen ("Use Points"). Strength and defence only go up when you spend points.
- **Items:** a Senzu Bean fully restores HP and energy. Drinks (Milk up to Dinosaur Milk) and Elixirs restore energy (EP). Holy Water boosts your stats for 30 seconds. Exact amounts are in the item table at the end.
- **Saving:** use the save pads (the Capsule Corp logo on the floor) wherever you find them.
- **The secret chapter:** you must find all four of Eighteen's memories in Act 3. See "Missables" below before you start chapter 8.

## Missables
Nothing in the game locks you out of finishing it. Four things in Act 3 decide whether you see the **secret chapter** after the epilogue, and the first two can only be done in chapter 8:
1. **The apple** (chapter 8): visit the old hideout at the docks first, then talk to the fruit seller in West City. {{X:ch8_hideout}}{{X:ch8_stall}}
2. **The mother and son** (chapter 8): after the Vegeta fight, talk to the woman holding her son before you walk up to Tien. Eighteen lets them go. {{X:ch8_civilians}}
3. **Mount Paozu** (chapter 9, Age 772): fly to Goku's house and meet Chi-Chi. {{X:ch9_paozu}}
4. **Kame House** (chapter 9, Age 772): fly to Roshi's island and meet Master Roshi. {{X:ch9_kame}}

Talking to Eighteen at the Capsule Corporation hub ({{L:ch9_hub18}}) reminds you which of the chapter 9 visits you have made.

**Optional, but only in their own chapter:** the Ribbon Ruby heist (chapter 5, it pays off in chapter 8), and the lore pages below. Missing them never blocks the story.

## Lore pages
Two sets of collectibles tell the story behind the story. Each page is an examine spot; the Inventory counts them.
- **Army Files** (Act One, 6): {{L:file_range}} / {{L:file_yard}} / {{L:file_line}} / {{L:file_depot}} / {{L:file_grave}} / {{L:file_cave}}. All six: Gero closes the folder ({{X:files_check}}{{X:files_done}}) and gets 2 Holy Waters. The files stay with Gero when Act One ends.
- **Gero's Notes** (Acts Two and Three, 10): {{L:note_park}} / {{L:note_museum}} / {{L:note_house}} / {{L:note_wing}} / {{L:note_archive}} / {{L:note_warehouse}} / {{L:note_bunker}} / {{L:note_cave}} / {{L:note_mine}} / {{L:note_shelter}}. All ten: the twins read the whole notebook ({{X:notes_check}}{{X:notes_done}}) and find Gero's last capsule: 3 Senzu Beans and 2 Super Elixirs.

---

# Act One: The Doctor

## Chapter 1: Red Ribbon Science
**You play:** Dr. Gero, then his combat drone. **Goal:** calibrate the drone on the proving ground.

1. The game opens in Gero's lab with his son Gevo. When Gevo leaves, the journal asks you to "Check the drone terminal". Use it ({{L:lab_terminal}}). The technician and the spare drone in the lab have a few lines each ({{X:scientist_talk}}{{X:drone_npc_talk}}{{X:gevo_talk}}{{X:lift_talk}}).
2. The drone arrives at the **Range Gate**. The briefing gives the objective {{J:ch1_brief}}. The Range Sergeant ({{L:range_sergeant}}) tells you where the three sites are.
3. **The three target sites.** Each one is a grounded sensor drone; talk to it to log the data:
   - Site A: {{L:site_a}}. From the Range Gate, go up through the Canyon Road.
   - Site B: {{L:site_b}}. From the Range Gate, go down.
   - Site C: {{L:site_c}}. From the Range Gate, go right into The Pit, then up.
4. **Caches on the range:**
   - {{C:crate_depot}}
   - {{C:crate_pit}}
   - Army file 1 (on the Fuel Depot's left fuel tank): {{L:file_range}}.
   - **Side job "Rogue Targets":** the Range Sergeant also asks the drone to destroy three rogue training mechanoids ({{B:3}}): one on the Canyon Road, one in the Pit, one on the Target Field. They only appear after he asks. Report back to him for the reward ({{C:range_sergeant}}).
5. With all three sites logged, the objective becomes {{J:ch1_sites}}. The arena gate on the Bone Flats' west side opens ({{X:arena_locked}}). Before that, walking up to the gate and pressing A just shows the "locked" sign.
6. **Boss: {{B:127}}** in the Live-Fire Arena. {{X:ch1_arena}}
7. The drone link returns you to the lab for Gero's report ({{X:ch1_report}}), and chapter 2 begins.

## Chapter 2: An Enemy Bullet
**You play:** the drone (from the lab terminal). **Goal:** find Squad Seven, then reach Gevo.

1. Before dawn, Gevo radios in from the Northern Wastelands and the squad is ambushed ({{X:ch2_start}}{{X:radio_tech_talk}}). Use the drone terminal again ({{X:drone_toggle}}).
2. The drone lands on **Ambush Ridge** ({{X:ch2_field}}): {{J:ch2_field}}. Go up into the Scorched Canyon. It's the hub of this chapter, with exits in every direction.
3. **The three survivors:**
   - Pvt. Kurz: {{L:surv_a}}. From the Scorched Canyon, go down.
   - Cpl. Mori: {{L:surv_b}}. From the Scorched Canyon, go left into the Dry Basin, then up.
   - Sgt. Halden: {{L:surv_c}}. He's tied up; free him after the boss fight there.
4. **Boss: {{B:128}}** in the Supply Yard ({{X:ch2_yard}}). He guards Sgt. Halden.
5. **Caches:**
   - {{C:cache_dump}}
   - {{C:cache_yard}} (face the top crate of the stack)
   - Army file 4 (the Supply Yard office): {{L:file_yard}}.
   - **Side job "The Squad Radio":** once you've found Cpl. Mori, talk to him again ({{C:surv_b}}). Bring him the radio's antenna (behind the lone crate by the right-hand fuel tank in the Fuel Dump: {{L:radio_antenna}}), its battery pack (behind the bottom crate in the Supply Yard: {{L:radio_battery}}) and its handset (on the dead stump at the bottom of Ambush Ridge: {{L:radio_handset}}). The fixed radio picks up HQ writing Squad Seven off, and a raider sniper on the canyon rim. **Mini-boss: {{B:46}}** on the east side of the Scorched Canyon.
6. With all three found ({{X:ch2_found}}), the objective becomes {{J:ch2_found}}. The Scorched Canyon's right-hand exit now leads to Gevo ({{X:gevo_field_talk}}). Walk up to him for the end of the chapter ({{X:ch2_gevo}}).

## Chapter 3: The Boy Called Goku
**You play:** Gero, and the drone from the lab terminals. **Goal:** save the android blueprints and wipe the archive.

1. Headquarters is under attack ({{X:ch3_start}}): {{J:ch3_start}}. The technician ({{L:ch3_tech_talk}}) reminds you the terminal still controls the drone.
2. In the tank room, take the blueprint core from the pod ({{L:ch3_pod}}). The objective becomes {{J:ch3_pod}}. The south corridor from the main lab now leads to the Munitions Lines; before that it only tells you the core comes first ({{X:ch3_corridor}}).
3. **Munitions Line A, then B, then C.** Looters strip the belts ({{X:ch3_factory}}): {{J:ch3_factory}}.
   - **Mini-boss: {{B:47}}** in Munitions Line C. He drops the vault keycard.
   - Caches: {{C:cache_line}} and {{C:cache_belt}}.
   - Army file 3 (in Line B, by the press): {{L:file_line}}.
4. **Archive Vault** (down from Line C): the blast door needs the keycard ({{X:ch3_vault}}{{X:vault_locked}}). With it, go up into the Army Archive and use the console ({{L:ch3_archive}}). Gero wipes the files and starts the self-destruct.
5. The emergency hatch drops you on the escape route: {{J:ch3_escape}} ({{X:ch3_escape}}). The old bridge is out ({{X:bridge_out}}): take the trail off the east edge of the slope to the **Supply Depot**.
6. **Supply Depot** ({{X:ch3_depot}}): {{J:ch3_depot}}.
   - **Mini-boss: {{B:43}}** stands in front of the back tunnel, with looters.
   - Army file 2 (the ledger, on the crates by the door): {{L:file_depot}}. Cache: {{C:cache_depot}}.
   - With the Quartermaster beaten, examine the dark gap in the crates from their right side ({{L:depot_tunnel}}) for the end of the chapter ({{X:ch3_end}}).

## Chapter 4: The First Androids
**You play:** the drone (Gero at the end). **Goal:** restore the bunker's power and wake Android 16.

1. Years later, in the northern bunker ({{X:ch4_start}}): {{J:ch4_start}}.
2. **Relay 1:** {{L:relay_1}}.
3. Leave the bunker by its lower exit for the Mountain Pass ({{X:ch4_pass}}). Prototypes Gero dumped here still have power.
   - **Relay 2:** {{L:relay_2}}. Go right from the Mountain Pass.
   - **Relay 3:** {{L:relay_3}}. Go up from the Generator Cave, through the hole at the top of its east ramp.
   - **Mini-boss: {{B:41}}** sits on relay 3 in the Old Mine; destroy it first.
   - The barred shaft in the Old Mine is not an exit ({{L:mine_gate}}).
   - Caches: {{C:cache_gen}} and {{C:cache_mine}}.
   - Army file 6 (the radio log in the Generator Cave): {{L:file_cave}}.
   - **Optional: the Prototype Graveyard**, down the trail at the bottom of the Mountain Pass ({{X:ch4_graveyard}}). Gero's old failures lie in the canyon ({{X:wreck_1}}{{X:wreck_5}}{{X:wreck_8}}). **Mini-boss: {{B:63}}** wakes up among them. Army file 5 is under the wreck at the bottom ({{L:file_grave}}). Cache: {{C:cache_grave}}.
4. With all three relays on ({{X:ch4_power}}), Prototype 12 breaks out of the conversion pod: {{J:ch4_power}}.
5. **Boss: {{B:30}}** in the bunker incubator.
6. Talk to Android 16 in the tank room ({{L:a16_talk}}). Then enter the conversion pod ({{L:ch4_pod}}): {{J:a16_talk}}. **End of Act One.**

---

# Act Two: Lapis and Lazuli

## Chapter 5: Siblings
**You play:** Lapis (Lazuli in the party). **Goal:** West City. Four things must be done before you can end the chapter: the fence, Hercule, the police chase, and the warehouse.

1. West City ({{X:ch5_start}}): {{J:ch5_start}}. The townsfolk all have something to say ({{X:wc_woman_pink}}{{X:wc_woman_blue}}{{X:wc_old_man}}{{X:wc_police_1}}{{X:wc_police_2}}{{X:wc_police_3}}).
2. **The fence** ({{L:wc_man_green}}) recognises the Red Ribbon mark on your stolen capsule case: {{J:wc_man_green}}.
3. **Young Hercule** ({{L:wc_hercule}}) is practising his kicks on the sidewalk. Talk to him.
4. **"Ditch the Patrol":** talk to the police officer ({{L:wc_cop_chase}}): {{J:wc_cop_chase}}. Lose him behind the park hedge, on the left side of West City ({{X:park_hide}}). Afterwards, the man in the long coat ({{L:wc_coat_man}}) has a new line.
5. **The Red Fangs:** the street vendor in the Circus Lot ({{L:ch5_vendor}}) says the gang took your warehouse: {{J:ch5_vendor}}. Go down from West City to the Riverside, right to the Docks, then up to the Old Warehouse.
   - **Boss: {{B:12}}** and his gang in the Old Warehouse ({{X:ch5_den}}).
   - Then take your tin box and the gang's haul ({{C:ch5_stash}}).
6. **Return the stolen goods.** These are optional and only work after the warehouse:
   - The Z-Mart clerk ({{C:zmart_clerk}}).
   - The West City Museum curator ({{C:museum_curator}}). The Red Ribbon exhibit in the museum ({{L:museum_exhibit}}) is worth a look.
7. **Other caches:** {{C:cache_river}} and {{C:docks_dome}} (the dome house).
8. **Side job "Lost Brother":** a little boy in the Circus Lot ({{L:lost_boy}}) lost his sister: {{J:lost_boy}}. She's on the Riverside ({{C:lost_sister}}).
9. **Side job "The Ribbon Ruby"** (after returning the medal, the curator mentions it: {{J:museum_curator}}). A guard sits by the tall STAFF ONLY door at the back of the museum ({{X:museum_guard}}{{X:storeroom_door}}). Tell Hercule there's a crowd at the museum ({{L:wc_hercule}}); while the guard watches his show, slip through the door.
   - **Museum Storeroom** ({{X:ch5_storeroom}}): the night guard's flashlight sweeps the middle of the room ({{X:storeroom_beam}}{{X:storeroom_guard}}). Walk up along either wall and across the top row to the case between the statues ({{C:ruby_case}}).
   - The ruby goes into the tin box when you rest at the warehouse, and turns up again in chapter 8.
10. Gero's notes 1 and 2: under the park bench in West City's park ({{L:note_park}}) and by the uniform case in the museum ({{L:note_museum}}).
11. Once the fence, Hercule, the chase and the warehouse are done ({{X:ch5_check}}): {{J:ch5_check}}. Finish anything else in town, then examine the mattresses in the Old Warehouse ({{L:ch5_rest}}) to end the chapter ({{X:ch5_end}}): {{J:ch5_end}}.

## Chapter 6: Taken
**You play:** Lapis, at night. **Goal:** get home unseen.

1. West City at night ({{X:night_police}}{{X:night_drone}}). Drones hover over the south bridge ({{X:night_south}}{{X:night_crossroads}}), and a line of searchlight drones runs down the east side of the main road, plus one in the lane past the city hall. Step into a beam and you're sent back to the park ({{X:night_spotted}}). **The gap:** cross just south of where the two beams on the main road end, about halfway down the park. Two hunter drones on the street north of the shops can be fought for experience.
2. **The old house:** the dome house top right, east of the road ({{X:ch6_oldhouse}}): {{J:ch6_oldhouse}}. Cache: {{C:cache_house}}. Gero's note 3 is on the television ({{L:note_house}}). The ladder ({{L:house_ladder}}) also takes you back up to the roof.
3. **Rooftops** ({{X:roof_chase_1}}): {{J:roof_chase_1}}. **Mini-boss: {{B:95}}** blocks the fire stairs at the east end ({{X:roof_stairs_blocked}}). Once it's down, the stairs lead down to the Riverside.
4. Gero's hunter drones patrol the Riverside and the Docks.
   - Caches: {{C:night_cache_river}} and {{C:night_cache_docks}}.
   - **Side job "Mrs. Oda":** the twins' old neighbour sleeps under the bridge on the Riverside ({{C:mrs_oda}}). Her bag is snagged on the white fence by the dome house at the Docks ({{L:oda_bag}}). Bring it back for a memory of their mother.
5. The Old Warehouse ({{X:ch6_home}}): {{J:ch6_home}}.
6. **Boss: {{B:76}}**.
7. The ambush follows ({{X:ch6_ambush}}). The twins wake in Gero's lab ({{X:gero_lab_talk}}{{X:lazuli_lab_talk}}): {{J:ch6_ambush}}. New skills for both twins: **Energy Blast** (their blasts are blue), **Full Power Energy Wave** (a long green beam) and **Outfit** (select it and press B to switch between the android outfit and the old clothes). Eighteen also gets **Stun Shot**.

---

# Act Three: Seventeen and Eighteen

## Chapter 7: Activation
**You play:** Seventeen (Eighteen in the party). **Goal:** get out of Gero's hidden laboratory.

1. Age 767. Gero wakes the twins, and it goes badly for him ({{X:ch7_start}}): {{J:ch7_start}}. Eighteen lingers in the pod room ({{X:eighteen_lab_talk}}).
2. Go down into the Security Wing. The lab's computer locks everything down ({{X:ch7_alarm}}): {{J:ch7_alarm}}.
   - Cache: {{C:ch7_locker}}.
   - Gero's note 4: under the small console's keyboard in the Security Wing ({{L:note_wing}}).
3. **Optional: the Research Archive**, through the opening on the right of the pod room ({{X:ch7_archive}}). Walk up the centre aisle and face the shelves on either side: three research logs ({{L:log_subjects}}{{X:log_units}}{{X:log_cell}}) and Gero's note 5 ({{L:note_archive}}).
   - **The power puzzle:** the lower corridor at the bottom of the Security Wing is shuttered ({{X:wing_lower_locked}}). Close the three breakers on the Security Wing's consoles in the order CORE ({{L:breaker_core}}), LIGHTS ({{L:breaker_lights}}), DOORS ({{L:breaker_doors}}). The wrong order trips them all.
   - **Bio Wing** (down the lower corridor; {{X:ch7_bio}}): {{J:ch7_bio}}. **Mini-boss: {{B:42}}** on the catwalk. Then use the monitor on the far side ({{L:bio_monitor}}) for a first look at Project Cell. The door on the left is sealed ({{X:bio_units_door}}).
4. **Boss: {{B:20}}** guards the Control Room (right of the Security Wing).
5. Use the console ({{L:ch7_console}}) to end the lockdown. This takes you out to the cave in front of the lab.
6. **Optional: Gero's Quarters**, through the misty passage on the right side of the cave ({{X:ch7_quarters}}). Read the diary on the nightstand ({{L:quarters_diary}}), straighten Gevo's photograph on the dresser to find the key ({{L:quarters_photo}}), and open the safe behind the painting ({{C:quarters_safe}}). **Mini-boss: {{B:58}}** wakes up when the safe opens. The bed: {{X:quarters_bed}}. You can't come back here once you leave the cave.
7. Leave through the cave mouth to the northern mountains for the end of the chapter ({{X:ch7_end}}).

## Chapter 8: The Massacre
**You play:** Seventeen; one fight as Eighteen. **Goal:** West City, then the Z Fighters.

1. West City, three days later ({{X:ch8_start}}): {{J:ch8_start}}. Townsfolk: {{X:ch8_man}}{{X:ch8_woman}}{{X:ch8_police}}one man has heard that Goku is dead.
2. Go down to the Riverside, right to the Docks, and up to the Old Warehouse. Gero's old machines prowl here.
   - **The tin box** (needed for the apple). Examine the crates in the Old Warehouse ({{L:ch8_hideout}}): {{J:ch8_hideout}}.
   - Caches: {{C:ch8_cache_river}} and {{C:ch8_cache_docks}}.
   - If you took the Ribbon Ruby in chapter 5, it's still in the tin box.
   - Gero's note 6: pinned behind a crate in the Old Warehouse ({{L:note_warehouse}}).
3. **Memory: the apple (missable).** Back in West City, talk to the fruit seller ({{L:ch8_stall}}). It only works after the tin box. The objective becomes {{J:ch8_stall}}.
4. Walk onto the crossroads; the Z Fighters land ({{X:ch8_landing}}).
5. **Boss: {{B:70}}**.
6. After Vegeta ({{X:ch8_after_vegeta}}), **talk to the woman and her son before anything else** ({{L:ch8_civilians}}). This is missable memory 2. Then walk up to Tien ({{X:ch8_tien}}). Tien's and Yamcha's stands are scenes ({{X:ch8_yamcha}}).
7. **Boss: {{B:18}}**, fought as Eighteen ({{X:ch8_krillin}}). Krillin remembers whether you spared the mother and son.
8. **Boss: {{B:136}}**, fought as Seventeen ({{X:ch8_after_krillin}}{{X:ch8_piccolo}}). Gohan runs ({{X:ch8_run}}), and the night on the Z-Mart roof ends the chapter.

## Chapter 9: Years of Terror
**You play:** Seventeen. **Goal:** Gero's computer, Android 13 and Super 13, then the open world. Two missable memories are in this chapter.

1. Age 768, Capsule Corporation ({{X:ch9_start}}): {{J:ch9_start}}. Bulma and baby Trunks are in the dome house ({{L:ch9_bulma}}); talk to her. Gero's computer calls the twins home.
2. **The northern mountains.** The bunker door is sealed ({{X:ch9_pass}}{{X:ch9_sealed}}): {{J:ch9_pass}}.
   - **Mini-boss: {{B:100}}** in the Generator Cave (right of the Mountain Pass).
   - Cache: {{C:ch9_cache_mine}}. The Old Mine is up from the Generator Cave.
   - Gero's notes 8 and 9: behind the generator in the Generator Cave ({{L:note_cave}}) and under a rock by the Old Mine's lower-left wall ({{L:note_mine}}).
   - With the Sentinel destroyed, the bunker door on the left of the Mountain Pass opens.
3. The bunker ({{X:ch9_bunker}}): {{J:ch9_bunker}}. Gero's note 7 is tucked behind the old tank in the bottom-left corner ({{L:note_bunker}}). Android 16's empty pod is in the tank room ({{L:ch9_pod16}}).
4. **Two-phase boss in the incubator** ({{X:ch9_thirteen}}): first **{{B:11}}**, then he absorbs Fourteen and Fifteen{{X:ch9_thirteen2}} (you're fully healed) and you fight **{{B:21}}** ({{X:ch9_after13}}).
5. **Age 772: the hub.** Capsule Corporation is now the twins' base ({{X:ch9_hub}}): {{J:ch9_hub}}.
   - **New outfits:** talk to Eighteen at the hub ({{L:ch9_hub18}}). From then on, Outfit cycles through every outfit you own (see "Outfits and Super 17" below).
   - **The world map opens here.** Examine Bulma's airship, or walk off the west edge of the grounds ({{X:fly_hub}}), or examine the hangar jets ({{X:fly_hub_jet}}) to take off. See "The open world" below.{{X:ch9_fly_paozu}}{{X:ch9_fly_kame}}
   - **Memory: Mount Paozu (missable).** Land on Mount Paozu and meet Chi-Chi ({{L:ch9_paozu}}).
   - **Memory: Kame House (missable).** Land on Roshi's island and meet Roshi ({{L:ch9_kame}}).
6. When you're ready, walk out of the hub's front gate to West City ({{X:ch9_to_gohan}}).
7. **Boss: {{B:22}}** (Age 774), in the West City ruins ({{X:ch9_gohan}}). Then "End of Chapter 9" ({{X:ch9_end}}).

## Chapter 10: The Last Stand
**You play:** Seventeen. **Goal:** the crossroads.

1. Age 780, the Circus Lot ruins ({{X:ch10_start}}): {{J:ch10_start}}. The resistance has wired the lot with turrets and old machines.
   - Cache: at the foot of the circus sign's left post, in the Circus Lot ruins ({{C:ch10_cache}}).
   - The world map is open again here: talk to Eighteen, or walk off the top of the lot.
2. **The Burning District** (right of the Circus Lot ruins): the resistance ambushes the twins ({{X:ch10_district}}): {{J:ch10_district}}.
   - **Optional: the Resistance Shelter**, down the subway stairs at the top left ({{X:ch10_shelter}}). **Mini-boss: {{B:2}}**. Afterwards, the girl behind the crates ({{L:ch10_girl}}), the radio ({{L:shelter_radio}}), Gero's note 10 on the resistance's map ({{L:note_shelter}}), and a cache ({{C:cache_shelter}}).
3. Go right from the Burning District to the crossroads in the rain ({{X:ch10_rain}}). If you visited Mount Paozu, Eighteen tells Gohan about his mother.
4. **Final boss: {{B:23}}** ({{X:ch10_after}}).
5. **The finale** (Age 785) and the **epilogue** (Age 788) follow ({{X:ch10_finale}}). With all four memories, the **secret chapter** starts. Otherwise the game ends and hints that something else could wake up.

---

# The open world (Act 3, from chapter 9)
**Taking off:** Bulma's airship or the hangar jets at the Age 772 hub, Eighteen at any destination, or walking off the edge of an open area. The first take-off explains the controls ({{X:fly_hub}}).

**Flying:** steer with the + pad. Hold A over a place to land on it. Kami's Lookout floats high above the wasteland, so hold B to climb into it. West City lands at the Age 772 hub, or at the Age 780 Circus Lot from chapter 10.

Eighteen stands next to the landing spot at every destination; talk to her to fly on.{{X:fly_osc}}{{X:fly_lookout}}{{X:fly_papaya}}{{X:fly_diablo}}{{X:fly_pilaf}}{{X:fly_nataday}}{{X:fly_paozu}}{{X:fly_kame}}{{X:fly_west}}

**The seven stone Dragon Balls.** Kami died in Age 767, so the Dragon Balls have turned to stone. Find all seven, then take them to Kami's Lookout:
1. **One-star:** the wreck of Kame House ({{C:kame_ball}}).
2. **Two-star:** Hercule in Orange Star City ({{C:osc_hercule}}).
3. **Three-star:** under Prototype 11 in Diablo Desert ({{C:diablo_ball}}). You must beat **{{B:19}}** first (optional boss).
4. **Four-star:** the shrine in Goku's house on Mount Paozu ({{C:paozu_ball}}).
5. **Five-star:** the elder of Nataday Village ({{C:nat_elder}}). Run Butcher's raiders out first: **{{B:131}}** (optional boss). The farmer ({{L:nat_farmer}}) tells you about them.
6. **Six-star:** Pilaf's old safe ({{C:pilaf_safe}}). Beat **{{B:82}}** first (optional boss).
7. **Seven-star:** the tournament announcer on Papaya Island ({{C:papaya_announcer}}). The welded tournament gate is {{L:papaya_gate}}.

**Kami's palace:** stand under the palace arch on the Lookout and examine it ({{C:lookout_door}}). With all seven balls, Eighteen sets them on the altar.

**Outfits and Super 17.** Select Outfit with the L Button and press B to change. Each press moves on to the next outfit:
- Seventeen: old clothes, android clothes, then (after talking to Eighteen at the hub) a white shirt and a brown jacket.
- Eighteen: old clothes, android clothes, then (same unlock) a red top with yellow trousers, a red top with black sleeves, and a maroon tracksuit.
- **Super 17:** beat **{{B:19}}** in Diablo Desert and open the field case under it: the Project 17-S chip teaches Seventeen **Super 17**, his own transformation. Use it from the android clothes. Super 17 raises Seventeen's Strength by half (x1.5) until he changes back or runs out of ki.

**Other sights:** Orange Star City's school ({{L:osc_school}}), a police officer ({{L:osc_police}}) and a schoolgirl ({{L:osc_girl}}). Every place also has its own first-landing scene.{{X:osc_arrive}}{{X:lookout_arrive}}{{X:papaya_arrive}}{{X:diablo_arrive}}{{X:pilaf_arrive}}{{X:nat_arrive}}

---

# Secret Chapter: First Steps
**Unlocked by:** all four memories (see "Missables"). **You play:** Imperfect Cell, Age 788. Cell has a fixed level and gains no EXP.

1. Cell wakes beneath the bunker ({{X:fs_start}}{{X:fs_wake}}): {{J:fs_wake}}. Android 16's pod is in the tank room ({{L:fs_pod16}}).
2. In the main lab, the backup console plays Gero's recording ({{L:fs_computer}}): {{J:fs_computer}}.
3. The south corridor ({{X:fs_leave}}) leads to the Age 788 Security Wing. It holds four Cyborgs ({{B:17}}); Cell absorbs each one. The hangar door ({{L:fs_out}}) leads outside.
4. **Boss: {{B:24}}** in the West City ruins ({{X:fs_trunks}}).
5. Cell takes the time machine to Age 763 ({{X:fs_after}}{{X:fs_763}}): {{J:fs_763}}. Burrow into the soft ground of the clearing to end the secret chapter ({{X:fs_burrow}}).
