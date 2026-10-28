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
CS:S `.dem` (Source 1, HL2DEMO) разбирается полностью:
- **позиции всех игроков per tick** — наш `css_extract.exe` на базе
  css-demo-parser (sockfish/bamtna, MIT): origin/angles/velocity/team/health
  + камера POV (source 5) + kill/round события; сборка —
  `source1\build_css_extract.bat`, вызов — `source1\css_demo2json.py`.
- режиссёрская камера кино-сцен — через HLAE BVH (см. выше),
- карта — наш импортёр Source BSP или SourceIO 5.5.4+ (Blender 5).
