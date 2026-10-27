// demo_extract: GoldSrc (CS 1.6) demo -> per-tick JSON of camera + entity states.
//
// Usage:
//   demo_extract <demo.dem> <output.json> [tick_interval] [--cam-only] [--max-clients N]
//
// Pipeline: HLDemo (structural parsing) + internal GoldSrc svc/delta decoder
// (entity_state tracking over delta updates, Xash3D-compatible semantics).
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include "DemoFile.hpp"
#include "DemoFrame.hpp"
#include "demodecoder.hpp"
#include "json_writer.hpp"

using namespace gs;

static int g_tickInterval = 1;
static int g_maxClients = MAX_CLIENTS;

static std::string fieldFloat(double v) { return json_float(v); }

static void emitVec(std::string& j, const char* indent, const float v[3]) {
	j += indent; j += "[";
	j += fieldFloat(v[0]); j += ", ";
	j += fieldFloat(v[1]); j += ", ";
	j += fieldFloat(v[2]); j += "]";
}

static bool run(const std::string& demopath, const std::string& outpath, bool camOnly) {
	DemoFile demo(demopath, true);
	DemoDecoder dec;
	dec.begin(g_tickInterval, g_maxClients, (int)demo.header.netProtocol);

	const DemoHeader& h = demo.header;
	int framesParsed = 0;
	int camFrames = 0;

	auto visit = [&](const DemoFrame* f) {
		switch (f->type) {
		case DemoFrameType::CLIENT_DATA: {
			auto* cd = static_cast<const ClientDataFrame*>(f);
			float origin[3], angles[3];
			std::memcpy(origin, cd->origin, sizeof(origin));
			std::memcpy(angles, cd->viewangles, sizeof(angles));
			dec.addCameraFrame(origin, angles, cd->fov, f->frame, f->time);
			camFrames++;
			break;
		}
		case DemoFrameType::DEMO_BUFFER: {
			auto* db = static_cast<const DemoBufferFrame*>(f);
			if (!db->buffer.empty())
				dec.parseNetmsg(db->buffer.data(), db->buffer.size(), f->frame, f->time);
			break;
		}
		default: {
			if ((int)f->type <= 1) {
				auto* nm = static_cast<const NetMsgFrame*>(f);
				// camera source 2: RefParams inside the 464-byte demo info prefix
				{
					float origin[3], angles[3];
					std::memcpy(origin, nm->DemoInfo.RefParams.vieworg, sizeof(origin));
					std::memcpy(angles, nm->DemoInfo.RefParams.viewangles, sizeof(angles));
					float fov = nm->DemoInfo.RefParams.viewsize;
					if (fov <= 0 || fov > 170) fov = 90;
					dec.addCameraFrameSrc(origin, angles, fov, f->frame, f->time, 2);
				}
				if (!nm->msg.empty())
					dec.parseNetmsg(nm->msg.data(), nm->msg.size(), f->frame, f->time);
			}
		}
		}
		dec.sampleTick(f->frame, f->time);
		framesParsed++;
		if (framesParsed % 20000 == 0)
			std::cerr << "  ... " << framesParsed << " frames\n";
	};

	try {
		for (const auto& entry : demo.directoryEntries)
			for (const auto& f : entry.frames) {
				try {
					visit(f.get());
				} catch (const std::exception& e) {
					std::cerr << "warning: frame " << framesParsed << " skipped: " << e.what() << "\n";
				}
			}
	} catch (const std::exception& e) {
		std::cerr << "warning: parsing stopped early: " << e.what() << "\n";
	}
	dec.finish();

	// --- write JSON ---
	std::string j;
	j += "{\n";
	j += "\"demo\": " + json_escape(demopath) + ",\n";
	j += "\"map\": " + json_escape(h.mapName) + ",\n";
	j += "\"game\": " + json_escape(h.gameDir) + ",\n";
	j += "\"demo_protocol\": " + std::to_string(h.demoProtocol) + ",\n";
	j += "\"net_protocol\": " + std::to_string(h.netProtocol) + ",\n";
	j += "\"tick_interval\": " + std::to_string(g_tickInterval) + ",\n";
	j += "\"max_clients\": " + std::to_string(g_maxClients) + ",\n";
	j += "\"frames_parsed\": " + std::to_string(framesParsed) + ",\n";
	j += "\"camera_frames\": " + std::to_string(camFrames) + ",\n";
	j += "\"notes\": \"coordinates: GoldSrc units (inches), Z-up; angles: pitch/yaw/roll degrees\"";

	// camera
	j += ",\n\"camera\": [\n";
	{
		bool first = true;
		for (const auto& c : dec.camera) {
			if (!first) j += ",\n";
			first = false;
			j += "{\n";
			j += "\"tick\": " + std::to_string(c.tick) + ",\n";
			j += "\"time\": " + fieldFloat(c.time) + ",\n";
			j += "\"origin\": "; emitVec(j, "", c.origin); j += ",\n";
			j += "\"viewangles\": "; emitVec(j, "", c.viewangles); j += ",\n";
			j += "\"fov\": " + fieldFloat(c.fov) + ",\n";
			j += "\"source\": " + std::to_string(c.source) + "\n";
			j += "}";
		}
		j += "\n]";
	}

	if (camOnly) {
		j += "\n}\n";
		std::ofstream ofs(outpath, std::ios::binary);
		ofs << j;
		return ofs.good();
	}

	// entity frames
	j += ",\n\"frames\": [\n";
	{
		bool firstFrame = true;
		for (const auto& f : dec.frames) {
			if (!firstFrame) j += ",\n";
			firstFrame = false;
			j += "{\n";
			j += "\"tick\": " + std::to_string(f.tick) + ",\n";
			j += "\"time\": " + fieldFloat(f.time) + ",\n";
			j += "\"entities\": [\n";
			{
				bool firstEnt = true;
				for (const auto& e : f.entities) {
					if (!firstEnt) j += ",\n";
					firstEnt = false;
					j += "{\n";
					j += "\"index\": " + std::to_string(e.index);
					j += ",\n\"player\": " + std::string(e.index > 0 && e.index <= g_maxClients ? "true" : "false");
					if (e.has_origin) {
						j += ",\n\"origin\": "; emitVec(j, "", e.origin);
					}
					if (e.has_angles) {
						j += ",\n\"angles\": "; emitVec(j, "", e.angles);
					}
					if (e.velocity[0] || e.velocity[1] || e.velocity[2]) {
						j += ",\n\"velocity\": "; emitVec(j, "", e.velocity);
					}
					j += ",\n\"modelindex\": " + std::to_string(e.modelindex);
					j += ",\n\"sequence\": " + std::to_string(e.sequence);
					j += ",\n\"frame\": " + fieldFloat(e.frame);
					j += ",\n\"animtime\": " + fieldFloat(e.animtime);
					j += ",\n\"framerate\": " + fieldFloat(e.framerate);
					j += ",\n\"body\": " + std::to_string(e.body);
					{
						float cycle = 0;
						if (e.animtime != 0 && e.framerate != 0)
							cycle = (f.time - e.animtime) * e.framerate;
						j += ",\n\"cycle\": " + fieldFloat(cycle);
					}
					j += "\n}";
				}
				j += "\n]\n";
			}
			j += "}";
		}
		j += "\n]\n";
	}
	j += "}\n";

	std::ofstream ofs(outpath, std::ios::binary);
	ofs << j;
	return ofs.good();
}

