# CS:S кино-набор (cssetup)

То же, что `csgosetup`, но для Counter-Strike: Source (Source 2009).

## Установка
```
install_css_kit.bat ["D:\путь\к\Counter-Strike Source"]
```
Бэкапы `movie.cfg`/`mirv_screen_record.cfg` → `.cs16db.bak`, автоexec
подхватывает `movie.cfg`.

## Горячие клавиши
| Клавиша | Действие |
|---|---|
| F6 | `record css_movie` — демка для пайплайна |
| F7 | `stop` |
| F8 | `demoui 1` |
| F9 | `exec mirv_screen_record` — экранная запись HLAE |

## Ограничения CS:S (важно)

В отличие от CS:GO, полный `mirv_streams` (depth/matte/OpenEXR) у CS:S
**отсутствует** — вики advancedfx прямо перечисляет CS:S в списке игр с
единственной возможностью *screen recording*: при закрытой консоли пишется
экран (через детур `startmovie`) с заданным `host_framerate`.

Пример записи (HLAE):
```
host_framerate 1200; mirv_streams record fps 1200; mirv_streams record start
// ... поиграть/продемонстрировать (консоль закрыта) ...
mirv_streams record end; host_framerate 0
```
FFMPEG-профили (`afxFFmpegYuv420p`) — если ffmpeg установлен установщиком HLAE.

## Демки CS:S в конвейер
CS:S `.dem` (Source 1, netproto 6/7) парсится:
- события (kills/раунды) — `source1/css_demo2json.py` (обёртка над demoinfogo),
- позиции per-tick — TODO (открытого парсера плотного трекинга CS:S нет;
  камеру кино-сцен делайте через HLAE BVH, карту — нашим импортёром, см. ниже),
- карта — наш импортёр Source BSP (`make_replay_csgo.bat --game` или в
  Blender: `blender/bsp_source_import.py`; текстуры: `core/tools/source1_tex.py`).
