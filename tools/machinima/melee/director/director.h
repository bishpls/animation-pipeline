/* director: turns Super Smash Bros. Melee (the doldecomp/melee decompilation, non-matching build) into a deterministic
 * machinima renderer. The game boots straight into a VS match set up by the script, the HUD and music are off, and every game
 * frame the director writes the script's controller states, camera and one-shot cues. It reports back through OSReport, which
 * Dolphin logs: frame-stamped hits, action-state changes and the end marker. tools/machinima/melee/build.py compiles a film's
 * shot script (Python, tools/machinima/melee/dsl.py) into script.c, which defines the tables declared here.
 *
 * Timeline, in game frames F from match start:
 *   [0, SLATE)              slate: the stage hidden on a magenta clear colour, fighters frozen, a menu click on its first
 *                           frame. The host trims the plates up to its end and syncs the audio dump to the click.
 *   s = F - SLATE, [0, len) the script, on the film's clock (s / 60 = seconds from the plate's first frame)
 *   [len, len + SLATE)      end slate, so the host can check no frame was dropped or doubled
 *   then OSReport("DIRECTOR END") and the scene ends.
 */
#ifndef MELEE_DIRECTOR_H
#define MELEE_DIRECTOR_H

#include <Runtime/platform.h>
#include <melee/ft/forward.h>
#include <melee/mn/types.h>
#include <dolphin/mtx.h>

#define DIR_SLATE 8

/* a pad state, held from `frame` until the port's next entry; sticks are raw -80..80, trig is the analog L/R 0..140 */
typedef struct DirPad {
    s32 frame; /* s16 capped a script at 32767 frames (~9 minutes); labs run longer */
    u8 port;
    u8 trig;
    u32 buttons;
    s8 sx, sy, cx, cy;
} DirPad;

enum { DIR_CUT = 0, DIR_LINEAR, DIR_INOUT, DIR_IN, DIR_OUT };
enum { DIR_AUTO_FASTFALL = 1, DIR_AUTO_LCANCEL = 2, DIR_AUTO_LOWLASER = 4 };

enum { DIR_WORLD = 0, DIR_MID, DIR_P0, DIR_P1, DIR_P2, DIR_P3, DIR_ALL };

/* camera keys: eye, interest (at), vertical fov in degrees and roll in degrees; `ease` shapes the move to the next key.
 * With `track` set, eye and at are offsets from a smoothed tracking point: the fighters' midpoint, or one fighter. The point
 * snaps to the fighters on a cut, so each shot starts framed. */
typedef struct DirCam {
    s32 frame; /* s16 capped a script at 32767 frames (~9 minutes); labs run longer */
    u8 ease;
    u8 track;
    f32 eye[3];
    f32 at[3];
    f32 fov;
    f32 roll;
} DirCam;

