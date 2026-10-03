/* director.c: the runtime half of the machinima director (see director.h). C89, prototypes required (-requireprotos). */
#include "director.h"

#include <dolphin/os.h>
#include <melee/cm/camera.h>
#include <melee/ft/fighter.h>
#include <melee/ft/ft_0892.h>
#include <melee/ft/ftcommon.h>
#include <melee/ft/ftwaitanim.h>
#include <melee/ft/ftcolanim.h>
#include <melee/ft/ft_0C31.h>
#include <melee/ft/ft_0D31.h>
#include <melee/ft/ftmetal.h>
#include <melee/ft/ftanim.h>
#include <melee/ft/ftdevice.h>
#include <melee/ft/ftlib.h>
#include <melee/ft/ftparts.h>
#include <melee/ft/inlines.h>
#include <melee/ft/types.h>
#include <melee/ft/kinds/ftCommon/types.h>
#include <melee/gm/forward.h>
#include <melee/gm/gm_1601.h>
#include <melee/gm/gm_16F1.h>
#include <melee/gm/gm_1A3F.h>
#include <melee/gm/gmmain_lib.h>
#include <melee/gm/gmscene.h>
#include <melee/gr/forward.h>
#include <melee/gr/ground.h>
#include <melee/gr/stage.h>
#include <melee/gr/types.h>
#include <melee/gr/grcastle.h>
#include <melee/lb/lb_00B0.h>
#include <melee/mp/mplib.h>
#include <melee/mp/types.h>
#include <melee/if/ifall.h>
#include <melee/if/ifstatus.h>
#include <melee/if/iftime.h>
#include <melee/if/ifmagnify.h>
#include <melee/if/ifhazard.h>
#include <melee/if/if_2FD9.h>
#include <melee/if/ifcoget.h>
#include <melee/gm/gmmain_lib.h>
#include <melee/it/itzako.h>
#include <melee/ef/eflib.h>
#include <melee/it/kinds/itnokonoko.h>
#include <melee/it/kinds/itpatapata.h>
#include <melee/it/it_26B1.h>
#include <melee/it/it_2725.h>
#include <melee/it/itCommonItems.h>
#include <melee/it/item.h>
#include <melee/it/kinds/itfoxlaser.h>
#include <melee/it/types.h>
#include <melee/lb/lbaudio_ax.h>
#include <melee/mn/mncharsel.h>
#include <melee/mn/mnstagesel.h>
#include <melee/pl/forward.h>
#include <melee/pl/player.h>
#include <melee/pl/plstale.h>
#include <melee/sfx/crowdsfx.h>
#include <sysdolphin/baselib/cobj.h>
#include <sysdolphin/baselib/controller.h>
#include <sysdolphin/baselib/gobj.h>
#include <sysdolphin/baselib/perf.h>
#include <sysdolphin/baselib/jobj.h>
#include <math.h>
#include <string.h>
#include <sysdolphin/baselib/random.h>

static void director_match_start(void);
static void director_update(void);
static void put_pad(int port, const DirPad* p);
static void put_camera(int s);
extern HSD_CObj* cm_804D6464;  /* camera.c: the camera a screen KO is placed against (DIR_GLASS) */
static int glass_sync;          /* DIR_GLASS: keep cm_804D6464 on the director's camera */
static int game_cam;            /* DIR_GAMECAM: the game's own camera is running */
static void cam_abs(const DirCam* k, Vec3* eye, Vec3* at);
static void run_cue(const DirCue* c);
static void slate(int on);
static f32 ease(int kind, f32 u);
static Fighter* fighter(int port);
static void track_update(int snap);
static void menu_goto(void);
static void show_coll(void);

static int F;                 /* game frames since match start */
static int perf_log;          /* DIR_PERF: log the engine's frame timings */
static s32 crowd_last[3] = { -1, -1, -1 }; /* the crowd state last logged (CROWD lines) */
static int s_end;             /* the script's last frame + 1 (a DIR_END cue can shorten it) */
static int done;
static int pad_i[4];          /* next dir_pads index per port is found by scanning; this is the last applied entry */
static const DirPad* pad_cur[4];
static u32 last_buttons[4];
static int cue_i;
static s32 last_msid[4];
static s32 last_held[4];      /* whether each port held an item last frame (HOLD / LETGO lines) */
static s32 last_vis[4];       /* each port's visibility-group options last frame, packed 4 bits a group (VIS lines) */
static Vec3 trk[7];           /* smoothed tracking points: [DIR_MID], [DIR_P0] .. [DIR_P3], [DIR_ALL] */
static int slow_n;            /* DIR_SLOW: run one game frame in slow_n (0/1: normal) */
static int frozen;            /* DIR_FREEZE on */
static int itrace_until = -1; /* DIR_ITEMTRACE */
static HSD_GObj* pin_g[16];   /* DIR_ITEMPIN: the pinned items, their x and their damage when pinned */
static f32 pin_x[16];
static f32 pin_y[16];
static int pin_mode;          /* 1: x only (walk in place), 2: x and y, velocity zeroed (a box floating in the air) */
static int pin_m[16];         /* each pinned item's own mode (DIR_ITEMPIN b = 1 adds items with their own mode) */
static s32 pin_dmg[16];
static int pin_n;
static int star_contact;       /* DIR_STARCONTACT on */
static f32 star_kb, star_angle;
static HSD_GObj* star_hit[16];  /* enemies it has already KO'd (one hit each) */
static int star_nhit;
static int bill_until = -1;    /* DIR_BILL: log the flight until this frame */
static int bone_until[4];      /* DIR_BONE: per port, the part and until when */
static int bone_part[4];
static s32 hold_entry[4];      /* DIR_HOLDENTRY: the EntryEnd timer each port is held at (-1: not held) */
static s32 hold_dead[4];       /* DIR_HOLDDEAD: keep a star KO's respawn wait from running out */
static s32 rng_lock;           /* DIR_RNGLOCK: 1 reseed the RNG every frame, 2 and log what the last frame left */
static void star_contact_update(int s);
#define REACT_SLOTS 12          /* DIR_REACT: independent armed reactions (a grab and the throw after it, per port) */
static int react_until[REACT_SLOTS]; /* armed until this frame (-1: free) */
static s32 react_port[REACT_SLOTS], react_state[REACT_SLOTS], react_prev[REACT_SLOTS];
static u32 react_btn[REACT_SLOTS];
static int react_dir[REACT_SLOTS], react_hold[REACT_SLOTS];
static void react_update(int s);
static void bill_trace(int s);
static int cam_key;           /* the camera key in effect last frame */
static int ap_until[4];       /* approach: active while s < ap_until */
static f32 ap_range[4];
static s8 ap_stick[4];
static u8 auto_flags[4];      /* DIR_AUTO_* per port */
static u8 ff_done[4], lc_done[4];
static s8 ff_hold[4], lc_hold[4];
static u8 ll_done[4], ll_ff[4];
static int air_frames[4];
static int trace_until[4];
static f32 aspect0 = 0.0f;      /* the match camera's own aspect, before the film's (DIR_HUDWIDE) */
static s32 last_msid5 = -1;    /* the fifth fighter's (player slot 4) last motion state (DirSetup.fifth) */
static s32 last_msid6 = -1;    /* the sixth's (player slot 5; DirSetup.sixth) */
/* the extra fighters past the four pads: port 4 when DirSetup.fifth, port 5 when DirSetup.sixth too */
#define DIR_EXTRA(port) (((port) == 4 && dir_setup.fifth) || ((port) == 5 && dir_setup.fifth && dir_setup.sixth))
static void auto_tech(int s);

static int boot_F;             /* loop frames since boot */
static int menu_i[4];
static u8 last_mode = 0xFF, last_scene = 0xFF;

/* the developer display of hitboxes and hurtboxes, on every fighter in a match (the flags Melee's develop mode toggles:
 * x21FC b6 draws the collision capsules, b7 the model) */
static void show_coll(void)
{
    int port;
    u8 mode = gm_GetCurrentGameMode();
    if (dir_show_coll == 0 || !(mode == GM_DEBUG_VS || (mode == GM_VS && gm_GetCurrentSceneIndex() == 2))) {
        return;
    }
    for (port = 0; port < 4; port++) {
        HSD_GObj* g = Player_GetEntity(port);
        if (g != NULL) {
            Fighter* fp = GET_FIGHTER(g);
            fp->x21FC_flag.b6 = 1;
            fp->x21FC_flag.b7 = dir_show_coll != 2;
        }
    }
}

/* steer each active goto's token toward its target: the hand moves ~0.015 units a frame per unit of stick, so half the
 * error per frame converges without overshoot; menus ignore small sticks, so a move is at least 24 */
static void menu_goto(void)
{
    int i, k;
    f32 hand[2], tok[2];
    if ((gm_GetCurrentGameMode() != GM_VS && gm_GetCurrentGameMode() != GM_TRAINING) || gm_GetCurrentSceneIndex() != 0) {
        return; /* the character select of VS or Training */
    }
    for (i = 0; i < dir_nmenu_gotos; i++) {
        const DirMenuGoto* g = &dir_menu_gotos[i];
        HSD_PadStatus* ps = &HSD_PadMasterStatus[g->port];
        f32 e[2];
        s8 st[2];
        if (boot_F < g->frame || boot_F >= g->until || !mnCharSel_DebugPositions(g->port, hand, tok)) {
            continue;
        }
        e[0] = g->x - tok[0];
        e[1] = g->y - tok[1];
        for (k = 0; k < 2; k++) {
            f32 v = e[k] / 0.015f * 0.5f;
            if (v > 80.0f) {
                v = 80.0f;
            } else if (v < -80.0f) {
                v = -80.0f;
            }
            if (e[k] > 0.25f && v < 24.0f) {
                v = 24.0f;
            } else if (e[k] < -0.25f && v > -24.0f) {
                v = -24.0f;
            } else if (e[k] <= 0.25f && e[k] >= -0.25f) {
                v = 0.0f;
            }
            st[k] = (s8) v;
        }
        ps->err = 0;
        ps->stickX = st[0];
        ps->stickY = st[1];
        ps->nml_stickX = st[0] / 80.0f;
        ps->nml_stickY = st[1] / 80.0f;
        if ((boot_F - g->frame) % 4 == 0 || boot_F == g->until - 1) {
            OSReport("CSSPOS %d port %d hand %.2f %.2f token %.2f %.2f stick %d %d\n", boot_F, g->port, hand[0], hand[1],
                     tok[0], tok[1], st[0], st[1]);
        }
    }
}

