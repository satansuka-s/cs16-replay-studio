-- 3ds Max branch launcher: runs the pymxs importer from MAXScript.
-- Usage:
--   1) In 3ds Max, open MAXScript > Run Script... > max_import.ms
--   2) Set the demo JSON path in the rollout, press Import
--
-- Requires max_import.py next to this file. 3ds Max 2022+ ships Python support.
-- If Python is unavailable, use max_import.py directly via MAXScript:
--     python.ExecuteFile @"C:\dev\cs16db\max\max_import.py"
(
    global Cs16MaxRollout
    rollout Cs16MaxRollout "CS 1.6 Demo Import" width 420
    (
        edittext edt_json "JSON:" text:"C:\\dev\\cs16db\\core\\tests\\stub.json" width:380
        spinner spn_scale "Scale:" range:[0.001, 100.0, 1.0] type:#float width:120
        spinner spn_fps "FPS:" range:[1, 240, 30] type:#integer width:120
        checkbox chk_yaw "Mirror Yaw" checked:true
        checkbox chk_pitch "Flip Pitch" checked:true
        checkbox chk_cam "Camera only" checked:false
        button btn_run "Import demo" width:160 height:28

        on btn_run pressed do
        (
            local jsonPath = edt_json.text
            if not (doesFileExist jsonPath) do
            (
                messageBox ("File not found: " + jsonPath)
                return undefined
            )
            local opts = "--json=\"" + jsonPath + "\" --scale=" + (spn_scale.value as string) + \
                        " --fps=" + (spn_fps.value as string)
            if chk_yaw.checked do opts += " --mirror-yaw"
            if chk_pitch.checked do opts += " --flip-pitch"
            if chk_cam.checked do opts += " --cam-only"
            local pyPath = (getFilenamePath (getThisScriptFilename())) + "max_import.py"
            -- feed options via environment + script arg
            setEnv "MAX_IMPORT_JSON" jsonPath
            setEnv "MAX_IMPORT_OPTIONS" opts
            python.ExecuteFile pyPath
            messageBox "Import finished. Check MAXScript listener output."
        )
    )
    if Cs16MaxRollout != undefined do closeRolloutFloater (cui.getFloaterByName "CS16")
    createDialog Cs16MaxRollout 440 240
)
