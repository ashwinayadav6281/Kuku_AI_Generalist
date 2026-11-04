# Promo Tool Failure & Edge-Case Analysis

This document highlights boundary cases, failure modes, and systematic biases discovered during automated quality checks and gold-set benchmarking.

---

## Part 1: Top 5 Most Suspicious High-Ranked Promos
These promos received high scores from the scoring pipeline, but human editorial inspection reveals genuine risks of viewer drop-off or context ambiguity.

### #1: Promo `ep01_u22_u52` (Rank #1, Score: 4.00)
- **Episode:** 1 | **Duration:** 47.2s
- **Timestamps:** `00:33.80 - 01:21.00`
- **Opening Hook:** *"LADY JULIANA: "Gerald?" | LADY JULIANA: "Why are you holding her hand?" | CAMERA: Close-up insert of Gerald's fingers fi..."*
- **Cliffhanger Ending:** *"CAMERA: Medium two-shot of the Lady in Gold Gown and Gerald looking together down at Juliana. | LADY IN GOLD GOWN: "Long..."*
- **Why the tool picked it:** High emotional volume and explosive dialogue confrontation.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Long duration (47.2s) risks TikTok viewer drop-off before cliffhanger
- **Human Editor Recommendation:** Tighten opening by 3-5 seconds to remove dead air, or pair with a text overlay introducing character names.

---

### #2: Promo `ep02_u3_u33` (Rank #3, Score: 4.00)
- **Episode:** 2 | **Duration:** 48.6s
- **Timestamps:** `00:02.80 - 00:51.40`
- **Opening Hook:** *"ACTION: Juliana gasps softly in heartbreak, her eyes wide and brimming with tears. | CAMERA: Medium shot returning to Ge..."*
- **Cliffhanger Ending:** *"CAMERA: Extreme close-up on Juliana's tear-drenched eyes as the sting of her father's rejection lands. | LADY JULIANA: "..."*
- **Why the tool picked it:** High emotional volume and explosive dialogue confrontation.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Long duration (48.6s) risks TikTok viewer drop-off before cliffhanger
  - ⚠️ Cliffhanger lacks explicit question mark or urgent threat
- **Human Editor Recommendation:** Tighten opening by 3-5 seconds to remove dead air, or pair with a text overlay introducing character names.

---

### #3: Promo `ep05_u31_u57` (Rank #6, Score: 4.00)
- **Episode:** 5 | **Duration:** 46.3s
- **Timestamps:** `00:54.50 - 01:40.80`
- **Opening Hook:** *"ACTION: Lady Ashcroft snatches the heavy book away and flings it disdainfully into the rain-soaked courtyard. | JULIANA:..."*
- **Cliffhanger Ending:** *"CAMERA: Over-the-shoulder shot behind the Mysterious Bearded Man looking up toward Gerald on the stairs. Gerald's arroga..."*
- **Why the tool picked it:** High emotional volume and explosive dialogue confrontation.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Long duration (46.3s) risks TikTok viewer drop-off before cliffhanger
- **Human Editor Recommendation:** Tighten opening by 3-5 seconds to remove dead air, or pair with a text overlay introducing character names.

---

### #4: Promo `ep09_u21_u58` (Rank #8, Score: 4.00)
- **Episode:** 9 | **Duration:** 48.5s
- **Timestamps:** `00:29.00 - 01:17.50`
- **Opening Hook:** *"JULIANA: "Feverfew... Not alone." | CAMERA: Profile close-up of Juliana studying the grimoire's remedies intently while ..."*
- **Cliffhanger Ending:** *"CAMERA: Medium shot from inside the cottage framing the mother standing at the open door looking back. | PEASANT MOTHER:..."*
- **Why the tool picked it:** High emotional volume and explosive dialogue confrontation.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Long duration (48.5s) risks TikTok viewer drop-off before cliffhanger
- **Human Editor Recommendation:** Tighten opening by 3-5 seconds to remove dead air, or pair with a text overlay introducing character names.

---

### #5: Promo `ep25_u36_u48` (Rank #10, Score: 4.00)
- **Episode:** 25 | **Duration:** 26.2s
- **Timestamps:** `00:55.60 - 01:21.80`
- **Opening Hook:** *"JULIANA: "The Dowager Duchess." | CAMERA: Tight close-up of Alexander's face freezing in shock, his eyes widening as the..."*
- **Cliffhanger Ending:** *"CAMERA: Medium shot of Alexander staring down at her, waiting for the dark truth. | ALEXANDER: "What did you find?" | CA..."*
- **Why the tool picked it:** High emotional volume and explosive dialogue confrontation.
- **Why the tool likely erred / Risks identified:**
  - ⚠️ Later episode (Ep 25) assumes viewer knows established character dynamics
