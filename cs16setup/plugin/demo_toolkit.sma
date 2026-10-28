/* ============================================================
 *  cs16db Demo Toolkit - AMX Mod X plugin for CS 1.6
 *
 *  Features
 *   - record demos with automatic names (map + date/time)
 *   - optional auto record on map start
 *   - optional round splitting: one demo per round
 *   - edit event log: dtk_events.jsonl (rounds, kills, bomb, record)
 *   - camera spots: save/teleport (dtk_spots.ini)
 *   - chat commands: /rec /stop /status /spot /gospot
 *
 *  Commands (server console / amx_*)
 *   amx_record [name]    start recording (name optional)
 *   amx_stop             stop recording
 *   amx_spot <name>      save current camera position/angles
 *   amx_gospot <name>    teleport to a saved spot
 *   amx_dtk              show status
 *
 *  Cvars
 *   dtk_autorecord 1     start recording when a map loads
 *   dtk_split_rounds 0   1 = one demo per round
 *   dtk_events 1         write dtk_events.jsonl edit log
 *   dtk_prefix dtk       demo filename prefix
 *   dtk_admin_only 0     1 = require ADMIN_MAP for commands
 * ============================================================ */

#include <amxmodx>
#include <fakemeta>
#include <fun>

#define PLUGIN  "cs16db Demo Toolkit"
#define VERSION "1.0.0"
#define AUTHOR  "cs16db"

#define EVENTS_FILE "dtk_events.jsonl"
#define SPOTS_FILE  "dtk_spots.ini"

new bool:g_recording = false;
new g_recName[96];
new g_round = 0;
new Float:g_recStart = 0.0;

new cvar_autorecord, cvar_split, cvar_events, cvar_prefix, cvar_admin, cvar_autostop;

public plugin_init()
{
    register_plugin(PLUGIN, VERSION, AUTHOR);

    cvar_autorecord = register_cvar("dtk_autorecord", "1");
    cvar_split     = register_cvar("dtk_split_rounds", "0");
    cvar_events    = register_cvar("dtk_events", "1");
    cvar_prefix    = register_cvar("dtk_prefix", "dtk");
    cvar_admin     = register_cvar("dtk_admin_only", "0");
    cvar_autostop  = register_cvar("dtk_autostop", "0");

    register_concmd("amx_record", "cmd_record", ADMIN_ALL, "[name] - start demo recording");
    register_concmd("amx_stop", "cmd_stop", ADMIN_ALL, "stop demo recording");
    register_concmd("amx_spot", "cmd_spot", ADMIN_ALL, "<name> - save camera spot");
    register_concmd("amx_gospot", "cmd_gospot", ADMIN_ALL, "<name> - teleport to spot");
    register_concmd("amx_dtk", "cmd_status", ADMIN_ALL, "show demo toolkit status");

    register_clcmd("say /rec", "chat_rec");
    register_clcmd("say /stop", "chat_stop");
    register_clcmd("say /status", "chat_status");
    register_clcmd("say /spot", "chat_spot");
    register_clcmd("say /gospot", "chat_gospot");

    register_event("DeathMsg", "ev_death", "a");

    register_logevent("ev_round_start", 2, "1=Round_Start");
    register_logevent("ev_round_end", 2, "1=Round_End");
    register_logevent("ev_round_end", 2, "1=Target_Bombed");
    register_logevent("ev_round_end", 2, "1=Target_Saved");
    register_logevent("ev_round_end", 2, "1=CTs_Win");
    register_logevent("ev_round_end", 2, "1=Terrorists_Win");
    register_logevent("ev_round_end", 2, "1=Hostages_Rescued");
    register_logevent("ev_round_end", 2, "1=Hostages_Not_Rescued");
    register_logevent("ev_round_end", 2, "1=Round_Draw");
    register_logevent("ev_bomb_planted", 3, "2=Planted_The_Bomb");
    register_logevent("ev_bomb_defused", 3, "2=Defused_The_Bomb");

    if (get_pcvar_num(cvar_autorecord) && !get_pcvar_num(cvar_split))
        set_task(5.0, "task_auto_start");

    server_print("[cs16db] %s v%s loaded (autorecord=%d split=%d)",
        PLUGIN, VERSION, get_pcvar_num(cvar_autorecord), get_pcvar_num(cvar_split));

    log_edit_event("plugin_loaded", PLUGIN, VERSION, "");
}

/* ---------------- permissions ---------------- */

stock bool:allowed(id)
{
    if (id == 0) return true;                 // server console
    if (!get_pcvar_num(cvar_admin)) return true;
    return (get_user_flags(id) & ADMIN_MAP) ? true : false;
}

/* ---------------- recording core ---------------- */

