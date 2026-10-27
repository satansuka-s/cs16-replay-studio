// Parser for CS 1.6 cstrike/delta.lst (builtin delta table definitions).
// Format:
//   table_name [dll] [func]
//   {
//       DEFINE_DELTA( field, FLAGS, bits, multiplier ),
//       DEFINE_DELTA_POST( field, FLAGS, bits, multiplier, post_multiplier )
//   }
#pragma once
#include <cctype>
#include <string>
#include <vector>
#include "delta.hpp"
#include "netprotocol.hpp"

namespace gs {

namespace impl {

inline std::string trim(const std::string& s) {
	size_t a = 0, b = s.size();
	while (a < b && std::isspace((unsigned char)s[a])) ++a;
	while (b > a && std::isspace((unsigned char)s[b - 1])) --b;
	return s.substr(a, b - a);
}

inline uint32_t parseDeltaFlag(const std::string& tok) {
	if (tok == "DT_BYTE") return DT_BYTE;
	if (tok == "DT_SHORT") return DT_SHORT;
	if (tok == "DT_FLOAT") return DT_FLOAT;
	if (tok == "DT_INTEGER") return DT_INTEGER;
	if (tok == "DT_ANGLE") return DT_ANGLE;
	if (tok == "DT_TIMEWINDOW_8") return DT_TIMEWINDOW_8;
	if (tok == "DT_TIMEWINDOW_BIG") return DT_TIMEWINDOW_BIG;
	if (tok == "DT_STRING") return DT_STRING;
	if (tok == "DT_SIGNED") return DT_SIGNED;
	return 0;
}

// tokenize "a, b | c" style arguments preserving [] in field names
inline void splitArgs(const std::string& s, std::vector<std::string>& out) {
	std::string cur;
	int depth = 0;
	for (char ch : s) {
		if (ch == '[') depth++;
		if (ch == ']') depth--;
		if (ch == ',' && depth == 0) {
			out.push_back(trim(cur));
			cur.clear();
		} else cur.push_back(ch);
	}
	out.push_back(trim(cur));
}

inline bool parseFloat(const std::string& s, float& v) {
	try {
		size_t pos = 0;
		v = std::stof(s, &pos);
		return pos == s.size();
	} catch (...) { return false; }
}

} // namespace impl

// Parse the whole delta.lst text; fill `table` for the wanted structure name.
// Returns true if found. Unsupported field types are skipped.
inline bool parseDeltaLstTable(const std::string& text, const std::string& want, DeltaTable& table) {
	std::string current;
	bool inTable = false;
	bool inBody = false;
	table.name = want;
	table.fields.clear();

	std::vector<std::string> lines;
	{
		std::string cur;
		for (char c : text) {
			if (c == '\n') { lines.push_back(cur); cur.clear(); }
			else cur.push_back(c);
		}
		if (!cur.empty()) lines.push_back(cur);
	}

	for (const auto& raw : lines) {
		std::string ln = impl::trim(raw);
		if (ln.empty()) continue;

		// strip // comments
		auto pos = ln.find("//");
		if (pos != std::string::npos) ln = ln.substr(0, pos);
		ln = impl::trim(ln);
		if (ln.empty()) continue;

		if (!inTable) {
			// structure header: "clientdata_t none" or "entity_state_t gamedll Entity_Encode"
			size_t sp = ln.find(' ');
			std::string name = ln;
			if (sp != std::string::npos) name = ln.substr(0, sp);
			inTable = (name == want);
			if (inTable) {
				inBody = false;
			}
			continue;
		}
		if (!inBody) {
			if (ln == "{") { inBody = true; }
			continue;
		}
		if (ln == "}") {
			return !table.fields.empty();
		}

		// DEFINE_DELTA( ... ) / DEFINE_DELTA_POST( ... )
		if (ln.rfind("DEFINE_DELTA", 0) != 0) continue;
		bool post = ln.rfind("DEFINE_DELTA_POST", 0) == 0;
		auto open = ln.find('(');
		auto close = ln.rfind(')');
		if (open == std::string::npos || close == std::string::npos || close <= open) continue;
		std::vector<std::string> args;
		impl::splitArgs(ln.substr(open + 1, close - open - 1), args);
		if (args.size() < 4) continue;

		DeltaField f;
		f.name = impl::trim(args[0]);
		// flags: "DT_SIGNED | DT_FLOAT"
		{
			std::string fl = args[1];
			std::string tok;
			for (char ch : fl) {
				if (std::isalnum((unsigned char)ch) || ch == '_') tok.push_back(ch);
				else { f.flags |= impl::parseDeltaFlag(tok); tok.clear(); }
			}
			f.flags |= impl::parseDeltaFlag(tok);
		}
		f.bits = std::atoi(args[2].c_str());
		if (!impl::parseFloat(args[3], f.multiplier)) f.multiplier = 1.0f;
		if (post && args.size() >= 5)
			impl::parseFloat(args[4], f.post_multiplier);
		else
			f.post_multiplier = 1.0f;
		if (f.bits <= 0 || f.bits > 32) continue;
		table.fields.push_back(std::move(f));
	}
	return !table.fields.empty();
}

} // namespace gs