enum {
    DIR_FREEZE = 1, /* a: 1 freezes fighters, items and effects (the camera keeps running), 0 releases them */
    DIR_STAGE,      /* a: stage visible 0/1 */
    DIR_BGCOLOR,    /* a, b, c: clear colour 0..255 */
    DIR_SETPOS,     /* port; a, b: x, y */
    DIR_FACE,       /* port; a: facing -1 or 1 */
    DIR_MOTION,     /* port; a: motion state id; b: animation start frame */
    DIR_PERCENT,    /* port; a: damage percent */
    DIR_MARK,       /* a: id, logged as MARK */
    DIR_END,        /* end the script here */
    DIR_RESET,      /* port; a: x, b: facing, c: 1 also clears the stale-move table (fresh moves: dsl reset()'s default on the
                     * Geno line; fresh=False keeps staling). Stand the fighter on the floor at x, in Wait, with no momentum
                     * (between shots) */
    DIR_APPROACH,   /* port; a: range, b: until frame, c: stick. Closed loop: walk toward the opponent while farther than
                     * range, then stand, so a scripted move finds its mark whatever the last knockback did */
    DIR_AUTO,       /* port; a: flags. Closed-loop tech on every aerial: 1 fast fall on the first descending frame,
                     * 2 L-cancel (a shoulder press ~3 frames before touching the floor), 4 low laser (B on the 8th
                     * airborne frame of any hop: the laser spawns 12 frames later at standing-fighter height) */
    DIR_TRACE,      /* port; a: until frame. Log POS s port x y motion hipx hipy vx vy kbx kby air jumps percent every frame
                     * (for planning combos; the hip joint shows the body where cur_pos does not, e.g. hanging on a ledge;
                     * then self and knockback velocity, airborne, jumps used and percent, SO BACK), and HB s port k damage
                     * angle x y radius for each active hitbox */
    DIR_STATUS,     /* port. Log STATUS s port percent x y motion (for labs: throw damage, launch results) */
    DIR_SHIELD,     /* port. Log the shield sphere (ThrowN's world centre and scale) and every hurtbox capsule in world space */
    DIR_FEET,       /* port. Log FEET s port side x y z fx fy fz dx dy dz motion frame: each foot bone's world position and
                     * its local X and Y axes (ftData's LeftFootBone/RightFootBone), the motion state and animation frame */
    DIR_SHIELDHP,   /* port; a: shield health (60 is full): a lab's shield break without minutes of shielding */
    DIR_ITEM,       /* a: ::ItemKind, b, c: x, y. Spawn a common item there (a bat, a crate, a Super Scope...), as the
                     * game's own item drop does, whatever the match's item switch; for labs of the item actions */
    DIR_SFX,        /* a: sound id, b: volume 0-127 (0 = 127). Play a sound as a move script's SoundEffect does
                     * (lbAudioAx_800237A8, centred) and log SFX s id voice: for labs that check a bank's sounds in game */
    DIR_ANIM,       /* port; a: action-table entry. Play that entry's animation and script in the current state, through
                     * the engine's own idle-variant player (ftCo_8008A6D8, Wait's): for animations no state plays
                     * (ItemBlind) */
    DIR_GRDUMP,     /* a: 0 floors only, 1 every line. The stage as the engine holds it this frame: STAGE s grkind stkind
                     * blast l r t b cam l r t b offset x y; LINE s id flags lo x0 y0 x1 y1 for each live collision line
                     * (after joint binding, so moving platforms read where they are); GROUND s port x y air line motion
                     * ledge for every fighter (the floor line it stands on; the ledge line it holds, in the cliff states).
                     * For stage labs and stage-build checks */
    DIR_ITEMS,      /* Log ITEMS s kind x y per live item this frame (a lab's projectile paths: Link's boomerang, Geno's Whirl) */
    DIR_SHOOT,      /* port: the owner; a: kind*16 + state + 4096*(speed*10); b, c: the spawn's offset from the owner (b along
                     * his facing, c up). A laser-type projectile (it_8029C504: Fox's, Falco's, Geno's Finger Shot and Beam
                     * states) fired straight ahead, as its owner's: a lab fires any state of those articles where a move
                     * can't aim it (Geno's throw shots at a PSI Magnet). Logs SHOOT s port kind state x y speed */
    DIR_STALL,      /* a: milliseconds. Busy-waits that long in this frame (console time), so the next loop frame finds
                     * the extra pad samples: a lag frame on purpose, the lag measure's in-band positive control. Logs STALL */
    DIR_PERF,       /* a: 1 on, 0 off. Logs PERF s cpu draw total mtx every frame: the engine's own timings of the last loop
                     * frame (HSD_PerfLastStat, in 60ths of a second of console time: logic, logic + draw submission, all
                     * of it; over 1.0 the frame overran) and its matrix loads. Performance labs */
    /* numbering: 1-25 Geno's labs, 40-41 SO BACK's capture lanes (main), 50 on the Geno trailer. Values are explicit past
     * 25 so parallel lines of work can't collide; keep dsl.py's CUE in step */
    DIR_GLASS = 40  /* (lane 2) a: 1 keeps the screen-KO camera (cm_804D6464) on the director's camera, 0 stops. A screen KO places
                     * the fighter in that camera's view space, and the game only refreshes it in its standard and fixed modes,
                     * so under the director's debug free camera a screen KO hit the glass of the match-start camera */,
    DIR_GAMECAM = 41 /* (lane 2) a: 1 hands the camera back to the game (its own standard match camera; the director's keys
                      * are ignored), 0 takes it again. For checking what the vanilla game shows */,
    /* the trailer lab's cues (projects/geno/trailer/lab), numbered from 50: geno's own run 1-25 and main's SO BACK kit
     * takes 40 (glass) and 41 (gamecam), so the three merge without collisions */
    DIR_STARKO = 50,     /* port. A star KO from where the fighter is (ftCo_800D40B8: the death bookkeeping, the flight into the
                     * background, the twinkle), no blast-zone crossing needed. Skipped if already dead. Logs STARKO */
    DIR_SLOW,       /* a: N. Slow motion by strobing the pause flag: the game runs one frame in N (1 = normal speed); the
                     * camera keeps moving every frame. A freeze cue wins while on. Logs SLOW */
    DIR_METAL,      /* port; a: 1 metal (the Metal Box look, ftCo_800C8348), 0 back to normal (ftCo_800C8540) */
    DIR_ANIMRATE,   /* port; a: the animation rate (0 holds the pose: a trophy); an action change resets it to 1 */
    DIR_COLANIM,    /* port; a: a PlCo colour-animation id (ftCo_800BFFD0; the entry's glow is 0x75), -1 clears it */
    DIR_ENTRY,      /* port. Replay the match-start entry: the fighter hides, then grows out of the trophy stand
                     * (ftCo_800C61B0, the Entry state). Logs ENTRY */
    DIR_ENEMY,      /* port: variant | (fighter + 1) << 4 (x, y relative to that fighter); a: ::ItemKind, b, c: x, y. Spawn a stage enemy through the zako spawner
                     * (it_8027B5B0: the Goomba 0x2B lives in ItCo and works on any stage; Koopas 0xD3 and Paratroopas 0xD4
                     * need their stage's item data, it_802DD7F0 / it_802E16F8). Logs ENEMY */
    DIR_RESPAWN,    /* port; a: costume. Free the fighter and create it again in another costume (Player_80031EBC,
                     * Player_SetCostumeId, Player_80031AD0), then stand it where it was. Logs RESPAWN */
    DIR_HUD,        /* a: 0 the HUD hidden (films' default), 1 name tags only (percents, timer and the rest hidden),
                     * 2 the whole HUD, 3 the whole HUD but the off-screen magnifiers (a film camera frames tighter than
                     * the game's: the bubbles would mark fighters who are on the stage, only out of shot) */
    DIR_ITEMTRACE,  /* a: until frame. Log ITR s kind x y state dmg for every live item every frame (enemies' damage:
                     * Item xC9C), for overlays tracked to an enemy */
    DIR_ITEMVEL,    /* a, b: vx, vy. Set the newest live item's velocity (hold a Starman still: 0, 0). Logs ITEMVEL */
    DIR_ITEMPIN,    /* a: 1 pins every live item's x where it is now (enemies walk in place: a battle line-up) until it is
                     * hit (its damage rises) or a: 0 releases them all; 2 pins x and y with no velocity (a box held in
                     * the air). b: 1 adds the items not pinned yet, each keeping its own mode (geno-film2); c: only this
                     * ::ItemKind (0: any; a stage's own block items can fill the 16 pins). Logs PIN */
    DIR_ITEMCLEAR,  /* Destroy every live item no fighter holds (Item_8026A8EC): a clean slate between a lab's tries.
                     * Logs ITEMCLEAR */
    DIR_EFCLEAR,    /* port. Destroy the fighter's attached effects (efLib_DestroyAll: the entry's light pillars and
                     * sparkles), so a held entry reads as a figure on its stand. Logs EFCLEAR */
    /* the trailer lab's round 2 (projects/geno/trailer/lab, geno-trailer-lab2), numbered from 64 */
    DIR_PLACE = 64, /* port; a: x, b: y, c: facing. DIR_RESET on a floor that isn't y = 0: the floor line under (x, y) is
                     * found (mpCheckFloor, from 10 above to 10 below), the fighter stood on it and linked to that line,
                     * in Wait with no momentum, fresh moves. Logs PLACE s port x y line (line -1: no floor, skipped) */
    DIR_STARCONTACT, /* a: 1 on, 0 off; b: knockback (0: 120); c: angle in degrees (0: 70). SMRPG's star run: while on,
                     * any stage enemy (the zako items: Goombas, ReDeads, Octoroks, Koopas) whose hurtbox touches the hurtbox of
                     * a fighter under a Starman (x221D_b6) takes a hit from that fighter, as the item collision would
                     * credit one (it_802706D0's fighter case: source, direction away from him, angle, knockback, 20
                     * damage), which the enemy's own damage callback turns into its KO flight. Logs STARHIT s port kind x y */
    DIR_BILL,       /* a: variant. Princess Peach's Castle's Banzai Bill (grCastle_DirectorBill): 0-8 launches that flight
                     * now, -1 lets the game pick, -2 stops the natural timer, -3 logs its parameters (BILLPARAM, BILLVAR).
                     * b: log the flight and explosion (map gobjs 1, 2 and 8-16: BILLPOS s gobj x y z) every frame until
                     * that frame. Logs BILL s variant launched */
    DIR_BONE,       /* port; a: FtPart (the fighter's part enum, e.g. HeadN), b: until frame. Log BONE s port part x y z
                     * ax ay az bx by bz cx cy cz motion frame every frame: the part's world position and its local X, Y and Z
                     * axes (a head's pitch, a look up) */
    DIR_REACT       /* port; a: motion state; b: buttons + 4096 * stick (0 none, 1 up, 2 down, 3 forward, 4 back, relative
                     * to his facing); c: until frame. Closed loop, once: on the first frame from the cue whose motion (at
                     * the frame's start, when the game reads the pad) is `a` after a different one, press those buttons
                     * (a new press) and the stick, held 2 frames, on top of the script's pad. The frame an action becomes
                     * possible: a grab on the first frame out of landing lag, a shielder's jump on his first frame out of
                     * shieldstun. Logs REACT s port motion anim-frame */,
    /* the trailer's Part Two (geno-film2), numbered 69-74 (Parts One and Three take 75 up) */
    DIR_HUDWIDE = 69 /* a widescreen film (DirSetup.aspect) with the HUD on: the HUD's own cameras take the film's aspect, so
                      * the HUD keeps its 4:3 shape, pillarboxed in the middle of the 16:9 frame, instead of being widened
                      * by the stretch to 16:9. Logs HUDWIDE s cobj prio aspect and HUDWIDE s n */,
    DIR_FOODVAR = 70 /* a: a Food variant (its index in the Food article's table): the newest live Food (It_Kind_Foods) takes that
                      * variant's model, heal and index, as its own random pick would have set them (a cookie for 6.8).
                      * Logs FOODVAR s variant n heal */,
    /* the trailer's film crew, Parts One and Three (projects/geno/trailer/film/part1_3), numbered from 75 (the montage's
     * crew takes 69-74) */
    DIR_KBVEL = 75, /* port; a, b: vx, vy. Set the fighter's knockback velocity, which decays in the air as a hit's does: a
                     * launch with no hit (Bowser flung in from the sky, with DIR_MOTION DamageFall: he lands into his down
                     * state). Logs KBVEL */
    DIR_HOLDENTRY,  /* port; a: 1 holds the entry's trophy stand (EntryEnd's timer kept where it is: the figure stays on the
                     * stand at full size while the others play on; with DIR_ANIMRATE 0 a doll), 0 releases it (the stand
                     * sinks over its 30 frames and he steps off into Wait). Logs HOLDENTRY */
    DIR_EYES        /* port; a: the eye texture's frame on both eye slots (ftAnim_80070458; Mario's order, which Geno's model
                     * keeps: 0 open, 1 half, 2 closed, 3 squint, 4-5 aside). They hold through action changes until a
                     * move script sets the eyes. Logs EYES */,
    DIR_HOLDDEAD,   /* port; a: 1 holds a star-KO'd fighter after his twinkle (DeadUpStar's respawn wait kept from running
                     * out), 0 lets the respawn go on: a clean sky after the twinkles. Logs HOLDDEAD */
    DIR_RNGLOCK     /* a: 1 reseeds the game's RNG at the start of every frame from the script frame and the setup's seed,
                     * 2 the same and logs the seed each frame found (RNG s seed: the last frame's draws), 0 frees it.
                     * The film camera changes what the game draws, and some of what it draws draws random numbers, so
                     * with the RNG free two cameras on one script can play different matches (9.x: Peach's smash picks
                     * its random item); locked, every frame's gameplay draws are the same whatever the camera sees.
                     * Logs RNGLOCK */
};

