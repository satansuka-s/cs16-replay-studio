# Аудит инструментов (cs16db)

Дата аудита: 27.10.2026. Источники: GitHub API (поля `pushed_at`, `archived`),
crates.io, репозитории/код инструментов, эмпирические прогоны на реальных демках.

## Таблица: Этап | Инструмент | Язык | Статус | GoldSrc | Сложность интеграции

| Этап | Инструмент | Язык | Статус | GoldSrc | Сложность |
|---|---|---|---|---|---|
| Ядро | **HLDemo** (YaLTeR/HLDemo) | C++ | Заброшен (03.2016), стабилен | Полный структурный парсинг (чтение+запись) | Низкая (CMake); сетевой слой — ручной |
| Ядро | hldemo-rs (YaLTeR) | Rust | Заброшен (07.2022) | Полный структурный парсинг | Средняя (нужен Rust) |
| Ядро | dem (khanghugo/dem) | Rust | Живой (05.2026), v0.3.0 | Парсер + **писатель**, svc-слой | Средняя; использован как референс |
| Ядро | py-goldsrc-demo | Python | Заброшен (01.2024), юзабелен | Структурный парсинг, демки CS1.6 в тестах | Низкая |
| Ядро | talent (cgdangelo/talent) | TS | Живой (референс) | Парсер + jsonify-demo | Низкая (референс) |
| Ядро | VolvoWrench (Traderain) | C# | Заброшен (12.2022) | Анализатор демок | Средняя; инструмент отладки |
| Ядро | hl-demofile-spec | — | Репозиторий не найден | — | — |
| Ядро | **Xash3D-FWGS** (движок) | C | Живой | Точные реализации svc/дельта-декодирования | Служит спецификацией |
| Карта Blender | GoldImporter | Python | Репо не найден (вне GitHub) | BSP v29/30 | Низкая; **выбор** |
| Карта Blender | blender_io_mesh_bsp (andyp123) | Python | Заброшен (06.2022) | BSP (Quake/HL-семейство) | Низкая; fallback |
| Карта Blender | SourceIO (REDxEYE) | Python | Живой (10.2026) | GoldSrc в legacy-ветках | Средняя; избыточен |
| Карта Max | Wall Worm | MAXScript/C# | Живой (коммерч.) | VMF/MAP импорт, MDL Loader | Средняя; **выбор** |
| Карта Max | BSPSource (ata4/bspsrc) | Java | Живой (10.2026) | BSP → VMF | Низкая; **выбор** |
| Карта Max | Crafty | — | Репозиторий не найден (404) | — | Отклонён |
| Модель | **Crowbar** (ZeqMacaw) | VB.NET | Живой (08.2026) | MDL → SMD (GoldSrc+Source) | Низкая; **выбор** |
| Модель | DecompMDL (halflife-tools) | C++ | Репозиторий не найден | MDL → SMD | Отклонён (Crowbar покрывает) |
| Модель | studiodec | — | Отдельного репозитория нет | — | Отклонён |
| SMD Blender | cs-smd-blender-importer (sg-first) | Python | Заброшен (01.2022) | SMD, CS 1.6/Blender 3.0+ | Низкая; приоритет для CS |
| SMD Blender | Blender Source Tools (Artfunkel) | Python | Живой (11.2025) | SMD/Source | Средняя; fallback |
| SMD Max | NeilJed/3DSMax-SMD-Importer | MAXScript | Заброшен (07.2019), стабилен | SMD кости+материалы | Низкая |
| SMD Max | Wall Worm MDL Loader | C# | Живой | MDL напрямую | Низкая; проще |
| Камера | **HLAE** (advancedfx) | C++ | Живой (10.2026) | BVH-экспорт камеры; afx-blender-scripts | Низкая; **выбор** |
| Камера | Saturated Demo Tools | — | Не найден (pre-alpha) | — | Только референс; отклонён |

## Обоснование выбора

**Ядро: HLDemo (C++).** Зрелый структурный парсер (заголовок, записи, 9 типов
фреймов, чтение/запись, CMake). Заброшен с 2016 г., но формат не менялся 20 лет —
код стабилен. Однако он **не декодирует сетевой слой** (svc-сообщения отдаёт сырыми
байтами). Поэтому поверх HLDemo написан собственный декодер:
- референс точной семантики — **Xash3D-FWGS** (net_encode.c, cl_parse_gs.c,
  protocol.h: дельта-описания, packet entities, битовые чтения) и **dem (Rust)**
  (полный парсер svc, включая структуру кадров 0/1/9);
