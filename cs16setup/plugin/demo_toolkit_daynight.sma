// ============================================================
//  demo_toolkit_daynight.sma - cinematic day/night lighting add-on
//  для demo_toolkit (cs16setup). Плавные переходы светового
//  стиля Level 0 (мировой свет) day -> dusk -> night.
//
//  Управление:
//    dtk_time day|dusk|night|random     - сменить свет (плавный фейд)
//    say /day , /night , /dusk          - тоже для всех игроков
//    dtk_light_day   (default 255)      - значение стиля для дня
//    dtk_light_dusk  (default 105)      - вечер
//    dtk_light_night (default 40)       - ночь (для кино: 20-60)
//    dtk_fade_ms     (default 4000)     - длительность перехода
//
//  Замечания: небо/Skybox в GoldSrc меняется только Trinity Engine
//  (см. cs16setup/trinity/README.md); туман - только шейдерный тринити.
//  Световые стили cтавятся broadcast'ом - работает на listen-сервере.
// ============================================================
#include <amxmodx>

new g_light_day   = 255
new g_light_dusk  = 105
new g_light_night = 40
new g_fade_ms     = 4000

new Float:g_cur = 255.0
new Float:g_tgt = 255.0
new g_task

public plugin_init()
{
	register_plugin("DTK Day&Night", "1.0", "cs16db")
	register_cvar("dtk_light_day", "255")
	register_cvar("dtk_light_dusk", "105")
	register_cvar("dtk_light_night", "40")
	register_cvar("dtk_fade_ms", "4000")

	register_concmd("dtk_time", "cmd_time", ADMIN_KICK, "day|dusk|night|random")
	register_clcmd("say /day", "cmd_say_day")
	register_clcmd("say /dusk", "cmd_say_dusk")
	register_clcmd("say /night", "cmd_say_night")

	g_task = 0
	set_task(0.5, "reload_cvars", _, _, _, "b")
}

public reload_cvars()
{
	new day = get_cvar_num("dtk_light_day")
	new dusk = get_cvar_num("dtk_light_dusk")
	new night = get_cvar_num("dtk_light_night")
	new fade = get_cvar_num("dtk_fade_ms")
	if (day == g_light_day && dusk == g_light_dusk && night == g_light_night && fade == g_fade_ms)
		return
	g_light_day = day
	g_light_dusk = dusk
	g_light_night = night
	g_fade_ms = fade
}

public cmd_time(id)
{
	new arg[16]
	read_argv(1, arg, charsmax(arg))
	if (equal(arg, "day")) set_target(float(g_light_day))
	else if (equal(arg, "dusk")) set_target(float(g_light_dusk))
	else if (equal(arg, "night")) set_target(float(g_light_night))
	else if (equal(arg, "random"))
	{
		new Float:r = float(random(3))
		if (r < 1.0) set_target(float(g_light_day))
		else if (r < 2.0) set_target(float(g_light_dusk))
		else set_target(float(g_light_night))
	}
	else
		client_print(id, print_console, "usage: dtk_time day|dusk|night|random")
	return PLUGIN_HANDLED
}

public cmd_say_day(id) { set_target(float(g_light_day)); return PLUGIN_HANDLED; }
public cmd_say_dusk(id) { set_target(float(g_light_dusk)); return PLUGIN_HANDLED; }
public cmd_say_night(id) { set_target(float(g_light_night)); return PLUGIN_HANDLED; }

set_target(Float:t)
{
	g_tgt = t
	if (!g_task)
		g_task = set_task(0.1, "fade_step", _, _, _, "b")
}

public fade_step()
{
	new Float:speed = (float(g_fade_ms) / 100.0) * 0.1
	if (g_fade_ms <= 0) speed = 9999.0
	new Float:diff = g_tgt - g_cur
	if (floatabs(diff) < speed)
	{
		g_cur = g_tgt
		remove_task(g_task)
		g_task = 0
	}
	else if (diff > 0.0)
		g_cur += speed
	else
		g_cur -= speed

	apply_light(floatround(g_cur))
}

apply_light(val)
{
	// LightStyle level 0: строка "abcd", a..z, 0..9 - яркость телесн.
	new style[5]
	format(style, charsmax(style), "%c%c%c%c",
		style_char(val), style_char(val), style_char(val), style_char(val))
	message_begin(MSG_BROADCAST, SVC_LIGHTSTYLE)
	write_byte(0)
	write_string(style)
	message_end()
}

style_char(val)
{
	if (val <= 0) return 'a'
	if (val >= 255) return 'z'
	new table[] = "abcdefghijklmnopqrstuvwxyz"
	return table[val * 25 / 255]
}

public plugin_end()
{
	if (g_task)
		remove_task(g_task)
}
