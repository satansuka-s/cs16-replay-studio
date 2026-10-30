import re
for p in [r"D:\CS 1.6 GoldClient\MetaHook_blob.exe", r"D:\CS 1.6 GoldClient\MetaHook.exe"]:
    data = open(p,"rb").read()
    print("===", p.split("\\")[-1], len(data))
    for kw in [b"MH_LoadEngine: Failed to resolve", b"metahook\\dlls", b"plugins.lst", b"METAHOOK_PLUGIN_API_VERSION002", b"Unable to determine engine version", b"does not support blob engine", b"MH_LoadPlugins"]:
        print("   ", kw, data.count(kw))
