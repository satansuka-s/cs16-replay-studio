// GoldSrc demo net-stream decoder: svc message sequences, delta tables,
// entity state tracking, camera extraction.
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include "bitreader.hpp"
#include "builtin_delta.hpp"
#include "delta.hpp"
#include "delta_lst.hpp"
#include "netprotocol.hpp"

namespace gs {

struct CameraSample {
	int tick = 0;
	float time = 0;
	float origin[3] = {0, 0, 0};
	float viewangles[3] = {0, 0, 0};
	float fov = 90;
	int source = 0; // 0 = demo CLIENT_DATA frame, 1 = svc_clientdata, 2 = RefParams prefix
};

// Resource inventory from svc_resourcelist
struct ResourceInfo {
	std::vector<std::string> models;
	std::vector<std::string> sounds;
	std::vector<std::string> sprites;
	std::vector<std::string> skins;
	std::vector<std::string> generic;
};

// Sound event captured from svc_sound (position-based), used for edit markers
struct SoundEvent {
	int tick = 0;
	float time = 0;
	int index = -1;
	float origin[3] = {0, 0, 0};
};

struct EntityFrame {
	int tick = 0;
	float time = 0;
	std::vector<EntityState> entities;
};

class DemoDecoder {
public:
	// --- camera collection (chronological after finish()) ---
	std::vector<CameraSample> camera;
	std::vector<CameraSample> cam_raw;

	// --- entity sampling (every sampleTick_ steps) ---
	std::vector<EntityFrame> frames;

	// --- stats ---
	int msgCount = 0;
	int skippedUnsupported = 0;
	std::map<int, int> opStats;
	std::map<std::string, int> tableStats;
	ResourceInfo resources;
	int reslistCalls = 0;    // svc_resourcelist calls (debug)
	int reslistEntries = 0;  // entries accepted (debug)
	int reslistBits = 0;     // bits consumed by the last list (debug)
	int reslistErrorEntry = -1;     // first rejected entry index (-1 = none)
	std::string reslistErrorText;   // diagnostics for the rejected entry

	static int traceLimit() {
		if (const char* v = std::getenv("CS16DB_TRACE_LIMIT")) {
			int n = std::atoi(v);
			if (n > 0) return n;
		}
		return 4;
	}
	// edit markers: sound events with position (decimated)
	std::vector<SoundEvent> soundEvents;
	int soundDecim_ = 8; // keep every 8th sound event

	void begin(int sampleInterval = 1, int maxClients = MAX_CLIENTS, int netProto = 48) {
		sampleInterval_ = sampleInterval;
		maxClients_ = maxClients;
		nextSampleTick_ = -1;
		serverTime_ = 0;
		instancedBaselineMode_ = false;
		classicMode_ = (netProto < 48); // proto 47 -> classic MSG_ReadDeltaEntity layout
	}

	void addCameraFrame(float origin[3], float viewangles[3], float fov, int tick, float time) {
		addCameraFrameSrc(origin, viewangles, fov, tick, time, 0);
	}

	void addCameraFrameSrc(float origin[3], float viewangles[3], float fov, int tick, float time, int src) {
		if (origin[0] == 0 && origin[1] == 0 && origin[2] == 0 && viewangles[0] == 0 &&
		    viewangles[1] == 0 && viewangles[2] == 0)
			return;
		CameraSample c;
		c.tick = tick;
		c.time = time;
		std::memcpy(c.origin, origin, sizeof(c.origin));
		std::memcpy(c.viewangles, viewangles, sizeof(c.viewangles));
		c.fov = fov;
		c.source = src;
		cam_raw.push_back(c);
	}

	void parseNetmsg(const uint8_t* data, size_t len, int tick, float demotime) {
		++msgCount;
		curTick_ = tick;
		curTime_ = demotime;
		// CS 1.6 writes a filler "userdata" packet between real net messages:
		// svc_nop + 4 zero bytes + float 90.0. It carries no entity/camera data.
		if (len == 8 && data[0] == SVC_NOP)
			return;
		BitReader br(data, len);
		int op = -1;
		try {
			while (br.bitsLeft() >= 8) {
				size_t opBit = br.bitPos();
				op = (int)br.readUBits(8);
				opStats[op]++;
				if (std::getenv("CS16DB_TRACE") && (msgCount <= traceLimit() || op == 40 || op == 41)) {
					std::fprintf(stderr, "[trace] msg=%d tick=%d op=%d bit=%zu\n", msgCount, tick,
					             op, opBit);
					if (opBit == 0 || op == 40 || op == 41) {
						std::fprintf(stderr, "[msg] len=%zu head=", br.size() * 8);
						for (size_t i = 0; i < br.size() && i < 64; ++i)
							std::fprintf(stderr, "%02x", br.data()[i]);
						std::fprintf(stderr, "\n");
					}
				}
				if (op == SVC_BAD) {
					// delimiter/alignment artifact in recorded streams:
					// a trailing zero byte terminates the frame quietly
					bool allZero = true;
					while (br.bitsLeft() > 0)
						if (br.readBit()) { allZero = false; break; }
					if (!allZero) ++skippedUnsupported;
					break;
				}
				handleSvc((uint8_t)op, br);
				// GoldSrc MSG_WriteByte is UBitLong(8) at the current bit position:
				// svc commands are bit-continuous. Only bit-writing sections
				// (MSG_Start/EndBitWriting) pad their own payload to a byte boundary.
			
			}
		} catch (const std::exception& e) {
			if (std::getenv("CS16DB_DEBUG"))
				debugDump(data, len, tick, op, br.bitPos(), e.what());
			throw;
		}
	}

	static void debugDump(const uint8_t* data, size_t len, int tick, int op,
	                      size_t bitPos, const char* what) {
		std::fprintf(stderr, "[netmsg] tick=%d op=%d bit=%zu/%zu: %s\n  head:", tick, op,
		             bitPos, len * 8, what);
		for (size_t i = 0; i < len && i < 40; ++i) std::fprintf(stderr, " %02x", data[i]);
		std::fprintf(stderr, "\n");
	}

