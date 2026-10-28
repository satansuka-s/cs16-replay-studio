# Source 1 (CS:GO / Counter-Strike: Source) ветка

Демки движка Source 1 (.dem): те же HLTV-ограничения, что и в GoldSrc
(камера-наблюдателя в файл не пишется), но **позиции всех игроков на каждый
тик — записываются**. Единицы совпадают с GoldSrc: **Source unit = 1 дюйм,
Z-up** — поэтому сгенерированный JSON сразу принимают `blender_import.py` и
`max_import.py` из корневого проекта.

## Готовые решения (аудит 10.2026)

| Задача | Инструмент | Статус | Как ставить |
|---|---|---|---|
| Парсинг демок CS:GO | **demoparser2** (PyPI, Rust-core) | Живой, v0.42.1, де-факто стандарт | `pip install demoparser2` |
| Парсинг демок CS:GO | **awpy** (Python-обёртка, аналитика) | Живой | `pip install awpy` |
| Парсинг демок CSS | **demoinfogo** (Valve, C++) | Устаревший, но рабочий | `git clone https://github.com/ValveSoftware/csgo-demoinfogo` + CMake |
| Камера всех Source | **HLAE** (advancedfx) | Живой | hlae.org; экспорт BVH + afx-скрипты |
| Карты (BSP) Blender | **SourceIO** (REDxEYE) | Живой, 10.2026, Blender 4.0+ | Аддон из релизов GitHub: REDxEYE/SourceIO |
| Карты (BSP) Max | **Wall Worm** (BSPSource → VMF) | Живой | wallworm.com |
| Модели MDL | **Crowbar** | Живой | zeqmacaw.github.io |
| Модели/карты Blender | **Blender Source Tools** (Artfunkel) | Живой, 11.2025 | GitHub: Artfunkel/BlenderSourceTools |

## Конвейер CS:GO — статус парсинга (проверено 10.2026)

**Работает.** Для CS:GO собран собственный экстрактор `source1/go_extract/csgo_extract.exe`
(Go, demoinfocs-golang v3 — последняя ветка с поддержкой CS:GO).

Проверка End-to-End на реальной CS:GO-демке (ok.dem, de_dust2, 2017):
```
csgo_extract.exe demo.dem out.json --follow 1
blender --background --python blender\blender_import.py -- --json out.json --out scene.blend
→ 1625 кадров, игроки с origin/angles/velocity, .blend собран ✅
```

## «Одна кнопка» (CS:GO / CS:S) + своя карта + монтажная сетка событий

`source1/make_replay_csgo.bat [demo.dem] [followUserID]` — полный цикл без
ручных шагов (как `make_replay.bat` для CS 1.6):

```
=== [1/4] csgo_extract  демка → JSON: игроки (origin/angles/velocity/health/team)
                         + POV-камера (source 5; авто или --follow N)
                         + события kill / round (монтажная сетка)
=== [2/4] source1_tex   карта → текстуры: свой VMT/VTF-декодер
                         (pak-лумп карты + pak01_dir.vpk установки)
=== [3/4] Blender        сцена: карта (свой BSP v17-v21 импортёр, включая
                         displacement-ландшафт), текстуры, игроки-кубы с ключами,
                         камера, маркеры kill/round/sound + маячки
=== [4/4] demos\csgo_replay.blend ✅
```

**Собственный импортёр Source BSP** (`blender/bsp_source_import.py`):
вершины/грани/UV по texinfo, текстуры через `core/tools/source1_tex.py`
(VMT → `$basetexture` → VTF: DXT1/3/5 и RGBA-форматы; чистый Python +
небольшой нативный VPK-ридер pylib (MIT, REDxEYE — см.
`core/tools/source1_tex.py` шапку)), displacement-террейн из LUMP_DISPINFO/
DISP_VERTS. Проверено на de_dust2 (CS:GO legacy): 229k вершин / 301k полигонов,
27 материалов, 42 PNG-текстуры, A-site пола — на месте.

События в JSON (`"events"`): `type: kill` (subject/target/origin убийцы),
`type: round` (тик/время старта раунда). Те же маркеры пишутся в After Effects
через `ae/import_camera.jsx` — готовая сетка для монтажа: раунды = секции,
килы = точки смены плана.

Проверка на демке пользователя (demo-de_dust2-14_54_10.dem, 202 МБ, GOTV 2018):
заголовок и первые 70% демки разбираются: **112 248 кадров, 20 сущностей/кадр**
(имена, team, HP, origin, angles) → `.blend` собран ✅. В последних 27 МБ файла
есть битое поле размера (0x6ADE6000 = 1.79 ГБ в LE), вызывавшее VirtualAlloc OOM:
обходной приём — обрезать демку (битое поле в хвосте) и прогнать экстрактор:

```
python -c "open(r'out.dem','wb').write(open(r'demo.dem','rb').read(150_000_000))"
```

Версии экосистемы: демопарсер2 (0.34..0.42) потерял Source1 (`Source1DemoError`),
go.dev и pacman-зеркала в этой сети режутся; MSYS2 (GitHub-архив) → pacman →
`mingw-w64-x86_64-go 1.27.3` — сборка прошла именно так.

Известные ограничения на большой демке (202 МБ, 2018, GOTV): demoinfocs v3 запрашивает
~1.8 ГБ одним блоком (commit limit виртуальной памяти, errno 1455) — на слабых
машинах/маленьком pagefile падает с OOM. Лечение: больше своп/коммита либо
другая демка (современные CS:GO-демки такого выделения не требуют).

