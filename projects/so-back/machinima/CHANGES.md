# Changes to the pinned kit (director, dsl, build)

The kit is shared by every capture lane, so each change must be additive. Log each change here as a date, the lane,
the change and why.

## 2026-09-27, lane 1 (sacred combo)
- **dolphin.py: `[Hacks] ImmediateXFBEnable = True`.** Every capture now has exactly `len` frames between the slates;
  without it, script frame 7 was lost on every run. Dumps are the XFB: 640x480 × res, square pixels.
- **director.c, `POS` trace lines (DIR_TRACE): extra fields appended.** After the old five fields: self_vel x/y,
  knockback velocity x/y, airborne, jumps used and percent. Parsers reading only the first five are unaffected.
- **director.c: new `HB s port k damage angle x y radius` lines while tracing,** one per active hitbox.
- **director.c: a new `ATTR2` line at frame 1.** It logs each fighter's air-mobility attributes: ground-to-air momentum
  multiplier, jump h max, air jump v/h multipliers, jumps, air drift stick multiplier, base and max, and dash accel.
- **director.c, DIR_RESET: now also restarts the collision sweep** (coll_data cur/prev/last = the new position), as
  DIR_SETPOS already did. This is a bug fix. A reset of a fighter falling far offstage swept him back across the stage
  onto the far ledge (lab_falcon, segment B). Resets of grounded fighters are unaffected.

## 2026-09-27, lane 2 (the "over" flashes)
- **director: new cue DIR_GLASS = 40** (dsl `f.cue(t, 'glass', a=1)`); explicit value, a lane-2 range, so parallel lanes'
  appended cues can't collide. A top-blast screen KO (motions 6-7, DeadUpFall / HitCamera) places the fighter in the view
  space of `cm_804D6464` (ftdrawcommon.c), which the game refreshes only in its standard and fixed camera modes. Under the
  director's debug free camera it stayed at the match-start camera, so the screen KO hit the wrong lens. With the cue on,
  put_camera also writes the director's eye, interest, fov, roll and aspect into it. It is the only reader of that
  camera, so nothing else changes; off by default.
- **director: new cue DIR_GAMECAM = 41** (dsl `f.cue(t, 'gamecam', a=1)`). Hands the camera back to the game's own match
  camera (Camera_800300F0 restores the mode the debug free camera replaced; put_camera stops writing); a=0 takes it again.
  For checking what the vanilla game shows (the screen KO's orientation). Off by default.

## 2026-09-27, lane 1 (sacred combo), second round
- **dsl.py: new `Film.menu_hold(boot_frame, port, dur, btn)`** (additive). It holds buttons on a port's master pad from a
  loop frame since boot, using the director's existing menu-pad tables. A film that doesn't call it emits exactly the
  old `NO_MENU` lines, so existing scripts build byte-identically. Use: after a stock match ends, the victory screen
  picks the winner's pose from the button held on his port as it sets up (gm_1798.c): B is pose 0, Y pose 1, X pose 2,
  none a random pose (`HSD_Randi(3)`).