	void sampleTick(int tick, float time) {
		if (sampleInterval_ <= 0) return;
		if (nextSampleTick_ < 0) nextSampleTick_ = tick;
		if (tick < nextSampleTick_) return;
		nextSampleTick_ += sampleInterval_;
		EntityFrame f;
		f.tick = tick;
		f.time = time;
		f.entities.reserve(entities_.size());
		for (const auto& kv : entities_)
			f.entities.push_back(kv.second);
		frames.push_back(std::move(f));

		// HLTV: the proxy has no clientdata; follow the view entity set by
		// svc_setview.  Player entity origin is at the feet, so lift it to eye
		// level; map cameras (trigger_camera etc.) are used as-is.
		if (spectator_ && viewEntity_ > 0 && tick != lastHltvCamTick_) {
			auto it = entities_.find(viewEntity_);
			if (it != entities_.end() && it->second.has_origin) {
				CameraSample c;
				c.tick = tick;
				c.time = time;
				std::memcpy(c.origin, it->second.origin, sizeof(c.origin));
				if (viewEntity_ <= maxClients_)
					c.origin[2] += 28.0f;
				if (hasHltvAngles_) {
					std::memcpy(c.viewangles, hltvAngles_, sizeof(c.viewangles));
				} else if (it->second.has_angles) {
					std::memcpy(c.viewangles, it->second.angles, sizeof(c.viewangles));
				}
				c.fov = 90;
				c.source = 4;
				cam_raw.push_back(c);
				lastHltvCamTick_ = tick;
			}
		}
	}

	void finish() {
		buildSpectatorCamera();
		std::sort(cam_raw.begin(), cam_raw.end(),
		          [](const CameraSample& a, const CameraSample& b) { return a.tick < b.tick; });
		camera = std::move(cam_raw);
	}

	// HLTV fallback: if the streaming sampleTick loop produced nothing (view
	// entity unknown / zero at sample time, e.g. after a bitstream desync),
	// rebuild the camera from the setview history and the entity timeline.
	void buildSpectatorCamera() {
		if (!spectator_ || !cameraIsEmpty()) return;
		// pick the most frequent non-zero setview target
		std::map<int, int> freq;
		for (const auto& [t, ve] : setviewHistory_)
			if (ve > 0) ++freq[ve];
		if (freq.empty()) return;
		int best = 0, bestN = 0;
		for (const auto& [ve, n] : freq)
			if (n > bestN) { best = ve; bestN = n; }
		const bool lift = best <= maxClients_;
		float lastOrigin[3] = {0, 0, 0};
		float lastAngles[3] = {0, 0, 0};
		bool haveOrigin = false, haveAngles = false;
		for (const auto& f : frames) {
			for (const auto& e : f.entities) {
				if (e.index != best) continue;
				if (e.has_origin) {
					std::memcpy(lastOrigin, e.origin, sizeof(lastOrigin));
					lastOrigin[2] += lift ? 28.0f : 0.0f;
					haveOrigin = true;
				}
				if (e.has_angles) {
					std::memcpy(lastAngles, e.angles, sizeof(lastAngles));
					haveAngles = true;
				}
				break;
			}
			if (!haveOrigin) continue;
			CameraSample c;
			c.tick = f.tick;
			c.time = f.time;
			std::memcpy(c.origin, lastOrigin, sizeof(c.origin));
			if (hasHltvAngles_)
				std::memcpy(c.viewangles, hltvAngles_, sizeof(c.viewangles));
			else if (haveAngles)
				std::memcpy(c.viewangles, lastAngles, sizeof(c.viewangles));
			c.fov = 90;
			c.source = 4;
			cam_raw.push_back(std::move(c));
		}
		if (std::getenv("CS16DB_DEBUG"))
			std::fprintf(stderr, "[hltv-cam] entity=%d samples=%zu\n", best, cam_raw.size());
	}

	bool cameraIsEmpty() const { return cam_raw.empty(); }

	int entityCount() const { return (int)entities_.size(); }

private:
	// --- member declarations (in-class definitions below are complete-class) ---

	// state
	int sampleInterval_ = 1;
	int maxClients_ = MAX_CLIENTS;
	int nextSampleTick_ = -1;
	int curTick_ = 0;
	float curTime_ = 0;
	float serverTime_ = 0;
	bool instancedBaselineMode_ = false;
	bool spectator_ = false; // HLTV proxy demo: svc_clientdata has no payload
	float hltvAngles_[3] = {0, 0, 0};
	bool hasHltvAngles_ = false;
	int lastHltvCamTick_ = -1;
	std::vector<std::pair<int, int>> setviewHistory_; // {tick, entity}
	std::map<std::string, DeltaTable> tables_;
	std::map<int, EntityState> entities_;
	std::map<int, EntityState> baselines_;
	std::map<int, EntityState> staticEntities_; // from svc_spawnstatic (index = -(N+1))
	int staticCount_ = 0;
	std::vector<EntityState> instancedBaselines_;
	// GoldSrc user messages registered by svc_newusermsg: id -> payload size
	// (-1 = variable length, first byte of the payload carries the size).
	std::map<int, int> userMsgSizes_;
	std::map<int, std::string> userMsgNames_;

	float cd_origin[3] = {0, 0, 0};
	float cd_viewangles[3] = {0, 0, 0};
	float cd_fov = 90;
	bool cd_has_origin = false;
	bool cd_has_viewangles = false;
	bool cd_has_fov = false;

	const DeltaTable& requireTable(const std::string& name) {
		auto it = tables_.find(name);
		if (it == tables_.end()) {
			ensureBuiltinTables();
			it = tables_.find(name);
			if (it == tables_.end())
				throw std::runtime_error("delta table not found: " + name);
		}
		return it->second;
	}

