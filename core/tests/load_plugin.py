import ctypes, os
p = r'D:\CS 1.6 GoldClient\cstrike\metahook\plugins\TrinityRender.dll'
os.add_dll_directory(os.path.dirname(p))
try:
    h = ctypes.WinDLL(p)
    print('LOADED OK', h)
except OSError as e:
    print('LOAD FAILED:', e)
