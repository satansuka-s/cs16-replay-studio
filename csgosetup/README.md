# CS:GO кино-набор (csgosetup)

Аналог `cs16setup` для CS:GO (Source 1, в т.ч. legacy-сборка 2023 от Valve):
готовый `movie.cfg` + пресет `mirv_streams` (HLAE) для кино-записи.

## Установка

```
install_csgo_kit.bat ["D:\путь\к\csgo"]
```
Создаёт бэкапы `movie.cfg` → `.cs16db.bak`, ставит наши конфиги и подхватывает
их в `autoexec.cfg`. Откат: `restore_csgo_kit.bat`.

## Горячие клавиши (после `exec movie.cfg`)

| Клавиша | Действие |
|---|---|
| F6 | `record csgo_movie` — запись демки (для пайплайна) |
| F7 | `stop` — конец демки |
| F8 | `demoui 1` — просмотр демок |
| F9 | `exec mirv_streams_movie` — собрать кино-стримы (HLAE) |
| F10 | `mirv_streams record end; host_framerate 0` — стоп записи |

Чистота кадра зашита в `movie.cfg`: `cl_drawhud 0`, `r_drawviewmodel 0`,
`mat_motion_blur 0`, `fps_max 300`, `sv_cheats 1`.

## mirv_streams (HLAE / advancedfx)

Полную документацию см. [вики advancedfx (mirv_streams)](https://github.com/advancedfx/advancedfx/wiki/Source%3Amirv_streams).

Пресет `mirv_streams_movie.cfg` собирает:
- `main`  — композитный рендер (FFMPEG YUV420P),
- `depth` — глубина как OpenEXR (`depthVal 7`..`depthValMax 8192`, 23 бит)
  для DOF/фокус в After Effects,
- `ent` — матте сущностей (изоляция игроков),
- `wrld` — матте мира.

Запись: `host_framerate 60; host_timescale 0; mirv_snd_timescale 1;
mirv_streams record start` … `mirv_streams record end; host_framerate 0`.
Файлы окажутся в папке `csgo_movie` рядом с игрой.

**Важно**: `mirv_*` команды доступны только при запуске CS:GO через HLAE
(hlae.org). Без HLAE работают только F6/F7/F8 и движковые настройки.

## Конвейер «демка → Blender»

```
source1\make_replay_csgo.bat demo.dem [followUserID]
```
→ `demos\csgo_replay.blend`: карта (свой Source-BSP/VPK/VTF-импортёр),
игроки, камера POV (source 5), маркеры kill/round — и `demo.json`
для After Effects (`ae/import_camera.jsx`).

Файлы набора:
- `movie.cfg` — базовая клавиатура (F6/F7/F8/F9/F10),
- `mirv_streams_movie.cfg` — стримы normal/depth-EXR/matte (F9),
- `mirv_hud_separate.cfg` — **отдельный HUD-слой** (main без HUD +
  hudBlack/hudWhite — формула композитинга в шапке файла; туториал:
  advancedfx «Tutorial: CS:GO Separate HUD Stream»),
- `preset_cinematic.cfg` — стиль «кино» (DoF, плавная камера, fps 60).

Пресеты «хоррор/ночь» честно: в CS:GO день-в-ночь делается
командами из вики advancedfx «How to change demos from day to night as of
early 2017» (mat_tonemapping + небо); готовые LUT-тонировки мы не включаем
— цветокоррекцию лучше вести в AE по нашим пассам (depth/matte уже есть).