int director_boot(void)
{
    int i;
    /* the prize boot (dsl Menu(boot='prize')): the challenger mode with no human starts on its prize screen
     * (gm_Mode_ChallengerApproach_OnLoad), as the game's own unlock-only flow does */
    bool prize = dir_boot_mode == GM_CHALLENGER_APPROACH && dir_setup.ckind[0] == ChKind_None;
    if (dir_boot_mode != GM_DEBUG_VS && !prize && dir_unlock_all) { /* (unlocking all would raise the "all characters" prizes) */
        *gmMainLib_GetUnlockedCharactersBitmaskPtr() = 0x7FF; /* all 11 unlockable characters */
        *gmMainLib_8015EDA4() = 0x7FF;                         /* all 11 unlockable stages (save data x186A) */
        gmMainLib_GetGamePrefs()->stage_mask = 0xFFFFFFFF;     /* and every stage on in random stage select */
    }
    if (dir_boot_mode == GM_CHALLENGER_APPROACH) {
        /* the challenger screen (dsl Menu(boot='challenger', challenger=(human, cpu))): the mode reads the challenger
         * record that a VS or 1P ending fills; zeroed, it shows the fallback silhouette and its fight reads out of bounds.
         * Human on port 0, nametag none, returning to the main menu */
        gm_InitChallengerData(dir_setup.ckind[0], dir_setup.color[0], 0, 120, dir_setup.ckind[1], GM_MENU);
        OSReport("DIRECTOR CHALLENGER human %d cpu %d\n", dir_setup.ckind[0], dir_setup.ckind[1]);
        for (i = 0; i < 4; i++) {
            if (prize && dir_setup.prize[i] != 0) {
                gmMainLib_8015D818(dir_setup.prize[i] - 1);   /* unlocked and not yet shown */
                OSReport("DIRECTOR PRIZE %d\n", dir_setup.prize[i] - 1);
            }
        }
    }
    OSReport("DIRECTOR BOOT mode %d unlock %d\n", dir_boot_mode, dir_unlock_all);
    return dir_boot_mode;
}

void director_boot_frame(void)
{
    int port, i;
    u8 mode = gm_GetCurrentGameMode(), scene = gm_GetCurrentSceneIndex();
    if (mode != last_mode || scene != last_scene) {
        OSReport("SCENE %d mode %d scene %d stkind %d\n", boot_F, mode, scene, (int) Stage_80225194());
        if (mode == GM_VS && scene == 1) {
            /* the stage select: which random-switch entries Random may pick now (gm_80164330, the picker's own test;
             * entry 29 is the Forest Maze in non-matching builds) */
            u32 mask = 0;
            for (i = 0; i < 30; i++) {
                if (gm_80164330(i)) {
                    mask |= 1u << i;
                }
            }
            OSReport("SSSRANDOM %d mask %08X\n", boot_F, mask);
        }
        last_mode = mode;
        last_scene = scene;
        if (dir_results_music && F > 0) {
            /* leaving a match that has run (F: its frames): the match muted the music (director_match_start) and the
             * results screen's fanfare needs it back. The stage music stays off regardless (rules.x1_4) */
            lbAudioAx_80025064(1, 1);
            OSReport("DIRECTOR MUSIC ON %d\n", boot_F);
        }
    }
    if (boot_F == 0) {
        for (port = 0; port < 4; port++) {
            menu_i[port] = -1;
        }
    }
    if (dir_boot_mode != GM_DEBUG_VS && !dir_stage_music) {
        lbAudioAx_80025064(0, 1); /* a menu test with Menu(music=False): the menus' music muted, their sounds and the
                                   * announcer kept (the BGM and SFX volume multipliers) */
    }
    for (port = 0; port < 4; port++) {
        HSD_PadStatus* ps = &HSD_PadMasterStatus[port];
        const DirMenuPad* p = NULL;
        for (i = menu_i[port] + 1; i < dir_nmenu_pads && dir_menu_pads[i].frame <= boot_F; i++) {
            if (dir_menu_pads[i].port == port) {
                menu_i[port] = i;
            }
        }
        if (menu_i[port] < 0) {
            continue;
        }
        p = &dir_menu_pads[menu_i[port]];
        ps->err = 0;
        ps->button = p->buttons;
        ps->stickX = p->sx;
        ps->stickY = p->sy;
        ps->subStickX = p->cx;
        ps->subStickY = p->cy;
        ps->analogL = ps->analogR = p->trig;
        ps->nml_stickX = p->sx / 80.0f;
        ps->nml_stickY = p->sy / 80.0f;
        ps->nml_subStickX = p->cx / 80.0f;
        ps->nml_subStickY = p->cy / 80.0f;
        ps->nml_analogL = ps->nml_analogR = p->trig / 140.0f;
    }
    if (dir_boot_mode != GM_DEBUG_VS && boot_F == dir_len) {
        OSReport("DIRECTOR MENU END %d\n", boot_F); /* a menu test's length: dolphin.py --until stops here */
    }
    menu_goto();
    {
        /* the stage select (menu tests): the hovered entry and the cursor, every 4 frames and on each change */
        static int last_hover = -2;
        f32 xy[2];
        int count, hover = mnStageSel_DebugState(xy, &count);
        if (hover >= 0 && (hover != last_hover || boot_F % 4 == 0)) {
            OSReport("SSS %d hover %d cursor %.2f %.2f stages %d\n", boot_F, hover, xy[0], xy[1], count);
        }
        last_hover = hover;
    }
    show_coll();
    boot_F++;
}

void director_setup_match(StartMeleeData* start)
{
    int i;
    if (dir_boot_mode != GM_DEBUG_VS) {
        return; /* a menu test: the menus chose this match */
    }
    *HSD_RandSeedPtr = dir_setup.seed; /* before stage setup draws from it */
    start->rules.stkind = dir_setup.stage;
    start->rules.match_kind = dir_setup.stocks ? MatchKind_Stock : MatchKind_Time;
    start->rules.timer_enabled = 0;
    start->rules.item_freq = -1;
    start->rules.x1_2 = 1; /* no READY splash */
    start->rules.x1_3 = 1; /* no GO splash; input live at once */
    start->rules.x1_4 = !dir_stage_music; /* never start the stage music, unless a film asks for it (dsl music=True) */
    start->rules.disable_pausing = 1;
    start->rules.on_match_start = director_match_start;
    start->rules.on_frame_start = director_update;
    for (i = 0; i < 4; i++) {
        if (i < dir_setup.nplayers) {
            start->players[i].ckind = dir_setup.ckind[i];
            start->players[i].color = dir_setup.color[i];
            start->players[i].slot_type = dir_setup.cpu[i] ? Gm_PKind_Cpu : Gm_PKind_Human;
            start->players[i].cpu_level = dir_setup.cpu[i];
            start->players[i].cpu_kind = 4; /* VS mode's CPU (gmvsmode.c) */
            start->players[i].xC_b1 = dir_setup.entry;
            if (dir_setup.stocks) {
                start->players[i].stocks = dir_setup.stocks;
            }
        } else {
            start->players[i].slot_type = Gm_PKind_NA;
        }
        start->players[i].rumble_enabled = 0;
        start->players[i].nametag = 120;
        if (i < dir_setup.nplayers && dir_setup.nametag[i][0] != 0) {
            /* a name tag: the save data's name table slot 119 - i (the slots from the top, rarely used), Shift-JIS */
            struct NameTagData* nd = GetPersistentNameData(119 - i);
            int k;
            for (k = 0; k < 8; k++) {
                nd->namedata[k] = dir_setup.nametag[i][k];
            }
            nd->x1A0 = 0;
            start->players[i].nametag = 119 - i;
            OSReport("NAMETAG port %d slot %d\n", i, 119 - i);
        }
    }
    if (dir_setup.fifth) {
        /* a fifth fighter in player slot 4: the match setup walks all six slots (gmvs.c), so slot 4 takes a fighter the
         * way the game's own modes add one. Port 0's record is the template (scale, ratios, handicap, stocks); a CPU, as no
         * pad drives slot 4 (its pad port is set to 3 through `slot`, never read for a CPU) */
        PlayerInitData* p5 = &start->players[4];
        *p5 = start->players[0];
        p5->ckind = dir_setup.ckind5;
        p5->color = dir_setup.color5;
        p5->slot_type = Gm_PKind_Cpu;
        p5->cpu_level = dir_setup.cpu_level5 ? dir_setup.cpu_level5 : 1;
        p5->cpu_kind = dir_setup.cpu_kind5;
        p5->slot = 4;
        p5->nametag = 120;
        p5->rumble_enabled = 0;
        OSReport("FIFTH ckind %d color %d cpu %d kind %d\n", dir_setup.ckind5, dir_setup.color5, p5->cpu_level,
                 dir_setup.cpu_kind5);
        if (dir_setup.sixth) { /* the sixth, in slot 5, the same way */
            PlayerInitData* p6 = &start->players[5];
            *p6 = start->players[0];
            p6->ckind = dir_setup.ckind6;
            p6->color = dir_setup.color6;
            p6->slot_type = Gm_PKind_Cpu;
            p6->cpu_level = dir_setup.cpu_level6 ? dir_setup.cpu_level6 : 1;
            p6->cpu_kind = dir_setup.cpu_kind6;
            p6->slot = 5;
            p6->nametag = 120;
            p6->rumble_enabled = 0;
            OSReport("SIXTH ckind %d color %d cpu %d kind %d\n", dir_setup.ckind6, dir_setup.color6, p6->cpu_level,
                     dir_setup.cpu_kind6);
        }
    }
    if (dir_setup.teams) {
        start->rules.is_teams = 1;
        start->rules.friendly_fire = 0;
        for (i = 0; i < 5; i++) {
            start->players[i].team = dir_setup.team[i];
        }
        OSReport("TEAMS %d %d %d %d %d\n", dir_setup.team[0], dir_setup.team[1], dir_setup.team[2], dir_setup.team[3],
                 dir_setup.team[4]);
    }
    OSReport("DIRECTOR SETUP stage %d players %d seed %u\n", dir_setup.stage, dir_setup.nplayers, dir_setup.seed);
}

static void director_match_start(void)
{
    int i;
    F = 0;
    done = 0;
    cue_i = 0;
    s_end = dir_len;
    cam_key = -1;
    glass_sync = 0;
    game_cam = 0;
    slow_n = 0;
    frozen = 0;
    itrace_until = -1;
    pin_n = 0;
    star_contact = 0;
    for (i = 0; i < REACT_SLOTS; i++) {
        react_until[i] = -1;
        react_hold[i] = 0;
    }
    star_nhit = 0;
    rng_lock = 0;
    bill_until = -1;
    last_msid5 = -1;
    for (i = 0; i < 4; i++) {
        bone_until[i] = -1;
        hold_entry[i] = -1;
        hold_dead[i] = 0;
        pad_i[i] = -1;
        pad_cur[i] = NULL;
        last_buttons[i] = 0;
        last_msid[i] = -1;
        last_held[i] = 0;
        last_vis[i] = -1;
        ap_until[i] = -1;
        auto_flags[i] = ff_done[i] = lc_done[i] = 0;
        ff_hold[i] = lc_hold[i] = 0;
        ll_done[i] = ll_ff[i] = 0;
        trace_until[i] = -1;
    }
    if (!dir_setup.stocks) {
        ifAll_HideHUD(); /* films are clean plates; a stock match (a HUD test) keeps it */
    }
    Camera_SetQuakeScale(0.0f);
    if (dir_ncams > 0) {
        Camera_8003006C(); /* debug free camera: the director writes eye, interest and fov every frame */
    } /* else the game's own camera: the match framing players see (dsl Film.game_camera) */
    if (dir_setup.aspect > 0.0f) {
        aspect0 = HSD_CObjGetAspect(GET_COBJ(Camera_80030A50()));
        HSD_CObjSetAspect(GET_COBJ(Camera_80030A50()), dir_setup.aspect);
    }
    if (!dir_stage_music) {
        lbAudioAx_80025064(0, 1); /* music off, sound effects on (belt and braces with rules.x1_4) */
    }
    OSReport("DIRECTOR START len %d slate %d\n", dir_len, DIR_SLATE);
}