stock build_demo_name(buf[], len, const suffix[])
{
    new map[32], stamp[32], prefix[24];
    get_mapname(map, charsmax(map));
    get_time("%Y%m%d-%H%M%S", stamp, charsmax(stamp));
    get_pcvar_string(cvar_prefix, prefix, charsmax(prefix));
    if (suffix[0])
        formatex(buf, len, "%s_%s_%s_%s", prefix, map, stamp, suffix);
    else
        formatex(buf, len, "%s_%s_%s", prefix, map, stamp);
}

stock start_rec(const suffix[])
{
    if (g_recording)
        stop_rec();

    build_demo_name(g_recName, charsmax(g_recName), suffix);
    server_cmd("stop");
    server_cmd("record %s", g_recName);
    g_recording = true;
    g_recStart = get_gametime();
    server_print("[cs16db] recording: %s.dem", g_recName);
    client_print(0, print_chat, "[cs16db] REC %s.dem", g_recName);
    log_edit_event("record_start", g_recName, "", "");

    if (get_pcvar_num(cvar_autostop) > 0)
        set_task(float(get_pcvar_num(cvar_autostop)), "task_auto_stop");
}

stock stop_rec()
{
    if (!g_recording)
        return;

    if (task_exists(0))
        remove_task(0);

    server_cmd("stop");
    server_print("[cs16db] demo saved: %s.dem", g_recName);
    client_print(0, print_chat, "[cs16db] demo saved: %s.dem", g_recName);
    log_edit_event("record_stop", g_recName, "", "");
    g_recording = false;
    g_recName[0] = 0;
}

public task_auto_start()
{
    if (!g_recording && get_pcvar_num(cvar_autorecord))
        start_rec("auto");
}

public task_auto_stop()
{
    if (g_recording)
        stop_rec();
}

/* ---------------- console commands ---------------- */

public cmd_record(id, level, cid)
{
    if (!allowed(id)) return PLUGIN_HANDLED;
    new arg[64];
    read_argv(1, arg, charsmax(arg));
    start_rec(arg);
    return PLUGIN_HANDLED;
}

public cmd_stop(id, level, cid)
{
    if (!allowed(id)) return PLUGIN_HANDLED;
    stop_rec();
    return PLUGIN_HANDLED;
}

public cmd_status(id, level, cid)
{
    if (!allowed(id)) return PLUGIN_HANDLED;
    new msg[192];
    formatex(msg, charsmax(msg),
        "[cs16db] rec=%s name=%s round=%d uptime=%.1fs",
        g_recording ? "YES" : "no", g_recName, g_round,
        g_recording ? get_gametime() - g_recStart : 0.0);
    if (id == 0) server_print(msg);
    else console_print(id, msg);
    return PLUGIN_HANDLED;
}

public cmd_spot(id, level, cid)
{
    if (!allowed(id)) return PLUGIN_HANDLED;
    new name[64];
    read_argv(1, name, charsmax(name));
    save_spot(id, name);
    return PLUGIN_HANDLED;
}

public cmd_gospot(id, level, cid)
{
    if (!allowed(id)) return PLUGIN_HANDLED;
    new name[64];
    read_argv(1, name, charsmax(name));
    goto_spot(id, name);
    return PLUGIN_HANDLED;
}

/* ---------------- chat commands ---------------- */

public chat_rec(id)
{
    if (!allowed(id)) return PLUGIN_HANDLED;
    new arg[64];
    read_argv(2, arg, charsmax(arg));
    start_rec(arg);
    return PLUGIN_HANDLED;
}

public chat_stop(id)
{
    if (!allowed(id)) return PLUGIN_HANDLED;
    stop_rec();
    return PLUGIN_HANDLED;
}

public chat_status(id)
{
    return cmd_status(id, 0, 0);
}

public chat_spot(id)
{
    new name[64];
    read_argv(2, name, charsmax(name));
    save_spot(id, name);
    return PLUGIN_HANDLED;
}

public chat_gospot(id)
{
    new name[64];
    read_argv(2, name, charsmax(name));
    goto_spot(id, name);
    return PLUGIN_HANDLED;
}

/* ---------------- round events ---------------- */

public ev_round_start()
{
    g_round++;
    log_edit_event("round_start", "", "", "");

    if (get_pcvar_num(cvar_split))
    {
        new suffix[16];
        formatex(suffix, charsmax(suffix), "r%02d", g_round);
        start_rec(suffix);
    }
}

public ev_round_end()
{
    if (get_pcvar_num(cvar_split) && g_recording)
        stop_rec();
}

/* ---------------- game events ---------------- */

public ev_death()
{
    new killer_id = read_data(1);
    new victim_id = read_data(2);
    new hs = read_data(3);

    new killer[32] = "world", victim[32] = "unknown";
    if (killer_id > 0 && killer_id <= 32)
        get_user_name(killer_id, killer, charsmax(killer));
    if (victim_id > 0 && victim_id <= 32)
        get_user_name(victim_id, victim, charsmax(victim));

    new hs_str[4];
    formatex(hs_str, charsmax(hs_str), "%d", hs);
    log_edit_event("kill", killer, victim, hs_str);
}

