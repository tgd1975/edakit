# Review of step D.5: handbook/15-regulatory.md

Status: condensed in place on 2026-11-01, not reviewed yet – the assumptions below are for the owner. This chapter is
regulatory content: support, not legal advice, nothing legally guaranteed, without any claim to correctness.

## Measures

| | before | after |
| --- | --- | --- |
| lines | 143 | 187 |
| own words (prose, without tables and code) | 1365 | 1883 |
| all words (tables included, link targets left out) | 2804 | 2874 (+2.5 %) |
| mean sentence | 31.0 | 21.2 |
| test_style violations | paragraphs 2 (154 and 181 words), words 2 ("the user", lines 34 and 41) | none |

`tests/test_style.py` now passes `paragraphs` and `words` for the chapter (XPASS strict): the chapter can leave those
two sets of `RED`.

"Own words" rose because three table cells that were paragraphs – `private` and `gift` in 15.1, frequency use and the
German EMC scope in 15.2 – became prose, which the measure counts and a table cell it does not.

**Why not a third fewer.** Every section of the chapter is named from outside: 15.1, 15.2, 15.4, 15.5 and 15.6 by
`edakit/` (codes.toml, cart.py, radio.py, national.py/.toml, the maker profiles, domains core and radio), skills and
`agents/regulatory-reviewer.md`, chapter 15 as a whole by four skills and the agent, which opens the file by path, and
15.3 by `tests/test_rohs.py`. The chapter is a map of law: nearly every clause is a number, a date, a threshold, an
article or a condition, each a statement. The grading of 15.4 stays word for word (the owner's decision), as do both
not-legal-advice passages. A new first paragraph (27 words) and three `###` headings were added. What could go – one
example of three in the intro, a repeated LIM.eirp sentence in 15.3, a repeated "(8.2)", "as before" – is small; the
rest of the work was splitting sentences (31 → 21 words on average) and taking paragraph cells out of tables, which
costs words. The statements won.

## Per section

- **(new) first paragraph** – for whom and what after: a board sold, given away or transmitting; state the purpose, give
  the review what it needs, read M-6.
- **Intro** (named as "handbook 15" by `skills/circuit-design`, `part-search`, `own-part`, `agents/regulatory-reviewer`,
  `edakit/radio.py`, codes.toml) – the three examples cut to one (the soldered-in cell; see Findings and Assumptions).
  "(8.2)" now follows "the sign-off M-6 that every release needs". "The state of October 2026" and the not-legal-advice
  paragraph kept word for word.
- **15.1 The purpose decides** (named by `skills/new-project`, `edakit/cart.py:505`, codes.toml 131, 377, 1104, 1302,
  `edakit/domains/core.toml:53`, the agent) – the run-on sentence with `purpose`, `country` and `radio` became the
  `purpose` line plus a two-item list of the optional keys; "It is part of the circuit hash" → "The purpose is part of
  the circuit hash". The three-row table `use` / Means / What applies (cells of up to 120 words, read by no test or
  generator) became a list of entries `private`, `gift`, `sale`, each statement kept: EMVG § 6 and FuAG § 7 for private,
  Blue Guide 2.2 and 1.5, REACH Art. 3(12), 33(1), 33(2), 3(35), 45 days, EMVG § 6 passing on, regular giveaways count
  as sale, the seller (of a kit too) is the manufacturer.
- **15.2 The rules** (named by `edakit/radio.py`, `edakit/cart.py:501–504`, `edakit/national.toml:61`,
  `edakit/makers/jlcpcb.toml:23`, `edakit/domains/radio.toml`, `edakit/catalog/tables/radio_eu.toml`, the agent) –
  nothing left the section. The Frequency use cell (about 200 words) keeps the bands, powers and duty cycle and
  "prohibited also privately"; its e.i.r.p. definition, LIM.eirp, LIM.band, US LoRa and the ESP32 paragraph moved under
  a new `### Frequency use` below the table, word for word where possible, split into sentences. The EMC row's German
  scope (EMVG §§ 3 no. 2 a, 4, 6, 8; FuAG § 7 with § 4(1) no. 2) moved under a new `### National references`, next to
  the existing paragraph that the national references are Germany's. "the user" → "the end user" twice (EN 18031
  password, replaceable battery) – there it is the buyer of the product, not the reader. Other rows unchanged.