static Fighter* fighter(int port)
{
    HSD_GObj* g = Player_GetEntity(port);
    return g != NULL ? GET_FIGHTER(g) : NULL;
}

static void slate(int on)
{
    Camera_SetStageVisible(!on);
    if (on) {
        Camera_SetBackgroundColor(255, 0, 255);
        gm_SetDbPauseFlag(1);
        lbAudioAx_80024030(1); /* a click at each slate's first frame: the host syncs the game's audio dump to it */
    } else {
        Camera_SetBackgroundColor(0, 0, 0);
        gm_ClearDbPauseFlag(1);
    }
}

static void director_update(void)
{
    int s = F - DIR_SLATE, port, i;
    if (done) {
        return;
    }
    if (rng_lock) { /* before anything this frame draws: the same draws whatever the camera saw last frame */
        u32 x = (u32) F * 2654435761u + (u32) dir_setup.seed * 2246822519u; /* murmur3's finaliser: every bit */
        if (rng_lock == 2) {
            OSReport("RNG %d %u\n", s, *HSD_RandSeedPtr);
        }
        x ^= x >> 16;
        x *= 0x85EBCA6Bu;
        x ^= x >> 13;
        x *= 0xC2B2AE35u;
        x ^= x >> 16;
        *HSD_RandSeedPtr = x;
    }
    if (perf_log) {
        OSReport("PERF %d %.3f %.3f %.3f %u\n", s, HSD_PerfLastStat.cpu_time, HSD_PerfLastStat.draw_time,
                 HSD_PerfLastStat.total_time, HSD_PerfLastStat.nb_mtx_load);
    }
    if (F == 0) {
        slate(1);
        if (!dir_setup.entry) {
            for (i = 0; i < dir_setup.nplayers; i++) {
                Fighter* fp = fighter(i);
                Vec3 hit0, nrm0;
                int line0 = -1;
                u32 flags0 = 0;
                if (fp != NULL && !mpCheckFloor(dir_setup.x[i], 10.0f, dir_setup.x[i], -10.0f, 0.0f, &hit0, &line0, &flags0,
                                               &nrm0, -1, -1, -1, NULL, NULL))
                {
                    /* no floor within 10 of y = 0 under x (geno-film2): leave him on his spawn point (a stage whose floors
                     * aren't at 0: Hyrule Temple, Peach's Castle) for a DIR_PLACE */
                    OSReport("SETUP NOFLOOR %d %.2f\n", i, dir_setup.x[i]);
                } else if (fp != NULL) {
                    Vec3 p;
                    p.x = dir_setup.x[i];
                    p.y = 0.0f;
                    p.z = 0.0f;
                    ftLib_SetPos(Player_GetEntity(i), &p);
                    /* restart the collision sweep at the new place too, as DIR_RESET and DIR_SETPOS do (geno-film2): it
                     * sweeps from the previous positions, still the spawn point, so where a stage's spawn points stand on
                     * platforms (Yoshi's Story, Peach's Castle, Pokémon Stadium's port 0) the fighter was swept straight
                     * back onto them on the first frame */
                    fp->prev_pos = p;
                    fp->coll_data.cur_pos = p;
                    fp->coll_data.prev_pos = p;
                    fp->coll_data.last_pos = p;
                    fp->facing_dir = (f32) dir_setup.face[i];
                }
            }
            if (dir_setup.fifth && fighter(4) != NULL) {
                Vec3 p;
                p.x = dir_setup.x5;
                p.y = 0.0f;
                p.z = 0.0f;
                ftLib_SetPos(Player_GetEntity(4), &p);
                fighter(4)->prev_pos = p;
                fighter(4)->coll_data.cur_pos = p;
                fighter(4)->coll_data.prev_pos = p;
                fighter(4)->coll_data.last_pos = p;
                fighter(4)->facing_dir = (f32) dir_setup.face5;
            }
            if (dir_setup.fifth && dir_setup.sixth && fighter(5) != NULL) {
                Vec3 p;
                p.x = dir_setup.x6;
                p.y = 0.0f;
                p.z = 0.0f;
                ftLib_SetPos(Player_GetEntity(5), &p);
                fighter(5)->prev_pos = p;
                fighter(5)->coll_data.cur_pos = p;
                fighter(5)->coll_data.prev_pos = p;
                fighter(5)->coll_data.last_pos = p;
                fighter(5)->facing_dir = (f32) dir_setup.face6;
            }
        }
    }
    if (F == 1) { /* the fighters' own attributes, from the disc's fighter data: tools/machinima/melee/framedata.py */
        for (i = 0; i < dir_setup.nplayers; i++) {
            Fighter* fp = fighter(i);
            if (fp != NULL) {
                OSReport("ATTR %d %d walk %.4f dash0 %.4f dashmax %.4f jumpsquat %.1f hop %.4f jump %.4f jumph %.4f "
                         "grav %.4f term %.4f ff %.4f drift %.4f airfric %.4f fric %.4f\n",
                         i, fp->kind, fp->co_attrs.walk_max_vel, fp->co_attrs.dash_initial_velocity,
                         fp->co_attrs.dash_max_velocity, fp->co_attrs.jump_startup_time,
                         fp->co_attrs.hop_v_initial_velocity, fp->co_attrs.jump_v_initial_velocity,
                         fp->co_attrs.jump_h_initial_velocity, fp->co_attrs.gravity, fp->co_attrs.terminal_velocity,
                         fp->co_attrs.fast_fall_velocity, fp->co_attrs.air_drift_max, fp->co_attrs.aerial_friction,
                         fp->co_attrs.ground_friction);
                /* SO BACK: the air-mobility attributes (ftCo_DatAttrs), for the carried-momentum lab */
                OSReport("ATTR2 %d %d gr2air %.4f jumphmax %.4f airjumpv %.4f airjumph %.4f jumps %d airmul %.4f airbase %.4f "
                         "airhmax %.4f groundhmax %.4f dashaccm %.4f dashaccb %.4f\n",
                         i, fp->kind, fp->co_attrs.ground_to_air_jump_momentum_multiplier, fp->co_attrs.jump_h_max_velocity,
                         fp->co_attrs.air_jump_v_multiplier, fp->co_attrs.air_jump_h_multiplier, fp->co_attrs.max_jumps,
                         fp->co_attrs.air_drift_stick_mul, fp->co_attrs.aerial_drift_base,
                         fp->co_attrs.air_max_horizontal_velocity, fp->co_attrs.ground_max_horizontal_velocity,
                         fp->co_attrs.dash_accel_mul, fp->co_attrs.dash_accel_base);
                OSReport("LAG %d landing %.0f n %.0f f %.0f b %.0f hi %.0f lw %.0f weight %.0f\n", i,
                         fp->co_attrs.normal_landing_lag, fp->co_attrs.landingairn_lag, fp->co_attrs.landingairf_lag,
                         fp->co_attrs.landingairb_lag, fp->co_attrs.landingairhi_lag, fp->co_attrs.landingairlw_lag,
                         fp->co_attrs.weight);
            }
        }
    }
    if (s == 0) {
        slate(0);
        OSReport("S0 %d\n", F);
    }
    if (s >= 0 && s < s_end && slow_n > 1 && !frozen) {
        /* slow motion: the fighters, items and effects run one frame in slow_n; the camera keeps moving */
        if (F % slow_n == 0) {
            gm_ClearDbPauseFlag(1);
        } else {
            gm_SetDbPauseFlag(1);
        }
    }
    if (s >= 0 && pin_n > 0) {
        /* pinned items: put each back on its x (before the game's logic moves it again), while it is still alive and
         * unhurt */
        HSD_GObj* ig;
        int k;
        for (k = 0; k < pin_n; k++) {
            for (ig = HSD_GObjPLinkHead[HSD_GOBJ_PLINK_ITEM]; ig != NULL && ig != pin_g[k]; ig = ig->next) {
            }
            if (ig == NULL) {
                pin_g[k] = NULL;
            } else {
                Item* ip = (Item*) ig->user_data;
                if (pin_m[k] != 2 && ip->xC9C != pin_dmg[k]) { /* a floating box stays up until it breaks */
                    pin_g[k] = NULL;
                } else {
                    ip->pos.x = pin_x[k];
                    if (pin_m[k] == 2) {
                        ip->pos.y = pin_y[k];
                        ip->x40_vel.x = ip->x40_vel.y = 0.0f;
                    }
                }
            }
        }
    }
    if (s >= 0 && s < itrace_until) {
        HSD_GObj* ig;
        for (ig = HSD_GObjPLinkHead[HSD_GOBJ_PLINK_ITEM]; ig != NULL; ig = ig->next) {
            Item* ip = (Item*) ig->user_data;
            OSReport("ITR %d %d %.2f %.2f %d %d\n", s, (int) ip->kind, ip->pos.x, ip->pos.y, (int) ip->msid, (int) ip->xC9C);
        }
    }
    if (s >= 0 && s < s_end) {
        while (cue_i < dir_ncues && dir_cues[cue_i].frame <= s) {
            run_cue(&dir_cues[cue_i]);
            cue_i++;
        }
    }
    if (s >= 0 && s < s_end && star_contact) {
        star_contact_update(s);
    }
    if (s >= 0 && s < bill_until) {
        bill_trace(s);
    }
    if (s >= 0 && s < s_end) {
        for (port = 0; port < dir_setup.nplayers; port++) {
            Fighter* fp = fighter(port);
            if (fp != NULL && hold_entry[port] >= 0 && fp->motion_id == 324 /* ftCo_MS_EntryEnd */) {
                fp->mv.co.entry.timer = hold_entry[port];
            }
            if (fp != NULL && hold_dead[port] && fp->motion_id == 4 /* ftCo_MS_DeadUpStar */ &&
                fp->mv.co.unk_deadup.x44 == 2 && fp->mv.co.unk_deadup.x40 < 4)
            {
                fp->mv.co.unk_deadup.x40 = 4; /* past the twinkle: the respawn waits */
            }
            if (fp != NULL && s < bone_until[port]) {
                MtxPtr m = HSD_JObjGetMtxPtr(fp->parts[ftParts_GetBoneIndex(fp, bone_part[port])].joint);
                OSReport("BONE %d %d %d %.3f %.3f %.3f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %.4f %d %.2f\n", s, port,
                         bone_part[port], m[0][3], m[1][3], m[2][3], m[0][0], m[1][0], m[2][0], m[0][1], m[1][1], m[2][1],
                         m[0][2], m[1][2], m[2][2], fp->motion_id, fp->cur_anim_frame);
            }
        }
    }
    if (s == s_end) {
        slate(1);
    }
    /* pads: each port holds its latest entry at or before s (neutral before its first) */
    for (port = 0; port < 4; port++) {
        for (i = pad_i[port] + 1; i < dir_npads; i++) {
            if (dir_pads[i].frame > s) {
                break;
            }
            if (dir_pads[i].port == port) {
                pad_i[port] = i;
                pad_cur[port] = &dir_pads[i];
            }
        }
        if (port < dir_setup.nplayers) {
            put_pad(port, s >= 0 && s < s_end ? pad_cur[port] : NULL);
        }
    }
    /* approach: steer the stick toward the opponent until inside range (2-player films: the opponent is port ^ 1) */
    for (port = 0; port < dir_setup.nplayers && port < 2; port++) {
        if (s >= 0 && s < ap_until[port]) {
            Fighter* me = fighter(port);
            Fighter* op = fighter(port ^ 1);
            if (me != NULL && op != NULL) {
                f32 dx = op->cur_pos.x - me->cur_pos.x;
                s8 st = 0;
                if (dx > ap_range[port]) {
                    st = ap_stick[port];
                } else if (-dx > ap_range[port]) {
                    st = -ap_stick[port];
                }
                HSD_PadGameStatus[port].stickX = st;
                HSD_PadGameStatus[port].nml_stickX = st / 80.0f;
            }
        }
    }
    if (s >= 0 && s < s_end) {
        react_update(s);
        auto_tech(s);
        for (port = 0; port < dir_setup.nplayers; port++) {
            Fighter* fp = fighter(port);
            if (fp != NULL && s < trace_until[port]) {
                /* POS: position, motion, then the hip joint's world position (what the eye follows: a ledge action's
                 * cur_pos is the ledge plus TransN, but CliffWait keeps cur_pos at the corner and hangs the body by TransN
                 * in the skeleton, so only the joint shows whether the body jumps between actions), then SO BACK's
                 * velocities (self and knockback), the airborne flag, the jump counter and percent. Fields only ever
                 * append: parsers read by index (Geno's labs the hip at 6-7) */
                MtxPtr m = HSD_JObjGetMtxPtr(fp->parts[ftParts_GetBoneIndex(fp, FtPart_HipN)].joint);
                /* then (the trailer lab, round 2) hitlag frames left, the animation frame and shield health: the
                 * frame-by-frame advantage of shield pressure */
                OSReport("POS %d %d %.2f %.2f %d %.2f %.2f %.3f %.3f %.3f %.3f %d %d %.1f %.0f %.2f %.2f\n", s, port,
                         fp->cur_pos.x, fp->cur_pos.y, fp->motion_id, m[0][3], m[1][3], fp->self_vel.x, fp->self_vel.y,
                         fp->x8c_kb_vel.x, fp->x8c_kb_vel.y, fp->ground_or_air == GA_Air, fp->x1968_jumpsUsed,
                         fp->dmg.x1830_percent, fp->dmg.x195c_hitlag_frames, fp->cur_anim_frame, fp->shield_health);
                {
                    int k;
                    for (k = 0; k < 4; k++) {
                        HitCapsule* hb = &fp->x914[k];
                        if (hb->state != HitCapsule_Disabled) {
                            OSReport("HB %d %d %d %.1f %d %.2f %.2f %.2f\n", s, port, k, hb->damage, hb->kb_angle, hb->x4C.x,
                                     hb->x4C.y, hb->scale);
                        }
                    }
                }
            }
        }
    }
    /* the crowd (sfx/crowdsfx.c): who it chants for (spawn number), the chant's sound id, and its play count (0 while the
     * opening gasp plays, 1..max_gasp_count-1 each time the chant sample restarts, then the closing cheer) */
    if (s >= 0 && s < s_end && crowdsfx_ptr != NULL) {
        CrowdSFX_UnkStruct* c = crowdsfx_ptr;
        if ((s32) c->xC != crowd_last[0] || c->x14 != crowd_last[1] || c->x18 != crowd_last[2]) {
            crowd_last[0] = (s32) c->xC;
            crowd_last[1] = c->x14;
            crowd_last[2] = c->x18;
            OSReport("CROWD %d fighter %d chant %d count %d voice %d\n", s, (int) c->xC, (int) c->x14, (int) c->x18,
                     (int) c->x2C);
        }
    }
    put_camera(s < 0 ? 0 : (s < s_end ? s : s_end - 1));
    /* the fifth and sixth fighters (player slots 4 and 5): their motion states, and their positions every frame */
    for (port = 4; port < 6; port++) {
        Fighter* fp = s >= 0 && s < s_end && DIR_EXTRA(port) ? fighter(port) : NULL;
        s32* last = port == 4 ? &last_msid5 : &last_msid6;
        if (fp != NULL) {
            if (fp->motion_id != *last) {
                *last = fp->motion_id;
                OSReport("MS %d %d %d %.2f %.2f\n", s, port, fp->motion_id, fp->cur_pos.x, fp->cur_pos.y);
            }
            OSReport("POS %d %d %.2f %.2f %d %.2f %.2f %.3f %.3f %.3f %.3f %d %d %.1f %.0f %.2f %.2f\n", s, port, fp->cur_pos.x,
                     fp->cur_pos.y, fp->motion_id, fp->cur_pos.x, fp->cur_pos.y, fp->self_vel.x, fp->self_vel.y,
                     fp->x8c_kb_vel.x, fp->x8c_kb_vel.y, fp->ground_or_air == GA_Air, fp->x1968_jumpsUsed,
                     fp->dmg.x1830_percent, fp->dmg.x195c_hitlag_frames, fp->cur_anim_frame, fp->shield_health);
        }
    }
    /* report motion-state changes: the action timeline the host checks against the script */
    if (s >= 0 && s < s_end) {
        for (port = 0; port < dir_setup.nplayers; port++) {
            Fighter* fp = fighter(port);
            if (fp != NULL && fp->motion_id != last_msid[port]) {
                last_msid[port] = fp->motion_id;
                OSReport("MS %d %d %d %.2f %.2f\n", s, port, fp->motion_id, fp->cur_pos.x, fp->cur_pos.y);
            }
            /* an item taken or let go (the hand's item slot), with the action and its animation frame: an item throw's
             * own release event, to line the throw's key pose up with */
            /* the model's visibility groups (script command 0x1F model mod; an action change reverts them): the option
             * each group shows, when any changes, with the action and its animation frame (-1: the group hidden) */
            if (fp != NULL) {
                s32 v = 0;
                int g, n = fp->x5AC.model_num < 7 ? fp->x5AC.model_num : 7;
                int o[7];
                for (g = 0; g < 7; g++) {
                    o[g] = g < n ? (int) fp->x5F4_arr[g].idx : 9;
                    v |= ((o[g] + 1) & 0xF) << (4 * g);
                }
                if (v != last_vis[port]) {
                    last_vis[port] = v;
                    OSReport("VIS %d %d state %d anim %.2f groups %d %d %d %d %d %d %d\n", s, port, fp->motion_id,
                             fp->cur_anim_frame, o[0], o[1], o[2], o[3], o[4], o[5], o[6]);
                }
            }
            if (fp != NULL && (fp->item_gobj != NULL) != last_held[port]) {
                last_held[port] = fp->item_gobj != NULL;
                OSReport("%s %d %d state %d anim %.2f\n", last_held[port] ? "HOLD" : "LETGO", s, port, fp->motion_id,
                         fp->cur_anim_frame);
            }
        }
    }
    if (s == s_end + DIR_SLATE) {
        OSReport("DIRECTOR END %d\n", F);
        done = 1;
        gm_801A4B60();
    }
    F++;
}

