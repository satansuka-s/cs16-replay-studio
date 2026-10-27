// GoldSrc delta decoding: delta tables (svc_deltatable) and field values.
// Semantics mirror Xash3D net_encode.c (Delta_ReadGSFields / Delta_ReadField_) and
// khanghugo/dem (delta_description.rs).
#pragma once
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#include "bitreader.hpp"
#include "netprotocol.hpp"

namespace gs {

struct DeltaField {
	std::string name;
	uint32_t flags = 0;
	int bits = 0;
	float multiplier = 1.0f;
	float post_multiplier = 1.0f;

	bool isSigned() const { return (flags & DT_SIGNED) != 0; }

	float readFloatValue(BitReader& br, float timebase) const {
		if (flags & DT_ANGLE) {
			uint32_t raw = br.readUBits(bits);
			return (float)raw * (360.0f / (float)(1 << bits));
		}
		if (flags & DT_TIMEWINDOW_8) {
			int i = br.readSBits(bits);
			return (timebase * 100.0f - (float)i) / 100.0f;
		}
		if (flags & DT_TIMEWINDOW_BIG) {
			int i = br.readSBits(bits);
			return (timebase * multiplier - (float)i) / multiplier;
		}
		// integer-like (BYTE/SHORT/INTEGER/FLOAT are all read as fixed-point ints)
		int32_t raw = br.readSBits(bits);
		float v = (float)raw;
		if (multiplier != 1.0f) v /= multiplier;
		if (post_multiplier != 1.0f) v *= post_multiplier;
		return v;
	}

	std::string readStringValue(BitReader& br) const {
		return br.readString();
	}

	bool isString() const { return (flags & DT_STRING) != 0; }

	void apply(BitReader& br, float timebase, float& out) const { out = readFloatValue(br, timebase); }
};

// One delta table as transmitted by svc_deltatable (name + ordered fields).
struct DeltaTable {
	std::string name;
	std::vector<DeltaField> fields;

	const DeltaField* find(const std::string& fname) const {
		for (const auto& f : fields)
			if (f.name == fname) return &f;
		return nullptr;
	}
};

// Minimal entity state snapshot (fields we track).
struct EntityState {
	int index = -1;
	float origin[3] = {0, 0, 0};
	float angles[3] = {0, 0, 0};
	float velocity[3] = {0, 0, 0};
	int modelindex = 0;
	int sequence = 0;
	float frame = 0;
	float animtime = 0;
	float framerate = 0;
	int body = 0;
	int skin = 0;
	int effects = 0;
	bool has_origin = false;
	bool has_angles = false;
	int entityType = 0; // 2-bit baseline type
};

// The 7 meta fields of goldsrc_delta_t, in network order (net_encode.c dt_goldsrc_meta).
struct GoldSrcMetaFields {
	uint32_t fieldType = 0;
	std::string fieldName;
	uint32_t fieldOffset = 0;
	uint32_t fieldSize = 0;
	uint32_t significant_bits = 0;
	float premultiply = 0;
	float postmultiply = 0;
};

inline bool readMetaFields(BitReader& br, GoldSrcMetaFields& m) {
	// Delta_ParseGSFields with dt_goldsrc_meta:
	//   [3 bits bytecount][bytecount mask bytes]
	//   then for each set bit, the meta field in order:
	//     fieldType(INTEGER 32), fieldName(STRING), fieldOffset(INTEGER 16),
	//     fieldSize(INTEGER 8), significant_bits(INTEGER 8),
	//     premultiply(FLOAT, mult 4000), postmultiply(FLOAT, mult 4000)
	uint32_t c = br.readUBits(3);
	if (c > 8) throw std::runtime_error("delta meta: bad byte count");
	uint8_t mask[8] = {0};
	for (uint32_t i = 0; i < c; ++i)
		mask[i] = (uint8_t)br.readUBits(8);

	int i = 0;
	if (c > 0 && (mask[i >> 3] & (1 << (i & 7)))) m.fieldType = br.readUBits(32);
	++i;
	if (c > 0 && (mask[i >> 3] & (1 << (i & 7)))) m.fieldName = br.readString();
	++i;
	if (c > 0 && (mask[i >> 3] & (1 << (i & 7)))) m.fieldOffset = br.readUBits(16);
	++i;
	if (c > 0 && (mask[i >> 3] & (1 << (i & 7)))) m.fieldSize = br.readUBits(8);
	++i;
	if (c > 0 && (mask[i >> 3] & (1 << (i & 7)))) m.significant_bits = br.readUBits(8);
	++i;
	if (c > 0 && (mask[i >> 3] & (1 << (i & 7)))) m.premultiply = br.readFloat() / 4000.0f;
	++i;
	if (c > 0 && (mask[i >> 3] & (1 << (i & 7)))) m.postmultiply = br.readFloat() / 4000.0f;
	return true;
}

// Read one delta record's fields. Two stream layouts:
//  - GoldSrc (proto 48/49): 3-bit byte count + mask bytes + changed values
//  - classic  (proto 47):   per field: 1 bit changed + optional value
template <typename StateT>
void readDeltaFields(BitReader& br, const DeltaTable& table, float timebase, StateT& to,
                     void (*apply)(StateT&, const DeltaField&, float), bool classicMode = false) {
	if (!classicMode) {
		uint32_t c = br.readUBits(3);
		if (c > 8) throw std::runtime_error("delta: bad byte count");
		uint8_t mask[8] = {0};
		for (uint32_t i = 0; i < c; ++i)
			mask[i] = (uint8_t)br.readUBits(8);

		for (size_t i = 0; i < table.fields.size(); ++i) {
			size_t byteIdx = i >> 3;
			if (byteIdx >= 8) break;
			if (mask[byteIdx] & (1 << (i & 7))) {
				const DeltaField& f = table.fields[i];
				if (f.isString())
					f.readStringValue(br); // ignore string fields (not used in entity state we track)
				else
					apply(to, f, f.readFloatValue(br, timebase));
			}
		}
	} else {
		// classic proto 47: per-field changed bit, no mask
		for (const auto& f : table.fields) {
			if (!br.readBit()) continue;
			if (f.isString())
				f.readStringValue(br);
			else
				apply(to, f, f.readFloatValue(br, timebase));
		}
	}
}

} // namespace gs
