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
    s16 frame;
    u8 port;
    u8 trig;
    u32 buttons;
    s8 sx, sy, cx, cy;
} DirPad;

enum { DIR_CUT = 0, DIR_LINEAR, DIR_INOUT, DIR_IN, DIR_OUT };
enum { DIR_AUTO_FASTFALL = 1, DIR_AUTO_LCANCEL = 2, DIR_AUTO_LOWLASER = 4 };

enum { DIR_WORLD = 0, DIR_MID, DIR_P0, DIR_P1 };

/* camera keys: eye, interest (at), vertical fov in degrees and roll in degrees; `ease` shapes the move to the next key.
 * With `track` set, eye and at are offsets from a smoothed tracking point: the fighters' midpoint, or one fighter. The point
 * snaps to the fighters on a cut, so each shot starts framed. */
typedef struct DirCam {
    s16 frame;
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
    DIR_RESET,      /* port; a: x, b: facing. Stand the fighter on the floor at x, in Wait, with no momentum (between shots) */
    DIR_APPROACH,   /* port; a: range, b: until frame, c: stick. Closed loop: walk toward the opponent while farther than
                     * range, then stand, so a scripted move finds its mark whatever the last knockback did */
    DIR_AUTO,       /* port; a: flags. Closed-loop tech on every aerial: 1 fast fall on the first descending frame,
                     * 2 L-cancel (a shoulder press ~3 frames before touching the floor), 4 low laser (B on the 8th
                     * airborne frame of any hop: the laser spawns 12 frames later at standing-fighter height) */
    DIR_TRACE       /* port; a: until frame. Log POS s port x y every frame (for planning combos) */
};

typedef struct DirCue {
    s16 frame;
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
} DirSetup;

extern const DirSetup dir_setup;
extern const DirPad dir_pads[];
extern const int dir_npads;
extern const DirCam dir_cams[];
extern const int dir_ncams;
extern const DirCue dir_cues[];
extern const int dir_ncues;
extern const int dir_len;

void director_setup_match(StartMeleeData* start);
void director_on_hit(Fighter_GObj* attacker, Fighter_GObj* victim, float dmg);
void director_on_item_hit(HSD_GObj* item, Fighter_GObj* victim, float dmg);
void director_on_laser(HSD_GObj* parent, Vec3* pos, int kind, float angle, float speed);

#endif