typedef struct DirCue {
    s32 frame; /* s16 capped a script at 32767 frames (~9 minutes); labs run longer */
    u8 kind;
    u8 port;
    f32 a, b, c;
} DirCue;

typedef struct DirSetup {
    u16 stage;     /* ::StageKind (St_Kind_Last = Final Destination) */
    u8 nplayers;
    u8 entry;      /* 1: fighters play their entry animation */
    s8 ckind[4];   /* ::CharacterKind */
    u8 color[4];   /* costume */
    f32 x[4];      /* start position (placed at F = 0) */
    s8 face[4];    /* start facing */
    u32 seed;      /* RNG seed, fixed before stage setup */
    f32 aspect;    /* 0 keeps the game's 4:3 */
    u8 cpu[4];     /* 0: the director's pads drive the port; 1-9: the game's CPU at that level */
    u8 stocks;     /* 0: a time match with no timer (films); N: a stock match with N stocks each (the HUD shows stocks) */
    char nametag[4][12]; /* a VS name tag per port, Shift-JIS (2 bytes a character, up to 4): written into the save data's
                          * name table (slots 119 - port) and shown over the fighter (human ports; DIR_HUD 1 or 2). Empty: none */
    u8 prize[4];   /* the prize boot (GM_CHALLENGER_APPROACH with no human, ckind[0] = ChKind_None: the mode starts on its prize
                    * screen): save-data notifications to raise first, id + 1 (0: none); a Geno challenger (ckind[1]) adds
                    * his own two messages (if/ifprize.c) */
    /* the Geno trailer's Part Two (geno-film2). Older emitters' initializers stop before these, and C zero-fills them */
    u8 teams;      /* 1: a team match with friendly fire off (teammates' attacks and items pass through each other) */
    u8 team[5];    /* each player slot's team (0 red, 1 blue, 2 green), slots 0-4 */
    u8 fifth;      /* 1: a fifth fighter in player slot 4. Melee has four pads but six player slots (GM_MAX_PLAYERS), and the
                    * match setup walks all six, so slot 4 takes a CPU fighter: placed at x5 facing face5 on the first frame,
                    * logged as MS and POS lines with port 4, and a target of the cues that only place or set him */
    s8 ckind5;     /* ::CharacterKind */
    u8 color5;     /* costume */
    s8 face5;
    f32 x5;
    u8 cpu_level5; /* 1-9 */
    u8 cpu_kind5;  /* the CPU's behaviour (PlayerInitData.cpu_kind): 0 stands still (training mode's), 4 VS mode's */
    /* the camera pass (geno-camera, 2026-10-02): a sixth fighter in player slot 5, the last of the six (GM_MAX_PLAYERS); as
     * the fifth, a CPU, placed at x6 facing face6 on the first frame, logged with port 5, a target of the cues that only
     * place or set a fighter. Needs `fifth`. Older initializers stop before these, and C zero-fills them */
    u8 sixth;
    s8 ckind6;
    u8 color6;
    s8 face6;
    f32 x6;
    u8 cpu_level6;
    u8 cpu_kind6;
} DirSetup;

