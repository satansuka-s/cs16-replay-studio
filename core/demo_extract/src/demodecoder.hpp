// GoldSrc demo net-stream decoder: svc message sequences, delta tables,
// entity state tracking, camera extraction.
#pragma once
#include <algorithm>
#include <cstdint>
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
		BitReader br(data, len);
		while (br.bitsLeft() >= 8) {
			uint8_t op = (uint8_t)br.readUBits(8);
			opStats[op]++;
			if (op == SVC_BAD) {
				// delimiter/alignment artifact in recorded streams
				++skippedUnsupported;
				break;
			}
			handleSvc(op, br);
		}
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
	}

	void finish() {
		std::sort(cam_raw.begin(), cam_raw.end(),
		          [](const CameraSample& a, const CameraSample& b) { return a.tick < b.tick; });
		camera = std::move(cam_raw);
	}

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
	std::map<std::string, DeltaTable> tables_;
	std::map<int, EntityState> entities_;
	std::map<int, EntityState> baselines_;
	std::vector<EntityState> instancedBaselines_;

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
	}

	bool builtinLoaded_ = false;
	bool classicMode_ = false; // proto 47 entity packet layout
	int viewEntity_ = 0; // last svc_setview target

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
	void parseClientData(BitReader& br);
	void applyClientField(const DeltaField& f, float v);
	void skipSound(BitReader& br);
	void skipSpawnStatic(BitReader& br);
	void parseEvents(BitReader& br, bool reliable);
	void parseBaselines(BitReader& br);
	void parsePacketEntities(BitReader& br, bool delta);
	void parsePacketEntitiesClassic(BitReader& br, bool delta);
	// ---- svc_resourcelist (Xash CL_ParseResourceList, GoldSrc) ----
	void parseResourceList(BitReader& br) {
		uint32_t total = br.readUBits(12);
		ResourceInfo r;
		for (uint32_t i = 0; i < total; ++i) {
			uint32_t type = br.readUBits(4);
			std::string name = br.readString();
			br.skip(12); // index
			br.skip(24); // download size
			uint32_t flags = br.readUBits(3);
			if (flags & 0x02) br.skip(16 * 8); // RES_CUSTOM: md5
			if (br.readBit()) br.skip(16 * 8); // reserved (HLSDK resource_t, future use)
			// sanity: recorded streams often lack a real resourcelist payload;
			// bail out if entries look degenerate (empty names, absurd counts)
			{
				bool nameOk = !name.empty() && name.size() <= 250;
				for (char c : name)
					if ((unsigned char)c > 0x7e || (unsigned char)c < 0x20) { nameOk = false; break; }
				if (!nameOk || i > 600 || br.bitsLeft() < 32) {
					return; // degenerate/not a real resource list; keep previous state
				}
			}
			switch (type & 0xF) {
			case 0: r.models.push_back(name); break;   // t_model
			case 1: r.sounds.push_back(name); break;   // t_sound
			case 2: r.skins.push_back(name); break;    // t_skin
			case 3: r.sprites.push_back(name); break;  // t_sprite
			default: r.generic.push_back(name); break; // t_generic etc
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
	}

	// ---- svc_customization: file metadata (name/size/type) for custom resources----
	void parseCustomization(BitReader& br) {
		br.skip(8);                 // playernum
		uint32_t type = br.readUBits(8);
		std::string name = br.readString();
		br.skip(16);                // index
		uint32_t size = br.readUBits(32);
		uint32_t flags = br.readUBits(8);
		if ((int)(flags & 0x40) != 0) br.skip(16 * 8); // RES_CUSTOM -> md5
		// remember: best-effort, only metadata; body goes through download channels
		{
			bool ok = !name.empty() && name.size() <= 250;
			for (char c : name)
				if ((unsigned char)c > 0x7e || (unsigned char)c < 0x20) { ok = false; break; }
			if (!ok) return;
		}
		ResourceInfo& r = resources;
		switch (type & 0xF) {
		case 0: r.models.push_back(name); break;
		case 1: r.sounds.push_back(name); break;
		case 2: r.skins.push_back(name); break;
		case 3: r.sprites.push_back(name); break;
		default: r.generic.push_back(name); break;
		}
		(void)size;
	}

	void skipDirector(BitReader& br);
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
	case SVC_PRINT:
	case SVC_STUFFTEXT:
	case SVC_CENTERPRINT:
		br.readString();
		break;
	case SVC_SETVIEW:
		viewEntity_ = (int)br.readUBits(16);
		break;
	case SVC_SETANGLE:
		br.skip(16 * 3);
		break;
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
		br.skip(32);
		break;
	case SVC_INTERMISSION:
	case SVC_FINALE:
	case SVC_CUTSCENE:
	case SVC_CHOKE:
		break;
	case SVC_CDTRACK:
	case SVC_RESTORE:
		br.readString();
		break;
	case SVC_SETPAUSE:
	case SVC_SIGNONNUM:
	case SVC_CROSSHAIRANGLE:
		br.skip(8);
		break;
	case SVC_WEAPONANIM:
		br.skip(8 + 8);
		break;
	case SVC_ADDANGLE:
		br.skip(16 * 3);
		break;
	case SVC_RESOURCEREQUEST:
		br.skip(16);
		br.readString();
		break;
	case SVC_SENDEXTRAINFO:
		br.readString();
		br.skip(8);
		break;
	case SVC_TIMESCALE:
		br.skip(32);
		break;
	case SVC_UPDATEUSERINFO:
		br.skip(8);
		br.readString();
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
			br.skip(5);  // slot (MAX_CLIENT_BITS)
			br.skip(12); // ping
			br.skip(7);  // packet loss
		}
		break;
	case SVC_RESTORESOUND:
		br.readString();
		break;
	case SVC_PACKETENTITIES:
		if (classicMode_) parsePacketEntitiesClassic(br, false);
		else parsePacketEntities(br, false);
		break;
	case SVC_DELTAPACKETENTITIES:
		if (classicMode_) parsePacketEntitiesClassic(br, true);
		else parsePacketEntities(br, true);
		break;
	case SVC_HLTV:
		br.skip(8);
		break;
	case SVC_DIRECTOR:
		skipDirector(br);
		break;
	case SVC_DELTAMOVEVARS: {
		auto it = tables_.find("movevars_t");
		if (it == tables_.end()) { ++skippedUnsupported; break; }
		readDeltaFields(br, it->second, serverTime_, br, &DemoDecoder::noopDelta);
		break;
	}
	case SVC_CUSTOMIZATION:
		parseCustomization(br);
		break;
	case SVC_RESOURCELIST:
		parseResourceList(br);
		break;
	default:
		if (op > SVC_LASTMSG) {
			// user message: [byte id][byte size][size bytes]
			br.skip(8);
			uint32_t sz = br.readUBits(8);
			br.skip((int)(sz * 8));
			break;
		}
		++skippedUnsupported;
		throw std::runtime_error("unsupported svc opcode: " + std::to_string((int)op));
	}
}

