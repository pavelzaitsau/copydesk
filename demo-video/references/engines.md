# Voice engines

Detail for the `engine`, `voice` and `speed` options of `startDemo`. `scripts/tts_lines.py` owns the model behind each name. `ENGINES` in `scripts/demo-kit.mjs` owns each engine's languages, licence class and peak memory; the table below is a copy of those facts.

## Engines

Every engine except `kokoro` synthesises through `tts_lines.py` and [mlx-audio](https://github.com/Blaizzy/mlx-audio) on an Apple Silicon Mac. Kokoro synthesises in its own environment, and its lines are checked by Whisper in the MLX one, so every voice needs the MLX setup. All of them recorded the same 45-second demo on an M5 Pro with 48 GB, in English and in Russian, in 1 to 4 minutes per take.

| Engine | Model | Weights licence | Class | Peak memory with Whisper |
| --- | --- | --- | --- | --- |
| `kokoro` | Kokoro 82M | Apache-2.0 | clean | 2.6 GB (Whisper's); English only |
| `qwen3` | Qwen3-TTS 1.7B CustomVoice | Apache-2.0 | clean | 9.7 GB |
| `voxcpm2` | VoxCPM2 2B | Apache-2.0 | clean | 9.8 GB |
| `chatterbox` | Chatterbox Multilingual V3 | MIT | clean | 6.2 GB |
| `omnivoice` | OmniVoice 0.6B | CC-BY-NC | noncommercial | 5.2 GB |
| `fish-s2` | Fish Audio S2 Pro | Fish Audio Research License | noncommercial | 18.1 GB |
| `drama3` | Fish Audio Drama 3, 4 bit | Fish Audio Community License v1.0 | conditional | 30.2 GB |
| `higgs3` | Higgs Audio V3 4B | Research and Non-Commercial, with a Creator Use Grant | noncommercial | 12.2 GB |

The weights decide the licence, not the code. Read it from the original model card (`base_model`), not from an `mlx-community` conversion: the OmniVoice conversion says Apache-2.0, while its original weights are CC-BY-NC.

- **clean:** any use, including a video for a client.
- **conditional:** Drama 3 allows commercial use while the licensee and its affiliates earn under USD 500k a year. Built with Fish Audio.
- **noncommercial:** no commercial use. Work for a client or an own team usually counts as commercial use.

Chatterbox's original package watermarks its output; the mlx-audio port does not. Higgs Audio V3 was renamed upstream to `bosonai/higgs-tts-3-4b`; `tts_lines.py` keeps the old name, which redirects and keeps an existing cache valid. Clone only the voice of a person who agreed to it: the Fish licences require that consent. `NOTICE` beside `SKILL.md` carries the licence terms the Fish and Higgs licences ask a repository that uses them to carry.

## Voices

`assets/voices.json` is the list a demo picks from: the 3 strongest voices per language and sex. `scripts/fit_votes.py` fits the votes in `assets/voice-vote.json` and writes it; `references/voice-vote.md` has the method and the full result. A voice named after an engine, such as `voxcpm` or `higgs3`, clones the default reference clip, Qwen3's `ryan`. So `voxcpm`, `higgs3` and `ryan` are one speaker: a dialogue cannot pair them.

`assets/defaults.json` names the default voice per language. `fit_votes.py --check` fails unless each default is in the list and runs on a clean engine, because a demo may be for a client.

A Qwen3 speaker outside its list stops the run: Qwen3 would otherwise pick a random voice for every line. For experiments, `engine` with an engine's own value still works: any Kokoro voice, any Qwen3 speaker, or for a cloning engine a WAV file with its transcript in a `.txt` file of the same name. `speed` works for `kokoro` and `qwen3` only.

To refresh the default reference clip, delete `~/.cache/demo-video/ref-qwen3-ryan-<lang>.wav`. Qwen3 samples at random, and every cloning engine copies the clip's pace and tone, so listen to a new clip before recording with it. A cloning engine's first run synthesises that clip with Qwen3, so it needs Qwen3's memory once.

## Takes

The MLX engines sample at random: one take of a line can drop a word, drawl or trail off. Whisper transcribes every line of every engine, Kokoro included, and `scripts/wer.py` compares what it heard with the line: WER, the words substituted, dropped or added, divided by the words in the line. Numbers drop out of both sides in digits and in words. In Russian a Latin word in the line matches any one heard word, because Whisper writes OK as ОК and email as имейл. The user checks numbers and terms by ear.

`takes: 3` synthesises three takes per line. Among the takes at or under `WER_FAIL`, a steady one beats one slower than its engine's `SLOW_CPS`, because a drawled take usually ends in noise; then the lower WER wins. With none passing, the lowest WER wins. A line whose best take is above `WER_FAIL` gets up to two more takes (`--retries` in `tts_lines.py`), because one random take can fail on its own. A line still above it is failed: `startDemo` stops and names it, unless `allowFailedTakes` is set by a caller that rewrites such lines itself. `voice/takes.json` holds every take's WER, its length, whether it drawled and what Whisper heard. A benchmark in the repository measured both thresholds; `tts_lines.py` records the result, its date and what the threshold lets through.

## Setup

The environments are set up as `SKILL.md`, "Prerequisites", says. `tts_lines.py` calls engine-specific code in mlx-audio, so test an engine again after upgrading the package.

The memory figures above come from `tts_lines.py --takes 2 --report-peak`: Whisper checks every take in the same process, and `--report-peak` prints the peak. Kokoro runs in its own process; its figure is the larger of that process's peak, 1.7 GB, and Whisper's alone, 2.6 GB.

## Tests

The repository's `tests/` folder holds the unit and end-to-end tests, the benchmarks and the first round of the voice vote; the packaged skill leaves it out. Each file says what it checks. The `fake` engine writes silence of a length set by the text, and a Whisper report that heard every line exactly.
