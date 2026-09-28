// SO BACK: its plates, by name (engine/edit.js plays them: time maps, keyed pairs, preloading what is drawn). Plates live in
// assets/plates/soback_<name>/v (a symlink to ~/games/melee/plates; tools/machinima/prep_plates.py makes them).
const vplate = (name, n, o = {}) => keyedPlate(`assets/plates/soback_${name}/v`, n, o);