/* aerial attacks are the common motion states AttackAirN..AttackAirLw */
#define IS_AERIAL(fp) ((fp)->motion_id >= 65 && (fp)->motion_id <= 69)

static void auto_tech(int s)
{
    int port;
    (void) s;
    for (port = 0; port < dir_setup.nplayers; port++) {
        Fighter* fp = fighter(port);
        HSD_PadStatus* ps = &HSD_PadGameStatus[port];
        if (fp == NULL || auto_flags[port] == 0) {
            continue;
        }
        if (fp->ground_or_air != GA_Air) {
            ff_done[port] = lc_done[port] = 0;
            ll_done[port] = ll_ff[port] = 0;
            air_frames[port] = 0;
        } else {
            air_frames[port]++;
        }
        /* low laser: B on the 8th airborne frame of a hop. The laser leaves the gun 12 frames later, at about 15 units: the
         * laser lab measured that anything fired before air frame 7 flies over a standing fighter */
        if ((auto_flags[port] & DIR_AUTO_LOWLASER) && fp->ground_or_air == GA_Air && !ll_done[port] &&
            air_frames[port] == 8)
        {
            ll_done[port] = 1;
            ps->button |= 0x200;
            ps->trigger |= 0x200 & ~ps->last_button;
        }
        /* fast fall: a sharp stick-down on the first descending frame of an aerial (the game sees a smash input) */
        if ((auto_flags[port] & DIR_AUTO_FASTFALL) && !ff_done[port] && fp->ground_or_air == GA_Air && IS_AERIAL(fp) &&
            fp->self_vel.y < 0.0f)
        {
            ff_done[port] = 1;
            ff_hold[port] = 2;
        }
        if (ff_hold[port] > 0) {
            ff_hold[port]--;
            ps->stickY = -80;
            ps->nml_stickY = -1.0f;
        }
        /* L-cancel: press a shoulder once the fighter is falling within 6 units of the floor (y = 0): two to four frames
         * before touching down at any fall speed, inside the game's 7-frame window */
        if ((auto_flags[port] & DIR_AUTO_LCANCEL) && !lc_done[port] && fp->ground_or_air == GA_Air && IS_AERIAL(fp) &&
            fp->self_vel.y < 0.0f && fp->cur_pos.y < 6.0f)
        {
            lc_done[port] = 1;
            lc_hold[port] = 2;
        }
        if (lc_hold[port] > 0) {
            lc_hold[port]--;
            ps->button |= 0x20 | 0x80000000; /* R, and the either-shoulder bit */
            ps->trigger |= (0x20 | 0x80000000) & ~ps->last_button;
            ps->analogR = 140;
            ps->nml_analogR = 1.0f;
        }
    }
}

static void put_pad(int port, const DirPad* p)
{
    HSD_PadStatus* ps = &HSD_PadGameStatus[port];
    u32 b = p != NULL ? (p->buttons | (p->trig ? 0x80000000 : 0)) : 0;
    u32 last = last_buttons[port];
    s8 sx = p != NULL ? p->sx : 0, sy = p != NULL ? p->sy : 0;
    s8 cx = p != NULL ? p->cx : 0, cy = p != NULL ? p->cy : 0;
    u8 tr = p != NULL ? p->trig : 0;
    ps->last_button = last;
    ps->button = b;
    ps->trigger = b & ~last;
    ps->release = last & ~b;
    ps->repeat = ps->trigger;
    ps->stickX = sx;
    ps->stickY = sy;
    ps->subStickX = cx;
    ps->subStickY = cy;
    ps->analogL = tr;
    ps->analogR = 0;
    ps->nml_stickX = sx / 80.0f;
    ps->nml_stickY = sy / 80.0f;
    ps->nml_subStickX = cx / 80.0f;
    ps->nml_subStickY = cy / 80.0f;
    ps->nml_analogL = tr / 140.0f;
    ps->nml_analogR = 0.0f;
    ps->err = 0;
    last_buttons[port] = b;
}

static f32 ease(int kind, f32 u)
{
    switch (kind) {
    case DIR_CUT:
        return 0.0f;
    case DIR_IN:
        return u * u * u;
    case DIR_OUT:
        u = 1.0f - u;
        return 1.0f - u * u * u;
    case DIR_INOUT:
        if (u < 0.5f) {
            return 4.0f * u * u * u;
        }
        u = -2.0f * u + 2.0f;
        return 1.0f - u * u * u * 0.5f;
    default:
        return u;
    }
}

