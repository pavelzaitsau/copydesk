# Voice vote, November 2026

How the voices in `assets/voices.json` were chosen, and the full result. The votes are in `assets/voice-vote.json`; `scripts/fit_votes.py` fits them and writes the voice list.

## Method

1. **Scores.** One listener scored 58 voices from 1 to 5. All read the same line, one in English and one in Russian. Every voice at 3 or below was dropped.
2. **Blind pairs.** The remaining voices met in pairs within one language and one sex. Every clip was trimmed of silence and normalised to -18 LUFS; sides were random and names hidden. Each answer had five steps, from "A clearly better" through "same" to "B clearly better", scored 1, 0.7, 0.5, 0.3 and 0.
3. **Pairing.** Each voice first met opponents of similar strength. After that, pairs went to the voices whose place near the shortlist boundary was still uncertain. Every seventh pair repeated an earlier decided pair with the sides swapped.
4. **Fit.** `fit_votes.py` fits a Bradley-Terry model with a normal prior (sigma 1) to all answers of a group at once. Strength is the chance, in percent, to beat an average voice of the same group.
5. **Selection.** The 3 strongest voices of each group go into `assets/voices.json`, whatever their licence. `ENGINES` in `demo-kit.mjs` says which may be used for what.

<!-- fit_votes:stats -->
116 answers in all. 12 pairs were asked again with the sides swapped; 7 of them kept the same side (both times A better, both times B better, or both times the same). Each voice met at least 2 different opponents; a group of 3 voices allows no more than 2.
<!-- /fit_votes -->

## Result

`fit_votes.py` writes this table and the counts above; `fit_votes.py --check` fails when they are stale.

<!-- fit_votes:result -->
| Group | Voice | Engine | Strength | Wins, losses, ties |
| --- | --- | --- | --- | --- |
| en-f | `ono_anna` (kept) | `qwen3` | 64 | 5, 0, 2 |
| en-f | `sohee` (kept) | `qwen3` | 59 | 4, 0, 4 |
| en-f | `nicole` (kept) | `kokoro` | 56 | 5, 1, 2 |
| en-f | `serena` | `qwen3` | 54 | 2, 0, 5 |
| en-f | `heart` | `kokoro` | 48 | 2, 3, 3 |
| en-f | `bella` | `kokoro` | 43 | 1, 6, 2 |
| en-f | `sky` | `kokoro` | 43 | 2, 4, 1 |
| en-f | `emma` | `kokoro` | 41 | 1, 4, 1 |
| en-f | `isabella` | `kokoro` | 41 | 0, 4, 2 |
| en-m | `voxcpm` (kept) | `voxcpm2` | 70 | 5, 0, 0 |
| en-m | `higgs3` (kept) | `higgs3` | 59 | 4, 1, 3 |
| en-m | `ryan` (removed) | `qwen3` | 58 | 4, 1, 3 |
| en-m | `omnivoice` | `omnivoice` | 56 | 4, 1, 2 |
| en-m | `drama3` | `drama3` | 55 | 3, 1, 4 |
| en-m | `uncle_fu` | `qwen3` | 53 | 1, 1, 4 |
| en-m | `chatterbox` | `chatterbox` | 51 | 2, 2, 4 |
| en-m | `fable` | `kokoro` | 50 | 2, 5, 2 |
| en-m | `onyx` | `kokoro` | 48 | 3, 2, 1 |
| en-m | `lewis` | `kokoro` | 46 | 1, 2, 2 |
| en-m | `santa` | `kokoro` | 45 | 0, 2, 3 |
| en-m | `adam` | `kokoro` | 44 | 0, 2, 1 |
| en-m | `fish-s2` | `fish-s2` | 44 | 2, 2, 1 |
| en-m | `michael` | `kokoro` | 44 | 1, 3, 2 |
| en-m | `echo` | `kokoro` | 40 | 1, 4, 0 |
| en-m | `george` | `kokoro` | 35 | 0, 4, 0 |
| ru-f | `sohee` (removed) | `qwen3` | 57 | 6, 0, 4 |
| ru-f | `serena` (kept) | `qwen3` | 48 | 3, 5, 3 |
| ru-f | `vivian` (removed) | `qwen3` | 45 | 1, 5, 3 |
| ru-m | `uncle_fu` (removed) | `qwen3` | 57 | 4, 0, 2 |
| ru-m | `eric` (removed) | `qwen3` | 53 | 2, 0, 4 |
| ru-m | `higgs3` (kept) | `higgs3` | 51 | 1, 1, 5 |
| ru-m | `dylan` | `qwen3` | 50 | 1, 1, 4 |
| ru-m | `ryan` | `qwen3` | 50 | 1, 1, 5 |
| ru-m | `drama3` | `drama3` | 39 | 0, 6, 0 |
<!-- /fit_votes -->

## Reading it

After the vote, the owner heard one sample of each listed voice and removed five, which `assets/removed.json` names; no other voice took their places. The error bars of neighbouring voices overlap in every group, so the list is a set of safe choices, not a proven order. Most answers were "slightly better" or "same": among voices that already scored 4 or 5, the differences are small. `voxcpm` leads on 5 comparisons, the fewest of any leader. In Russian only Qwen3, Drama 3 and Higgs took part in the pairs; Fish S2, VoxCPM2, Chatterbox and OmniVoice need a new vote before they can enter the Russian list.
