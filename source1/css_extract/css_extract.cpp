// css_extract: Counter-Strike: Source demo -> cs16db JSON.
//
// Built on top of css-demo-parser (sockfish/bamtna, MIT) - the open C++
// parser for CS:S demos (HL2DEMO, demo protocol 3, net proto 24, 14-23
// handled).  Output schema matches csgo_extract / demo_extract:
//   frames[]  per-tick player samples (origin/angles/velocity/team/health)
//   camera[]  follow/POV camera (source 5) - auto or --follow USERID
//   events[]  kills (player_death) and round_starts
//
// Build:  build_css_extract.bat
// Usage:  css_extract.exe demo.dem out.json [--follow N]
#include "cssdemo/cssdemo.h"
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

using namespace cssdemo;

static std::string json_esc(const std::string& s) {
	std::string out = "\"";
	for (char c : s) {
		if (c == '"' || c == '\\') out += '\\';
		if (c == '\n') { out += '\\'; out += 'n'; continue; }
		out += c;
	}
	out += '"';
	return out;
}

static std::string fmt_float(double v) {
	char b[64];
	snprintf(b, sizeof(b), "%.4g", v);
	return b;
}

struct KillEvent {
	int tick;
	std::string attacker, victim;
	std::string a_name, v_name;
};

class EventListener : public DemoListener {
public:
	std::vector<KillEvent> kills;
	std::vector<int> round_ticks;
	int last_tick = 0;

	void on_frame(const DemoFrame& frame) override {
		if (frame.is_packet())
			last_tick = frame.tick;
	}

	void on_game_event(const GameEvent& event) override {
		if (event.name == "player_death") {
			KillEvent k;
			k.tick = last_tick;
			k.victim = std::to_string(event.get_int("userid"));
			k.attacker = std::to_string(event.get_int("attacker"));
			k.v_name = event.get_string("victim_name");
			k.a_name = event.get_string("attacker_name");
			kills.push_back(std::move(k));
		} else if (event.name == "round_start" || event.name == "round_freeze_end") {
			round_ticks.push_back(last_tick);
		}
	}
};

