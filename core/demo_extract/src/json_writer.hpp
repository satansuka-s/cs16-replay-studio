// Minimal JSON emission helpers: raw string building + string escaping.
#pragma once
#include <cstdio>
#include <string>

namespace gs {

inline std::string json_escape(const std::string& s) {
	std::string out;
	out.push_back('"');
	for (char c : s) {
		switch (c) {
		case '"': out += "\\\""; break;
		case '\\': out += "\\\\"; break;
		case '\n': out += "\\n"; break;
		case '\r': out += "\\r"; break;
		case '\t': out += "\\t"; break;
		default:
			if ((unsigned char)c < 0x20) {
				char buf[8];
				std::snprintf(buf, sizeof(buf), "\\u%04x", (unsigned)c);
				out += buf;
			} else out.push_back(c);
		}
	}
	out.push_back('"');
	return out;
}

inline std::string json_float(double v, const char* fmt = "%.7g") {
	if (v != v || v > 1e30 || v < -1e30) return "0"; // NaN/inf safety
	char buf[64];
	std::snprintf(buf, sizeof(buf), fmt, v);
	return buf;
}

} // namespace gs