public ev_bomb_planted()
{
    new data[160], name[32];
    read_logargv(0, data, charsmax(data));
    parse_loguser(data, name, charsmax(name));
    log_edit_event("bomb_planted", name, "", "");
}

public ev_bomb_defused()
{
    new data[160], name[32];
    read_logargv(0, data, charsmax(data));
    parse_loguser(data, name, charsmax(name));
    log_edit_event("bomb_defused", name, "", "");
}

/* ---------------- edit event log (JSONL) ---------------- */

stock log_edit_event(const type[], const a[], const b[], const c[])
{
    if (!get_pcvar_num(cvar_events))
        return;

    new map[32], ea[64], eb[64], ec[16], line[384];
    get_mapname(map, charsmax(map));
    escape_json(a, ea, charsmax(ea));
    escape_json(b, eb, charsmax(eb));
    formatex(ec, charsmax(ec), "%s", c);

    formatex(line, charsmax(line),
        "{^"type^":^"%s^",^"time^":%.2f,^"map^":^"%s^",^"a^":^"%s^",^"b^":^"%s^",^"c^":^"%s^"}",
        type, get_gametime(), map, ea, eb, ec);

    new f = fopen(EVENTS_FILE, "a");
    if (f)
    {
        fprintf(f, "%s^n", line);
        fclose(f);
    }
}

stock escape_json(const src[], dst[], len)
{
    new j = 0;
    for (new i = 0; src[i] && j < len - 2; i++)
    {
        new ch = src[i];
        if (ch == '"' || ch == '\')
        {
            dst[j++] = '\';
            dst[j++] = ch;
        }
        else if (ch == '^n' || ch == '^r' || ch == '^t')
        {
            dst[j++] = ' ';
        }
        else
        {
            dst[j++] = ch;
        }
    }
    dst[j] = 0;
}

/* ---------------- camera spots ---------------- */

stock save_spot(id, const name[])
{
    if (!allowed(id)) return;
    if (!name[0])
    {
        client_print(id, print_chat, "[cs16db] usage: /spot <name>");
        return;
    }

    new Float:origin[3], Float:angles[3];
    pev(id, pev_origin, origin);
    pev(id, pev_v_angle, angles);

    new f = fopen(SPOTS_FILE, "a");
    if (!f)
    {
        client_print(id, print_chat, "[cs16db] cannot write %s", SPOTS_FILE);
        return;
    }
    fprintf(f, "%s %.1f %.1f %.1f %.2f %.2f %.2f^n",
        name, origin[0], origin[1], origin[2], angles[0], angles[1], angles[2]);
    fclose(f);

    client_print(id, print_chat, "[cs16db] spot '%s' saved (%.0f %.0f %.0f)", name,
        origin[0], origin[1], origin[2]);
}

stock goto_spot(id, const name[])
{
    if (!allowed(id)) return;
    if (!name[0])
    {
        client_print(id, print_chat, "[cs16db] usage: /gospot <name>");
        return;
    }

    new f = fopen(SPOTS_FILE, "r");
    if (!f)
    {
        client_print(id, print_chat, "[cs16db] no spots file (%s)", SPOTS_FILE);
        return;
    }

    new line[192];
    new found = 0;
    while (fgets(f, line, charsmax(line)) > 0)
    {
        new sname[32], xs[16], ys[16], zs[16], ps[16], yas[16], rs[16];
        parse(line, sname, charsmax(sname), xs, charsmax(xs), ys, charsmax(ys),
            zs, charsmax(zs), ps, charsmax(ps), yas, charsmax(yas), rs, charsmax(rs));

        if (!equal(sname, name))
            continue;

        new Float:origin[3], Float:angles[3];
        origin[0] = floatstr(xs);
        origin[1] = floatstr(ys);
        origin[2] = floatstr(zs);
        angles[0] = floatstr(ps);
        angles[1] = floatstr(yas);
        angles[2] = floatstr(rs);

        if (is_user_bot(id))
        {
            set_pev(id, pev_origin, origin);
        }
        else
        {
            new iorigin[3];
            iorigin[0] = floatround(origin[0]);
            iorigin[1] = floatround(origin[1]);
            iorigin[2] = floatround(origin[2]);
            set_user_origin(id, iorigin);
        }
        set_pev(id, pev_v_angle, angles);
        set_pev(id, pev_angles, angles);
        set_pev(id, pev_fixangle, 1);

        client_print(id, print_chat, "[cs16db] teleported to spot '%s'", name);
        found = 1;
        break;
    }
    fclose(f);

    if (!found)
        client_print(id, print_chat, "[cs16db] spot '%s' not found", name);
}
