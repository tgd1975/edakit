# 19 The circuit language

For you if a circuit repeats itself, comes in variants, or has values that follow from a rule – an LED's series
resistor, a divider, a pull-up. After this chapter you can derive a block's values with `edakit block add --set` and
read what edakit holds a derived value to. The notation is
[circuit-dsl-language.md](../docs/concepts/new/circuit-dsl-language.md); this chapter grows with the steps of
[circuit-dsl-toolchain.md](../docs/concepts/new/circuit-dsl-toolchain.md).

## 19.1 Derivations

A derivation is a rule of edakit's that derives a part's value from the parameters, the ranges of the nets it is
bound to and the entries of the parts: the series resistor of an LED from its current, a divider from its output
voltage and current, a pull-up from the bus. The rule proposes, the designer chooses: it never writes a value no entry
has, and the part keeps the value it is given.

```bash
edakit block add led --as STATUS --connect in=SIG --set i=4mA
edakit block add led --as STATUS --connect in=SIG --set i=2mA --part R1=C17630
```

`--set i=4mA` evaluates `series_resistor` with the block's own entries and the range of the net `in` joins (SIG,
0…3.4 V): derived 140 Ω, E24's nearest 150 Ω, the window 130…160 Ω. The block's 150 Ω fits and stays. Where the block's
value lies outside, `add` stops and names the window and the entries of the same kind and package inside it, from
the library and the project; `--part R1=KEY` takes one – its LCSC number, part number, value and pin map. A value no
entry has is never written: the part-search skill finds one.

The record goes into the graph's `derivations`, in a TOML graph as a `[[derivations]]` table: the rule, its inputs
with where each number came from, the derived value, the series' nearest value and the window, the chosen value and
what it predicts. `edakit graph show R3` lists it. `edakit graph derive` evaluates every record again with the entries
as they are now, and `--write` rewrites those of a JSON graph.

The engine DEF holds the part to its record; it compares numbers only and never evaluates a rule:

<!-- edakit:generated table DEF -->
| Code | Title | Severity |
| --- | --- | --- |
| [`DEF.derive`](../docs/catalog/def.html#DEF.derive) | derived values within their window | warning, inputs: warning |

Rule, why, fix and sources of each: `edakit explain CODE`, or the code on its page of the catalog.
<!-- edakit:end -->

The rules, generated from their table (`edakit/lang/rules.py`), each choosing from an E-series of IEC 60063:

<!-- edakit:generated rules -->
| Rule | Inputs | Output and formula | Series, window |
| --- | --- | --- | --- |
| `series_resistor` | `i` (the LED current; a range gives its centre), `led` (the LED – the one of the definition), `in` (the driving port – the one besides gnd; v_on is its range's upper bound) | value: vf(i) = vf_typ_v + rs_ohm·(i − vf_at_a); R = (v_on − vf(i)) / i | E24; one step of the series around the derived value |
| `divider` | `v_out` (the output voltage), `i` (the divider's current), `in` (the port whose range's upper bound is v_in) | top, bottom: R_bottom = v_out / i; R_top = (v_in − v_out) / i | E24; one step each |
| `pullup` | `v` (the supply: a port's upper bound or a quantity), `i_sink` (the sink current – the I2C table's), `v_ol` (the low level – the I2C table's), `c_bus` (optional), `t_rise` (optional) | value: R_min = (v − v_ol) / i_sink; R_max = t_rise / (0.8473 · c_bus), else the table's r_max_ohm; the value nearest √(R_min · R_max) | E24; [R_min, R_max] |
| `rc` | `f_c` (the corner frequency), `c` (optional), `r` (optional) | value: R = 1 / (2π f_c C), C = 1 / (2π f_c R) | E24 for a resistor, E6 for a capacitor; one step |
<!-- edakit:end -->
