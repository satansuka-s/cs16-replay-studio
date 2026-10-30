'use strict';

function emit(o) { try { send(o); } catch (e) {} }

const t0 = Date.now();
function ts() { return Date.now() - t0; }

function where(addr) {
    try {
        const m = Process.findModuleByAddress(addr);
        return m ? (m.name + '+' + addr.sub(m.base).toString()) : addr.toString();
    } catch (e) { return '?'; }
}

const main = Process.enumerateModules()[0];
emit({ t: 'main', name: main.name, base: main.base.toString() });

const k32 = Process.getModuleByName('kernel32.dll');
Interceptor.attach(k32.getExportByName('LoadLibraryA'), {
    onEnter(args) {
        try { this.path = args[0].readAnsiString(); } catch (e) { this.path = null; }
        this.caller = where(this.returnAddress);
    },
    onLeave(ret) {
        let actual = null;
        try {
            const m = Process.findModuleByAddress(ret);
            if (m) actual = m.path;
        } catch (e) {}
        emit({ t: 'LLA', ms: ts(), req: this.path, ret: ret.toString(), actual: actual, caller: this.caller });
    }
});
emit({ t: 'hooked' });
