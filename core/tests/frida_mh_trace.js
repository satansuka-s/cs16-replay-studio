'use strict';

function emit(o) {
    try { send(o); } catch (e) {}
}

const k32 = Process.getModuleByName('kernel32.dll');
const u32 = Process.getModuleByName('user32.dll');

// Force the working directory the launcher expects.
try {
    const setCwd = new NativeFunction(k32.getExportByName('SetCurrentDirectoryW'), 'int', ['pointer']);
    const ok = setCwd(Memory.allocUtf16String('D:\\CS 1.6 GoldClient'));
    emit({ t: 'setcwd', ok: ok });
} catch (e) {
    emit({ t: 'setcwd-error', error: String(e) });
}

function attach(mod, name, handlers) {
    try {
        const addr = mod.getExportByName(name);
        Interceptor.attach(addr, handlers);
        emit({ t: 'hooked', fn: name });
    } catch (e) {
        emit({ t: 'hook-error', fn: name, error: String(e) });
    }
}

attach(k32, 'CreateFileW', {
    onEnter(args) {
        try {
            const path = args[0].readUtf16String();
            if (path && /plugins|metahook|gamedata|\.dll/i.test(path)) emit({ t: 'CreateFileW', path: path });
        } catch (e) {}
    }
});

attach(k32, 'CreateFileA', {
    onEnter(args) {
        try {
            const path = args[0].readAnsiString();
            if (path && /plugins|metahook|gamedata|\.dll/i.test(path)) emit({ t: 'CreateFileA', path: path });
        } catch (e) {}
    }
});

attach(k32, 'SetEnvironmentVariableA', {
    onEnter(args) {
        try {
            const n = args[0].readAnsiString();
            const v = args[1].isNull() ? null : args[1].readAnsiString();
            if (n && /path/i.test(n)) emit({ t: 'SetEnv', name: n, value: v ? v.slice(-160) : null });
        } catch (e) {}
    }
});

attach(k32, 'LoadLibraryExW', {
    onEnter(args) {
        try {
            const p = args[0].readUtf16String();
            if (p) emit({ t: 'LoadLibraryExW', path: p });
        } catch (e) {}
    }
});

attach(k32, 'LoadLibraryW', {
    onEnter(args) {
        try {
            const p = args[0].readUtf16String();
            if (p) emit({ t: 'LoadLibraryW', path: p });
        } catch (e) {}
    }
});

attach(u32, 'MessageBoxA', {
    onEnter(args) {
        try {
            emit({ t: 'MessageBoxA', text: args[1].readAnsiString(), title: args[2].readAnsiString() });
        } catch (e) {}
    }
});

attach(u32, 'MessageBoxW', {
    onEnter(args) {
        try {
            emit({ t: 'MessageBoxW', text: args[1].readUtf16String(), title: args[2].readUtf16String() });
        } catch (e) {}
    }
});

emit({
    t: 'ready',
    modules: Process.enumerateModules()
        .filter(m => /hw\.dll|filesystem_stdio|MetaHook|client\.dll/i.test(m.name))
        .map(m => ({ name: m.name, base: m.base.toString(), size: m.size, path: m.path }))
});
