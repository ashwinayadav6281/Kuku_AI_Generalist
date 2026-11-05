# Promo Tool Failure & Edge-Case Analysis

This document highlights boundary cases, failure modes, and systematic biases discovered during automated quality checks and gold-set benchmarking.

---

## Part 1: Top 5 Most Suspicious High-Ranked Promos
These promos received high scores from the scoring pipeline, but human editorial inspection reveals genuine risks of viewer drop-off or context ambiguity.

### #1: Promo `ep01_u22_u52` (Rank #1, Score: 5.00)
- **Episode:** 1 | **Duration:** 47.2s
- **Timestamps:** `00:33.80 - 01:21.00`
- **Opening Hook:** *"LADY JULIANA: "Gerald?" | LADY JULIANA: "Why are you holding her hand?" | CAMERA: Close-up insert of Gerald's fingers fi..."*
- **Cliffhanger Ending:** *"CAMERA: Medium two-shot of the Lady in Gold Gown and Gerald looking together down at Juliana. | LADY IN GOLD GOWN: "Long..."*
- **Why the tool picked it:** Altar betrayal with high visceral shock and clear victim/antagonist dynamics.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Long duration (47.2s) risks TikTok viewer drop-off before cliffhanger
- **Human Editor Recommendation:** Trim 12.2s of establishing dialogue/camera action to bring runtime down to ~35s sweet spot. Insert audio sting or sudden audio silence right before the final cut to sharpen cliffhanger impact.

---

### #2: Promo `ep05_u31_u57` (Rank #7, Score: 4.65)
- **Episode:** 5 | **Duration:** 46.3s
- **Timestamps:** `00:54.50 - 01:40.80`
- **Opening Hook:** *"ACTION: Lady Ashcroft snatches the heavy book away and flings it disdainfully into the rain-soaked courtyard. | JULIANA:..."*
- **Cliffhanger Ending:** *"CAMERA: Over-the-shoulder shot behind the Mysterious Bearded Man looking up toward Gerald on the stairs. Gerald's arroga..."*
- **Why the tool picked it:** Public family rejection and sudden marriage pact creating high curiosity.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Long duration (46.3s) risks TikTok viewer drop-off before cliffhanger
- **Human Editor Recommendation:** Trim 11.3s of establishing dialogue/camera action to bring runtime down to ~35s sweet spot. Insert audio sting or sudden audio silence right before the final cut to sharpen cliffhanger impact.

---

### #3: Promo `ep10_u6_u41` (Rank #9, Score: 4.65)
- **Episode:** 10 | **Duration:** 50.1s
- **Timestamps:** `00:05.10 - 00:55.20`
- **Opening Hook:** *"JULIANA: "Alexander!" | CAMERA: Close-up of Alexander struggling to breathe, clutching his bloodied coat over his chest...."*
- **Cliffhanger Ending:** *"CAMERA: Medium close-up of Juliana dipping a linen cloth into the water bowl. | JULIANA: "Your scars disagree." | CAMERA..."*
- **Why the tool picked it:** High-stakes interpersonal confrontation with strong character indignation.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Long duration (50.1s) risks TikTok viewer drop-off before cliffhanger
  - ⚠️ Cliffhanger lacks explicit question mark or urgent threat
- **Human Editor Recommendation:** Trim 15.1s of establishing dialogue/camera action to bring runtime down to ~35s sweet spot. Insert audio sting or sudden audio silence right before the final cut to sharpen cliffhanger impact.

---

### #4: Promo `ep01_u49_u78` (Rank #2, Score: 5.00)
- **Episode:** 1 | **Duration:** 42.6s
- **Timestamps:** `01:13.10 - 01:55.70`
- **Opening Hook:** *"LADY JULIANA: "How long?" | CAMERA: Medium two-shot of the Lady in Gold Gown and Gerald looking together down at Juliana..."*
- **Cliffhanger Ending:** *"CAMERA: Close-up on Juliana absorbing the venomous words, her breathing shallow. | LADY IN GOLD GOWN: "I am the daughter..."*
- **Why the tool picked it:** Altar betrayal with high visceral shock and clear victim/antagonist dynamics.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Borderline candidate duration; pacing may feel sluggish in first 10 seconds.
- **Human Editor Recommendation:** Ready for editor cut; add title card and trending background audio.

---

