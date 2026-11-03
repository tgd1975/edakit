"""The texts of circuit-dsl-language.md section 11 – the fixtures of the language's tests (T.2 on)."""

LED_BAR = """\
graph led-bar version 1.0 date 2026-10-25
description "Example for edakit: a Raspberry Pi Pico 2 drives eight LEDs through a TLC5916 constant-current sink; 5 V
    input with reverse-polarity diode, one push button."
purpose private market EU
  notes "An example board for edakit, built for testing, not sold or given away."
convention pin_reference "'<designator>.<pin>' with the pin's name or role, else its symbol number – the parts entry
    says which pin that is"
convention v "per net: [min, max] in V over all intended operating states"
convention accept "per net or component: {code: reason} accepts a finding on purpose (edakit explain <code>)"

part J1 connector B2B-PH-K-S(LF)(SN) lcsc C131337 no-bom source reversible "5 V input (JST PH, top entry)"
  notes "Pin 1 = VIN (+5 V), pin 2 = GND. Through-hole, soldered by hand (Economic assembly: SMD only)."
part D1 diode SS34 lcsc C8678 "Reverse-polarity protection"
  notes "A reversed supply reaches only the anode of D1."
part U1 microcontroller "Raspberry Pi Pico 2" lcsc C41407547 "Raspberry Pi Pico 2 (SMD module)"
  nc GP0 GP1 GP7 GP8 GP9 GP10 GP11 GP12 GP13 GP14 GP15 GP16 GP17 GP18 GP19 GP20 GP21 GP22 RUN GP26_ADC0 GP27_ADC1
  nc GP28_ADC2 ADC_VREF 3V3_EN VBUS SWCLK SWDIO TP1 TP2 TP3 TP4 GPIO25/LED BOOTSEL
  notes "GP2 (SPI0 SCK) and GP3 (SPI0 TX) clock and shift into the LED driver, GP4 latches, GP5 dims (PWM), GP6 reads
    the button (internal pull-up). The module's 3V3 regulator supplies U2."
part U2 ic TLC5916IDR lcsc C90107 "TLC5916 8-channel constant-current LED driver"
  nc SDO
  function "8-channel constant-current sink"
  notes "I_OUT = 15 x 1.26 V / R1 = 9.45 mA per output."
part R1 resistor 0805W8F2001T5E lcsc C17604 value 2k "R-EXT 2 k (sets the LED current)"
part R2 resistor 0805W8F1002T5E lcsc C17414 value 10k "OE pull-up 10 k: LEDs off until the firmware runs"
part C1 capacitor CC0805KRX7R9BB104 lcsc C49678 value 100nF "100 nF at U2 VDD"
part C2 capacitor CL21A226MAQNNNE lcsc C45783 value 22uF "22 µF on +5V at the module"
part SW1 button TS-1187A-B-A-B lcsc C318884 "Push button to GND"
  nc B D
  notes "Pins 1/2 and 3/4 are connected inside."

net VIN 0..5.5 V J1.1 D1.anode
  notes "5 V from a USB power supply, up to 5.5 V unloaded."
net +5V 0..5.5 V D1.cathode U1.VSYS C2.1
  notes "Behind D1: module VSYS and all LED anodes."
net GND 0 V J1.2 U2.GND R1.2 C1.2 C2.2 SW1.C U1.3 U1.8 U1.13 U1.18 U1.23 U1.28 U1.AGND U1.38 U1.42
net 3V3 0..3.4 V U1.3V3(OUT) U2.VDD C1.1 R2.1
  notes "From the module's regulator."
net LED_SDI 0..3.4 V U1.GP3 (locked) U2.SDI fn spi.tx fn_bus LED
  accept LVL.undefined "Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."
net LED_CLK 0..3.4 V U1.GP2 (locked) U2.CLK fn spi.sck fn_bus LED
  accept LVL.undefined "Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."
net LED_LE 0..3.4 V U1.GP4 (locked) U2.LE(ED1)
  accept LVL.undefined "Floating until the firmware runs, but harmless: R2 holds OE high, so no output can switch on."
net LED_OE 0..3.4 V U1.GP5 (locked) U2.OE(ED2) R2.2 fn pwm
  notes "Active low; R2 keeps the LEDs dark at boot."
net BTN 0..3.4 V U1.GP6 (locked) SW1.A
  notes "Internal pull-up of GP6; pressed = 0."
net REXT 0..1.3 V U2.R-EXT R1.1

for n in 0..7
  part D{n+2} led KT-0805G lcsc C2297 value green "LED {n+1} (green 0805)"
  net LED{n} 0..5.5 V U2.OUT{n} D{n+2}.cathode
  net +5V D{n+2}.anode

set cables []
layout fixed SW1 D2 D3 D4 D5 D6 D7 D8 D9
layout edge J1
layout near R1 U2
layout note "D2 to D9 form the bar: one row, in this order from left to right, as the user reads it."
"""

BELL_STEP = """\
def led (color = green, i = 10 mA) ports in gnd
  title "LED with series resistor, driven by a signal"
  part R resistor
  part D led value color
  net in     R.1
  net anode  R.2 D.anode    v @in
  net gnd    D.cathode
  derive R.value series_resistor(i)
  covers LIM.v LIM.i LIM.p LIM.t LIM.range LIM.declared LIM.backfeed LVL.threshold LVL.direction SIM.config SIM.state
  notes "sim.json: the driving net under the MCU's outputs, and leds_on in every load."

use led step1 (color = green)  in = LED_G1 gnd = GND anode = LED_G1_A
  R = R4   "330 Ω 0805" lcsc C17630 value 330Ω "Series resistor LED5"
  D = LED5 XL-504UGD lcsc C2895549 no-bom "5 mm LED, green, countdown step 1"
use led step2 (color = green)  in = LED_G2 gnd = GND anode = LED_G2_A
  R = R3   "330 Ω 0805" lcsc C17630 value 330Ω "Series resistor LED4"
  D = LED4 XL-504UGD lcsc C2895549 no-bom "5 mm LED, green, countdown step 2"
net LED_G1 vlogic U1.led1 (locked)
net LED_G2 vlogic U1.led2 (locked)
"""

BELL_SMD = """\
variant smd of ../../hardware/graph.circuit
  description "… the SMD configuration"
  part J1 connector "HX PZ2.54-1x3P TP-YQ" lcsc C41417360 bom yes
  part C1 capacitor "RVT1C102M1010 1000uF 16V SMD" lcsc C3359 bom yes
  use led step1 D = LED5 KT-0805G lcsc C2297 bom yes "0805 LED, green, countdown step 1"
  use led step2 D = LED4 KT-0805G lcsc C2297 bom yes "0805 LED, green, countdown step 2"
  accept HINT.bulk "C1 1000 µF / 16 V electrolytic on +5V, next to J1 (it buffers the Nano's 5V pin)"
"""

REQUIREMENTS = """\
need N-1 "The countdown is visible across the room." who owner status accepted
requirement R-3 from N-1 must "Every countdown LED carries 2 to 15 mA while its step is on."
  subject led
  require D.i within 2 mA .. 15 mA
  verify rows "LIM.i *"  verify rows "SIM.state *"
  status accepted
requirement R-7 from D-8 should "A USB power bank stays on: the circuit draws at least 100 mA."
  subject +5V
  verify signoff M-1
"""
