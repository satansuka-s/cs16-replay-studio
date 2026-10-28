"""Minimal Valve VPK (version 2) reader for Source 1 games.

Reads <dir>.vpk directory tree + <dir>_NNN.vpk data archives.
Only flat (non-tiered, non-lzma) entries are expected; preload data handled.

Usage:
    v = VPK(r'D:\\...\\csgo\\pak01_dir.vpk')
    data = v.read('materials/de_dust/hr_dust/foo_color.vtf')
    names = v.list_files('vtf')
"""
import os
import struct


class VPKEntry:
    __slots__ = ('path', 'crc', 'preload_size', 'archive_index',
                 'entry_offset', 'entry_size', 'preload')

    def __init__(self, path, crc, preload_size, archive_index, entry_offset,
                 entry_size, preload):
        self.path = path
        self.crc = crc
        self.preload_size = preload_size
        self.archive_index = archive_index
        self.entry_offset = entry_offset
        self.entry_size = entry_size
        self.preload = preload


class VPK:
    def __init__(self, dir_path):
        self.dir_path = dir_path
        base = dir_path[:-4] if dir_path.lower().endswith('.vpk') else dir_path
        self.base = base
        self.files = {}      # 'ext/path/name' -> entry
        self._archives = {}
        with open(dir_path, 'rb') as f:
            head = f.read(12)
            magic, version, treesize = struct.unpack('<III', head)
            if magic != 0x55AA1234:
                raise ValueError('not a Valve VPK dir file (magic %08x)' % magic)
            if version != 2:
                raise ValueError('VPK version %d not supported' % version)
            tree = f.read(treesize)
            # leave the 4-byte footer signature if present
        pos = 0
        while pos < len(tree):
            end = tree.index(b'\0', pos)
            ext = tree[pos:end].decode('latin1')
            pos = end + 1
            if not ext:
                break
            while pos < len(tree):
                end = tree.index(b'\0', pos)
                folder = tree[pos:end].decode('latin1')
                pos = end + 1
                if not folder:
                    break
                while pos < len(tree):
                    end = tree.index(b'\0', pos)
                    fname = tree[pos:end].decode('latin1')
                    pos = end + 1
                    if not fname:
                        break
                    crc, preload_size = struct.unpack_from('<IH', tree, pos)
                    archive_index, entry_offset, entry_size = \
                        struct.unpack_from('<HII', tree, pos + 6)
                    pos += 16
                    preload = tree[pos:pos + preload_size]
                    pos += preload_size
                    path = '%s/%s/%s' % (ext, folder, fname)
                    self.files[path.lower()] = VPKEntry(
                        path, crc, preload_size, archive_index, entry_offset,
                        entry_size, preload)
                    if not entry_offset and not entry_size and archive_index == 0xFFFF:
                        # not stored in an archive: data is the preload itself
                        self.files[path.lower()].entry_size = preload_size

    def _archive(self, index):
        if index not in self._archives:
            p = '%s_%03d.vpk' % (self.base, index)
            self._archives[index] = open(p, 'rb')
        return self._archives[index]

    def read(self, path):
        e = self.files.get(path.lower().replace('\\', '/'))
        if e is None:
            return None
        if e.entry_size == e.preload_size and e.entry_offset == 0 and e.archive_index == 0xFFFF:
            return e.preload
        if e.preload_size == e.entry_size:
            # wholly preloaded
            return e.preload
        with self._archive(e.archive_index) as f:
            f.seek(e.entry_offset)
            data = f.read(e.entry_size)
        if e.preload_size and len(e.preload):
            return e.preload + data
        return data

    def list_files(self, ext=None):
        out = []
        for path in self.files:
            if ext is None or path.startswith(ext.lower() + '/'):
                out.append(path)
        return out

    def close(self):
        for a in self._archives.values():
            a.close()
        self._archives = {}


if __name__ == '__main__':
    import sys
    v = VPK(sys.argv[1])
    n = 0
    for name in v.list_files('vtf')[:int(sys.argv[2]) if len(sys.argv) > 2 else 10]:
        print(name, len(v.read(name) or b''))
    print('total vtf', len(v.list_files('vtf')))
    v.close()