### #5: Promo `ep09_u25_u58` (Rank #8, Score: 4.65)
- **Episode:** 9 | **Duration:** 42.6s
- **Timestamps:** `00:34.90 - 01:17.50`
- **Opening Hook:** *"ALEXANDER: "You're certain?" | CAMERA: Close-up of Juliana looking up into his eyes with resolute conviction. | JULIANA:..."*
- **Cliffhanger Ending:** *"CAMERA: Medium shot from inside the cottage framing the mother standing at the open door looking back. | PEASANT MOTHER:..."*
- **Why the tool picked it:** High-stakes interpersonal confrontation with strong character indignation.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Borderline candidate duration; pacing may feel sluggish in first 10 seconds.
- **Human Editor Recommendation:** Insert audio sting or sudden audio silence right before the final cut to sharpen cliffhanger impact.

---

## Part 2: 5 Worst-Ranked Yet Passing Candidates
These candidate windows satisfied all duration (20-60s) and unit boundary constraints, but received the lowest composite scores.

### #1: Candidate `ep42_u30_u36` (Score: 0.45)
- **Episode:** 42 | **Duration:** 23.5s
- **Timestamps:** `00:54.00 - 01:17.50`
- **Opening Hook:** *"ALEXANDER'S MOTHER: "I saw you again... but seeing you like this... I see my son as he was always meant to be."..."*
- **Ending Line:** *"CAMERA: Medium shot of Rupert cowering on the altar steps beside Catherine and her father, utterly defeated. | CAMERA: T..."*
- **Why the tool scored it poorly:** Reflective sentimental dialogue without an immediate external threat or urgent hook.
- **Verdict:** Correctly rejected by candidate pruning filter; would cause immediate drop-off as a paid social ad.

---

### #2: Candidate `ep29_u12_u23` (Score: 1.05)
- **Episode:** 29 | **Duration:** 20.8s
- **Timestamps:** `00:21.00 - 00:41.80`
- **Opening Hook:** *"CATHERINE: "Your mother's little book of weeds?" | CATHERINE: "You still call this a legacy?"..."*
- **Ending Line:** *"CAMERA: Medium shot of Catherine tucking the book under her arm, her eyes glinting with malicious intent. | CATHERINE: "..."*
- **Why the tool scored it poorly:** Low conflict volume, procedural movement, or closed narrative resolution.
- **Verdict:** Correctly rejected by candidate pruning filter; would cause immediate drop-off as a paid social ad.

---

### #3: Candidate `ep39_u10_u24` (Score: 1.05)
- **Episode:** 39 | **Duration:** 24.2s
- **Timestamps:** `00:18.30 - 00:42.50`
- **Opening Hook:** *"LOYALIST SCOUT: "Six at the front." | LOYALIST FIGHTER: "Four more inside."..."*
- **Ending Line:** *"CAMERA: Medium close-up as a second loyalist emerges from behind the doorway, wrapping his arms around the remaining roy..."*
- **Why the tool scored it poorly:** Low conflict volume, procedural movement, or closed narrative resolution.
- **Verdict:** Correctly rejected by candidate pruning filter; would cause immediate drop-off as a paid social ad.

---

### #4: Candidate `ep40_u6_u15` (Score: 1.05)
- **Episode:** 40 | **Duration:** 20.8s
- **Timestamps:** `00:12.40 - 00:33.20`
- **Opening Hook:** *"LADY HARRINGTON: "Look at them. Every noble family in the county is here today." | CAMERA: Medium two-shot tracking slig..."*
- **Ending Line:** *"CAMERA: Tight close-up of Lord Harrington looking down at her, his expression cold and ruthless. | LADY HARRINGTON: "Goo..."*
- **Why the tool scored it poorly:** Low conflict volume, procedural movement, or closed narrative resolution.
- **Verdict:** Correctly rejected by candidate pruning filter; would cause immediate drop-off as a paid social ad.

---

### #5: Candidate `ep41_u27_u37` (Score: 1.05)
- **Episode:** 41 | **Duration:** 20.4s
- **Timestamps:** `00:45.00 - 01:05.40`
- **Opening Hook:** *"CATHERINE: "This is the world you thought you belonged to." | CAMERA: Low-angle medium shot of Catherine gesturing broad..."*
- **Ending Line:** *"CAMERA: Dramatic low-angle full shot looking up at Juliana, her posture straight, imposing, and regal despite the heavy ..."*
- **Why the tool scored it poorly:** Low conflict volume, procedural movement, or closed narrative resolution.
- **Verdict:** Correctly rejected by candidate pruning filter; would cause immediate drop-off as a paid social ad.

---
