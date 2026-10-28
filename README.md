# CS 1.6 → Blender / 3ds Max: демо-конвейер (cs16db)

Перенос демок Counter-Strike 1.6 (GoldSrc) в Blender и 3ds Max:
демо → JSON (позиции, углы, анимация сущностей) → сцена.

```
[demo.dem] ── demo_extract (C++, HLDemo) ──> [demo.json]
                                                ├──> Blender: blender_import.py (карта+модель — аддоны, камера+NLA — скрипт)
                                                └──> 3ds Max:  max_import.py / max_import.ms
```

**Кино-сборка для записи демок прямо в игре** (MetaMod+AMXX, кнопки записи/
камера/slow-mo/боты, HLTV-рекордер): см. `cs16setup\README.md` →
`cs16setup\install_demo_toolkit.bat` (ставится в обе установки CS 1.6).

## Состав

| Путь | Что это |
|---|---|
| `core/demo_extract/` | Утилита ядра (C++17 + HLDemo), `demo_extract.exe` |
| `core/extern/HLDemo` | HLDemo (YaLTeR) — структурный парсер демок GoldSrc |
| `core/extern/` | Референсные реализации: hldemo-rs, py-goldsrc-demo, dem-rs, xash3d-fwgs |
| `core/tools/` | Генератор синтетической демки, зонды формата, заглушка JSON |
| `core/build.bat` | Сборка ядра (MSVC Build Tools + Ninja) |
| `blender/blender_import.py` | Импорт JSON в Blender: камера, root-объекты игроков, NLA |
| `blender/replay_import.py` | Сборка полной сцены демки: BSP-карта + игроки + камера + скайбокс + NLA |
| `blender/bsp_import.py` | Свой импортёр GoldSrc BSP v29/30 + WAD3-текстуры + lightmap (без аддонов) |
| `blender/bsp_source_import.py` | Свой импортёр Source 1 BSP v17-v21 (CS:GO/CS:S): геометрия + displacement |
| `core/tools/source1_tex.py` | Текстуры Source-карт: VMT→VTF→PNG (pak BSP + VPK игры) |
| `core/tools/vtf_decode.py` | Python-декодер VTF (DXT1/3/5, RGBA-семейство) |
| `core/tools/vpk.py` | VPK v2 reader (fallback; нативный ридер — pylib, MIT REDxEYE — предпочтителен) |
| `blender/smd_import.py` | Импорт SMD-арматур и Actions игроков |
| `make_replay.bat` | «Одна кнопка»: демка → Blender-сцена целиком |
| `max/max_import.py`, `max/max_import.ms` | Импорт JSON в 3ds Max (pymxs) + обёртка MAXScript |
| `audit/AUDIT.md` | Отчёт аудита инструментов (выбор/отклонения) |
| `source1/` | Ветка Source 1: CS:GO/CSS демки (demoinfogo / собственный Go-экстрактор) → общий JSON |
| `source1/go_extract/` | `csgo_extract.exe` (Go + demoinfocs v3): игроки/камера/события CS:GO |
| `csgosetup/` | Кино-набор CS:GO: movie.cfg + пресет HLAE `mirv_streams` (normal/depth-EXR/matte) |
| `cssetup/` | Кино-набор CS:S: movie.cfg + экранная запись HLAE (`mirv_streams record screen`) |
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

**Одна кнопка** (карта + текстуры + lightmap + игроки + анимации/набор NLA +
камера + скайбокс + маркеры событий):

```
make_replay.bat demo.dem        (или просто перетащить .dem на файл)
# результат: demos\replay_export.blend
```

Конвейер (все этапы внутри batch):

1. `demo_extract.exe demo.dem core\tests\replay_work\demo.json` — разбор демки;
2. `core\tools\mdl2smd.py` — декомпиляция моделей игроков из
   `cstrike\models\player\*` в SMD + анимации + манифест;
3. `blender\replay_import.py` — сборка сцены:
   - карта: собственный BSP v29/30 импортёр (`blender\bsp_import.py`) —
     геометрия, UV по texinfo, текстуры (вшитые + внешние WAD3
     `cstrike\*.wad`/`valve\*.wad`), lightmap → vertex colors `LM`,
     скип `sky`-граней (их заменяет скайбокс);
   - скайбокс из `gfx/env/<skyname>{up,dn,lf,rt,ft,bk}.tga` (skyname из
     worldspawn BSP) — эмиссионные плоскости, только камера;
   - игроки: SMD-арматуры + NLA-полосы по прогонам `sequence`
     (учитываются fps и cycle каждой анимации), привязка локального игрока
     (listen-сервер) к треку `source: 0` (позиция ног);
   - камера: keyframes по **времени** (`time`), выбор источника
     `2 → 1 → 4 → 0` (см. ниже), FOV через `lens`, интерполяция LINEAR,
     сплайн-путь `CamPath` по `--cam-spline`;
   - события: sound/kill/round → timeline-маркеры + beacons.

Подробнее о камере: `source` 0 = CLIENT_DATA-кадр (ноги игрока, +28 юнитов),
1 = svc_clientdata, 2 = RefParams из префикса кадра (взгляд рендера), 4 = HLTV
viewentity (позиция объекта; для игроков +28, для map-камер — как есть).
В старых сценариях остался `blender_import.py` (только камера/игроки из JSON):

```
blender --background --python blender\blender_import.py -- \
    --json out\qqq.json --out scene.blend --mirror-yaw --flip-pitch --cam-step 20
```

Шаги полного продакшн-пайплайна в Blender:

1. **Карта**: `make_replay.bat` уже импортирует BSP/WAD сам — аддоны не нужны.
   Для CS:GO-карт (SourceIO) по-прежнему нужен Blender 4.x.
2. **Модель**: MDL→SMD делает `core\tools\mdl2smd.py` (9 моделей CS 1.6,
   ~103 анимации каждая).
3. **Камера**: из JSON; для HLAE-пути остаётся BVH (`--bvh camera.bvh`).
4. **Анимация**: NLA-полосы строятся автоматически по `sequence`/`cycle`.

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

- **Blender 5.0 + `--factory-startup` = чёрные рендеры** в фоновом режиме на
  этой машине (EEVEE/Workbench/Cycles): запускайте без флага (make_replay так
  и делает). Шум аддонов (BY-GEN/Auto-Rig-Pro) в лог не влияет на результат.
- **EEVEE-свет**: в headless-режиме SUN-источники не освещают (физические
  падение point-света 1/r²); в сцену добавлен риг `Fill` (point у камеры) +
  Sun — итоговое освещение крутится как обычно в редакторе.
- **WAD-текстуры `cs_dust.wad`** в обеих установках содержат повреждённые
  инструментом lump'ы (мусор в именах, шумный пиксельный поток с полной
  палитрой). Импортёр выводит их как есть; вшитые в BSP текстуры
  (например `csSandWallBTA`) корректны. Для замены подложите свои `.tga`
  в `map_tex/`.
- HLTV-демки `desur1` (de_survivor): со второй половины записи битстрим
  рассинхронизируется (пакеты `packetentities` рвутся); камера
  восстанавливается по истории `svc_setview` (source 4), позиция
  статичного map-камера берется из первого появления сущности.
  Спавнстаты с невалидными координатами/индексами отфильтровываются.
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