static void track_update(int snap)
{
    Vec3 raw[7];
    int i, n = 0, na = 0;
    raw[DIR_MID].x = raw[DIR_MID].y = raw[DIR_MID].z = 0.0f;
    raw[DIR_ALL] = raw[DIR_MID];
    for (i = 0; i < 4; i++) {
        Fighter* fp = i < dir_setup.nplayers ? fighter(i) : NULL;
        if (fp != NULL && fp->motion_id > 13) { /* alive and not on the respawn platform */
            raw[DIR_P0 + i] = fp->cur_pos;
            if (i < 2) {
                raw[DIR_MID].x += fp->cur_pos.x;
                raw[DIR_MID].y += fp->cur_pos.y;
                n++;
            }
            raw[DIR_ALL].x += fp->cur_pos.x;
            raw[DIR_ALL].y += fp->cur_pos.y;
            na++;
        } else {
            raw[DIR_P0 + i] = trk[DIR_P0 + i];
        }
    }
    if (n > 0) {
        raw[DIR_MID].x /= n;
        raw[DIR_MID].y /= n;
    } else {
        raw[DIR_MID] = trk[DIR_MID];
    }
    if (na > 0) {
        raw[DIR_ALL].x /= na;
        raw[DIR_ALL].y /= na;
    } else {
        raw[DIR_ALL] = trk[DIR_ALL];
    }
    for (i = DIR_MID; i <= DIR_ALL; i++) {
        if (snap) {
            trk[i] = raw[i];
        } else { /* critically damped enough for knockback, never jittery */
            trk[i].x += (raw[i].x - trk[i].x) * 0.12f;
            trk[i].y += (raw[i].y - trk[i].y) * 0.08f;
        }
        trk[i].z = 0.0f;
    }
}

static void cam_abs(const DirCam* k, Vec3* eye, Vec3* at)
{
    Vec3 o;
    o.x = o.y = o.z = 0.0f;
    if (k->track != DIR_WORLD) {
        o = trk[k->track];
    }
    eye->x = o.x + k->eye[0];
    eye->y = o.y + k->eye[1];
    eye->z = o.z + k->eye[2];
    at->x = o.x + k->at[0];
    at->y = o.y + k->at[1];
    at->z = o.z + k->at[2];
}

static void put_camera(int s)
{
    int k = 0;
    const DirCam* a;
    const DirCam* b;
    Vec3 ea, aa, eb, ab;
    f32 u = 0.0f;
    if (dir_ncams == 0 || game_cam) {
        /* the game's own camera (no keys, or DIR_GAMECAM handed it back): log where it is (eye, interest, fov) so a board
         * can place world points on the image */
        HSD_CObj* cobj = GET_COBJ(Camera_80030A50());
        HSD_CObjGetEyePosition(cobj, &ea);
        HSD_CObjGetInterest(cobj, &aa);
        OSReport("CAM %d %.3f %.3f %.3f %.3f %.3f %.3f %.3f\n", s, ea.x, ea.y, ea.z, aa.x, aa.y, aa.z, HSD_CObjGetFov(cobj));
        return;
    }
    while (k + 1 < dir_ncams && dir_cams[k + 1].frame <= s) {
        k++;
    }
    /* snap the trackers on the first frame and whenever a key is entered by a cut */
    track_update(cam_key < 0 || (k != cam_key && dir_cams[k - (k > 0)].ease == DIR_CUT));
    cam_key = k;
    a = &dir_cams[k];
    b = k + 1 < dir_ncams ? &dir_cams[k + 1] : a;
    if (b != a && b->frame > a->frame) {
        u = ease(a->ease, (f32) (s - a->frame) / (f32) (b->frame - a->frame));
    }
    cam_abs(a, &ea, &aa);
    cam_abs(b, &eb, &ab);
    cm_80453004.free_eye_pos.x = ea.x + (eb.x - ea.x) * u;
    cm_80453004.free_eye_pos.y = ea.y + (eb.y - ea.y) * u;
    cm_80453004.free_eye_pos.z = ea.z + (eb.z - ea.z) * u;
    cm_80453004.free_int_pos.x = aa.x + (ab.x - aa.x) * u;
    cm_80453004.free_int_pos.y = aa.y + (ab.y - aa.y) * u;
    cm_80453004.free_int_pos.z = aa.z + (ab.z - aa.z) * u;
    cm_80453004.free_fov = a->fov + (b->fov - a->fov) * u;
    HSD_CObjSetRoll(GET_COBJ(Camera_80030A50()), (a->roll + (b->roll - a->roll) * u) * 0.017453292f);
    if (glass_sync) { /* DIR_GLASS: the screen-KO camera sees what the director's camera sees */
        HSD_CObjSetFov(cm_804D6464, cm_80453004.free_fov);
        HSD_CObjSetInterest(cm_804D6464, &cm_80453004.free_int_pos);
        HSD_CObjSetEyePosition(cm_804D6464, &cm_80453004.free_eye_pos);
        HSD_CObjSetRoll(cm_804D6464, (a->roll + (b->roll - a->roll) * u) * 0.017453292f);
        if (dir_setup.aspect > 0.0f) {
            HSD_CObjSetAspect(cm_804D6464, dir_setup.aspect);
        }
    }
}

/* squared distance between segments p0-p1 and q0-q1 (x and y only: fighters and items live on z = 0, and a capsule's
 * z offset is the model's depth, which collision ignores too) */
static f32 seg_dist2(const Vec3* p0, const Vec3* p1, const Vec3* q0, const Vec3* q1)
{
    f32 dx = p1->x - p0->x, dy = p1->y - p0->y, ex = q1->x - q0->x, ey = q1->y - q0->y;
    f32 rx = p0->x - q0->x, ry = p0->y - q0->y;
    f32 a = dx * dx + dy * dy, e = ex * ex + ey * ey, f = ex * rx + ey * ry;
    f32 sn, tn, cx, cy;
    if (a < 1e-6f && e < 1e-6f) {
        sn = tn = 0.0f;
    } else if (a < 1e-6f) {
        sn = 0.0f;
        tn = f / e;
    } else {
        f32 c = dx * rx + dy * ry;
        if (e < 1e-6f) {
            tn = 0.0f;
            sn = -c / a;
        } else {
            f32 b = dx * ex + dy * ey, den = a * e - b * b;
            sn = den > 1e-6f ? (b * f - c * e) / den : 0.0f;
            if (sn < 0.0f) {
                sn = 0.0f;
            } else if (sn > 1.0f) {
                sn = 1.0f;
            }
            tn = (b * sn + f) / e;
        }
    }
    if (tn < 0.0f) {
        tn = 0.0f;
        sn = a > 1e-6f ? -(dx * rx + dy * ry) / a : 0.0f;
    } else if (tn > 1.0f) {
        tn = 1.0f;
        sn = a > 1e-6f ? (dx * ex + dy * ey - (dx * rx + dy * ry)) / a : 0.0f;
    }
    if (sn < 0.0f) {
        sn = 0.0f;
    } else if (sn > 1.0f) {
        sn = 1.0f;
    }
    cx = rx + dx * sn - ex * tn;
    cy = ry + dy * sn - ey * tn;
    return cx * cx + cy * cy;
}

static int is_zako(int kind)
{
    return (kind >= It_Kind_Kuriboh && kind < It_Kind_Octarock_Stone) || kind == It_Kind_Nokonoko ||
           kind == It_Kind_Patapata;
}

/* DIR_STARCONTACT: SMRPG's star run. An enemy touching a starred fighter takes a hit from him, set up as the item
 * collision's fighter case sets it (it_802706D0: the source, the direction away from him, the angle, the knockback and the
 * damage), before this frame's hit think (Item_8026A294, proc 14) hands it to the enemy's own damage callback. */
static void star_contact_update(int s)
{
    int port, k, j, n;
    HSD_GObj* ig;
    for (port = 0; port < dir_setup.nplayers; port++) {
        Fighter* fp = fighter(port);
        if (fp == NULL || !fp->x221D_b6 || fp->motion_id <= 13) {
            continue;
        }
        for (ig = HSD_GObjPLinkHead[HSD_GOBJ_PLINK_ITEM]; ig != NULL; ig = ig->next) {
            Item* ip = (Item*) ig->user_data;
            int touch = 0;
            if (ip == NULL || !is_zako((int) ip->kind)) {
                continue;
            }
            for (j = 0; j < star_nhit; j++) {
                if (star_hit[j] == ig) {
                    break;
                }
            }
            if (j < star_nhit) {
                continue;
            }
            n = ip->xAC8_hurtboxNum < 2 ? ip->xAC8_hurtboxNum : 2;
            for (k = 0; k < fp->hurt_capsules_len && !touch; k++) {
                HurtCapsule* h = &fp->hurt_capsules[k].capsule;
                if (n == 0) {
                    Vec3 c = ip->pos;
                    f32 r = h->scale + 4.0f;
                    c.y += 4.0f;
                    touch = seg_dist2(&h->a_pos, &h->b_pos, &c, &c) < r * r;
                }
                for (j = 0; j < n && !touch; j++) {
                    /* the item's capsule from its bone now: its stored a_pos/b_pos are only refreshed inside the game's
                     * own collision checks (skip_update_pos), so they can be stale */
                    HurtCapsule* ih = &ip->xACC_itemHurtbox[j];
                    f32 r = h->scale + ih->scale;
                    Vec3 ia, ib;
                    if (ih->bone == NULL) {
                        continue;
                    }
                    lb_8000B1CC(ih->bone, &ih->a_offset, &ia);
                    lb_8000B1CC(ih->bone, &ih->b_offset, &ib);
                    touch = seg_dist2(&h->a_pos, &h->b_pos, &ia, &ib) < r * r;
                }
            }
            if (!touch) {
                continue;
            }
            ip->xCB0_source_ply = port;
            ip->xCEC_fighterGObj = Player_GetEntity(port);
            ip->xCF0_itemGObj = NULL;
            ip->xCCC_incDamageDirection = ip->pos.x > fp->cur_pos.x ? -1.0f : 1.0f;
            ip->xCAC_angle = (s32) star_angle;
            ip->xCC8_knockback = star_kb;
            ip->xCC4 = 0;
            ip->xCA0 += 20;
            if (ip->xCA4 < 20) {
                ip->xCA4 = 20;
            }
            if (star_nhit < 16) {
                star_hit[star_nhit++] = ig;
            }
            OSReport("STARHIT %d %d %d %.2f %.2f fighter %.2f %.2f\n", s, port, (int) ip->kind, ip->pos.x, ip->pos.y,
                     fp->cur_pos.x, fp->cur_pos.y);
        }
    }
}

/* DIR_BILL's trace: the castle's Bill flights (map gobjs 8-16), the explosion (1) and gobj 2, where they are */
static void bill_trace(int s)
{
    static const int ids[] = { 1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 16 };
    int i;
    if (stage_info.grkind != Gr_Kind_Castle) {
        return;
    }
    for (i = 0; i < (int) (sizeof(ids) / sizeof(ids[0])); i++) {
        HSD_GObj* g = Ground_GetMapGObj(ids[i]);
        if (g != NULL) {
            HSD_JObj* j = Ground_801C3FA4(g, 0);
            Vec3 p;
            if (j != NULL) {
                lb_8000B1CC(j, NULL, &p);
                OSReport("BILLPOS %d %d %.2f %.2f %.2f\n", s, ids[i], p.x, p.y, p.z);
            }
        }
    }
}