// ---------------------------------------------------------------------------
// svc_deltatable: builds/extends delta tables (one message may carry one field)
// ---------------------------------------------------------------------------
inline void DemoDecoder::parseDeltaTable(BitReader& br) {
	std::string name = br.readString();
	uint32_t fieldCount = br.readUBits(16);
	DeltaTable& table = tables_[name];
	table.name = name;
	for (uint32_t i = 0; i < fieldCount; ++i) {
		GoldSrcMetaFields meta;
		readMetaFields(br, meta);
		DeltaField f;
		f.name = meta.fieldName;
		f.flags = meta.fieldType;
		if (f.flags & DT_SIGNED_GS) {
			f.flags &= ~DT_SIGNED_GS;
			f.flags |= DT_SIGNED;
		}
		f.bits = meta.significant_bits ? (int)meta.significant_bits : 1;
		f.multiplier = meta.premultiply != 0 ? meta.premultiply : 1.0f;
		f.post_multiplier = meta.postmultiply;
		table.fields.push_back(f);
	}
	tableStats[name]++;
}

// ---------------------------------------------------------------------------
// svc_clientdata
// ---------------------------------------------------------------------------
inline void DemoDecoder::parseClientData(BitReader& br) {
	auto it = tables_.find("clientdata_t");
	if (it == tables_.end()) {
		++skippedUnsupported; // table not ready yet: skip leniently
		return;
	}
	const DeltaTable& t = it->second;
	cd_has_origin = cd_has_viewangles = cd_has_fov = false;
	readDeltaFields(br, t, serverTime_, *this, &DemoDecoder::applyClientFieldThunk);
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
	if (flags & S_lg) br.skip(16);
	else br.skip(8);
	readGSBitVec3Coord(br);
	if (flags & S_pitch) br.skip(8);
}

inline void DemoDecoder::skipSpawnStatic(BitReader& br) {
	readGSBitVec3Coord(br);
	br.skip(16 + 16 + 8 + 8 + 16 + 16 + 8);
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
	while (true) {
		if (br.bitsLeft() < 16) throw std::runtime_error("baseline: truncated");
		if (br.peekUBits(16) == 0xffff) {
			br.skip(16);
			break;
		}
		int entnum = (int)br.readUBits(MAX_GOLDSRC_ENTITY_BITS);
		uint32_t type = br.readUBits(2);
		bool player = entnum > 0 && entnum <= maxClients_;
		EntityState base;
		base.index = entnum;
		base.entityType = (int)type;
		const DeltaTable* t = nullptr;
		if (type & 1) t = &requireTable("custom_entity_state_t");
		else if (player) t = &requireTable("entity_state_player_t");
		else t = &requireTable("entity_state_t");
		readDeltaFields(br, *t, 1.0f, base, applyEntityField);
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
	br.skip(16); // entity count
	if (delta) br.skip(8); // delta sequence
	int entnum = 0;
	while (true) {
		if (br.bitsLeft() < 16) throw std::runtime_error("packetentities: truncated");
		if (br.peekUBits(16) == 0) {
			br.skip(16);
			break;
		}
		bool remove = false;
		if (delta) remove = br.readBit();

		if (br.readBit()) {
			entnum += 1;
		} else {
			if (!br.readBit()) {
				entnum += (int)br.readUBits(6);
			} else {
				entnum = (int)br.readUBits(MAX_GOLDSRC_ENTITY_BITS);
			}
		}
		if (remove) {
			entities_.erase(entnum);
			continue;
		}
		bool custom = br.readBit() != 0;
		bool hasInstanced = false;
		uint32_t instancedIndex = 0;
		if (instancedBaselineMode_) {
			if (br.readBit()) {
				hasInstanced = true;
				instancedIndex = br.readUBits(6);
			} else if (!delta) {
				if (br.readBit()) br.skip(6);
			}
		} else if (!delta) {
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
	for (int i = 0; i < 3; ++i)
		if (br.readBit()) {
			bool iv = br.readBit();
			bool fv = br.readBit();
			if (iv || fv) {
				br.readBit(); // sign
				if (iv) br.skip(12);
				if (fv) br.skip(3);
			}
		}
}

} // namespace gs
