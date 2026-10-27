// csgo_extract: CS:GO demo -> cs16db JSON (positions/angles/velocity per tick).
//
// Uses demoinfocs-golang v3 - the last version with CS:GO support.
//
// Build & run on any machine with Go (go.dev/dl):
//   cd source1/go_extract && go mod tidy && go run . C:\path\demo.dem out.json --follow 1
//
// Output schema matches the rest of the pipeline (blender_import /
// max_import / ae import_camera.jsx). CS2 demos keep using demoparser2 via
// csgo_demo2json.py (auto-selected by magic: HL2DEMO -> this tool, PBDEMS2 -> demoparser2).
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"

	demoinfocs "github.com/markus-wa/demoinfocs-golang/v3/pkg/demoinfocs"
	"github.com/markus-wa/demoinfocs-golang/v3/pkg/demoinfocs/common"
	"github.com/markus-wa/demoinfocs-golang/v3/pkg/demoinfocs/events"
) 

type camSample struct {
	Tick       int       `json:"tick"`
	Time       float64   `json:"time"`
	Origin     []float64 `json:"origin"`
	ViewAngles []float64 `json:"viewangles"`
	FOV        float64   `json:"fov"`
	Source     int       `json:"source"`
}

type entFrame struct {
	Tick     int      `json:"tick"`
	Time     float64  `json:"time"`
	Entities []entity `json:"entities"`
}

type entity struct {
	Index    int       `json:"index"`
	Player   bool      `json:"player"`
	Name     string    `json:"name,omitempty"`
	Team     int       `json:"team"`
	Health   int       `json:"health"`
	Origin   []float64 `json:"origin,omitempty"`
	Angles   []float64 `json:"angles,omitempty"`
	Velocity []float64 `json:"velocity,omitempty"`
}

type doc struct {
	Demo          string     `json:"demo"`
	Map           string     `json:"map"`
	Game          string     `json:"game"`
	TickInterval  int        `json:"tick_interval"`
	FramesParsed  int        `json:"frames_parsed"`
	TickRate      int        `json:"tick_rate"`
	Notes         string     `json:"notes"`
	Camera        []camSample `json:"camera"`
	Frames        []entFrame `json:"frames"`
}

func main() {
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "csgo_extract demo.dem out.json [--follow USERID] [--tick-step N]\n")
		flag.PrintDefaults()
	}
	follow := flag.Int("follow", 0, "USERID of the player to build follow camera from")
	step := flag.Int("tick-step", 1, "export every N ticks")
	flag.Parse()
	if flag.NArg() < 1 {
		flag.Usage()
		os.Exit(2)
	}
	demoPath := flag.Arg(0)
	outPath := "csgo_out.json"
	if flag.NArg() > 1 {
		outPath = flag.Arg(1)
	}

	f, err := os.Open(demoPath)
	if err != nil {
		log.Fatal(err)
	}
	defer f.Close()

	p := demoinfocs.NewParser(f)
	defer p.Close()

	header, err := p.ParseHeader()
	if err != nil {
		log.Fatal("parse header: ", err)
	}
	fmt.Printf("map=%s proto=%s frames=%d\n", header.MapName, header.NetworkProtocol, header.PlaybackFrames)

	d := doc{
		Demo: demoPath,
		Map:  header.MapName,
		Game: "csgo",
		TickInterval: *step,
		TickRate: 64,
		Notes: "CS:GO (Source 1) via demoinfocs-golang v3; units = inches Z-up; no sequence/frame in CS:GO demos",
	}
	if header.PlaybackTime > 0 {
		d.TickRate = int(float64(header.PlaybackTicks)/header.PlaybackTime.Seconds() + 0.5)
		if d.TickRate <= 0 {
			d.TickRate = 64
		}
	}

	lastTick := int(0)
	p.RegisterEventHandler(func(e events.FrameDone) {
		defer func() {
			if r := recover(); r != nil {
				fmt.Fprintln(os.Stderr, "panic at FrameDone: ", r)
				os.Exit(3)
			}
		}()
		gs := p.GameState()
		tick := gs.IngameTick()
		if *step > 1 && tick-lastTick < *step {
			return
		}
		lastTick = tick

		frame := entFrame{Tick: int(tick), Time: float64(tick) / float64(d.TickRate)}
		for _, pl := range gs.Participants().All() {
			if pl == nil || pl.Name == "" {
				continue
			}
			e := entity{
				Index:  pl.UserID,
				Player: true,
				Name:   pl.Name,
				Health: pl.Health(),
			}
			if pl.Team != common.TeamSpectators && (pl.Team == common.TeamTerrorists || pl.Team == common.TeamCounterTerrorists) {
				e.Team = int(pl.Team)
			}
			pos := pl.Position()
			e.Origin = []float64{round2(pos.X), round2(pos.Y), round2(pos.Z)}
			e.Angles = []float64{round2(float64(pl.ViewDirectionX())), round2(float64(pl.ViewDirectionY())), 0}
			e.Velocity = []float64{round2(pl.Velocity().X), round2(pl.Velocity().Y), round2(pl.Velocity().Z)}
			frame.Entities = append(frame.Entities, e)
			if *follow > 0 && pl.UserID == *follow && len(e.Origin) == 3 && len(e.Angles) == 3 {
				d.Camera = append(d.Camera, camSample{
					Tick: int(tick), Time: float64(tick) / float64(d.TickRate),
					Origin: e.Origin, ViewAngles: e.Angles, FOV: 90, Source: 5,
				})
			}
		}
		if len(frame.Entities) > 0 {
			d.Frames = append(d.Frames, frame)
			d.FramesParsed++
		}
	})

	if err := p.ParseToEnd(); err != nil {
		fmt.Fprintln(os.Stderr, "parse: ", err)
	}

	buf, _ := json.MarshalIndent(d, "", "  ")
	if err := os.WriteFile(outPath, buf, 0o644); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("done: %s (%d frames, %d camera samples)\n", outPath, d.FramesParsed, len(d.Camera))
}

func round2(v float64) float64 {
	return float64(int64(v*100+0.5)) / 100
}