	// CS 1.6 delta tables from cstrike/delta.lst (fallback for HLTV demos that
	// do not retransmit svc_deltatable in the recording).
	// Different server/build generations shipped slightly different layouts;
	// CS16DB_DELTA_LST overrides the builtin one.
	void ensureBuiltinTables() {
		if (builtinLoaded_) return;
		builtinLoaded_ = true;
		std::string text = builtinDeltaLst();
		if (const char* over = std::getenv("CS16DB_DELTA_LST")) {
			std::ifstream f(over);
			if (f) {
				std::stringstream ss;
				ss << f.rdbuf();
				text = ss.str();
			}
		}
		static const char* names[] = {
			"clientdata_t", "entity_state_t", "entity_state_player_t",
			"custom_entity_state_t", "event_t", "usercmd_t", "weapon_data_t",
		};
		for (const char* n : names) {
			if (tables_.count(n)) continue;
			DeltaTable t;
			if (parseDeltaLstTable(text, n, t) && !t.fields.empty()) {
				tables_[n] = std::move(t);
				tableStats[std::string("builtin:") + n]++;
			}
		}
		// movevars_t is not in delta.lst: the engine carries a compiled-in
		// description (HLSDK net_encode.c Delta_InitMovevars) used by
		// svc_deltamovevars. Needed to stay in sync on client-recorded demos.
		if (!tables_.count("movevars_t")) {
			DeltaTable t;
			t.name = "movevars_t";
			auto add = [&t](const char* n, uint32_t flags, int bits, float mul) {
				DeltaField f;
				f.name = n;
				f.flags = flags;
				f.bits = bits;
				f.multiplier = mul;
				t.fields.push_back(f);
			};
			const uint32_t F = DT_FLOAT | DT_SIGNED;
			add("gravity", F, 16, 8.0f);
			add("stopspeed", F, 16, 8.0f);
			add("maxspeed", F, 16, 8.0f);
			add("spectatormaxspeed", F, 16, 8.0f);
			add("accelerate", F, 16, 8.0f);
			add("airaccelerate", F, 16, 8.0f);
			add("wateraccelerate", F, 16, 8.0f);
			add("friction", F, 16, 8.0f);
			add("edgefriction", F, 16, 8.0f);
			add("waterfriction", F, 16, 8.0f);
			add("bounce", F, 16, 8.0f);
			add("stepsize", F, 16, 16.0f);
			add("maxvelocity", F, 16, 8.0f);
			add("zmax", DT_FLOAT, 24, 1.0f);
			add("waveHeight", F, 16, 16.0f);
			add("footsteps", DT_INTEGER, 1, 1.0f);
			add("skyName", DT_STRING, 1, 1.0f);
			add("rollangle", F, 16, 32.0f);
			add("rollspeed", F, 16, 8.0f);
			add("skycolor_r", F, 16, 1.0f);
			add("skycolor_g", F, 16, 1.0f);
			add("skycolor_b", F, 16, 1.0f);
			add("skyvec_x", F, 16, 32.0f);
			add("skyvec_y", F, 16, 32.0f);
			add("skyvec_z", F, 16, 32.0f);
			tables_["movevars_t"] = std::move(t);
			tableStats["builtin:movevars_t"]++;
		}
	}

	bool builtinLoaded_ = false;
	bool classicMode_ = false; // proto 47 entity packet layout
	int viewEntity_ = 0; // last svc_setview target
	int sndCnt_ = 0;     // sound event counter for decimation

	static void applyEntityField(EntityState& st, const DeltaField& f, float v) {
		const std::string& n = f.name;
		if (n == "origin[0]") { st.origin[0] = v; st.has_origin = true; }
		else if (n == "origin[1]") { st.origin[1] = v; st.has_origin = true; }
		else if (n == "origin[2]") { st.origin[2] = v; st.has_origin = true; }
		else if (n == "angles[0]") { st.angles[0] = v; st.has_angles = true; }
		else if (n == "angles[1]") { st.angles[1] = v; st.has_angles = true; }
		else if (n == "angles[2]") { st.angles[2] = v; st.has_angles = true; }
		else if (n == "velocity[0]") st.velocity[0] = v;
		else if (n == "velocity[1]") st.velocity[1] = v;
		else if (n == "velocity[2]") st.velocity[2] = v;
		else if (n == "modelindex") st.modelindex = (int)v;
		else if (n == "sequence") st.sequence = (int)v;
		else if (n == "frame") st.frame = v;
		else if (n == "animtime") st.animtime = v;
		else if (n == "framerate") st.framerate = v;
		else if (n == "body") st.body = (int)v;
		else if (n == "skin") st.skin = (int)v;
		else if (n == "effects") st.effects = (int)v;
	}

	static void noopDelta(BitReader&, const DeltaField&, float) {}

	static void applyClientFieldThunk(DemoDecoder& d, const DeltaField& f, float v) {
		d.applyClientField(f, v);
	}

	void handleSvc(uint8_t op, BitReader& br);
	void parseDeltaTable(BitReader& br);
	void parseNewUserMsg(BitReader& br);
	void skipUserMessage(uint8_t op, BitReader& br);
	void parseClientData(BitReader& br);
	void applyClientField(const DeltaField& f, float v);
	void skipSound(BitReader& br);
	void skipSpawnStatic(BitReader& br);
	void skipTempEntity(BitReader& br);
	void parseEvents(BitReader& br, bool reliable);
	void parseBaselines(BitReader& br);
	void parsePacketEntities(BitReader& br, bool delta);
	void parsePacketEntitiesClassic(BitReader& br, bool delta);
	// ---- svc_resourcelist (Xash CL_ParseResourceList, GoldSrc) ----
	void parseResourceList(BitReader& br) {
		++reslistCalls;
		size_t startBit = br.bitPos();
		uint32_t total = br.readUBits(12);
		ResourceInfo r;
		for (uint32_t i = 0; i < total; ++i) {
			uint32_t type = br.readUBits(4);
			std::string name = br.readString();
			br.skip(12); // index (MAX_MODEL_BITS)
			br.skip(24); // download size (unsigned in GoldSrc)
			uint32_t flags = br.readUBits(3);
			if (flags & 0x04) br.skip(16 * 8); // RES_CUSTOM: md5
			if (br.readBit()) br.skip(32 * 8); // reserved block (rguc_reserved[32])
			// sanity: recorded streams often lack a real resourcelist payload;
			// bail out if entries look degenerate (empty names, absurd counts)
			{
				bool nameOk = !name.empty() && name.size() <= 250;
				for (char c : name)
					if ((unsigned char)c > 0x7e || (unsigned char)c < 0x20) { nameOk = false; break; }
				if (!nameOk || i > 1200) {
					reslistErrorEntry = (int)i;
					reslistErrorText = "name=" + name + " bitsLeft=" + std::to_string((long long)br.bitsLeft());
					// keep what was parsed so far, then stop
					break;
				}
			}
			// resourcetype_t: t_sound=0, t_skin=1, t_model=2, t_decal=3, t_generic=4
			switch (type & 0xF) {
			case 0: r.sounds.push_back(name); break;
			case 1: r.skins.push_back(name); break;
			case 2:
				if (name.rfind("sprites/", 0) == 0) r.sprites.push_back(name);
				else r.models.push_back(name);
				break;
			default: r.generic.push_back(name); break; // decals/event scripts etc.
			}
		}
		// consistency info trailer: [1 bit need][if need: while bit: [1 isdelta][5 or 10 bits]]
		if (br.readBit()) {
			int last = 0;
			while (br.readBit()) {
				if (br.readBit()) last += (int)br.readUBits(5);
				else last = (int)br.readUBits(10);
			}
		}
		if (!r.models.empty() || !r.sounds.empty() || !r.sprites.empty() || !r.skins.empty())
			resources = std::move(r);
		reslistEntries = (int)(resources.models.size() + resources.sounds.size() +
		                       resources.skins.size() + resources.sprites.size() +
		                       resources.generic.size());
		reslistBits = (int)(br.bitPos() - startBit);
	}