int main(int argc, char** argv) {
	std::vector<std::string> args(argv + 1, argv + argc);
	std::string demoPath, outPath = "out.json";
	bool camOnly = false;
	for (size_t i = 0; i < args.size(); ++i) {
		const std::string& a = args[i];
		if (a == "--cam-only") camOnly = true;
		else if (a == "--max-clients" && i + 1 < args.size()) g_maxClients = std::atoi(args[++i].c_str());
		else if (a == "-h" || a == "--help") {
			std::cout
				<< "demo_extract <demo.dem> [output.json] [tick_interval] [--cam-only] [--max-clients N]\n"
				<< "  tick_interval: sample every N demo ticks (default 1)\n"
				<< "  --cam-only: skip entity frames in output\n";
			return 0;
		} else if (demoPath.empty()) demoPath = a;
		else if (outPath == "out.json") outPath = a;
		else g_tickInterval = std::atoi(a.c_str());
	}
	if (demoPath.empty()) {
		std::cerr << "error: no demo file given. Use --help.\n";
		return 2;
	}
	if (g_tickInterval < 1) g_tickInterval = 1;

	try {
		bool ok = run(demoPath, outPath, camOnly);
		if (!ok) {
			std::cerr << "error: failed to write " << outPath << "\n";
			return 1;
		}
	} catch (const std::exception& e) {
		std::cerr << "error: " << e.what() << "\n";
		return 1;
	}
	std::cout << "done: " << outPath << "\n";
	return 0;
}
