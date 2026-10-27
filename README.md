# CS 1.6 → Blender / 3ds Max: демо-конвейер (cs16db)

Перенос демок Counter-Strike 1.6 (GoldSrc) в Blender и 3ds Max:
демо → JSON (позиции, углы, анимация сущностей) → сцена.

```
[demo.dem] ── demo_extract (C++, HLDemo) ──> [demo.json]
                                                ├──> Blender: blender_import.py (карта+модель — аддоны, камера+NLA — скрипт)
                                                └──> 3ds Max:  max_import.py / max_import.ms
```

## Состав

| Путь | Что это |
|---|---|
| `core/demo_extract/` | Утилита ядра (C++17 + HLDemo), `demo_extract.exe` |
| `core/extern/HLDemo` | HLDemo (YaLTeR) — структурный парсер демок GoldSrc |
| `core/extern/` | Референсные реализации: hldemo-rs, py-goldsrc-demo, dem-rs, xash3d-fwgs |
| `core/tools/` | Генератор синтетической демки, зонды формата, заглушка JSON |
| `core/build.bat` | Сборка ядра (MSVC Build Tools + Ninja) |
| `blender/blender_import.py` | Импорт JSON в Blender: камера, root-объекты игроков, NLA |
| `max/max_import.py`, `max/max_import.ms` | Импорт JSON в 3ds Max (pymxs) + обёртка MAXScript |
| `audit/AUDIT.md` | Отчёт аудита инструментов (выбор/отклонения) |
| `source1/` | Ветка Source 1: CS:GO/CSS демки (demoparser2 / demoinfogo) → общий JSON |
| `demos/` | Сюда класть `.dem` |

## 1. Сборка ядра (Windows)

Требуется: CMake ≥ 3.16, MSVC Build Tools (cl.exe), Git, Ninja (входит в Build Tools).

```
core\build.bat
# результат: core\demo_extract\build\demo_extract.exe
```

## 2. Извлечение данных из демки

```
demo_extract <demo.dem> <out.json> [tick_interval] [--cam-only] [--max-clients N]

demo_extract demos\synthetic.dem out\synthetic.json 1
demo_extract D:\Counter-Strike Build 4554\cstrike\qqq.dem out\qqq.json --cam-only
```

Формат JSON: поля `camera[]` (tick, time, origin, viewangles, fov, source) и
`frames[]` (по тикам: entity: index, player, origin, angles, velocity,
modelindex, sequence, frame, animtime, framerate, body, cycle).

Единицы: **GoldSrc = дюймы, Z-up**; углы — pitch/yaw/roll в градусах.
`source`: 0 = CLIENT_DATA-фрейм демки, 1 = svc_clientdata, 2 = RefParams из префикса netmsg.

Примечания:
- Игроки: entity index 1..maxclients.
- **Proto 47 vs 48**: серверы/демки двух поколений используют разные layouts
  для packet entities: классический (`MSG_ReadDeltaEntity`, proto ≤ 47) и
  GoldSrc-incremental (proto 48+). `demo_extract` выбирает режим автоматически
  по `net_protocol` в заголовке демки.
- **HLTV-демки (напр. `2008-de_inferno.dem`)** несут *полный* delta-поток
  сущностей (`svc_deltapacketentities`) + spectator-камеру — см. «HLTV-записи»
  ниже. Классик-таблицы HLTV не передают: используются встроенные
  `delta.lst` (CS 1.6, Valve), которые можно переопределить env `CS16DB_DELTA_LST`.
- Демки нового формата («типа 100», запись 2024+) разбираются частично
  (камера и ранние сообщения), подробности в `audit/AUDIT.md`.

## HLTV-записи: что извлекается

Проверено на `2008-de_inferno.dem` (HLTV.org, proto 47) и свежезаписанных
демках (`desur1-*.dem`, proto 48):

| Данные | Статус |
|---|---|
| Сущности (игроки миры): origin, angles, sequence, frame, animtime | ✅ есть (proto 47: классик; proto 48: GS) |
| Камера-зрителя: позиция (из svc_clientdata) + ориентация (от viewentity) | ✅ `source: 4`, движется по демке |
| Классическая камера (как у записей игрока: CLIENT_DATA/RefParams) | ❌ HLTV не пишет (нулевые поля) |
| «Режиссёрский» камерный трек (как в HLAE-экспорте) | ❌ **в формате отсутствует**: движение камеры HLTV генерирует локально при проигрывании (svc_director несёт только тексты/статус, см. `audit/AUDIT.md`) |

Пример из `desur1` (proto 48, 178 сущностей/кадр):
```
idx 1 player origin [2016.2, 835.3, 136.1] angles [2.7, 170.3, 0] seq 81
idx 4 player origin [1902.5, -2775.2, 0]    angles [0.4, 274.8, 0] seq 13
```

## 3. Ветка Blender

```
# камера + игроки из JSON:
blender --background --python blender\blender_import.py -- \
    --json out\qqq.json --out scene.blend --mirror-yaw --flip-pitch --cam-step 20

# параметры:
#   --scale 0.0254      GoldSrc дюймы -> метры (по умолчанию 0.0254)
#   --fps 30            кадров в секунду результирующего таймлайна
#   --mirror-yaw --flip-pitch   коррекция знаков углов (подбирается на тесте)
#   --cam-step N        прореживание сэмплов камеры (реальные демки дают ~100/с)
#   --seq-map "0:idle,1:run"    сопоставление sequence -> Action
#   --bvh camera.bvh    вместо ключей — импорт BVH из HLAE
#   --map-bsp de_map.bsp   импорт карты (нужен аддон GoldImporter / io_mesh_bsp)
```