int main(int argc, char** argv) {
	std::string in, out = "css_out.json";
	int follow = 0;
	for (int i = 1; i < argc; ++i) {
		std::string a = argv[i];
		if (a == "--follow" && i + 1 < argc) follow = atoi(argv[++i]);
		else if (in.empty()) in = a;
		else if (out == "css_out.json") out = a;
	}
	if (in.empty()) {
		fprintf(stderr, "Usage: css_extract demo.dem out.json [--follow N]\n");
		return 2;
	}
	try {
		DemoFile demo(in.c_str());
		DemoParser parser(demo);
		PlayerTracker tracker;
		EventListener events;
		parser.add_listener(tracker);
		parser.add_listener(events);
		parser.run();

		const DemoHeader& hdr = demo.header();
		double tick_rate = 64.0;
		if (hdr.playback_time > 0 && hdr.playback_ticks > 0)
			tick_rate = double(hdr.playback_ticks) / hdr.playback_time;

		std::string j;
		j += "{\n";
		j += "\"demo\": " + json_esc(in) + ",\n";
		j += "\"map\": " + json_esc(hdr.map_name) + ",\n";
		j += "\"game\": \"css\",\n";
		j += "\"demo_protocol\": " + std::to_string(hdr.demo_protocol) + ",\n";
		j += "\"net_protocol\": " + std::to_string(hdr.network_protocol) + ",\n";
		j += "\"tick_interval\": 1,\n";
		j += "\"tick_rate\": " + std::to_string(int(tick_rate + 0.5)) + ",\n";
		j += "\"notes\": \"CS:S via css-demo-parser (sockfish) PlayerTracker; units = inches, Z-up; no sequence/frame in CS:S demos\",\n";

		// ---------- frames ----------
		j += "\"frames\": [\n";
		bool first_frame = true;
		int auto_id = 0;
		bool auto_taken = false;
		for (const auto& [uid, samples] : tracker.samples()) {
			if (samples.empty()) continue;
			if (auto_id == 0) auto_id = uid;
		}
		int cam_id = follow > 0 ? follow : auto_id;
		for (const auto& [uid, samples] : tracker.samples()) {
			for (const auto& s : samples) {
				const PlayerSnapshot& p = s.player;
				if (!first_frame) j += ",\n";
				first_frame = false;
				j += "{\n\"tick\": " + std::to_string(s.tick) + ",\n";
				j += "\"time\": " + fmt_float(s.tick / tick_rate) + ",\n";
				j += "\"entities\": [\n";
				j += "{\"index\": " + std::to_string(uid) + ", \"player\": true, ";
				j += "\"name\": " + json_esc(p.info.name) + ", ";
				j += "\"team\": " + std::to_string(p.team) + ", ";
				j += "\"health\": " + std::to_string(p.health) + ", ";
				j += "\"origin\": [" + fmt_float(p.origin.x) + ", " + fmt_float(p.origin.y) + ", " + fmt_float(p.origin.z) + "], ";
				j += "\"angles\": [" + fmt_float(p.eye_angles.x) + ", " + fmt_float(p.eye_angles.y) + ", " + fmt_float(p.eye_angles.z) + "], ";
				j += "\"velocity\": [" + fmt_float(s.velocity.x) + ", " + fmt_float(s.velocity.y) + ", " + fmt_float(s.velocity.z) + "], ";
				j += "\"alive\": " + std::string(p.alive() ? "true" : "false") + "\n";
				j += "}\n],\n";
				j += "\"_cam\": " + std::string(uid == cam_id ? "true" : "false") + "\n}";
			}
		}
		j += "\n],\n";

		// ---------- camera ----------
		j += "\"camera\": [\n";
		bool first_cam = true;
		auto it = tracker.samples().find(cam_id);
		if (it != tracker.samples().end()) {
			for (const auto& s : it->second) {
				const PlayerSnapshot& p = s.player;
				if (!p.alive()) continue;
				if (!first_cam) j += ",\n";
				first_cam = false;
				j += "{\"tick\": " + std::to_string(s.tick) + ", ";
				j += "\"time\": " + fmt_float(s.tick / tick_rate) + ", ";
				j += "\"origin\": [" + fmt_float(p.origin.x) + ", " + fmt_float(p.origin.y) + ", " + fmt_float(p.origin.z) + "], ";
				j += "\"viewangles\": [" + fmt_float(p.eye_angles.x) + ", " + fmt_float(p.eye_angles.y) + ", " + fmt_float(p.eye_angles.z) + "], ";
				j += "\"fov\": 90, \"source\": 5}";
			}
		}
		j += "\n],\n";

		// ---------- events ----------
		j += "\"events\": [\n";
		bool first_ev = true;
		for (const auto& r : events.round_ticks) {
			if (!first_ev) j += ",\n";
			first_ev = false;
			j += "{\"tick\": " + std::to_string(r) + ", \"time\": " + fmt_float(r / tick_rate) + ", \"type\": \"round\"}";
		}
		for (const auto& k : events.kills) {
			if (!first_ev) j += ",\n";
			first_ev = false;
			j += "{\"tick\": " + std::to_string(k.tick) + ", \"time\": " + fmt_float(k.tick / tick_rate) + ", ";
			j += "\"type\": \"kill\", \"subject\": " + (k.attacker.empty() ? "0" : k.attacker) + ", ";
			j += "\"target\": " + (k.victim.empty() ? "0" : k.victim) + ", ";
			j += "\"aname\": " + json_esc(k.a_name) + ", \"vname\": " + json_esc(k.v_name) + "}";
		}
		j += "\n]\n}\n";

		FILE* f = fopen(out.c_str(), "w");
		if (!f) { perror("open output"); return 1; }
		fwrite(j.data(), 1, j.size(), f);
		fclose(f);
		fprintf(stderr, "done: %s map=%s %s demo, %zu players, %zu errors\n",
		        out.c_str(), hdr.map_name.c_str(), demo_kind_name(demo_kind(parser.state())),
		        tracker.samples().size(), parser.errors().size());
		return parser.errors().empty() ? 0 : 2;
	} catch (const std::exception& e) {
		fprintf(stderr, "failed: %s\n", e.what());
		return 1;
	}
}
