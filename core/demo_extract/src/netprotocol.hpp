// GoldSrc network protocol constants (proto 47/48, verified against Xash3D + khanghugo/dem).
#pragma once

namespace gs {

// server -> client opcodes
enum Svc {
	SVC_BAD = 0,
	SVC_NOP = 1,
	SVC_DISCONNECT = 2,
	SVC_EVENT = 3,
	SVC_CHANGING = 4,      // version
	SVC_SETVIEW = 5,
	SVC_SOUND = 6,
	SVC_TIME = 7,
	SVC_PRINT = 8,
	SVC_STUFFTEXT = 9,
	SVC_SETANGLE = 10,
	SVC_SERVERDATA = 11,
	SVC_LIGHTSTYLE = 12,
	SVC_UPDATEUSERINFO = 13,
	SVC_DELTATABLE = 14,
	SVC_CLIENTDATA = 15,
	SVC_STOPSOUND = 16,     // GoldSrc: [word] entnum<<3 | channel
	SVC_PINGS = 17,
	SVC_PARTICLE = 18,      // fixed 11 bytes in GoldSrc
	SVC_DAMAGE = 19,        // no payload (engine handles it in client.dll)
	SVC_SPAWNSTATIC = 20,
	SVC_EVENT_RELIABLE = 21,
	SVC_SPAWNBASELINE = 22,
	SVC_TEMP_ENTITY = 23,
	SVC_SETPAUSE = 24,	SVC_SIGNONNUM = 25,
	SVC_CENTERPRINT = 26,
	SVC_KILLEDMONSTER = 27, // no payload
	SVC_FOUNDSECRET = 28,   // no payload
	SVC_SPAWNSTATICSOUND = 29, // [14 bytes]
	SVC_INTERMISSION = 30,
	SVC_FINALE = 31,
	SVC_CDTRACK = 32,
	SVC_RESTORE = 33,
	SVC_CUTSCENE = 34,
	SVC_WEAPONANIM = 35,
	SVC_DECALNAME = 36,     // GoldSrc [byte][string]; in newer protocols "svc_bspdecal"
	SVC_ROOMTYPE = 37,
	SVC_ADDANGLE = 38,
	SVC_USERMESSAGE = 39,
	SVC_PACKETENTITIES = 40,
	SVC_DELTAPACKETENTITIES = 41,
	SVC_CHOKE = 42,
	SVC_RESOURCELIST = 43,
	SVC_DELTAMOVEVARS = 44,
	SVC_RESOURCEREQUEST = 45,
	SVC_CUSTOMIZATION = 46,
	SVC_CROSSHAIRANGLE = 47,
	SVC_SOUNDFADE = 48,
	SVC_FILETXFERFAILED = 49,
	SVC_HLTV = 50,
	SVC_DIRECTOR = 51,
	SVC_VOICEINIT = 52,
	SVC_VOICEDATA = 53,
	SVC_SENDEXTRAINFO = 54,
	SVC_TIMESCALE = 55,
	SVC_RESOURCELOCATION = 56,
	SVC_QUERYCVARVALUE = 57,
	SVC_QUERYCVARVALUE2 = 58,
	SVC_EXEC = 59,
	SVC_LASTMSG = 59, // user messages start at 60
};

// delta field type flags (net_encode.c)
enum {
	DT_BYTE = 1 << 0,
	DT_SHORT = 1 << 1,
	DT_FLOAT = 1 << 2,
	DT_INTEGER = 1 << 3,
	DT_ANGLE = 1 << 4,
	DT_TIMEWINDOW_8 = 1 << 5,
	DT_TIMEWINDOW_BIG = 1 << 6,
	DT_STRING = 1 << 7,
	DT_SIGNED = 1 << 8,
	DT_SIGNED_GS = 1u << 31,
};

// GoldSrc entity packet limits
constexpr int MAX_GOLDSRC_ENTITY_BITS = 11;
constexpr int MAX_CLIENTS = 32;

} // namespace gs
