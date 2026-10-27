/* After Effects import script: camera from cs16db JSON (demo_extract / csgo_demo2json).
 *
 * Creates a 3D camera with keyframed position/orientation/FOV.
 * Conventions same as the rest of the pipeline:
 *   - coordinates: GoldSrc/Source units (inches), Z-up
 *   - angles: pitch/yaw/roll degrees (pitch up positive)
 * This script converts to AE conventions (X/Y/Z, Y-up-ish via orientation math).
 *
 * Usage in After Effects:
 *   File > Scripts > Run Script File... > import_camera.jsx
 *   It will ask for the JSON file (e.g. demos/demo_cam.json).
 *
 * Tip: our pipeline centers everything on 0,0,0; AE camera looks down -Z,
 * so set the AE camera to point at the scene center (option below).
 */
(function () {
    // ---- settings ----
    var CAMERA_NAME = "DemoCamera";
    var FRAME_RATE = 30;          // fps of composition
    var POINT_AT_ORIGIN = true;   // face scene center
    var USE_DISTANCE = true;      // place camera far enough to avoid clipping

    // ---- helpers ----
    function lerp(a, b, t) { return a + (b - a) * t; }

    function readJsonFile(file) {
        var f = new File(file);
        f.encoding = "UTF-8";
        if (!f.open("r")) throw new Error("cannot open " + file);
        var text = f.read();
        f.close();
        return JSON.parse(text);
    }

    function askFile() {
        var f = new File("~/Desktop/demo_cam.json");
        return f.openDlg("Choose camera JSON (from demo_extract / csgo_demo2json)", "*.json");
    }

    // ---- main ----
    var file = askFile();
    if (!file) { alert("No file selected"); return; }

    var data = readJsonFile(file);
    var cam = data.camera;
    if (!cam || cam.length === 0) {
        alert("JSON has no 'camera' array. Run demo_extract with camera data first.");
        return;
    }
    var fps = FRAME_RATE;
    var tickRate = data.tick_rate ? data.tick_rate : (data.game === "csgo" ? 128 : 100);

    var comp = app.project.items.addComp("Demo_" + (data.map || "scene"), 1920, 1080, 1, 60, fps);
    var layer = comp.layers.addCamera(CAMERA_NAME, [0, 0, 0]);
    var camLayer = layer;
    var cPos = camLayer.property("Camera Options").property("Position").value;
    var ballast = comp.layers.addNull();
    ballast.name = "CamTarget";

    // center of the track
    var cx = 0, cy = 0, cz = 0;
    for (var i = 0; i < cam.length; i++) {
        cx += cam[i].origin[0]; cy += cam[i].origin[1]; cz += cam[i].origin[2];
    }
    cx /= cam.length; cy /= cam.length; cz /= cam.length;

    for (var t = 0; t < cam.length; t++) {
        var ev = cam[t];
        var timeSec = ev.tick / tickRate;
        var frame = Math.round(timeSec * fps);

        // GoldSrc Z-up inches -> AE: X_blender = X, Y_blender = Z(height), Z_ae = -Y
        var px = ev.origin[0] * 1.0;
        var py = ev.origin[2] * 1.0;   // AE treats Y as up
        var pz = -ev.origin[1] * 1.0;

        // pitch/yaw/roll -> AE orientation (roughly, pitch up positive)
        var pitch = -ev.viewangles[0] * Math.PI / 180;
        var yaw = (ev.viewangles[1] + 90) * Math.PI / 180;
        var roll = -ev.viewangles[2] * Math.PI / 180;

        // direction the camera points to (GoldSrc yaw=0 looks along +Y)
        var dx = Math.cos(pitch) * Math.sin(yaw);
        var dy = Math.cos(pitch) * Math.cos(yaw);   // Z-up direction
        var dz = Math.sin(pitch);

        // AE forward (camera looks -Z after orientation); build look-at basis
        var fwdX = dx, fwdY = dy, fwdZ = dz;
        // map GoldSrc forward to AE: (dx, dz, -dy)
        var fx = dx;
        var fy = dz;
        var fz = -dy;

        var upY = 1;
        var rightX = 1;
        // orientation from look vector: approximate with Euler: rotY = atan2(fx, -fz), rotX = asin(fy)
        var rotY = Math.atan2(fx, -fz);
        var rotX = Math.asin(Math.max(-1, Math.min(1, fy)));

        // --- place keyframes ---
        var pos = [px, py, pz];
        ballast.property("Position").setValueAtTime(frame, [cx, cz, -cy]);

        // position keyframe
        var posProp = camLayer.property("Position");
        posProp.setValueAtTime(frame, pos);

        // orientation keyframe
        var orient = camLayer.property("Orientation");
        var rotXdeg = -rotX * 180 / Math.PI;
        var rotYdeg = -rotY * 180 / Math.PI;
        var rotZdeg = (roll) * 180 / Math.PI;
        orient.setValueAtTime(frame, [rotXdeg, rotYdeg, rotZdeg]);

        var fov = ev.fov ? ev.fov : 90;
        camLayer.property("Camera Options").property("Zoom").setValueAtTime(frame, (1920 / 2) / Math.tan(fov * Math.PI / 360));
    }

    if (POINT_AT_ORIGIN) {
        // keep the null as look-at target
        ballast.property("Position").setValue([cx, cz, -cy]);
    }
    comp.selected = true;
    comp.openInViewer();
    alert("Camera imported: " + cam.length + " keys, map: " + (data.map || "?"));
})();
