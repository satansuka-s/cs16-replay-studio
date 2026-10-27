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
- HLTV-записи (например, `2008-de_inferno.dem`) не содержат entity-потока —
  из них извлекается только камера; сущностный трекинг работает на обычных
  записях игрока (и на синтетической тестовой демке).
- Демки нового формата («типа 100», запись 2024+) разбираются частично
  (камера и ранние сообщения), подробности в `audit/AUDIT.md`.

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

## Известные ограничения

- HLTV-демки: сущностей в потоке нет (архитектура HLTV): извлекается только камера.
- «Фреймы типа 100» (запись новыми клиентами 2024+): парсятся до момента
  переключения формата (камера доступна); полный новый формат — TODO.
- Имена игроков: userinfo не проецируется на entity-индексы.
- NLA: имена Actions должны совпадать с `--seq-map` (модель: `reference.smd`).
