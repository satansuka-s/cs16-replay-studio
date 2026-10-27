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

## Конвейер CS:GO

```
demo.dem ── source1/csgo_demo2json.py (demoparser2) ──> json
    └──> blender_import.py / max_import.py (общая ветка, тот же JSON)
карта:     SourceIO (Blender) / BSPSource→VMF→Wall Worm (Max)
модели:    Crowbar (MDL→SMD), импорт как обычно
камера:    --follow USERID (наш конвертер) или HLAE BVH
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

## Конвейер Counter-Strike: Source

Полноценного per-tick позиционного парсера под CSS нет в публичном доступе
(демки CSS = тот же Source-1 .dem, но demoparser2 их не поддерживает).
Состав рабочего конвейера:

1. **События**: `demoinfogo demo.dem -X -stdout` — JSON событий
   (`source1/css_demo2json.py` — обёртка в наш JSON).
2. **Камера**: HLAE (поддерживает CSS) — BVH → `--bvh` в blender_import.
3. **Карта**: SourceIO / Wall Worm (те же шаги, что CS:GO).
4. **Модели**: Crowbar (Source MDL), импорт как обычно.

Честно: плотный трекинг позиций для CSS — открытая TODO; если найдутся
публичные Python-парсеры (или демка CSS для reverse-а) — добавлю
`css_demo2json.py` полный per-tick режим.

## CS2 (Source 2)

`demoparser2` поддерживает и CS2; камера и анимации — те же ограничения.
Карты/модели: SourceIO (CS2-поддержка частичная) / движковые инструменты.
