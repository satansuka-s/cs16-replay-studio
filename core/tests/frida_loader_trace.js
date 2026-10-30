'use strict';

function emit(o) { try { send(o); } catch (e) {} }

const main = Process.enumerateModules()[0];
const t0 = Date.now();
function ts() { return Date.now() - t0; }

function where(addr) {
    try {
        const m = Process.findModuleByAddress(addr);
        return m ? (m.name + '+' + addr.sub(m.base).toString()) : addr.toString();
    } catch (e) { return '?'; }
}

emit({ t: 'main', name: main.name, base: main.base.toString(), size: main.size });

const k32 = Process.getModuleByName('kernel32.dll');

function hookLoad(name) {
    let fn = null;
    try { fn = k32.getExportByName(name); } catch (e) { return; }
    Interceptor.attach(fn, {
        onEnter(args) {
            try {
                this.path = name.indexOf('W') >= 0 ? args[0].readUtf16String() : args[0].readAnsiString();
            } catch (e) { this.path = null; }
            this.caller = where(this.returnAddress);
        },
        onLeave(ret) {
            let actual = null;
            try {
                const gmn = new NativeFunction(k32.getExportByName('GetModuleFileNameA'), 'uint32', ['pointer', 'pointer', 'uint32']);
                const buf = Memory.alloc(1024);
                if (gmn(ret, buf, 1024) > 0) actual = buf.readAnsiString();
            } catch (e) {}
            emit({ t: name, ms: ts(), req: this.path, ret: ret.toString(), actual: actual, caller: this.caller });
        }
    });
    emit({ t: 'hooked', name: name });
}

hookLoad('LoadLibraryA');
hookLoad('LoadLibraryW');
hookLoad('LoadLibraryExA');
hookLoad('LoadLibraryExW');

try {
    Interceptor.attach(k32.getExportByName('GetProcAddress'), {
        onEnter(args) {
            let proc = null;
            try { proc = args[1].readAnsiString(); } catch (e) {}
            let modPath = null;
            try {
                const gmn = new NativeFunction(k32.getExportByName('GetModuleFileNameA'), 'uint32', ['pointer', 'pointer', 'uint32']);
                const buf = Memory.alloc(1024);
                if (gmn(args[0], buf, 1024) > 0) modPath = buf.readAnsiString();
            } catch (e) {}
            emit({ t: 'GetProcAddress', ms: ts(), h: args[0].toString(), mod: modPath, proc: proc, caller: where(this.returnAddress) });
        }
    });
    emit({ t: 'hooked', name: 'GetProcAddress' });
} catch (e) {
    emit({ t: 'hook-error', name: 'GetProcAddress', error: String(e) });
}
