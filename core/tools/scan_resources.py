#!/usr/bin/env python3
"""Scan a CS 1.6 installation folder and list resources needed for full scene
reconstruction: maps, models, player models, sounds, sprites, WADs, TGA/MIP.
Flags likely-custom files (not part of stock CS 1.6) using a small builtin list.

Usage: python scan_resources.py <game_dir> [--json out.json]
Example: python scan_resources.py "D:\\Counter-Strike Build 4554"
"""
import json
import os
import sys

# stock CS 1.6 player models (prefixed 'models/player/<x>/<x>.mdl')
STOCK_PLAYERS = {
    "arctic", "gign", "guerilla", "leet", "militia", "phoenix", "sas", "swat",
    "terror", "urban", "vip", "gordon", "helmet",
}
# stock-ish weapon/entity model name tokens (first token of models/w_p_*.mdl etc.)
STOCK_WEAPON_PREFIXES = (
    "ak47", "aug", "awp", "c4", "deagle", "elite", "famas", "fiveseven",
    "flashbang", "g3sg1", "galil", "glock18", "grenade", "hegrenade", "knife",
    "m249", "m3", "m4a1", "mac10", "mp5navy", "p90", "para", "p228", "rpg",
    "sg550", "sg552", "scout", "smoke", "tmp", "ump45", "usp", "xm1014",
)
STOCK_MAPS = ("de_", "cs_", "as_", "fy_", "awp_", "aim_", "he_", "surf_", "ze_", "zm_", "ka_", "scoutzknivez", "cstrike", "de_dust", "de_dust2", "de_inferno", "de_train", "de_nuke", "de_aztec", "cs_office", "cs_assault", "cs_italy", "cs_militia")

def classify(rel):
    rel = rel.replace('\\', '/').lower()
    custom = False
    kind = "other"
    if rel.startswith("maps/") and rel.endswith(".bsp"):
        kind = "map"
        base = os.path.basename(rel)[:-4]
        custom = not (base.startswith(STOCK_MAPS) and len(base) > 3 and ("de_" in base or "cs_" in base or base in ("scoutzknivez", "cstrike", "de_dust2")))
    elif rel.startswith("models/player/") and rel.endswith(".mdl"):
        kind = "player_model"
        custom = not any(base in rel for base in STOCK_PLAYERS)
    elif rel.startswith("models/") and rel.endswith(".mdl"):
        kind = "model"
        base = os.path.basename(rel)[:-4]
        custom = True
        for p in STOCK_WEAPON_PREFIXES:
            if base.startswith(("w_" + p, "p_" + p, "v_" + p)):
                custom = False
                break
    elif rel.startswith("sound/") and (rel.endswith(".wav") or rel.endswith(".mp3")):
        kind = "sound"
        custom = rel.endswith(".mp3")
    elif rel.endswith(".wad"):
        kind = "wad"
        custom = True
    elif rel.endswith(".spr"):
        kind = "sprite"
        custom = True
    elif rel.endswith(".tga") or rel.endswith(".mip"):
        kind = "texture"
        custom = True
    return kind, custom

def main():
    args = sys.argv[1:]
    game_dir = None
    out_json = None
    for a in args:
        if a.startswith("--json="):
            out_json = a[len("--json="):]
        elif not a.startswith("--"):
            game_dir = a
    if not game_dir:
        print(__doc__)
        return 1
    cstrike = os.path.join(game_dir, "cstrike")
    roots = [cstrike]
    custom_dir = os.path.join(cstrike, "custom")
    if os.path.isdir(custom_dir):
        roots.append(custom_dir)

    items = []
    scanned = 0
    for root in roots:
        base = root
        if not os.path.isdir(root):
            print(f'[warn] {root} not found')
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            for fn in filenames:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in (".bsp", ".mdl", ".wav", ".mp3", ".wad", ".spr", ".tga", ".mip"):
                    continue
                scanned += 1
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, base).replace('\\', '/')
                size = os.path.getsize(full)
                kind, custom = classify(rel)
                items.append({"file": rel, "kind": kind, "custom": custom, "size": size})
    print(f'[scan] files visited: {scanned}')

    items.sort(key=lambda x: (not x["custom"], x["kind"], x["file"]))
    custom_items = [i for i in items if i["custom"]]
    print(f"resources: {len(items)} total, {len(custom_items)} likely custom")
    for i in items:
        tag = "CUSTOM " if i["custom"] else "       "
        print(f'{tag} [{i["kind"]:12s}] {i["size"]:>10,} {i["file"]}')
    if out_json:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=1)
    return 0

if __name__ == "__main__":
    sys.exit(main())
