# Purpose and licences

Which voices a demo may use depends on what the video is for. `startDemo` takes it as `purpose`; `ENGINES` in `scripts/demo-kit.mjs` owns each engine's licence class, and `references/engines.md` explains the classes.

| `purpose` | Voices |
| --- | --- |
| `personal` | Any |
| `team` | Any. The run warns on a conditional or non-commercial engine: work for an own team usually counts as commercial use, which those licences limit or forbid |
| `client` | Clean engines only. A conditional or non-commercial engine stops the run, unless `allowRestrictedLicence: true` |

Without `purpose`, a demo counts as `client`, the strictest: a video that leaves for a client with a non-commercial voice breaks that model's licence. Set `allowRestrictedLicence` only after the user agreed to that voice for this video. `run.json` records both, so the decision stays with the video.

Before any synthesis `startDemo` also checks the machine. It runs on an Apple Silicon Mac only. It refuses an engine whose peak memory with Whisper, from `ENGINES`, plus 2 GB does not fit in free memory, and names the engines that do fit. Free memory is the free, inactive, speculative and purgeable pages `vm_stat` reports. For tests, `DEMO_VIDEO_PLATFORM=other` and `DEMO_VIDEO_FREE_MEM=<GB>` stand in for the machine.

A run with the `higgs3` voice writes `credits.txt` beside the video: Higgs TTS 3's Creator Use Grant asks a video on the creator's own channels to credit the model.