- **15.3 What the review needs** (named by `tests/test_rohs.py` only) – the 154-word "Per part" item split in two: "Per
  part" (what the entry states) and a new item "Checked per part" (PARTS.fact, PARTS.fact/reach, PARTS.fact/rohs). The
  sentence "LIM.eirp compares the e.i.r.p. with the band's limit" dropped here – it stands in the frequency use of 15.2
  and in the sign-off of 15.4; the second "(4.1)" dropped. "Per project" split into sentences.
- **15.4 The sign-off** (named by `.claude/skills/add-rule`, `.claude/skills/triage-rule`, `edakit/domains/radio.toml`,
  codes.toml 1181, 1256, 1316) – the 181-word paragraph split into three: scope and hash, requirements, findings. The
  second "(8.2)" dropped (same sentence group, same reference); "(8.7)" → "(requirements, 8.7)", "(14.4)" → "(from a
  finding to a rule, 14.4)". The paragraph "What the firmware has to keep is graded by the purpose" is unchanged,
  character for character.
- **15.5 At the order** (named by `edakit/makers.py:35` and the four maker profiles) – one sentence split; "the owner" →
  "you" in the table (the one who imports, stays the manufacturer, supplies parts); the last paragraph split into
  sentences, "(8.4)" moved next to "the order record". The table's statements unchanged.
- **15.6 National law** (named by `skills/new-project`, `edakit/national.py:1`, `edakit/national.toml:1`, codes.toml
  124, the agent) – two long sentences split, the example line of `edakit domains --review regulatory` set on its own
  line; "as before" dropped from the table (history file). The closing not-legal-advice sentence kept word for word.

## History file

Only "as before" in the 15.6 table (the behaviour before `purpose.country`). The dates stay: the state of the law
(intro, 15.2) is what the review relies on, and the date of the owner's decision in 15.4 is part of the grading kept
word for word.

## Findings

1. **Intro, "no check of the circuit sees that"** (before: "A LoRa module made for the US band, a part without a RoHS
   statement, a soldered-in lithium cell in a board that is sold – no check of the circuit sees that."). Two of the
   three examples are checked today: LIM.band flags a part made for a band outside the EU's, PARTS.fact/rohs a BOM part
   without a RoHS status (the chapter's own 15.3 and 15.4 say so). Only the soldered-in cell has no check (domain core
   asks it as a review question). The condensed intro keeps that one example; the owner may prefer another wording.
2. **15.3, "PARTS.fact/reach, graded as 15.4 says"** – 15.4's grading paragraph is about what the firmware has to keep
   (channels, country, 802.11d, power); it says nothing about PARTS.fact/reach. The grading itself is in
   `edakit/domains/core.toml` ([severity.sale] warning; a gift: per codes.toml 1172 "information for a gift, a warning
   for a board that is sold, nothing for one built for oneself or without a purpose"). The chapter should either state
   that grade in 15.3, as it does for PARTS.fact/rohs, or 15.4 should name the facts too. Left as it was.
3. **codes.toml 1172 and the test docstrings** (`tests/test_reach.py:3`, `tests/test_rohs.py:3`) cite "handbook 15.4"
   for the grading of REACH and RoHS facts, which 15.4 does not hold (as 2). A source text for the owner, not changed.
4. **codes.toml 1172** still names "the reference project" in its finding example – a catalog text, data; not changed.

## Assumptions

1. The intro's three examples cut to one, the soldered-in cell – the one no check sees (Finding 1). Cutting the two
   others also removes a claim that is no longer true; if that is a fix the owner wants made differently, the old
   sentence is in the file's git history.
2. The 15.4 grading paragraph keeps "the owner's decision of 2026-10-29" although "the owner" leaves the chapter's own
   sentences elsewhere: the instruction was that its statements stay exactly, and the decision is its source.
3. "the owner" in the 15.5 table → "you": it is the person ordering, the reader. The agent's own table keeps "the
   owner".
4. "the user" → "the end user" in the RED and batteries rows: the person using the product, not the reader – "you" would
   be wrong there.
5. The 15.1 table became a list of entries and the frequency use cell and the German EMC scope of 15.2 left the table
   for prose under new `###` headings in the same section. No test or generator reads these tables (grepped).
6. "Arduino-ESP32 deinitialises the driver on `WiFi.mode(WIFI_OFF)`, which is why the call follows every start" spells
   out what the parenthesis implied in the original; no new claim is meant.
7. The second not-legal-advice passage (end of 15.6, about the national table) stays although CLAUDE.md asks for the
   statement once: 15.6 is named by `edakit/national.py` and `national.toml`, which carry the same words.
8. The chapter grew by 44 lines and 2.5 % of its words; the target of a third fewer was not met (see "Why not a third
   fewer").