/* menu tests: boot into one of the game's own modes (dir_boot_mode, a ::GameModeKind; films use GM_DEBUG_VS) and drive its
 * menus with pads written into the master pad status, so menus and matches read them like a real controller. Each entry is
 * held from `frame` (loop frames since boot) until the port's next entry. Films have no entries. */
typedef struct DirMenuPad {
    s32 frame;
    u8 port;
    u8 trig;
    u16 buttons;
    s8 sx, sy, cx, cy;
} DirMenuPad;

/* closed-loop cursor moves on the character select screen: from `frame` until `until`, the port's stick steers its token
 * (the chip it drops on an icon, which is what the screen hit-tests) to (x, y) in icon-bound units, then holds still */
typedef struct DirMenuGoto {
    s32 frame, until;
    u8 port;
    f32 x, y;
} DirMenuGoto;

extern const int dir_boot_mode;
extern const int dir_unlock_all;    /* menu boots: 1 unlocks Melee's own 11 characters and stages at boot (labs), 0 leaves the
                                     * save as it is (a fresh save keeps them locked; Geno and the Forest Maze need no unlock) */
extern const int dir_show_coll;     /* developer display: 0 off, 1 the model with hitboxes and hurtboxes, 2 the capsules only */
extern const int dir_stage_music;   /* 1: the match plays its stage music (reels) */
extern const int dir_results_music; /* 1: music back on for the scenes after a match (the victory fanfare); films 0 */
extern const DirMenuGoto dir_menu_gotos[];
extern const int dir_nmenu_gotos;
extern const DirMenuPad dir_menu_pads[];
extern const int dir_nmenu_pads;

extern const DirSetup dir_setup;
extern const DirPad dir_pads[];
extern const int dir_npads;
extern const DirCam dir_cams[];
extern const int dir_ncams;
extern const DirCue dir_cues[];
extern const int dir_ncues;
extern const int dir_len;

void director_setup_match(StartMeleeData* start);
int director_boot(void);        /* at boot: returns the ::GameModeKind to start in (menu tests also unlock every character) */
void director_boot_frame(void); /* every loop frame, after the master pad status is read */
void director_on_hit(Fighter_GObj* attacker, Fighter_GObj* victim, float dmg);
/* a loop frame that found N > 1 pad samples queued: it ran over a video frame (logged as LAG f n) */
void director_on_lag(int n) /* LAGFRAME f n */;
void director_on_item_hit(HSD_GObj* item, Fighter_GObj* victim, float dmg);
void director_on_laser(HSD_GObj* parent, Vec3* pos, int kind, float angle, float speed);

#endif
