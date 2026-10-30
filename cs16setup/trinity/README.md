# Trinity Engine + MetaHookSv для CS 1.6

Проверено 29.10.2026 на двух установках:

| Установка | Путь | MetaHook | Trinity | Запись демо |
|---|---|---|---|---|
| CS 1.6 build 4554 | `D:\Counter-Strike Build 4554` | работает | загружается, но роняет карту | работает (с AMXX, Trinity выключен) |
| CS 1.6 GoldClient (HL25, build 10846) | `D:\CS 1.6 GoldClient` | **не работает** | — | работает через штатный `hl.exe` |

Итог: **Trinity Engine непригоден для записи демо ни на одной из установок.**
Запись демо идёт штатным путём (`cs16setup` + AMXX-плагин `cs16db`), MetaHook/Trinity
для этого не нужны. Ниже — что именно проверено и почему.

---

## Что ставится

| Компонент | Источник | Куда |
|---|---|---|
| MetaHookSv `v20261027a` | `github.com/MetaHookSv/MetaHookSv/releases` | `MetaHook.exe`, `SDL3.dll`, `cstrike\metahook\*` |
| `TrinityRender.dll` | `github.com/ollerjoaco/Trinity-EngineSv/releases/tag/v0.2.0` | `cstrike\metahook\plugins\TrinityRender.dll` |
| gamedata-патч | `patch_gamedata_crc.py` (этот каталог) | `cstrike\metahook\gamedata\hl-*.json` |

`mp.dll` из релиза Trinity (**ReGame 5.30, 1 676 800 Б**) **не устанавливается**:
он собран под новый движок GoldClient и на 4554 ломает сервер
(`Game DLL version mismatch`, `Host_Error`). Оригинальный `mp.dll` 4554
(1 316 152 Б) остаётся на месте, `install_trinity.bat` его не трогает.

---

## Установка

```bat
rem поставить MetaHookSv + TrinityRender.dll, Trinity оставить выключенным
cs16setup\trinity\install_trinity.bat "D:\Counter-Strike Build 4554"

rem то же самое, но сразу включить Trinity (см. предупреждение ниже)
cs16setup\trinity\install_trinity.bat "D:\Counter-Strike Build 4554" --enable

rem откат (снимает плагин, gamedata из .bak, при желании сам MetaHook)
cs16setup\trinity\restore_trinity.bat "D:\Counter-Strike Build 4554"
cs16setup\trinity\restore_trinity.bat "D:\Counter-Strike Build 4554" --keep-metahook
```

Установщик:

1. качает `MetaHookSv-windows-x86.7z`, `TrinityRender.dll` и `7zr.exe`
   в `cs16setup\staging\trinity\` (повторно не качает);
2. распаковывает и запускает
   `MetahookInstallerCLI.exe -appid 10 -gamedir "<game>" -moddir cstrike -source <stage>\install\output`;
3. копирует `TrinityRender.dll` в `cstrike\metahook\plugins\`;
4. патчит CRC64 движка в gamedata (`patch_gamedata_crc.py`);
5. пишет `cstrike\metahook\configs\plugins.lst`: пусто (Trinity off) или
   `TrinityRender.dll` (с `--enable`).

Перед установкой скрипт делает `patch_gamedata_crc.py --dry-run` и **отказывается
ставить MetaHook на неподдерживаемый движок** (код возврата 2), чтобы не получить
незапускающуюся игру. Обойти: `--force`.

---

## Включить / выключить Trinity

```
cstrike\metahook\configs\plugins.lst      TrinityRender.dll   -> включён
cstrike\metahook\configs\plugins.lst      (пусто)            -> выключен
```

Запуск с MetaHook: `MetaHook.exe -game cstrike -steam`
Запуск без MetaHook: `hl.exe -game cstrike -steam` (так работает GoldClient).

---

## Почему Trinity не годится для записи (4554)

Проверено A/B на одном и том же запуске
(`MetaHook.exe -game cstrike -window -condebug +map de_dust2`):

| | без Trinity | с `TrinityRender.dll` |
|---|---|---|
| загрузка карты | `-------- Mapchange to de_dust2 --------` | то же |
| AMXX + `cs16db` | грузятся, `[cs16db] REC dtk_de_dust2_*.dem` | грузятся |
| результат | играем, демка пишется | через ~1 с диалог «Произошла непредвиденная ошибка» |

Файл падения `Protector_<дата>.json` в корне игры:

```json
"Exception": { "Message": "Failed to find in Find_UserMsgBase." }
```

`Find_UserMsgBase` — сигнатура, которую ищет Trinity/hwpatcher в `hw.dll`.
В этом билде её нет: Trinity собран под другой движок (GoldClient/HL25),
поэтому патчи применяются к неверным адресам и клиент падает на смене карты.

Дополнительно в логе AMXX при любом запуске на 4554:

```
GameConfig CRC computed engine=98CA3F51 (hw.dll)
GameConfig CRC mismatch ... expected 2C9EDE6B got 98CA3F51
client_disconnected and client_remove forwards have been disabled
Binding/Hooking cvars have been disabled
```

Это значит, что `hw.dll` в этой сборке — не стоковый 4554 (CRC32 `98CA3F51`
вместо `2C9EDE6B`/`F3A7F2F1`). AMXX частично работает, но часть форвардов
отключена; на фоне этого любой патч движка (Trinity) добивает процесс.

Вывод: **Trinity на 4554 держим выключенным.** Файлы лежат на месте,
включаются одной строкой, если понадобится эксперимент.

---

## Почему GoldClient не поддерживается

`MetaHook.exe`/`MetaHook_blob.exe` — лаунчеры, которые сами загружают движок и
вызывают `MH_LoadEngine(hEngineModule, ...)`. В GoldClient `hw.dll` — обычный PE
(ImageBase `0x10000000`, SizeOfImage `0x3ca6000`, `.text` 2 МБ, `.data` 60 МБ),
код движка подгружается позже внутри `EngineAPI->Run()`. Лаунчер видит только
`filesystem_stdio.dll` и передаёт его как «движок»:

```
MH_LoadEngine: Unable to determine engine version
Reason: the engine module CRC64 is not present in the gamedata catalog
Module: D:\CS 1.6 GoldClient\filesystem_stdio.dll
CRC64: e528ce35231f1021
```

Проверено Frida-трейсом `LoadLibraryA`: за весь запуск грузится ровно один
модуль — `filesystem_stdio.dll`; `hw.dll` лаунчером не грузится вообще.

Каталог gamedata содержит только снимки blob-движков (`hl-8684`, `hl-10210`,
`hl-9999` с RVA ~19 МБ). В `hw.dll` GoldClient (4 МБ) сигнатуры этих снимков
не находятся: 1 совпадение из 19 (случайное). Поэтому
`patch_gamedata_crc.py` для GoldClient честно отказывается:

```
[error] this engine build is not covered by the gamedata catalog.
        best signature match: hl-10210.json 1/19, hl-3248.json 0/18, ...
