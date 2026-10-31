# SparkFun Logic Level Converter – Bi-Directional – a published design, transcribed for edakit's tests

**Source:** SparkFun Electronics, schematic *Logic_Level_Bidirectional*, design Patrick Alberts, Rev V01, dated
2013-09-26 – <https://cdn.sparkfun.com/datasheets/BreakoutBoards/Logic_Level_Bidirectional.pdf> (linked from the
product page <https://www.sparkfun.com/sparkfun-logic-level-converter-bi-directional.html>), read on 2026-10-31.
Released under the Creative Commons Attribution Share-Alike 3.0 License (the schematic's title block); this
transcription keeps that licence.

**Transcribed:** four identical channels – Q1 to Q4 (BSS138) with the gate on LV, the source on LVn pulled up to LV and
the drain on HVn pulled up to HV, each through 10 kΩ (R1 to R7, R10) – and the headers JP1 (LV1, LV2, LV, GND, LV3,
LV4) and JP2 (HV1, HV2, HV, GND, HV3, HV4), pins as numbered in the schematic.

**Stand-ins:** the schematic names the BSS138 (SparkFun links Fairchild's datasheet, Rev C(W)) – onsemi's BSS138
C52895 is the part, its entry from that datasheet; the 10 kΩ resistors are 0805 parts of edakit's library; the headers
1 × 6 pin headers. Voltages: LV 3.3 V and HV 5 V, the hookup guide's example.

**What edakit finds** – and how each finding is judged – is in `findings.toml`, held by `tests/test_open_designs.py`.