	// ---- svc_customization: file metadata (name/size/type) for custom resources----
	void parseCustomization(BitReader& br) {
		br.skip(8);                 // playernum
		uint32_t type = br.readUBits(8);
		std::string name = br.readString();
		br.skip(16);                // index
		uint32_t size = br.readUBits(32);
		uint32_t flags = br.readUBits(8);
		if ((int)(flags & 0x04) != 0) br.skip(16 * 8); // RES_CUSTOM -> md5
		// remember: best-effort, only metadata; body goes through download channels
		{
			bool ok = !name.empty() && name.size() <= 250;
			for (char c : name)
				if ((unsigned char)c > 0x7e || (unsigned char)c < 0x20) { ok = false; break; }
			if (!ok) return;
		}
		ResourceInfo& r = resources;
		switch (type & 0xF) {
		case 0: r.sounds.push_back(name); break;
		case 1: r.skins.push_back(name); break;
		case 2: r.models.push_back(name); break;
		default: r.generic.push_back(name); break;
		}
		(void)size;
	}

	void skipDirector(BitReader& br);
	void readGSBitVec3CoordOut(BitReader& br, float* out, bool skipOnly);
	void readGSBitVec3Coord(BitReader& br);
};

// ---------------------------------------------------------------------------
// svc dispatcher
// ---------------------------------------------------------------------------
inline void DemoDecoder::handleSvc(uint8_t op, BitReader& br) {
	switch (op) {
	case SVC_NOP:
		break;
	case SVC_TIME:
		serverTime_ = br.readFloat();
		break;
	case SVC_DISCONNECT:
		br.readString();
		break;
	case SVC_PRINT:
	case SVC_STUFFTEXT:
	case SVC_CENTERPRINT:
		br.readString();
		break;
	case SVC_SETVIEW: {
		int ve = (int)br.readUBits(16);
		// Desynced streams read arbitrary 16-bit values; real entity ids are
		// well below MAX_EDICTS (4096).  Reject implausible ones but keep the
		// message length correct.
		if (ve <= 4095) {
			viewEntity_ = ve;
			setviewHistory_.push_back({curTick_, ve});
			if (std::getenv("CS16DB_DEBUG"))
				std::fprintf(stderr, "[setview] tick=%d entity=%d\n", curTick_, viewEntity_);
		}
		break;
	}
	case SVC_SETANGLE: {
		// MSG_WriteHiresAngle x3 (16 bits each, 360/65536 degrees)
		float a[3];
		bool ok = true;
		for (int i = 0; i < 3; ++i) {
			a[i] = (float)br.readUBits(16) * (360.0f / 65536.0f);
			if (a[i] > 360.0f + 1e-3f) ok = false; // angles wrap; larger = junk
		}
		if (ok) {
			std::memcpy(hltvAngles_, a, sizeof(a));
			hasHltvAngles_ = true;
		}
		break;
	}
	case SVC_SERVERDATA:
		br.skip(32);        // protocol
		br.skip(32);        // servercount
		br.skip(32);        // checksum
		br.skip(16 * 8);    // clientdll md5
		{
			uint32_t mc = br.readUBits(8);
			if (mc > 0 && mc <= 128) maxClients_ = (int)mc;
		}
		br.skip(8);         // playernum
		br.skip(8);         // quake leftover coop flag
		br.readString();    // game folder
		br.readString();    // remote host
		br.readString();    // map name (maps/...)
		br.readString();    // map cycle
		br.skip(8);         // vac2
		break;
	case SVC_LIGHTSTYLE:
		br.skip(8);
		br.readString();
		break;
	case SVC_INTERMISSION:
	case SVC_FINALE:
	case SVC_CUTSCENE:
	case SVC_CHOKE:
	case SVC_DAMAGE:
	case SVC_KILLEDMONSTER:
	case SVC_FOUNDSECRET:
		break;
	case SVC_CDTRACK:
		br.skip(8 + 8); // track, loop track
		break;
	case SVC_RESTORE: {
		br.readString();                 // savename
		int mapCount = (int)br.readUBits(8);
		for (int i = 0; i < mapCount; ++i) br.readString();
		break;
	}
	case SVC_SETPAUSE:
	case SVC_SIGNONNUM:
		br.skip(8);
		break;
	case SVC_CROSSHAIRANGLE:
		br.skip(8 + 8);
		break;
	case SVC_SOUNDFADE:
		br.skip(4 * 8); // fade percent, hold time, fade out/in seconds
		break;
	case SVC_WEAPONANIM:
		br.skip(8 + 8);
		break;
	case SVC_DECALNAME:
		br.skip(8);
		br.readString();
		break;
	case SVC_ROOMTYPE:
		br.skip(16);
		break;
	case SVC_ADDANGLE:
		br.skip(16);
		break;
	case SVC_RESOURCEREQUEST:
		br.skip(32 + 32); // servercount, start index
		break;
	case SVC_SENDEXTRAINFO:
		br.readString();
		br.skip(8);
		break;
	case SVC_TIMESCALE:
		br.skip(32);
		break;
	case SVC_UPDATEUSERINFO:
		br.skip(8);         // client slot
		br.skip(32);        // userid
		br.readString();    // userinfo
		br.skip(16 * 8);    // hashed cd key
		break;
	case SVC_DELTATABLE:
		parseDeltaTable(br);
		break;
	case SVC_CLIENTDATA:
		parseClientData(br);
		break;
	case SVC_SOUND:
		skipSound(br);
		break;
	case SVC_STOPSOUND:
		br.skip(16);
		break;
	case SVC_PARTICLE:
		br.skip(11 * 8); // vec3 coord + 3 chars + count + color
		break;
	case SVC_SPAWNSTATIC:
		skipSpawnStatic(br);
		break;
	case SVC_SPAWNSTATICSOUND:
		// [vec3 coord(16-bit coords)][short snd][byte vol][byte attn][short ent][byte pitch][byte flags]
		br.skip(16 * 3 + 16 + 8 + 8 + 16 + 8 + 8);
		break;
	case SVC_SPAWNBASELINE:
		parseBaselines(br);
		break;
	case SVC_EVENT:
	case SVC_EVENT_RELIABLE:
		parseEvents(br, op == SVC_EVENT_RELIABLE);
		break;
	case SVC_PINGS:
		while (br.readBit()) {
			br.skip(24); // slot(5) + ping(12) + packet loss(7)
		}
		break;
	case SVC_PACKETENTITIES:
		if (classicMode_) parsePacketEntitiesClassic(br, false);
		else parsePacketEntities(br, false);
		break;
	case SVC_DELTAPACKETENTITIES:
		if (classicMode_) parsePacketEntitiesClassic(br, true);
		else parsePacketEntities(br, true);
		break;
	case SVC_TEMP_ENTITY:
		skipTempEntity(br);
		break;
	case SVC_FILETXFERFAILED:
		br.readString();
		break;
	case SVC_HLTV: {
		uint32_t sub = br.readUBits(8);
		if (sub == 0) {
			// HLTV_ACTIVE: this demo was recorded by an HLTV proxy. Proxy
			// clients receive svc_clientdata without any payload (ReHLDS
			// SV_WriteClientdataToClient returns right after the opcode).
			spectator_ = true;
		} else if (sub == 1) {
			br.skip(10 * 8); // HLTV_STATUS: word + long + long
		} else if (sub == 2) {
			br.readString(); // HLTV_LISTEN
		}
		break;
	}
	case SVC_VOICEINIT:
		br.readString(); // codec name
		br.skip(8);      // voice quality
		break;
	case SVC_VOICEDATA: {
		br.skip(8); // client index
		uint32_t sz = br.readUBits(16);
		br.skip((int)(sz * 8));
		break;
	}
	case SVC_RESOURCELOCATION:
		br.readString();
		break;
	case SVC_QUERYCVARVALUE:
		br.readString();
		break;
	case SVC_QUERYCVARVALUE2:
		br.skip(32); // request id
		br.readString();
		break;
	case SVC_EXEC: {
		uint32_t isClass = br.readUBits(8);
		if (isClass) br.skip(8);
		break;
	}
	case SVC_CHANGING:
		br.skip(32); // protocol version
		break;
	case SVC_DIRECTOR:
		skipDirector(br);
		break;
	case SVC_DELTAMOVEVARS:
		// svc_deltamovevars / svc_newmovevars is NOT delta-encoded in the demo
		// stream: it is a plain movevars_t (16 floats, footsteps byte,
		// 8 floats, skyName string). See ReHLDS HLTV ParseMoveVars.
		br.skip(16 * 32); // gravity .. waveHeight
		br.skip(8);       // footsteps
		br.skip(8 * 32);  // rollangle, rollspeed, skycolor, skyvec
		br.readString();  // skyName
		break;
	case SVC_CUSTOMIZATION:
		parseCustomization(br);
		break;
	case SVC_RESOURCELIST:
		parseResourceList(br);
		break;
	case SVC_USERMESSAGE:
		parseNewUserMsg(br);
		break;
	default:
		if (op > SVC_LASTMSG) {
			skipUserMessage(op, br);
			break;
		}
		++skippedUnsupported;
		throw std::runtime_error("unsupported svc opcode: " + std::to_string((int)op));
	}
}

// ---------------------------------------------------------------------------
// svc_newusermsg: [byte id][byte size][16-byte name] (0xff size = variable)
// ---------------------------------------------------------------------------
inline void DemoDecoder::parseNewUserMsg(BitReader& br) {
	int id = (int)br.readUBits(8);
	int size = (int)br.readUBits(8);
	if (size == 0xFF) size = -1;
	char name[17] = {0};
	for (int i = 0; i < 16; ++i) name[i] = (char)br.readUBits(8);
	name[16] = 0;
	userMsgSizes_[id] = size;
	userMsgNames_[id] = name;
}

// ---------------------------------------------------------------------------
// user message payload (opcode itself is the registered message id)
// ---------------------------------------------------------------------------
inline void DemoDecoder::skipUserMessage(uint8_t op, BitReader& br) {
	auto ni = userMsgNames_.find(op);
	if (ni != userMsgNames_.end()) {
		// messages the engine handles itself, regardless of registered size
		if (ni->second == "ScreenShake") { br.skip(6 * 8); return; }
		if (ni->second == "ScreenFade") { br.skip(10 * 8); return; }
	}
	auto it = userMsgSizes_.find(op);
	int size = (it != userMsgSizes_.end()) ? it->second : -1;
	if (size < 0) size = (int)br.readUBits(8); // variable-length: actual size byte
	br.skip(size * 8);
}

// ---------------------------------------------------------------------------
// svc_deltatable: builds/extends delta tables (one message may carry one field)
// ---------------------------------------------------------------------------
inline void DemoDecoder::parseDeltaTable(BitReader& br) {
	std::string name = br.readString();
	uint32_t fieldCount = br.readUBits(16);

	// xash Delta_ParseTableField_GS: svc_deltatable does NOT describe the field
	// order. The server re-initializes the builtin delta.lst table and patches
	// matching entries (flags/bits/multipliers) by name. Unknown names are
	// appended only if a struct description exists. Decoding in wire order is
	// therefore wrong and desynchronizes every following delta record.
	ensureBuiltinTables();

	DeltaTable table;
	auto existing = tables_.find(name);
	if (existing != tables_.end())
		table = existing->second;
	else
		table.name = name;

	std::unordered_map<std::string, size_t> byName;
	for (size_t i = 0; i < table.fields.size(); ++i)
		byName[table.fields[i].name] = i;

	int patched = 0, appended = 0, unknown = 0;
	for (uint32_t i = 0; i < fieldCount; ++i) {
		GoldSrcMetaFields meta;
		readMetaFields(br, meta);
		uint32_t flags = meta.fieldType;
		if (flags & DT_SIGNED_GS) {
			flags &= ~DT_SIGNED_GS;
			flags |= DT_SIGNED;
		}
		auto it = byName.find(meta.fieldName);
		if (it != byName.end()) {
			DeltaField& f = table.fields[it->second];
			f.flags = flags;
			f.bits = meta.significant_bits ? (int)meta.significant_bits : 1;
			f.multiplier = meta.premultiply != 0 ? meta.premultiply : 1.0f;
			f.post_multiplier = meta.postmultiply;
			++patched;
			continue;
		}
		if (meta.fieldName.empty()) {
			++unknown;
			continue;
		}
		DeltaField f;
		f.name = meta.fieldName;
		f.flags = flags;
		f.bits = meta.significant_bits ? (int)meta.significant_bits : 1;
		f.multiplier = meta.premultiply != 0 ? meta.premultiply : 1.0f;
		f.post_multiplier = meta.postmultiply;
		byName[f.name] = table.fields.size();
		table.fields.push_back(f);
		++appended;
	}
	tables_[name] = std::move(table);
	tableStats[name]++;
	if (std::getenv("CS16DB_DEBUG"))
		std::fprintf(stderr, "[deltatable] %s wire=%u patched=%d appended=%d unknown=%d total=%zu\n",
		             name.c_str(), fieldCount, patched, appended, unknown,
		             tables_[name].fields.size());
}

// ---------------------------------------------------------------------------
// svc_clientdata
// ---------------------------------------------------------------------------
inline void DemoDecoder::parseClientData(BitReader& br) {
	// HLTV proxy: opcode only, no delta payload (ReHLDS SV_WriteClientdataToClient
	// returns immediately for client->proxy).
	if (spectator_)
		return;
	ensureBuiltinTables();
	auto it = tables_.find("clientdata_t");
	if (it == tables_.end()) {
		++skippedUnsupported; // table not ready yet: skip leniently
		return;
	}
	const DeltaTable& t = it->second;
	cd_has_origin = cd_has_viewangles = cd_has_fov = false;

	// ReHLDS SV_WriteClientdataToClient:
	//   [1 bit has_delta][if set: 8-bit delta_sequence][clientdata delta]
	//   [weapon updates: 1 bit per slot, 1 => 6-bit index + weapon_data_t delta]
	//   MSG_EndBitWriting pads the whole section to the next byte.
	if (br.readBit())
		br.skip(8);

	readDeltaFields(br, t, serverTime_, *this, &DemoDecoder::applyClientFieldThunk);

	auto wt = tables_.find("weapon_data_t");
	if (wt != tables_.end()) {
		int slots = 0;
		while (slots++ < 64 && br.readBit()) {
			br.skip(6); // weapon slot index
			EntityState sink;
			readDeltaFields(br, wt->second, serverTime_, sink, &ignoreDeltaField);
		}
	}
	br.skip((int)((8 - (br.bitPos() & 7)) & 7));

	if (cd_has_origin) {
		CameraSample c;
		c.tick = curTick_;
		c.time = curTime_;
		std::memcpy(c.origin, cd_origin, sizeof(c.origin));
		c.fov = cd_has_fov ? cd_fov : 90;
		auto ve = entities_.find(viewEntity_);
		if (cd_has_viewangles) {
			std::memcpy(c.viewangles, cd_viewangles, sizeof(c.viewangles));
			c.source = 1;
			cam_raw.push_back(c);
		} else if (ve != entities_.end() && ve->second.has_angles) {
			// spectator camera: origin from clientdata, orientation from view entity
			std::memcpy(c.viewangles, ve->second.angles, sizeof(c.viewangles));
			c.source = 4;
			cam_raw.push_back(c);
		}
	}
}

inline void DemoDecoder::applyClientField(const DeltaField& f, float v) {
	const std::string& n = f.name;
	if (n == "origin[0]") { cd_origin[0] = v; cd_has_origin = true; }
	else if (n == "origin[1]") { cd_origin[1] = v; cd_has_origin = true; }
	else if (n == "origin[2]") { cd_origin[2] = v; cd_has_origin = true; }
	else if (n == "viewangles[0]") { cd_viewangles[0] = v; cd_has_viewangles = true; }
	else if (n == "viewangles[1]") { cd_viewangles[1] = v; cd_has_viewangles = true; }
	else if (n == "viewangles[2]") { cd_viewangles[2] = v; cd_has_viewangles = true; }
	else if (n == "fov") { cd_fov = v; cd_has_fov = true; }
}

// ---------------------------------------------------------------------------
// svc_sound / svc_spawnstatic (skip via full interpretation)
// ---------------------------------------------------------------------------
inline void DemoDecoder::skipSound(BitReader& br) {
	static constexpr uint32_t S_vol = 0x001, S_att = 0x002, S_lg = 0x004, S_pitch = 0x008;
	uint32_t flags = br.readUBits(9);
	if (flags & S_vol) br.skip(8);
	if (flags & S_att) br.skip(8);
	br.skip(3);
	br.skip(MAX_GOLDSRC_ENTITY_BITS);
	int index = -1;
	if (flags & S_lg) { index = (int)br.readUBits(16); }
	else { index = (int)br.readUBits(8); }
	bool keep = ((sndCnt_++) % soundDecim_) == 0;
	float pos[3] = {0, 0, 0};
	readGSBitVec3CoordOut(br, pos, !keep);
	if (flags & S_pitch) br.skip(8);
	if (keep && index >= 0 && (pos[0] != 0 || pos[1] != 0 || pos[2] != 0)) {
		SoundEvent ev;
		ev.tick = curTick_;
		ev.time = curTime_;
		ev.index = index;
		std::memcpy(ev.origin, pos, sizeof(pos));
		soundEvents.push_back(ev);
	}
}

// svc_spawnstatic (PF_makestatic, ReHLDS pr_cmds.cpp):
//   short model, byte seq, byte frame, word colormap, byte skin,
//   3 x (coord short + angle byte), byte rendermode,
//   if rendermode: byte amt + 3 bytes color + byte renderfx
// Static entities keep server-side edict numbers that the client never sees
// (they are not transmitted in svc_spawnstatic); we store them with negative
// indices (-(N+1)) so they never collide with real entity ids.  They are
// constant for the whole demo, so they end up in every sampled frame and can
// be placed once by the Blender importer as free-standing props.
inline void DemoDecoder::skipSpawnStatic(BitReader& br) {
	EntityState e;
	e.index = -(int)(++staticCount_);
	e.modelindex = (int)br.readUBits(16);
	e.sequence = (int)br.readUBits(8);
	e.frame = (float)br.readUBits(8);
	br.skip(16); // colormap
	br.skip(8);  // skin
	for (int i = 0; i < 3; ++i) {
		e.origin[i] = (float)br.readUBits(16) / 8.0f; // MSG_WriteCoord (fixed 12.4)
		e.angles[i] = (float)br.readUBits(8) * (360.0f / 256.0f); // MSG_WriteAngle
	}
	e.has_origin = true;
	e.has_angles = true;
	uint32_t rendermode = br.readUBits(8);
	if (rendermode) br.skip(5 * 8); // renderamt, rgb, renderfx
	// a desynced bitstream produces absurd indices/coords; keep only plausible.
	// MSG_WriteCoord is 16-bit fixed-point (coord*8), so real coords |v| <= 4096.
	bool ok = e.modelindex > 0 && e.modelindex < 512;
	for (int i = 0; i < 3; ++i)
		if (e.origin[i] < -4096.0f || e.origin[i] > 4096.0f) ok = false;
	if (ok) {
		entities_[e.index] = std::move(e);
		staticEntities_[e.index] = entities_[e.index];
	}
	if (std::getenv("CS16DB_DEBUG"))
		std::fprintf(stderr, "[spawnstatic] tick=%d ok=%d model=%d origin=(%.1f %.1f %.1f)\n",
		             curTick_, ok ? 1 : 0, e.modelindex, e.origin[0], e.origin[1], e.origin[2]);
}

// ---------------------------------------------------------------------------
// svc_temp_entity: payload length is fixed per TE_* type (ReHLDS TE_LENGTH),
// except TE_BSPDECAL (13) and TE_TEXTMESSAGE (29) which are dynamic.
// ---------------------------------------------------------------------------
inline void DemoDecoder::skipTempEntity(BitReader& br) {
	// TE_LENGTH[type] = bytes after the type byte; -1 = dynamic, -2 = invalid.
	static const int16_t TE_LENGTH[128] = {
		24, 20,  6, 11,  6, 10, 12, 17, 16,  6,  6,  6,  8, -1,  9, 19,
		-2, 10, 16, 24, 24, 24, 10, 11, 16, 19, -2, 12, 16, -1, 19, 17,
		-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
		-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
		-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
		-2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2, -2,
		-2, -2, -2,  2, 10, 14, 12, 14,  9,  5, 17, 13, 24,  9, 17,  7,
		10, 19, 19, 12,  7,  7,  9, 16, 18,  6, 10, 13,  7,  1, 18, 15,
	};
	uint32_t type = br.readUBits(8);
	if (type >= 128) throw std::runtime_error("temp entity: type >= TE_MAX");
	int16_t len = TE_LENGTH[type];
	if (len == -2) throw std::runtime_error("temp entity: invalid type " + std::to_string((int)type));
	if (len == -1) {
		if (type == 13) { // TE_BSPDECAL: 3 coords + entity, then optional texture index
			br.skip(8 * 8);
			if (br.readUBits(16) != 0) br.skip(2 * 8);
			return;
		}
		if (type == 29) { // TE_TEXTMESSAGE
			br.skip(5 * 8);  // channel + x + y
			if (br.readUBits(8) == 2) br.skip(2 * 8); // effect == 2 -> fxtime
			br.skip(14 * 8); // rgba x2, fadein, fadeout, holdtime
			br.readString();
			return;
		}
		throw std::runtime_error("temp entity: unknown dynamic type " + std::to_string((int)type));
	}
	br.skip(len * 8);
}

// ---------------------------------------------------------------------------
// svc_event / svc_event_reliable
// ---------------------------------------------------------------------------
inline void DemoDecoder::parseEvents(BitReader& br, bool reliable) {
	auto dtIt = tables_.find("event_t");
	if (dtIt == tables_.end()) { ++skippedUnsupported; return; }
	const DeltaTable& t = dtIt->second;
	if (reliable) {
		br.skip(10);
		readDeltaFields(br, t, 0.0f, br, &DemoDecoder::noopDelta);
		if (br.readBit()) br.skip(16);
		return;
	}
	uint32_t numEvents = br.readUBits(5);
	for (uint32_t i = 0; i < numEvents; ++i) {
		br.skip(10);
		if (br.readBit()) {
			br.skip(MAX_GOLDSRC_ENTITY_BITS);
			if (br.readBit())
				readDeltaFields(br, t, 0.0f, br, &DemoDecoder::noopDelta);
		}
		if (br.readBit()) br.skip(16);
	}
}

// ---------------------------------------------------------------------------
// svc_spawnbaseline
// ---------------------------------------------------------------------------
inline void DemoDecoder::parseBaselines(BitReader& br) {
	int dbgCount = 0;
	while (true) {
		if (br.bitsLeft() < 16) throw std::runtime_error("baseline: truncated");
		if (br.peekUBits(16) == 0xffff) {
			br.skip(16);
			break;
		}
		size_t bitStart = br.bitPos();
		int entnum = (int)br.readUBits(MAX_GOLDSRC_ENTITY_BITS);
		uint32_t type = br.readUBits(2);
		if (std::getenv("CS16DB_TRACE") && dbgCount < 40)
			std::fprintf(stderr, "[baseline] #%d ent=%d type=%u bit=%zu left=%zu\n",
			             dbgCount, entnum, type, bitStart, br.bitsLeft());
		++dbgCount;
		bool player = entnum > 0 && entnum <= maxClients_;
		EntityState base;
		base.index = entnum;
		base.entityType = (int)type;
		const DeltaTable* t = nullptr;
		if (type & 2) t = &requireTable("custom_entity_state_t"); // ENTITY_BEAM = (1<<1)
		else if (player) t = &requireTable("entity_state_player_t");
		else t = &requireTable("entity_state_t");
		size_t deltaStart = br.bitPos();
		readDeltaFields(br, *t, 1.0f, base, applyEntityField);
		if (std::getenv("CS16DB_TRACE") && dbgCount <= 5)
			std::fprintf(stderr, "[baseline]   deltaBits=%zu end=%zu model=%d seq=%d orig=%.1f,%.1f,%.1f\n",
			             br.bitPos() - deltaStart, br.bitPos(), base.modelindex, base.sequence,
			             base.origin[0], base.origin[1], base.origin[2]);
		baselines_[entnum] = base;
	}
	uint32_t icount = br.readUBits(6);
	instancedBaselines_.clear();
	if (icount > 0) {
		const DeltaTable& t = requireTable("entity_state_t");
		for (uint32_t i = 0; i < icount; ++i) {
			EntityState es;
			readDeltaFields(br, t, 1.0f, es, applyEntityField);
			instancedBaselines_.push_back(es);
		}
		instancedBaselineMode_ = true;
	} else {
		instancedBaselineMode_ = false;
	}
}

// ---------------------------------------------------------------------------
// svc_packetentities / svc_deltapacketentities
// ---------------------------------------------------------------------------
inline void DemoDecoder::parsePacketEntities(BitReader& br, bool delta) {
	int count = (int)br.readUBits(16);
	int oldseq = delta ? (int)br.readUBits(8) : -1;
	int entnum = 0;
	int parsed = 0, removed = 0;
	if (std::getenv("CS16DB_TRACE"))
		std::fprintf(stderr, "[pktent] tick=%d bit=%zu delta=%d count=%d oldseq=%d\n",
		             curTick_, br.bitPos(), (int)delta, count, oldseq);
	while (true) {
		if (br.bitsLeft() < 16) throw std::runtime_error("packetentities: truncated");
		if (br.peekUBits(16) == 0) {
			br.skip(16);
			break;
		}
		// xash CL_ParseDeltaHeader
		bool remove = false;
		if (delta) {
			remove = br.readBit() != 0;
			if (br.readBit()) entnum = (int)br.readUBits(MAX_GOLDSRC_ENTITY_BITS);
			else entnum += (int)br.readUBits(6);
		} else {
			if (br.readBit()) entnum += 1;
			else if (!br.readBit()) entnum += (int)br.readUBits(6);
			else entnum = (int)br.readUBits(MAX_GOLDSRC_ENTITY_BITS);
		}
		if (std::getenv("CS16DB_TRACE") && parsed < 24)
			std::fprintf(stderr, "[pktent]   ent=%d remove=%d bit=%zu\n", entnum, (int)remove, br.bitPos());
		if (remove) {
			entities_.erase(entnum);
			++removed;
			continue;
		}
		++parsed;
		bool custom = br.readBit() != 0;
		bool hasInstanced = false;
		uint32_t instancedIndex = 0;
		if (instancedBaselineMode_) {
			hasInstanced = br.readBit() != 0;
			if (hasInstanced) instancedIndex = br.readUBits(6);
		}
		if (!delta && !hasInstanced) {
			// baseline offset (rare); 1 bit flag + 6-bit index
			if (br.readBit()) br.skip(6);
		}

		bool player = entnum > 0 && entnum <= maxClients_;
		EntityState st;
		st.index = entnum;
		if (hasInstanced && instancedIndex < instancedBaselines_.size()) {
			st = instancedBaselines_[instancedIndex];
			st.index = entnum;
			st.has_origin = true;
			st.has_angles = true;
		} else {
			auto itE = entities_.find(entnum);
			if (itE != entities_.end()) {
				st = itE->second;
			} else {
				auto itB = baselines_.find(entnum);
				if (itB != baselines_.end()) st = itB->second;
			}
		}

		const DeltaTable* t = nullptr;
		if (custom) t = &requireTable("custom_entity_state_t");
		else if (player) t = &requireTable("entity_state_player_t");
		else t = &requireTable("entity_state_t");
		readDeltaFields(br, *t, serverTime_, st, applyEntityField);
		entities_[entnum] = st;
	}
	if (std::getenv("CS16DB_TRACE"))
		std::fprintf(stderr, "[pktent]   parsed=%d removed=%d cached=%zu endbit=%zu\n",
		             parsed, removed, entities_.size(), br.bitPos());
}

// Classic (proto 47) entity packet layout (MSG_ReadDeltaEntity):
//   [13-bit entity number] loop, LAST_EDICT(0x1FFF) terminates
//   [2-bit fRemoveType] [1+7 baseline] [1+2 entityType] fields...
inline void DemoDecoder::parsePacketEntitiesClassic(BitReader& br, bool delta) {
	br.skip(11); // entity count (+1), unused
	if (delta) br.skip(8); // old packet sequence
	while (true) {
		if (br.bitsLeft() < 13) throw std::runtime_error("packetentities(c): truncated");
		int entnum = (int)br.readUBits(13);
		if (entnum == 0x1FFF) break; // LAST_EDICT

		uint32_t rm = br.readUBits(2);
		if (rm == 1) continue;  // removed from delta message, keep state
		if (rm == 2) {          // removed from server
			entities_.erase(entnum);
			continue;
		}
		if (br.readBit()) br.skip(7); // baseline offset

		bool custom = false;
		if (br.readBit()) {
			custom = (br.readUBits(2) & 1) != 0; // ENTITY_BEAM
		}

		bool player = entnum > 0 && entnum <= maxClients_;
		EntityState st;
		st.index = entnum;
		{
			auto itE = entities_.find(entnum);
			if (itE != entities_.end()) st = itE->second;
			else {
				auto itB = baselines_.find(entnum);
				if (itB != baselines_.end()) st = itB->second;
			}
		}
		const DeltaTable* t = nullptr;
		if (custom) t = &requireTable("custom_entity_state_t");
		else if (player) t = &requireTable("entity_state_player_t");
		else t = &requireTable("entity_state_t");
		readDeltaFields(br, *t, serverTime_, st, applyEntityField, /*classicMode=*/true);
		entities_[entnum] = st;
	}
}

// ---------------------------------------------------------------------------
// svc_resourcelist: resource inventory (models/sounds/sprites used by the server)
// ---------------------------------------------------------------------------
inline void DemoDecoder::skipDirector(BitReader& br) {
	uint32_t size = br.readUBits(8);
	br.skip((int)(size * 8));
}

inline void DemoDecoder::readGSBitVec3Coord(BitReader& br) {
	readGSBitVec3CoordOut(br, nullptr, false);
}

inline void DemoDecoder::readGSBitVec3CoordOut(BitReader& br, float* out, bool skipOnly) {
	// xash MSG_ReadGSBitVec3Coord: 3 presence bits first, then the values
	bool present[3];
	for (int i = 0; i < 3; ++i) present[i] = br.readBit();
	for (int i = 0; i < 3; ++i) {
		if (!present[i]) continue;
		bool iv = br.readBit();
		bool fv = br.readBit();
		float v = 0;
		if (iv || fv) {
			bool sign = br.readBit();
			float ival = 0, fval = 0;
			if (iv) ival = (float)br.readUBits(12);
			if (fv) fval = (float)br.readUBits(3);
			v = fval / 8.0f + ival;
			if (sign) v = -v;
		}
		if (out && !skipOnly) out[i] = v;
	}
}

} // namespace gs
