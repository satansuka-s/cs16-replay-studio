# HLAE (Half-Life Advanced Effects) — установлено и готово

**Версия:** 2.192.10 (2026-10-24), официальный релиз с GitHub advancedfx.
**Расположение:** `D:\HLAE\` (портативно, zip).

Установленный комплект:

| Компонент | Путь | Для чего |
|---|---|---|
| hlae.exe | `D:\HLAE\hlae.exe` | лаунчер (GUI + CLI, см. ниже) |
| AfxHookGoldSrc.dll | `D:\HLAE\` | **CS 1.6**: mirv_* кино-команды, рендер-пассы, запись видео/Af = `hlae\cs16.bat` |
| AfxHookSource.dll | `D:\HLAE\` | **CS:GO**: mirv_streams (normal/depth-EXR/matte/HUD-слои) = `hlae\csgo.bat`; **CS:S**: screen-record = `hlae\css.bat` |
| AfxHookSource2.dll | `D:\HLAE\` | CS2 (запас) |
| ffmpeg.ini | `D:\HLAE\ffmpeg\ffmpeg.ini` | указывает на ваш `D:\HLAE FFMPEG\ffmpeg\bin\ffmpeg.exe` — FFMPEG-энкодинг (`afxFFmpeg*`) в стримах |

## Запуск одной командой

```
hlae\cs16.bat                CS 1.6  (Build 4554; аргументом — любой путь к hl.exe)
hlae\csgo.bat                CS:GO  legacy (мост с Steam Offline)
hlae\css.bat                 CS:S    (hl2.exe -game cstrike, screen-record режим)
```

Во всех случаях применяется наш `movie.cfg` (кино-клавиши F4–F11 + пресеты
`mirv_streams_movie.cfg` / `mirv_hud_separate.cfg` / `preset_cinematic.cfg`).

## CLI-поддержка (для автоматизации)

HLAE полностью управляется из командной строки (см. вики «HLAE Interfaces»):
`-csgoLauncher`, `-afxHookGoldSrc`, `-customLoader` + `-noGui -autoStart`.
Лаунчеры выше используют именно этот интерфейс — можно вызывать из
batch/автоматизации без ручного GUI.

## Важно

- Для чистых пассов двигайтесь так: запись стримов HLAE → файлы
  `csgo_movie` (mono/exr/png) → композит в AE; либо демка → JSON →
  Blender-сцена (наши импортёры) для «невозможных» ракурсов и AOV.
- VAC: HLAE — технически хук; только локальные/кино-сессии
  (Steam Offline), не заходите на VAC-серверы.
- FFMPEG: путь уже прописан; проверить: `ffmpeg -version` в консоли
  (используется `D:\HLAE FFMPEG\ffmpeg\bin\ffmpeg.exe`).