/* DIR_REACT: the pad is read later this frame, so a press written now lands on the first frame the state allows it */
static void react_update(int s)
{
    int k;
    for (k = 0; k < REACT_SLOTS; k++) {
        int port = react_port[k];
        Fighter* fp;
        HSD_PadStatus* ps;
        if (react_until[k] < 0 && react_hold[k] == 0) {
            continue;
        }
        fp = fighter(port);
        ps = &HSD_PadGameStatus[port];
        if (fp == NULL) {
            continue;
        }
        if (react_until[k] > s && fp->motion_id == react_state[k] && react_prev[k] != react_state[k]) {
            react_until[k] = -1;
            react_hold[k] = 2;
            OSReport("REACT %d %d %d %.2f\n", s, port, fp->motion_id, fp->cur_anim_frame);
        } else if (react_until[k] >= 0 && react_until[k] <= s) {
            react_until[k] = -1; /* expired unfired */
        }
        react_prev[k] = fp->motion_id;
        if (react_hold[k] > 0) {
            int d = react_dir[k];
            s8 sx = 0, sy = 0;
            if (d == 1) {
                sy = 80;
            } else if (d == 2) {
                sy = -80;
            } else if (d == 3 || d == 4) {
                sx = (s8) ((d == 3 ? 80.0f : -80.0f) * fp->facing_dir);
            }
            if (react_hold[k] == 2) {
                ps->trigger |= react_btn[k] & ~ps->last_button;
            }
            ps->button |= react_btn[k];
            if (d != 0) {
                ps->stickX = sx;
                ps->stickY = sy;
                ps->nml_stickX = sx / 80.0f;
                ps->nml_stickY = sy / 80.0f;
            }
            react_hold[k]--;
        }
    }
}

/* a floor line within 10 of y = 0 under x */
static int floor_under(f32 x)
{
    Vec3 hit, nrm;
    int line = -1;
    u32 flags = 0;
    return mpCheckFloor(x, 10.0f, x, -10.0f, 0.0f, &hit, &line, &flags, &nrm, -1, -1, -1, NULL, NULL) != 0;
}

