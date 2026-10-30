'use strict';

function emit(o) { try { send(o); } catch (e) {} }

const mod = Process.getModuleByName('MetaHook_blob.exe');
const base = mod.base;
emit({ t: 'module', name: mod.name, base: base.toString(), size: mod.size, path: mod.path });

function hook(rva, name, cb) {
    try {
        const addr = base.add(rva);
        Interceptor.attach(addr, cb);
        emit({ t: 'hooked', name: name, addr: addr.toString() });
    } catch (e) {
        emit({ t: 'hook-error', name: name, error: String(e) });
    }
}

const t0 = Date.now();
function ts() { return Date.now() - t0; }

hook(0x1c070, 'MH_LoadEngine', {
    onEnter(args) {
        const info = { t: 'enter', fn: 'MH_LoadEngine', ms: ts() };
        try { info.ecx = this.context.ecx.toString(); } catch (e) {}
        try { info.edx = this.context.edx.toString(); } catch (e) {}
        try { info.gameName = args[0].readAnsiString(); } catch (e) {}
        try { info.fullPath = args[1].readAnsiString(); } catch (e) {}
        try { info.engineDLL = args[2].readAnsiString(); } catch (e) {}
        try {
            const k32b = Process.getModuleByName('kernel32.dll');
            const gmn = new NativeFunction(k32b.getExportByName('GetModuleFileNameA'), 'uint32', ['pointer', 'pointer', 'uint32']);
            const buf = Memory.alloc(1024);
            const n = gmn(this.context.ecx, buf, 1024);
            if (n > 0) info.ecxPath = buf.readAnsiString();
        } catch (e) {}
        try {
            const ra = this.returnAddress;
            const m = Process.findModuleByAddress(ra);
            info.ret = m ? (m.name + '+' + ra.sub(m.base).toString()) : ra.toString();
        } catch (e) {}
        try {
            info.bt = Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 8).map(a => {
                const m = Process.findModuleByAddress(a);
                return m ? (m.name + '+' + a.sub(m.base).toString()) : a.toString();
            });
        } catch (e) {}
        emit(info);
    },
    onLeave() { emit({ t: 'leave', fn: 'MH_LoadEngine', ms: ts() }); }
});

hook(0x18f50, 'MH_LoadDllPaths', {
    onEnter() { emit({ t: 'enter', fn: 'MH_LoadDllPaths', ms: ts() }); },
    onLeave() { emit({ t: 'leave', fn: 'MH_LoadDllPaths', ms: ts() }); }
});

hook(0x19670, 'MH_LoadPlugins', {
    onEnter() { emit({ t: 'enter', fn: 'MH_LoadPlugins', ms: ts() }); },
    onLeave() { emit({ t: 'leave', fn: 'MH_LoadPlugins', ms: ts() }); }
});

hook(0x18130, 'MH_SysError', {
    onEnter(args) {
        let fmt = null;
        try { fmt = args[0].readAnsiString(); } catch (e) {}
        const extras = [];
        for (let i = 1; i <= 3; i++) {
            try {
                const p = args[i];
                if (p.isNull()) { extras.push(null); continue; }
                const r = Process.findRangeByAddress(p);
                if (r) {
                    const s = p.readAnsiString();
                    if (s && s.length > 0 && /^[\x20-\x7e\r\n\t]+$/.test(s)) { extras.push(s); continue; }
                }
                extras.push('0x' + p.toString(16));
            } catch (e) { extras.push('?'); }
        }
        emit({ t: 'syserror', ms: ts(), fmt: fmt, args: extras });
    }
});

const k32 = Process.getModuleByName('kernel32.dll');

// Which module handle is MetaHook querying when it formats the error?
try {
    Interceptor.attach(k32.getExportByName('GetModuleFileNameA'), {
        onEnter(args) { this.h = args[0]; this.buf = args[1]; },
        onLeave(ret) {
            try {
                const n = ret.toInt32();
                if (n > 0) {
                    const p = this.buf.readAnsiString();
                    if (p) emit({ t: 'GetModuleFileNameA', ms: ts(), h: this.h.toString(), path: p });
                }
            } catch (e) {}
        }
    });
    emit({ t: 'hooked', name: 'GetModuleFileNameA' });
} catch (e) {
    emit({ t: 'hook-error', name: 'GetModuleFileNameA', error: String(e) });
}

// CRC helper used by the symbol-failure reporter.
hook(0x0c120, 'CRC?', {
    onEnter() {
        const info = { t: 'crc-enter', ms: ts() };
        try { info.ecx = this.context.ecx.toString(); } catch (e) {}
        try { info.edx = this.context.edx.toString(); } catch (e) {}
        emit(info);
    }
});

function hookExport(mod2, name, filter) {
    try {
        Interceptor.attach(mod2.getExportByName(name), {
            onEnter(args) {
                try {
                    const p = name.indexOf('W') >= 0 ? args[0].readUtf16String() : args[0].readAnsiString();
                    if (p && filter.test(p)) emit({ t: name, ms: ts(), path: p });
                } catch (e) {}
            }
        });
        emit({ t: 'hooked', name: name });
    } catch (e) {
        emit({ t: 'hook-error', name: name, error: String(e) });
    }
}
hookExport(k32, 'LoadLibraryA', /trinity|plugin|metahook/i);
hookExport(k32, 'LoadLibraryW', /trinity|plugin|metahook/i);
hookExport(k32, 'LoadLibraryExA', /trinity|plugin|metahook/i);
hookExport(k32, 'LoadLibraryExW', /trinity|plugin|metahook/i);

// Log every LoadLibraryA with its result, to see what the launcher actually loads.
try {
    Interceptor.attach(k32.getExportByName('LoadLibraryA'), {
        onEnter(args) {
            try { this.path = args[0].readAnsiString(); } catch (e) { this.path = null; }
            if (this.path && /hw\.dll/i.test(this.path)) {
                try {
                    this.bt = Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 8).map(a => {
                        const m = Process.findModuleByAddress(a);
                        return m ? (m.name + '+' + a.sub(m.base).toString()) : a.toString();
                    });
                } catch (e) {}
            }
        },
        onLeave(ret) {
            let actual = null;
            try {
                const gmn2 = new NativeFunction(k32.getExportByName('GetModuleFileNameA'), 'uint32', ['pointer', 'pointer', 'uint32']);
                const buf = Memory.alloc(512);
                if (gmn2(ret, buf, 512) > 0) actual = buf.readAnsiString();
            } catch (e) {}
            emit({ t: 'LoadLibraryA:result', ms: ts(), req: this.path, ret: ret.toString(), actual: actual, bt: this.bt });
        }
    });
    emit({ t: 'hooked', name: 'LoadLibraryA:result' });
} catch (e) {
    emit({ t: 'hook-error', name: 'LoadLibraryA:result', error: String(e) });
}

// The launcher's engine load call sites.