```

Чтобы Trinity заработал на GoldClient, нужен либо лаунчер, который вызывает
`MH_LoadEngine` **после** загрузки `hw.dll` (пересборка `MetaHook.exe`), либо
gamedata под build 10846 (снять RVA с живого процесса). Обе задачи — отдельный
проект, в текущем объёме не делались.

---

## `patch_gamedata_crc.py`

MetaHook выбирает снимок gamedata по CRC64 модуля движка. Для репаков
(у 4554 CRC64 `47dc98f6c909835a` вместо каталожного `af713d75d839d5c7`)
снимок не находится, и MetaHook не стартует. Скрипт:

1. считает CRC64 (ECMA/XZ) локального `hw.dll` и читает его `ImageBase`/`SizeOfImage`;
2. перебирает `cstrike\metahook\gamedata\hl-*.json`, отбрасывает те, чьи RVA
   не влезают в образ;
3. для оставшихся сверяет **байтовые сигнатуры** (`func_sig`/`gv_sig`) с бинарником
   и берёт снимок с лучшим совпадением (нужно ≥ 80 %);
4. пишет новый `crc64` в снимок и обновляет `sha256`/`size` в `index.json`
   (MetaHook проверяет и то, и другое), оригинал сохраняет как `*.json.bak`.

```bat
python cs16setup\trinity\patch_gamedata_crc.py "D:\Counter-Strike Build 4554"
python cs16setup\trinity\patch_gamedata_crc.py "D:\Counter-Strike Build 4554" --dry-run
python cs16setup\trinity\patch_gamedata_crc.py "D:\game" --gamedata hl-4554.json
```

Проверка сигнатур — не украшение: по одному лишь попаданию RVA в образ
«blob host» GoldClient принимает **все** снимки, и запись CRC в первый
попавшийся приводит к `symbol rva is out of the module bounds` уже в игре.

Вывод на 4554:

```
engine      : D:\Counter-Strike Build 4554\hw.dll
image base  : 0x01d00000
image size  : 0x01229a8e
crc64       : 47dc98f6c909835a
snapshot    : hl-4554.json (old crc64 47dc98f6c909835a)
signatures  : 18/18 found
max symbol  : 0x011fe3c8
already up to date
```

---

## Что осталось от визуальных модов

| Мод | Статус |
|---|---|
| Trinity Engine (`TrinityRender.dll`) | установлен, выключен: ломает карту на 4554, не стартует на GoldClient |
| CS_RenderHook | в открытом доступе не найден, установщик-оболочка в `cs16setup\renderhook\` |
| Dynamic Sky & Lighting | это AMXX-плагин, а не движковый мод — ставится в `addons\amxmodx\plugins` |
| HLAE 2.192.10 | работает, `D:\HLAE`, лаунчеры в `hlae\` — для CS:GO/CS:S, не для 1.6 |