static void run_cue(const DirCue* c)
{
    /* DIR_ENEMY packs more than a port into it; ports 4 and 5 are the fifth and sixth fighters (DirSetup.fifth, sixth) for
     * the cues that only place or set a fighter or play an animation (the rest keep per-port state for ports 0-3) */
    Fighter* fp = c->port < 4 ? fighter(c->port)
                              : (DIR_EXTRA(c->port) &&
                                 (c->kind == DIR_SETPOS || c->kind == DIR_FACE || c->kind == DIR_MOTION ||
                                  c->kind == DIR_PERCENT || c->kind == DIR_RESET || c->kind == DIR_STATUS ||
                                  c->kind == DIR_STARKO || c->kind == DIR_METAL || c->kind == DIR_ANIMRATE ||
                                  c->kind == DIR_COLANIM || c->kind == DIR_ANIM || c->kind == DIR_PLACE ||
                                  c->kind == DIR_EYES)
                                     ? fighter(4)
                                     : NULL);
    Vec3 p;
    SpawnItem spawn;
    switch (c->kind) {
    case DIR_FREEZE:
        frozen = c->a != 0.0f;
        if (c->a != 0.0f) {
            gm_SetDbPauseFlag(1);
        } else {
            gm_ClearDbPauseFlag(1);
        }
        break;
    case DIR_GAMECAM:
        game_cam = c->a != 0.0f;
        if (game_cam) {
            Camera_800300F0(); /* back to the mode the director's debug free camera replaced */
        } else {
            Camera_8003006C();
        }
        break;
    case DIR_GLASS:
        glass_sync = c->a != 0.0f;
        break;
    case DIR_STAGE:
        Camera_SetStageVisible(c->a != 0.0f);
        break;
    case DIR_BGCOLOR:
        Camera_SetBackgroundColor((u8) c->a, (u8) c->b, (u8) c->c);
        break;
    case DIR_SETPOS:
        p.x = c->a;
        p.y = c->b;
        p.z = 0.0f;
        ftLib_SetPos(Player_GetEntity(c->port), &p);
        if (fp != NULL) {
            /* a teleport: collision sweeps from the previous positions, so a jump across the stage's edge pushed the
             * fighter back onto it; start every sweep here, with no momentum */
            fp->prev_pos = p;
            fp->coll_data.cur_pos = p;
            fp->coll_data.prev_pos = p;
            fp->coll_data.last_pos = p;
            fp->self_vel.x = fp->self_vel.y = 0.0f;
        }
        break;
    case DIR_FACE:
        if (fp != NULL) {
            fp->facing_dir = c->a;
        }
        break;
    case DIR_MOTION:
        Fighter_ChangeMotionState(Player_GetEntity(c->port), (FtMotionId) c->a, 0, c->b, 1.0f, 0.0f, NULL);
        break;
    case DIR_PERCENT:
        ftLib_SetPercent(Player_GetEntity(c->port), (s32) c->a);
        /* the player's damage too: the HUD reads the player slot's copy (Player_GetDamage), so with the fighter's
         * alone a stock match's HUD kept its old number until the next hit (geno-film1, geno-film2) */
        Player_SetHUDDamage(c->port, (s32) c->a);
        break;
    case DIR_MARK:
        OSReport("MARK %d %d\n", c->frame, (int) c->a);
        break;
    case DIR_END:
        s_end = c->frame;
        break;
    case DIR_APPROACH:
        ap_range[c->port] = c->a;
        ap_until[c->port] = (int) c->b;
        ap_stick[c->port] = (s8) c->c;
        break;
    case DIR_AUTO:
        auto_flags[c->port] = (u8) c->a;
        break;
    case DIR_TRACE:
        trace_until[c->port] = (int) c->a;
        break;
    case DIR_STATUS:
        if (fp != NULL) {
            OSReport("STATUS %d %d %.1f %.2f %.2f %d\n", F - DIR_SLATE, c->port, fp->dmg.x1830_percent, fp->cur_pos.x,
                     fp->cur_pos.y, fp->motion_id);
        }
        break;
    case DIR_SHIELD:
        if (fp != NULL) {
            /* the guard's collision shield is a unit sphere on ThrowN (the lookup table's byte 0x11), so its world radius is
             * the joint matrix's scale; hurtbox radii are world units times the fighter's scale */
            MtxPtr m = HSD_JObjGetMtxPtr(fp->parts[fp->ft_data->x8->x11].joint);
            float sc = sqrtf(m[0][0] * m[0][0] + m[1][0] * m[1][0] + m[2][0] * m[2][0]);
            int k;
            OSReport("SHIELD %d %d motion %d health %.1f centre %.2f %.2f %.2f radius %.2f scale %.3f pos %.2f %.2f\n",
                     F - DIR_SLATE, c->port, fp->motion_id, fp->shield_health, m[0][3], m[1][3], m[2][3], sc,
                     fp->x34_scale.y, fp->cur_pos.x, fp->cur_pos.y);
            for (k = 0; k < fp->hurt_capsules_len; k++) {
                HurtCapsule* h = &fp->hurt_capsules[k].capsule;
                OSReport("HURT %d %d %d %.2f %.2f %.2f %.2f %.2f %.2f %.2f\n", F - DIR_SLATE, c->port, k, h->a_pos.x,
                         h->a_pos.y, h->a_pos.z, h->b_pos.x, h->b_pos.y, h->b_pos.z, h->scale);
            }
        }
        break;
    case DIR_FEET:
        if (fp != NULL) {
            int side;
            for (side = 0; side < 2; side++) {
                int j = side == 0 ? fp->ft_data->x8->x13 : fp->ft_data->x8->x14;
                MtxPtr m = HSD_JObjGetMtxPtr(fp->parts[j].joint);
                OSReport("FEET %d %d %d %.3f %.3f %.3f %.4f %.4f %.4f %.4f %.4f %.4f %d %.3f\n", F - DIR_SLATE, c->port, side,
                         m[0][3], m[1][3], m[2][3], m[0][0], m[1][0], m[2][0], m[0][1], m[1][1], m[2][1], fp->motion_id,
                         fp->cur_anim_frame);
            }
        }
        break;
    case DIR_SHIELDHP:
        if (fp != NULL) {
            fp->shield_health = c->a;
        }
        break;
    case DIR_ITEM:
        /* the game's own drop (itdrop.c): an item at rest where it lands, facing the stage's centre */
        memset(&spawn, 0, sizeof(spawn));
        spawn.kind = (ItemKind) c->a;
        spawn.prev_pos.x = c->b;
        spawn.prev_pos.y = c->c;
        spawn.prev_pos.z = 0.0f;
        spawn.pos = spawn.prev_pos;
        spawn.facing_dir = it_8026B684(&spawn.prev_pos);
        spawn.x44_flag.b0 = 1;
        OSReport("ITEM %d kind %d at %.1f %.1f %s\n", F - DIR_SLATE, (int) c->a, c->b, c->c,
                 Item_80268B18(&spawn) != NULL ? "ok" : "failed");
        break;
    case DIR_ANIM:
        if (fp != NULL) {
            ftCo_8008A6D8(Player_GetEntity(c->port), (s32) c->a);
            OSReport("ANIM %d %d entry %d state %d\n", F - DIR_SLATE, c->port, (int) c->a, fp->motion_id);
        }
        break;
    case DIR_SFX:
        OSReport("SFX %d id %d voice %d\n", F - DIR_SLATE, (int) c->a,
                 lbAudioAx_800237A8((int) c->a, c->b > 0.0f ? (int) c->b : 0x7F, 0x40));
        break;
    case DIR_SHOOT:
        if (fp != NULL) {
            int packed = (int) c->a;
            int kind = (packed & 4095) >> 4, state = packed & 15;
            f32 speed = (f32) (packed >> 12) / 10.0f;
            p = fp->cur_pos;
            p.x += fp->facing_dir * c->b;
            p.y += c->c;
            p.z = 0.0f;
            it_8029C504(Player_GetEntity(c->port), &p, state, kind, fp->facing_dir < 0.0f ? 3.14159265f : 0.0f, speed);
            OSReport("SHOOT %d %d kind %d state %d %.2f %.2f %.1f\n", F - DIR_SLATE, c->port, kind, state, p.x, p.y, speed);
        }
        break;
    case DIR_STALL: {
        OSTime t0 = OSGetTime();
        while (OSTicksToMilliseconds(OSGetTime() - t0) < (OSTime) c->a) {
        }
        OSReport("STALL %d %d\n", F - DIR_SLATE, (int) c->a);
        break;
    }
    case DIR_PERF:
        perf_log = c->a != 0.0f;
        break;
    case DIR_FOODVAR: {
        /* a: the variant (index into the Food article's own table, itFoodsAttributes: [0].x0 is the count). The newest live
         * Food (It_Kind_Foods) takes that variant: its model (it_80273318 with the variant's joint), its heal and its
         * index, as itFoods_Logic18_Spawned sets them from its random pick */
        HSD_GObj* ig;
        HSD_GObj* food = NULL;
        for (ig = HSD_GObjPLinkHead[HSD_GOBJ_PLINK_ITEM]; ig != NULL; ig = ig->next) {
            if (((Item*) ig->user_data)->kind == It_Kind_Foods) {
                food = ig;
            }
        }
        if (food != NULL) {
            Item* ip = (Item*) food->user_data;
            itFoodsAttributes* attr = ip->xC4_article_data->x4_specialAttributes;
            int n = attr[0].x0, v = (int) c->a;
            if (v >= 0 && v < n) {
                ip->xDD4_itemVar.foods.heal_amount = attr[v].x8;
                ip->xDD4_itemVar.foods.x0 = v;
                it_80273318(food, attr[v].x4);
            }
            OSReport("FOODVAR %d variant %d of %d heal %d\n", F - DIR_SLATE, v, n, (int) attr[v < n && v >= 0 ? v : 0].x8);
        } else {
            OSReport("FOODVAR %d no food\n", F - DIR_SLATE);
        }
        break;
    }
    case DIR_HUDWIDE: {
        /* the HUD's own cameras (the interface's scene cameras, gobj p-link 0x14) take the film's projection aspect, so
         * a widescreen film's HUD keeps its shape: drawn into the middle of the frame as on a 4:3 screen, pillarboxed,
         * where the film's stretch to 16:9 would widen it by aspect / aspect0 */
        HSD_GObj* g;
        HSD_GObj* main = Camera_80030A50();
        int n = 0;
        if (dir_setup.aspect > 0.0f && aspect0 > 0.0f) {
            for (g = HSD_GObjPLinkHead[0x14]; g != NULL; g = g->next) {
                if (g != main && g->obj_kind == HSD_GObj_CameraKind && g->hsd_obj != NULL) {
                    HSD_CObj* co = GET_COBJ(g);
                    f32 a0 = HSD_CObjGetAspect(co);
                    HSD_CObjSetAspect(co, a0 * dir_setup.aspect / aspect0);
                    OSReport("HUDWIDE %d cobj prio %d aspect %.4f -> %.4f\n", F - DIR_SLATE, (int) g->gxlink_prios,
                             a0, a0 * dir_setup.aspect / aspect0);
                    n++;
                }
            }
        }
        OSReport("HUDWIDE %d n %d\n", F - DIR_SLATE, n);
        break;
    }
    case DIR_STARKO:
        if (fp != NULL && fp->motion_id > 13) {
            ftCo_800D40B8(Player_GetEntity(c->port));
            OSReport("STARKO %d %d %.2f %.2f\n", F - DIR_SLATE, c->port, fp->cur_pos.x, fp->cur_pos.y);
        } else {
            OSReport("STARKO SKIPPED %d %d\n", F - DIR_SLATE, c->port);
        }
        break;
    case DIR_SLOW:
        slow_n = (int) c->a;
        if (slow_n <= 1 && !frozen) {
            gm_ClearDbPauseFlag(1);
        }
        OSReport("SLOW %d %d\n", F - DIR_SLATE, slow_n);
        break;
    case DIR_METAL:
        if (fp != NULL) {
            if (c->a != 0.0f) {
                ftCo_800C8348(Player_GetEntity(c->port), 0x7FFFFFFF, 1000);
            } else {
                ftCo_800C8540(Player_GetEntity(c->port));
            }
            OSReport("METAL %d %d %d\n", F - DIR_SLATE, c->port, (int) c->a);
        }
        break;
    case DIR_ANIMRATE:
        if (fp != NULL) {
            ftAnim_SetAnimRate(Player_GetEntity(c->port), c->a);
        }
        break;
    case DIR_COLANIM:
        if (fp != NULL) {
            if (c->a < 0.0f) {
                ftCo_800C0200(fp, ftCo_800C0694(fp));
            } else {
                ftCo_800BFFD0(fp, (int) c->a, 0);
            }
            OSReport("COLANIM %d %d %d\n", F - DIR_SLATE, c->port, (int) c->a);
        }
        break;
    case DIR_ENTRY:
        if (fp != NULL && fp->motion_id > 13) {
            ftCo_800C61B0(Player_GetEntity(c->port));
            OSReport("ENTRY %d %d\n", F - DIR_SLATE, c->port);
        }
        break;
    case DIR_ENEMY: {
        Item_GObj* ig = NULL;
        int kind = (int) c->a;
        int rel = (c->port >> 4) - 1; /* the port packs the variant (low 4 bits) and a fighter to spawn relative to */
        Fighter* rf = rel >= 0 ? fighter(rel) : NULL;
        p.x = c->b + (rf != NULL ? rf->cur_pos.x : 0.0f);
        p.y = c->c + (rf != NULL ? rf->cur_pos.y : 0.0f);
        p.z = 0.0f;
        if (kind == It_Kind_Nokonoko) {
            ig = it_802DD7F0(c->port & 15, &p, NULL, p.x > 0.0f ? -1 : 1);
        } else if (kind == It_Kind_Patapata) {
            ig = it_802E16F8(c->port & 15, &p, p.x > 0.0f ? -1 : 1);
        } else {
            ig = it_8027B5B0((ItemKind) kind, &p, NULL, NULL, 1);
        }
        OSReport("ENEMY %d kind %d variant %d at %.1f %.1f %s\n", F - DIR_SLATE, kind, c->port & 15, p.x, p.y,
                 ig != NULL ? "ok" : "failed");
        break;
    }
    case DIR_RESPAWN:
        if (fp != NULL && fp->motion_id > 13) {
            Vec3 at = fp->cur_pos;
            f32 face = fp->facing_dir;
            Fighter* nf;
            Player_80031EBC(c->port);
            Player_SetCostumeId(c->port, (int) c->a);
            Player_80031AD0(c->port);
            Player_80031848(c->port); /* the input link (ftLib_EnableInput), as the game's own mid-match spawn does
                                       * (gm_8016EDDC): without it the new fighter ignores its pad */
            nf = fighter(c->port);
            if (nf != NULL) {
                at.y = 0.0f;
                ftLib_SetPos(Player_GetEntity(c->port), &at);
                nf->facing_dir = face;
                last_msid[c->port] = -1;
            }
            OSReport("RESPAWN %d %d costume %d %s\n", F - DIR_SLATE, c->port, (int) c->a, nf != NULL ? "ok" : "failed");
        }
        break;
    case DIR_HUD:
        if (c->a == 0.0f) {
            ifAll_HideHUD();
        } else {
            ifAll_ShowHUD();
            if (c->a == 1.0f) { /* ifAll_802F3394's hides but the name tags' (un_802FD450) */
                ifStatus_802F6898();
                ifTime_HideTimers();
                ifMagnify_802FC8E8();
                un_802FD668();
                un_802FD910();
                un_802FF570();
            } else if (c->a == 3.0f) {
                ifMagnify_802FC8E8(); /* every player's magnifier ignores going off-screen */
            }
        }
        OSReport("HUD %d %d\n", F - DIR_SLATE, (int) c->a);
        break;
    case DIR_ITEMPIN: {
        HSD_GObj* ig;
        int add = c->b != 0.0f; /* b = 1 (geno-film2): pin the items not pinned yet, in mode a, keeping the others' pins */
        if (!add) {
            pin_n = 0;
        }
        pin_mode = (int) c->a;
        if (c->a != 0.0f) {
            for (ig = HSD_GObjPLinkHead[HSD_GOBJ_PLINK_ITEM]; ig != NULL && pin_n < 16; ig = ig->next) {
                Item* ip = (Item*) ig->user_data;
                int k, have = 0;
                if (c->c != 0.0f && (int) ip->kind != (int) c->c) {
                    continue; /* c: only this ::ItemKind (Mushroom Kingdom's bricks are items too, and filled the list) */
                }
                for (k = 0; k < pin_n; k++) {
                    if (pin_g[k] == ig) {
                        have = 1;
                    }
                }
                if (have) {
                    continue;
                }
                /* through a local index, and logged: written as pin_x[pin_n] in this switch, only the first item's x was
                 * stored (the camera pass, 2026-10-02: 6.3's Goombas after the first were all pinned at x 0, stacked, and
                 * KO'd on one frame); a call in between (the log) or a local index stores every one */
                k = pin_n;
                pin_g[k] = ig;
                pin_x[k] = ip->pos.x;
                pin_y[k] = ip->pos.y;
                pin_dmg[k] = ip->xC9C;
                pin_m[k] = pin_mode;
                pin_n = k + 1;
                OSReport("PINNED %d %d %d %.2f %.2f %d\n", F - DIR_SLATE, k, (int) ip->kind, pin_x[k], pin_y[k], pin_mode);
            }
        }
        OSReport("PIN %d %d\n", F - DIR_SLATE, pin_n);
        break;
    }
    case DIR_ITEMCLEAR: {
        HSD_GObj* ig = HSD_GObjPLinkHead[HSD_GOBJ_PLINK_ITEM];
        int k = 0;
        pin_n = 0;
        while (ig != NULL) {
            HSD_GObj* next = ig->next;
            Item* ip = (Item*) ig->user_data;
            if (ip != NULL && ip->owner == NULL) {
                Item_8026A8EC((Item_GObj*) ig);
                k++;
            }
            ig = next;
        }
        OSReport("ITEMCLEAR %d %d\n", F - DIR_SLATE, k);
        break;
    }
    case DIR_EFCLEAR:
        if (fp != NULL) {
            efLib_DestroyAll(Player_GetEntity(c->port));
            OSReport("EFCLEAR %d %d\n", F - DIR_SLATE, c->port);
        }
        break;
    case DIR_ITEMTRACE:
        itrace_until = (int) c->a;
        break;
    case DIR_ITEMVEL: {
        HSD_GObj* ig;
        Item* last = NULL;
        for (ig = HSD_GObjPLinkHead[HSD_GOBJ_PLINK_ITEM]; ig != NULL; ig = ig->next) {
            last = (Item*) ig->user_data;
        }
        if (last != NULL) {
            last->x40_vel.x = c->a;
            last->x40_vel.y = c->b;
            OSReport("ITEMVEL %d kind %d %.2f %.2f\n", F - DIR_SLATE, (int) last->kind, c->a, c->b);
        }
        break;
    }
    case DIR_ITEMS: {
        HSD_GObj* ig;
        for (ig = HSD_GObjPLinkHead[HSD_GOBJ_PLINK_ITEM]; ig != NULL; ig = ig->next) {
            Item* ip = (Item*) ig->user_data;
            OSReport("ITEMS %d kind %d %.2f %.2f\n", F - DIR_SLATE, (int) ip->kind, ip->pos.x, ip->pos.y);
        }
        break;
    }
    case DIR_GRDUMP: {
        MapCollData* cd = mpLib_8004D164();
        CollLine* ln = mpGetGroundCollLine();
        CollVtx* vx = mpGetGroundCollVtx();
        int k;
        OSReport("STAGE %d grkind %d stkind %d blast %.3f %.3f %.3f %.3f cam %.3f %.3f %.3f %.3f offset %.3f %.3f\n",
                 F - DIR_SLATE, (int) stage_info.grkind, (int) Stage_80225194(), Stage_GetBlastZoneLeftOffset(),
                 Stage_GetBlastZoneRightOffset(), Stage_GetBlastZoneTopOffset(), Stage_GetBlastZoneBottomOffset(),
                 Stage_GetCamBoundsLeftOffset(), Stage_GetCamBoundsRightOffset(), Stage_GetCamBoundsTopOffset(),
                 Stage_GetCamBoundsBottomOffset(), stage_info.cam_info.cam_x_offset, stage_info.cam_info.cam_y_offset);
        if (cd != NULL && ln != NULL && vx != NULL) {
            for (k = 0; k < cd->line_count; k++) {
                MapLine* m = ln[k].x0;
                if (m == NULL || (c->a == 0 && (ln[k].flags & LINE_FLAG_KIND) != 1)) {
                    continue;
                }
                OSReport("LINE %d %d %X %X %.3f %.3f %.3f %.3f\n", F - DIR_SLATE, k, (unsigned) ln[k].flags,
                         (unsigned) m->lo_flags, vx[m->v0_idx].pos.x, vx[m->v0_idx].pos.y, vx[m->v1_idx].pos.x,
                         vx[m->v1_idx].pos.y);
            }
        }
        for (k = 0; k < dir_setup.nplayers; k++) {
            Fighter* fk = fighter(k);
            if (fk != NULL) {
                /* the ledge line held, in the cliff states (CliffCatch 252 .. CliffJumpQuick2 263) */
                int ledge = (fk->motion_id >= 252 && fk->motion_id <= 263) ? (int) fk->mv.co.cliff.ledge_id : -1;
                OSReport("GROUND %d %d %.3f %.3f %d %d %d %d\n", F - DIR_SLATE, k, fk->cur_pos.x, fk->cur_pos.y,
                         (int) fk->ground_or_air, (int) fk->coll_data.floor.index, fk->motion_id, ledge);
            }
        }
        break;
    }
    case DIR_PLACE:
        if (fp != NULL && fp->motion_id > 13) {
            Vec3 hit, nrm;
            int line = -1;
            u32 flags = 0;
            HSD_GObj* g = Player_GetEntity(c->port);
            if (mpCheckFloor(c->a, c->b + 10.0f, c->a, c->b - 10.0f, 0.0f, &hit, &line, &flags, &nrm, -1, -1, -1, NULL,
                             NULL))
            {
                p.x = c->a;
                p.y = hit.y;
                p.z = 0.0f;
                ftLib_SetPos(g, &p);
                fp->prev_pos = p;
                fp->coll_data.cur_pos = p;
                fp->coll_data.prev_pos = p;
                fp->coll_data.last_pos = p;
                fp->coll_data.floor.index = line;
                fp->coll_data.floor.flags = flags;
                fp->coll_data.floor.normal = nrm;
                fp->self_vel.x = fp->self_vel.y = fp->self_vel.z = 0.0f;
                fp->x8c_kb_vel.x = fp->x8c_kb_vel.y = fp->x8c_kb_vel.z = 0.0f;
                fp->gr_vel = 0.0f;
                fp->xF0_ground_kb_vel = 0.0f;
                fp->facing_dir = c->c;
                plStale_ResetStaleMoveTableForPlayer(c->port);
                if (fp->ground_or_air == GA_Air) {
                    ftCommon_8007D7FC(fp);
                }
                ft_8008A2BC(g);
                OSReport("PLACE %d %d %.2f %.2f %d\n", F - DIR_SLATE, c->port, p.x, p.y, line);
            } else {
                OSReport("PLACE %d %d %.2f %.2f -1\n", F - DIR_SLATE, c->port, c->a, c->b);
            }
        }
        break;
    case DIR_STARCONTACT:
        star_contact = c->a != 0.0f;
        star_kb = c->b > 0.0f ? c->b : 120.0f;
        star_angle = c->c > 0.0f ? c->c : 70.0f;
        star_nhit = 0;
        OSReport("STARCONTACT %d %d %.0f %.0f\n", F - DIR_SLATE, star_contact, star_kb, star_angle);
        break;
    case DIR_BILL:
        OSReport("BILL %d %d %d\n", F - DIR_SLATE, (int) c->a, grCastle_DirectorBill((int) c->a));
        if (c->b > 0.0f) {
            bill_until = (int) c->b;
        }
        break;
    case DIR_REACT:
        if (c->port < 4) {
            Fighter* rf = fighter(c->port);
            int packed = (int) c->b, k;
            for (k = 0; k < REACT_SLOTS && (react_until[k] >= 0 || react_hold[k] > 0); k++) {
            }
            if (k < REACT_SLOTS) {
                react_port[k] = c->port;
                react_state[k] = (s32) c->a;
                react_btn[k] = (u32) (packed & 4095);
                react_dir[k] = packed >> 12;
                react_until[k] = (int) c->c;
                react_prev[k] = rf != NULL ? rf->motion_id : -1;
            } else {
                OSReport("REACT FULL %d %d\n", F - DIR_SLATE, c->port);
            }
        }
        break;
    case DIR_KBVEL:
        if (fp != NULL) {
            fp->x8c_kb_vel.x = c->a;
            fp->x8c_kb_vel.y = c->b;
            fp->x8c_kb_vel.z = 0.0f;
            OSReport("KBVEL %d %d %.2f %.2f\n", F - DIR_SLATE, c->port, c->a, c->b);
        }
        break;
    case DIR_HOLDENTRY:
        if (fp != NULL) {
            hold_entry[c->port] = c->a == 0.0f ? -1 : (fp->motion_id == 324 ? fp->mv.co.entry.timer : 30);
            OSReport("HOLDENTRY %d %d %d state %d\n", F - DIR_SLATE, c->port, hold_entry[c->port], fp->motion_id);
        }
        break;
    case DIR_EYES:
        if (fp != NULL) {
            /* the plain setter, not ftAnim_800704F0: that one flags the fighter so its next action change resets the
             * eyes to open (a one-frame blink at every change of state); these hold until a script sets the eyes */
            ftAnim_80070458(fp, &fp->tobj_list, 0, c->a);
            ftAnim_80070458(fp, &fp->tobj_list, 1, c->a);
            OSReport("EYES %d %d %d\n", F - DIR_SLATE, c->port, (int) c->a);
        }
        break;
    case DIR_HOLDDEAD:
        if (c->port < 4) {
            hold_dead[c->port] = c->a != 0.0f;
            OSReport("HOLDDEAD %d %d %d\n", F - DIR_SLATE, c->port, hold_dead[c->port]);
        }
        break;
    case DIR_RNGLOCK:
        rng_lock = (s32) c->a;
        OSReport("RNGLOCK %d %d\n", F - DIR_SLATE, rng_lock);
        break;
    case DIR_BONE:
        if (c->port < 4) {
            bone_part[c->port] = (int) c->a;
            bone_until[c->port] = (int) c->b;
        }
        break;
    case DIR_RESET:
        if (fp != NULL && fp->motion_id <= 13) {
            /* dead (0-11) or on the respawn platform (Rebirth, RebirthWait): forcing them onto the ground asserts
             * ("fighter ground no under Id") and freezes the game, so skip and say so */
            OSReport("RESET SKIPPED %d %d state %d\n", F - DIR_SLATE, c->port, fp->motion_id);
        } else if (fp != NULL && !floor_under(c->a)) {
            /* no floor within 10 of y = 0 under x: grounding him there asserted "fighter ground no under" and froze the
             * game (geno-film2, Hyrule Temple); skip and say so (DIR_PLACE stands a fighter on a floor at any height) */
            OSReport("RESET NOFLOOR SKIPPED %d %d %.2f\n", F - DIR_SLATE, c->port, c->a);
        } else if (fp != NULL) {
            HSD_GObj* g = Player_GetEntity(c->port);
            p.x = c->a;
            p.y = 0.0f;
            p.z = 0.0f;
            ftLib_SetPos(g, &p);
            fp->prev_pos = p;
            /* restart the collision sweep here too, as DIR_SETPOS does: collision sweeps from the previous positions, so a
             * reset from under a ledge (hanging on it) swept into the stage and dropped the fighter back below it (Geno),
             * and a reset from far offstage swept him back across the stage onto the far ledge (SO BACK) */
            fp->coll_data.cur_pos = p;
            fp->coll_data.prev_pos = p;
            fp->coll_data.last_pos = p;
            fp->self_vel.x = fp->self_vel.y = fp->self_vel.z = 0.0f;
            fp->x8c_kb_vel.x = fp->x8c_kb_vel.y = fp->x8c_kb_vel.z = 0.0f;
            fp->gr_vel = 0.0f;
            fp->xF0_ground_kb_vel = 0.0f;
            fp->facing_dir = c->b;
            if (c->c != 0.0f) { /* c = 1: fresh moves (a lab repeats one, and staling weakens it). dsl reset() sends it
                                 * by default on the Geno line; reset(..., fresh=False) keeps the game's staling (FRAME
                                 * PERFECT's damage was captured with it) */
                plStale_ResetStaleMoveTableForPlayer(c->port);
            }
            if (fp->x1990 != 0 || fp->x1994 != 0) { /* respawn invincibility (and its flashing) would carry into the test */
                fp->x1990 = fp->x1994 = 0;
                fp->x198C = 0;
                if (ftCo_800C0694(fp) == 9) {
                    ftCo_800C0200(fp, 9);
                }
            }
            {
                /* link him to the floor under x, as DIR_PLACE does: the floor line he was on can be another one (a
                 * grounded fighter follows his line, so a reset from the Forest Maze's mushroom cap to y = 0 put him
                 * straight back on the cap), or stale or unset (just off the respawn platform: grounding him asserted
                 * "fighter ground no under") */
                Vec3 hit, nrm;
                int line = -1;
                u32 flags = 0;
                if (mpCheckFloor(c->a, 10.0f, c->a, -10.0f, 0.0f, &hit, &line, &flags, &nrm, -1, -1, -1, NULL, NULL)) {
                    fp->coll_data.floor.index = line;
                    fp->coll_data.floor.flags = flags;
                    fp->coll_data.floor.normal = nrm;
                } else {
                    OSReport("RESET NOFLOOR %d %d %.2f\n", F - DIR_SLATE, c->port, c->a);
                }
            }
            if (fp->ground_or_air == GA_Air) {
                ftCommon_8007D7FC(fp);
            }
            ft_8008A2BC(g);
        }
        break;
    }
}

