#!/usr/bin/env python3
"""Embed CS 1.6 delta.lst into a C++ header (builtin delta tables).
Run: python gen_delta_hpp.py <delta.lst> <out.hpp>"""
import sys

def main():
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, 'r', encoding='utf-8-sig') as f:
        text = f.read()
    # raw string friendly: must not contain )"""
    assert ')"' + '""' not in text.replace('"""', ''), 'unexpected sequence in delta.lst'
    out = []
    out.append('// Auto-generated from CS 1.6 cstrike/delta.lst (Valve) - builtin delta tables.')
    out.append('// Used as a fallback when a demo/HLTV stream does not carry svc_deltatable updates.')
    out.append('#pragma once')
    out.append('#include <string>')
    out.append('namespace gs {')
    out.append('inline const char* kBuiltinDeltaLst =')
    out.append('R"DELTA(')
    out.append(text.rstrip('\n'))
    out.append(')DELTA";')
    out.append('inline const std::string builtinDeltaLst() { return std::string(kBuiltinDeltaLst); }')
    out.append('} // namespace gs')
    with open(dst, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out) + '\n')
    print(f'wrote {dst} ({len(text)} chars)')

if __name__ == '__main__':
    main()
