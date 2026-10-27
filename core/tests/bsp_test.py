import sys
sys.path.insert(0, r'C:\dev\cs16db\blender')
import bsp_import

bsp_import.import_bsp(r'D:\Counter-Strike Build 4554\cstrike\maps\de_dust2.bsp',
                      'map_dust2', tex_dir=r'C:\dev\cs16db\core\tests\map_tex2')
import bpy
print('objects:', [o.name for o in bpy.context.scene.objects][:5])
print('materials:', list(bpy.data.materials.keys())[:6])