- **Human Editor Recommendation:** Tighten opening by 3-5 seconds to remove dead air, or pair with a text overlay introducing character names.

---

## Part 2: 5 Worst-Ranked Yet Passing Candidates
These candidate windows satisfied all duration (20-60s) and unit boundary constraints, but received the lowest composite scores.

### #1: Candidate `ep42_u30_u36` (Score: 1.00)
- **Episode:** 42 | **Duration:** 23.5s
- **Timestamps:** `00:54.00 - 01:17.50`
- **Opening Hook:** *"ALEXANDER'S MOTHER: "I saw you again... but seeing you like this... I see my son as he was always meant to be."..."*
- **Ending Line:** *"CAMERA: Medium shot of Rupert cowering on the altar steps beside Catherine and her father, utterly defeated. | CAMERA: T..."*
- **Why the tool scored it poorly:** Starts on an inert conversational exchange or procedural movement rather than an explosive hook. The ending resolves the ongoing beat rather than posing an urgent narrative question.
- **Verdict:** Rightfully rejected by the candidate pruning filter.

---

### #2: Candidate `ep45_u6_u36` (Score: 1.10)
- **Episode:** 45 | **Duration:** 44.1s
- **Timestamps:** `00:07.40 - 00:51.50`
- **Opening Hook:** *"ALEXANDER: "Look at me." | CAMERA: Low angle close-up of Juliana looking down into Alexander's eyes with rising disbelie..."*
- **Ending Line:** *"CAMERA: Extreme close-up as Alexander and Juliana rest their foreheads and noses together in an intimate embrace. | ACTI..."*
- **Why the tool scored it poorly:** Starts on an inert conversational exchange or procedural movement rather than an explosive hook. The ending resolves the ongoing beat rather than posing an urgent narrative question.
- **Verdict:** Rightfully rejected by the candidate pruning filter.

---

### #3: Candidate `ep02_u11_u22` (Score: 1.50)
- **Episode:** 2 | **Duration:** 20.0s
- **Timestamps:** `00:12.40 - 00:32.40`
- **Opening Hook:** *"LADY JULIANA: "Gerald... Look at me." | CAMERA: Close-up on Gerald's cold, merciless face staring ahead unblinkingly...."*
- **Ending Line:** *"CAMERA: Wide shot from behind Juliana looking up the altar stairs at Gerald with Clarissa linked to his arm. | THE FORME..."*
- **Why the tool scored it poorly:** Starts on an inert conversational exchange or procedural movement rather than an explosive hook. The ending resolves the ongoing beat rather than posing an urgent narrative question.
- **Verdict:** Rightfully rejected by the candidate pruning filter.

---

### #4: Candidate `ep07_u14_u25` (Score: 1.50)
- **Episode:** 7 | **Duration:** 21.4s
- **Timestamps:** `00:33.20 - 00:54.60`
- **Opening Hook:** *"ARISTOCRATIC WOMAN: "Home? Look at your hands, Juliana."..."*
- **Ending Line:** *"CAMERA: Close-up on Juliana's clear blue eyes, shining with unbroken pride. | CAMERA: Wide shot framing Juliana facing o..."*
- **Why the tool scored it poorly:** Starts on an inert conversational exchange or procedural movement rather than an explosive hook. The ending resolves the ongoing beat rather than posing an urgent narrative question.
- **Verdict:** Rightfully rejected by the candidate pruning filter.

---

### #5: Candidate `ep08_u22_u41` (Score: 1.50)
- **Episode:** 8 | **Duration:** 24.6s
- **Timestamps:** `00:25.00 - 00:49.60`
- **Opening Hook:** *"JULIANA: "Your hair and beard..." | CAMERA: Medium shot of Alexander standing tall over her, looking down patiently. | C..."*
- **Ending Line:** *"CAMERA: Medium shot of Juliana chuckling quietly as she steps back toward the table. | JULIANA: "Very well." | CAMERA: C..."*
- **Why the tool scored it poorly:** Starts on an inert conversational exchange or procedural movement rather than an explosive hook. The ending resolves the ongoing beat rather than posing an urgent narrative question.
- **Verdict:** Rightfully rejected by the candidate pruning filter.

---