```
demo.dem ── source1/go_extract/csgo_extract.exe (Go, demoinfocs v3) ──> json
    ├──> replay_import.py / blender_import.py / max_import.py (общий JSON)
    ├──> "events": kill/round → маркеры Blender + AE (монтажная сетка)
карта:     собственный импортёр blender/bsp_source_import.py (v17-v21,
           displacement, VPK/VTF-текстуры) — без аддонов, работает в Blender 5;
           опционально SourceIO (только Blender 4.x) / BSPSource→VMF→Wall Worm
модели:    Crowbar (MDL→SMD), импорт как обычно; плейсхолдеры — автоматически
камера:    POV-слежение (source 5) или --follow USERID; HLAE BVH
кино-набор: csgosetup\ (movie.cfg + mirv_streams пресет HLAE: normal/depth-EXR/
           matte ent/wrld) и cssetup\ (CS:S: только screen record) — см.
           вики advancedfx Source:mirv_streams
CS2:       тот же готовый конвейер, но через demoparser2 (csgo_demo2json.py)
```

```
pip install demoparser2
python source1\csgo_demo2json.py demo.dem out.json --follow 2
blender --background --python blender\blender_import.py -- --json out.json --out scene.blend
```

Или одной командой (проверяет зависимости, конвертирует и гонит Blender):
```
python source1\run_pipeline.py demo.dem --out scene.blend --follow 2 --normalize
```

Поля на игрока за тик: origin (x,y,z), angles (pitch/yaw/roll в нашем виде),
velocity, health, team, место (placeholder). **Нет sequence/frame** —
анимации персонажей в CS:GO-демках не записываются (в отличие от GoldSrc):
для кино-сцен используйте SourceFilmmaker-совместимые репозитории или
мокап-анимации на root-объектах (движение/углы — точные).

Углы CS:GO: pitch вниз-положительный, yaw от −X против часовой; конвертер
приводит к нашему виду (pitch «вверх+», yaw GoldSrc-стиля). Если ориентация
в DCC получится зеркальной — поменяйте знаки в `csgo_demo2json.py` (строки
`pitch = float(...)` / `yaw = float(...)`).

## Общий JSON: мост между Blender / 3ds Max / After Effects

Все ветки (GoldSrc + Source 1) говорят на одном JSON (`camera[]` +
`frames[]`), поэтому «круг» замкнут одним форматом:

| Шаг | Инструмент |
|---|---|
| Демка → JSON | `demo_extract` (CS 1.6) / `csgo_demo2json.py` (CS:GO/CS2) / `css_demo2json.py` (CSS) |
| Blender | `blender_import.py --json ...` (камера+игроки+NLA: параметры ниже) |
| 3ds Max | `max_import.ms` (rollout) → тот же JSON |
| After Effects | `ae/import_camera.jsx` → выбирает JSON → камера с ключами в AE |
| Blender → AE | `blender_import.py --export-camera-json cam.json` + `ae/import_camera.jsx` |
| Экспорт геометрии (Blender↔Max) | FBX (встроен в оба DCC) |

### Параметры импорта (`blender_import.py`)

```
--scale 0.0254         GoldSrc-дюймы → метры (для Source-ветки тоже работает)
--fps 30               FPS таймлайна
--cam-step N           прореживание сэмплов камеры (реальные демки ~100-128/с)
--interp linear|bezier keyframes: linear = честное движение, bezier = плавное (default)
--normalize            центрировать сцену (среднее камеры+игроков = глубокая точка)
--export-camera-json P сохранить трек камеры для AE (import_camera.jsx)
--seq-map '0:idle,1:run'  (GoldSrc) sequence → Action для NLA
--bvh camera.bvh       импорт BVH из HLAE вместо JSON-ключей
--tick-rate 100        тиков в секунду демки (128 для CS:GO!)
```

`csgo_demo2json.py` дополнительно: `--start-tick N --end-tick N --tick-step N
--follow USERID`.

### Настройки перед записью демки (CS:GO) для чистого результата

```c
sv_cheats 1            // в одиночной игре: отключаем HUD/сглаживание
cl_drawhud 0
r_drawviewmodel 0      // кино-кадры без модели оружия
fps_max 300            // демо-таймкод с высокой частотой кадров не зависит от FPS
mat_motion_blur 0      // размытие добавляем в DCC/АE, а не в движке
host_timescale 1
```
Запись: `record имя_демки` (заканчивать `stop`), либо в меню на наблюдателе.

## Concises CS:S

Полноценного per-tick позиционного парсера под CSS нет в публичном доступе
(демки CSS = тот же Source-1 .dem, но demoparser2 их не поддерживает).
Состав рабочего конвейера:

1. **События**: `demoinfogo demo.dem -X -stdout` — JSON событий
   (`source1/css_demo2json.py` — обёртка в наш JSON).
2. **Камера**: HLAE (поддерживает CSS только в режиме экранной записи:
   `mirv_streams record screen`, см. `cssetup\`) — BVH → `--bvh` в blender_import.
3. **Карта**: наш импортёр Source BSP (CS:S тоже v20!) — `bsp_source_import.py`.
4. **Модели**: Crowbar (Source MDL), импорт как обычно.

Честно: плотный трекинг позиций для CSS — открытая TODO; если найдутся
публичные Python-парсеры (или демка CSS для reverse-а) — добавлю
`css_demo2json.py` полный per-tick режим.

## CS2 (Source 2)

`demoparser2` поддерживает и CS2; камера и анимации — те же ограничения.
Карты/модели: SourceIO (CS2-поддержка частичная) / движковые инструменты.