void director_on_hit(Fighter_GObj* attacker, Fighter_GObj* victim, float dmg)
{
    Fighter* a = GET_FIGHTER(attacker);
    Fighter* v = GET_FIGHTER(victim);
    OSReport("HIT %d %d %d %.1f %d\n", F - DIR_SLATE, a->player_idx, v->player_idx, dmg, a->x2070.x2073);
}

void director_on_item_hit(HSD_GObj* item, Fighter_GObj* victim, float dmg)
{
    Fighter* v = GET_FIGHTER(victim);
    Item* ip = (Item*) item->user_data;
    int owner = -1;
    /* appended (geno-film2): the item's kind and its owner's player slot (-1: none or not a fighter), so a shot can tell
     * a Whirl from a laser or a stage car */
    if (ip->owner != NULL && HSD_GObjGetClassifier(ip->owner) == HSD_GOBJ_CLASS_FIGHTER) {
        owner = GET_FIGHTER(ip->owner)->player_idx;
    }
    OSReport("IHIT %d %d %.1f %d %d\n", F - DIR_SLATE, v->player_idx, dmg, (int) ip->kind, owner);
}

void director_on_laser(HSD_GObj* parent, Vec3* pos, int kind, float angle, float speed)
{
    Fighter* fp = GET_FIGHTER(parent);
    (void) kind;
    OSReport("LASER %d %d %.2f %.2f %.3f %.2f\n", F - DIR_SLATE, fp->player_idx, pos->x, pos->y, angle, speed);
}

void director_on_lag(int n)
{
    OSReport("LAGFRAME %d %d\n", F - DIR_SLATE, n);
}
