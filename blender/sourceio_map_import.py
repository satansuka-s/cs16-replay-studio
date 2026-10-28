"""SourceIO map import helper (Blender 5.0+ compatible SourceIO >= 5.5.4).

Imports a Source 1 BSP (CS:GO/CS:S) with full static props / models /
multiblend materials into its own .blend for the replay pipeline.

Requires SourceIO installed from github.com/REDxEYE/SourceIO (5.5.4+):
  blender --background --python sourceio_map_import.py -- --bsp map.bsp --out map.blend
"""
import argparse
import os
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bsp', required=True)
    p.add_argument('--out', default='sio_map.blend')
    p.add_argument('--steam-app', default='-999')
    args = p.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])

    import bpy
    try:
        bpy.ops.preferences.addon_enable(module='SourceIO')
    except Exception as e:
        print('[sio] cannot enable SourceIO:', e)
        print('[sio] install: Preferences -> Get Extensions -> Install from Disk,')
        print('        choose the SourceIO zip (5.5.4+ supports Blender 5.x)')
        return 1
    try:
        bpy.ops.sourceio.bsp(filepath=os.path.abspath(args.bsp),
                             steam_app_id=args.steam_app, discover_resources=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('[sio] import failed:', e)
        return 1
    out = args.out if args.out.endswith('.blend') else args.out + '.blend'
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('[sio] map ->', out, 'objects:', len(bpy.data.objects))
    return 0


if __name__ == '__main__':
    sys.exit(main())
