"""SMD importer (GoldSrc .smd) for Blender: reference meshes + armature + per-sequence Actions.
Used by replay_import.py. SMD: version 1, nodes/skeleton/triangles.
"""
import bpy
import math
import os
from mathutils import Euler, Vector


def _parse(path):
    nodes = []
    skeleton = []   # list of frames: list per bone [bid, x,y,z, rx,ry,rz]
    tris = []       # list of (matname, [(vx,vy,vz, nx,ny,nz, u,v), ...])
    cur = None
    with open(path, 'r', errors='replace') as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            low = s.lower()
            if low in ('nodes', 'skeleton', 'triangles'):
                cur = low
                continue
            if s == 'end':
                cur = None
                continue
            if cur == 'nodes':
                parts = s.split('"')
                if len(parts) >= 3:
                    idx = int(parts[0].strip())
                    name = parts[1]
                    parent = int(parts[2].strip()) if len(parts) > 2 and parts[2].strip() else 0
                    nodes.append({'index': idx, 'name': name, 'parent': parent})
            elif cur == 'skeleton':
                if s.startswith('time '):
                    skeleton.append([])
                else:
                    v = [float(x) for x in s.split()]
                    if len(v) >= 7 and skeleton:
                        skeleton[-1].append(v)
            elif cur == 'triangles':
                parts = s.split()
                if len(parts) == 1:
                    tris.append([parts[0], []])
                elif len(parts) >= 7 and tris:
                    v = [float(x) for x in parts[:7]]
                    u = float(parts[7]) if len(parts) > 7 else 0.0
                    tris[-1][1].append(v + [u])
    return nodes, skeleton, tris


def _make_armature(name, nodes, skeleton, actions, fps=30.0):
    """Create armature with default pose from first skeleton frame; actions per seq."""
    if not skeleton or not nodes:
        return None
    frame0 = skeleton[0]
    pos = {int(v[0]): (v[1], v[2], v[3]) for v in frame0}
    # build chains: root bone = parent -1
    arm_data = bpy.data.armatures.new(name + '_arm')
    obj = bpy.data.objects.new(name, arm_data)
    bpy.context.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = {}
    for n in nodes:
        i, nm, p = n['index'], n['name'], n['parent']
        head = Vector(pos.get(i, (0, 0, 0)))
        # tail: towards parent direction or default length
        if p in bm:
            tail = bm[p].tail + (head - bm[p].head).normalized() * 8.0
        else:
            tail = head + Vector((0, 8, 0))
        eb = arm_data.edit_bones.new(nm)
        eb.head = head
        eb.tail = tail
        if p in bm:
            eb.parent = bm[p]
        bm[i] = eb
    bpy.ops.object.mode_set(mode='OBJECT')

    # per sequence Action: location/rotation keyframes per frame
    if not actions:
        return obj
    obj.animation_data_create()
    for seq_name, frames in actions.items():
        if not frames:
            continue
        action = bpy.data.actions.new(f'{name}_{seq_name}')
        action.use_fake_user = True
        obj.animation_data.action = action
        # write rotation+location per frame
        for bone_idx, bone_name in _bone_map(nodes).items():
            pbone = obj.pose.bones.get(bone_name)
            if not pbone:
                continue
            pbone.rotation_mode = 'XYZ'
            for fno, fr in enumerate(frames):
                data = {int(x[0]): x for x in fr}
                if bone_idx not in data:
                    continue
                v = data[bone_idx]
                loc = Vector((v[1], v[2], v[3]))
                rot = Euler((v[4], v[5], v[6]))
                pbone.location = loc
                pbone.rotation_euler = rot
                pbone.keyframe_insert('location', frame=fno, group=bone_name)
                pbone.keyframe_insert('rotation_euler', frame=fno, group=bone_name)
    obj.animation_data.action = None
    return obj


def _bone_map(nodes):
    return {n['index']: n['name'] for n in nodes}


def import_smd(path, obj_name=None, fps=30.0, seq_actions=None):
    """Import reference SMD: returns armature object (with mesh child if triangles present).
    seq_actions: dict name -> list of frames (from seq SMDs)."""
    nodes, skeleton, tris = _parse(path)
    if not nodes:
        return None
    name = obj_name or os.path.splitext(os.path.basename(path))[0]
    arm = _make_armature(name, nodes, skeleton, seq_actions, fps)
    if tris and arm:
        # mesh from triangles (bind pose: skeleton frame 0)
        mesh = bpy.data.meshes.new(name + '_mesh')
        me = bpy.data.objects.new(name + '_mesh', mesh)
        bpy.context.collection.objects.link(me)
        verts = []
        uvs = []
        faces = []
        mat_names = []
        for matname, tv in tris:
            if matname not in mat_names:
                mat_names.append(matname)
            mi = mat_names.index(matname)
            face = []
            for v in tv:
                verts.append((v[0], v[1], v[2]))
                uvs.append((v[7], v[6]))  # SMD stores u then v per vertex: (u, 1-v)
                face.append(len(verts) - 1)
            faces.append((mi, face))
        valid = [f for _, f in faces if len(f) >= 3]
        mesh.from_pydata(verts, [], valid)
        for matname in mat_names:
            mat = bpy.data.materials.new(matname)
            mesh.materials.append(mat)
        for fi, f in enumerate(valid):
            mesh.polygons[fi].material_index = mat_names.index(faces[faces.index((None, f))][0]) if False else 0
        # proper material mapping (robust: unknown names create a material)
        mat_of = {}
        fi = 0
        for mn0, fcv in faces:
            if len(fcv) < 3:
                continue
            mn = mn0 if isinstance(mn0, str) else ('mat%d' % len(mat_names))
            if mn not in mat_names:
                mat_names.append(mn)
                mesh.materials.append(bpy.data.materials.new(mn))
            mat_of[fi] = mat_names.index(mn)
            fi += 1
        for k, mi in mat_of.items():
            mesh.polygons[k].material_index = mi
        # UVs: one UV layer from tris order
        uv_layer = mesh.uv_layers.new(name='UVMap')
        # map face index (filtered) -> original vertex list
        fi = 0
        for mn, fcv in faces:
            if len(fcv) < 3:
                continue
            for k, vidx in enumerate(fcv):
                uv_layer.data[fi * len(fcv) + k].uv = (uvs[vidx][0], 1.0 - uvs[vidx][1])
            fi += 1
        me.parent = arm
    return arm


def attach_texture(obj, material_name, tga_path):
    """Give the material an image texture (tga must exist)."""
    if not tga_path or not os.path.exists(tga_path):
        return
    mat = bpy.data.materials.get(material_name) or bpy.data.materials.new(material_name)
    mat.use_nodes = True
    # localized UIs rename nodes; look up by type instead of name
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        return
    img = bpy.data.images.load(tga_path)
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = img
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