Шаги полного продакшн-пайплайна в Blender:

1. **Карта**: File → Import → BSP (аддон GoldImporter — доступен вне GitHub,
   либо `blender_io_mesh_bsp` (andyp123), либо SourceIO legacy). Масштаб 0.0254.
2. **Модель**: Crowbar: `mdl → smd/ref/smd`; импорт SMD через
   `cs-smd-blender-importer` (или Blender Source Tools). Анимации появятся как Actions.
3. **Камера**: `--bvh` могbe.  Из HLAE: AfxHookGoldSrc → export camera BVH →
   импорт `File > Import > BVH` или аргумент `--bvh`.
4. **Анимация**: `blender_import.py` строит NLA-полосы по `sequence` (см. `--seq-map`).

## 4. Ветка 3ds Max

1. **Карта**: BSP → VMF: `BSPSource (bspsrc)`: `java -jar bspsrc.jar -game cstrike de_map.bsp`,
   затем импорт VMF через Wall Worm (`Wall Worm > Import VMF`).
2. **Модель**: Wall Worm MDL Loader (прямой MDL-импорт) или Crowbar → SMD →
   `NeilJed 3DSMax-SMD-Importer`.
3. **Камера**: BVH из HLAE: `File > Import > Motion Capture (BVH)`.
4. **Анимация**: запустить `max\max_import.ms` в 3ds Max (rollout), либо:

```maxscript
python.ExecuteFile @"C:\dev\cs16db\max\max_import.py"
-- с переменной окружения MAX_IMPORT_JSON или --json=... в аргументах
```

Скрипт создаёт FreeCamera с линейными ключами и Point-хеперы игроков;
в user-свойства записывается таймлайн sequence для последующей сборки MotionMixer.

## 5. Тесты

```
core\tests\run_tests.bat
```

1. Сборка ядра.
2. Генерация синтетической демки `demos\synthetic.dem` (2 игрока, дельта-таблицы,
   baselines, packetentities, камера) → `demo_extract` → JSON: сверяются
   золотые значения (origin/sequence/frame/cycle).
3. Заглушка `core\tests\stub.json` (10 кадров) → импорт в Blender headless:
   `stub.blend` создаётся без ошибок.
4. Прогон `demo_extract` по реальным демкам из `demos/` (если есть): доклад в консоль.

## Кастомные карты, скины, текстуры (серверы с модифицированными файлами)

Демка **не содержит сами файлы** ресурсов — только сетевое состояние и
(иногда) список имён. Файлы нужно брать из клиентской копии игры
(папка `cstrike/`, включая `cstrike/custom/`) или с сервера (fastdl).
Пайплайн таких сцен такой же, как для «родных», с учётом:

1. **Инвентарь ресурсов** — что сервер вообще использует:
   - `python core\tools\scan_resources.py "D:\Counter-Strike Build 4554"`
     сканирует установку и помечает `CUSTOM` всё, что не похоже на ванильный
     CS 1.6 (модели, карты, звуки, WAD, TGA).
   - `demo_extract` кладёт в JSON секцию `resources` (models/sounds/sprites/
     skins/generic) — если демка несёт `svc_resourcelist` с именами
     (в записях встречается не всегда).

2. **Карта (.bsp)** — импорт как обычно (GoldImporter / io_mesh_bsp в Blender;
   BSPSource→VMF→Wall Worm в Max). Текстуры:
   - если вшиты в BSP: `python core\tools\bsp_tex_extract.py map.bsp out_dir` → TGA;
   - если во внешних WAD: `python core\tools\wad_extract.py textures.wad out_dir` → TGA.
   Пример: у de_survivor пустой texture-lump — текстуры берутся из
   `cstrike.wad` (123 шт) и соседних WAD.

3. **Модели/скины (.mdl)** — кастомные декомпилируются так же: Crowbar
   (MDL→SMD+SMD textures), далее стандартная ветка (cs-smd-blender-importer /
   BlenderSourceTools / NeilJed). Crowbar также извлекает .wav из моделей.

4. **Связывание ресурсов с сущностями** — `modelindex` из JSON сущностей
   отображается на список `resources.models` (порядок = precache-порядок),
   а имена — на файлы `models/*.mdl`. После декомпиляции нужных MDL просто
   импортируйте их и сопоставьте с root-объектами игроков.

## Известные ограничения

- «Режиссёрская» камера HLTV: трек отсутствует в файле (генерируется локально);
  доступна spectator-камера (`source: 4`: позиция зрителя + ориентация viewentity).
- В старых HLTV-записях (proto 47) часть сущностей вне FOV режиссёра может
  отсутствовать (PVS-фильтрация на ретрансляторе).
- «Фреймы типа 100» (запись новыми клиентами 2024+): парсятся до момента
  переключения формата (камера доступна); полный новый формат — TODO.
- Имена игроков: userinfo не проецируется на entity-индексы.
- NLA: имена Actions должны совпадать с `--seq-map` (модель: `reference.smd`).
- Синтетический генератор пишет net_protocol 48 (современная схема пакетов);
  для записи классических proto-47 пакетов (MSG_ReadDeltaEntity) используйте
  реальные демки или правку `core/tools/make_demo.py` `NET_PROTO`.
- Инструменты анализа формата: `core/tools/{probe_demo,svc_probe,prefix_probe,
  batch_probe,director_probe,decode_bits}.py` — см. комментарии в голове файлов.