- эмпирическая проверка — hldemo-rs, py-goldsrc-demo (их тест-демки и demo-файлы).

Итог: `demo_extract` читает: svc_time/print/stufftext/serverdata/lightstyle/
updateuserinfo/deltatable/clientdata/sound/spawnstatic/spawnbaseline/event(s)/
packetentities/deltapacketentities/director/hltv + user-сообщения (скип);
извлекает: камеру (3 источника) + трекинг сущностей игроков (origin, viewangles,
sequence, frame, animtime, framerate, velocity) с интерполяцией по тикам.

**Карта Blender: GoldImporter** (ориентирован на GoldSrc BSP), fallback —
blender_io_mesh_bsp, SourceIO — избыточен (заточен под Source).
**Карта Max: BSPSource → VMF → Wall Worm** (Wall Worm — проприетарный, но
это фактически стандарт для Hammer/3ds Max; Crafty отклонён: репозиторий удалён).
**Модель: Crowbar** (единственный живой MDL-декодер GoldSrc; DecompMDL и
studiodec — недоступны/не поддерживаются).
**SMD: cs-smd-blender-importer** (заточен под CS 1.6/Blender 3.0+) с fallback
на BlenderSourceTools; в Max — NeilJed-плагин или Wall Worm MDL Loader.
**Камера: HLAE BVH** + afx-blender-scripts; SDT — только референс (не найден).

## Эмпирические факты, установленные при аудите

1. Префикс netmsg в демках proto 47/48 — **464 байта** (не 496, как в HLDemo-коде
   комментарием; установлено по 5 демкам: 2008 HLTV, синтетика, современные записи).
   → В `demo_extract` префикс пропускается целиком, длина читается как int32.
2. svc-таблица Xash3D (proto 48) полностью совпадает с CS 1.6 (proto 47):
   time=7, deltatable=14, clientdata=15, spawnbaseline=22, packetentities=40,
   deltapacketentities=41, director=51 (проверено на `2008-de_inferno.dem`,
   протокол 47, cstrike).
3. **HLTV-демки НЕСУТ полный entity-поток** (`svc_deltapacketentities`:
   25 970 пакетов в 2008-записи), но **не передают svc_deltatable в записи**
   (все таблицы, кроме `event_t`, отсутствуют): декодирование требует
   встроенных таблиц из `cstrike/delta.lst` (добавлены в `builtin_delta.hpp`).
4. **Две генерации формата пакетов сущностей**: proto ≤47 — классика
   (`[13-бит entnum][2 бита remove][1+7 baseline][1+2 type][по 1 биту на поле]`),
   proto 48+ — GoldSrc-incremental (маска 3 бита + байты, инкрементальные номера).
   Выбор автоматический по `net_protocol` в заголовке демки.
5. **Режиссёрской камеры в HLTV-записи нет**: svc_director (51) несёт только
   DRC_CMD_MESSAGE (центр-тексты) и DRC_CMD_STATUS; команды CAMERA/CHASE/INEYE/
   CAMPATH в записи не появляются (движение камеры генерируется локально при
   проигрывании). Доступна spectator-камера: позиция из `svc_clientdata.origin`,
   ориентация — от viewentity (svc_setview) — источник 4 в JSON.
6. Сервер может передавать delta-таблицу как по одному полю на сообщение —
   декодер накапливает поля (append), а не перезаписывает таблицу.
7. Демки, записанные новыми клиентами (2024+, «фреймы типа 100»), содержат
   гибрид: классическая часть + блок нового формата; парсинг останавливается
   на переходе (камера при этом извлекается целиком).

## Отклонено и почему

- **SDT** — пре-alpha, репозиторий не найден → только референс (как и задано).
- **Crafty** — репозиторий удалён/недоступен.
- **DecompMDL, studiodec** — нет поддерживаемых релизов; заменены Crowbar.
- **py-goldsrc-demo / talent** — не используются как зависимости: парсят только
  структурный слой (svc не декодируют); остались как кросс-проверка.

## FIXME / TODO (следующие шаги)

- Полный парсинг «нового» формата фреймов 100+ (2024+ записи).
- Проекция userinfo → entity index (имена игроков в JSON).
- Авто-подбор знаков углов камеры (тестовый рендер) — сейчас флаги `--mirror-yaw/--flip-pitch`.
