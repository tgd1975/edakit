# 15 Regulatory review (M-6)

Not everything that can be ordered may be sold, given away or even switched on in the EU. A LoRa module made for the
US band, a part without a RoHS statement, a soldered-in lithium cell in a board that is sold – no check of the circuit
sees that. The agent `regulatory-reviewer` checks circuit and parts against EU law for the purpose stated in the
graph; its result is the sign-off M-6, which every release needs (8.2). It runs at the hand-over of the circuit
(14.1), before the layout, because its findings usually change parts.

This chapter is its map: the state of October 2026, with the primary sources. The law changes – the agent checks every
date and threshold it relies on against the source. It is no legal advice; whoever sells the board answers for it.

## 15.1 The purpose decides

`purpose` in the graph (3.1): `{"use": "private" | "gift" | "sale", "market": "EU", "notes": "what it is, who uses
it"}`. It is part of the circuit hash: a new purpose needs a new M-6.

| `use` | Means | What applies |
|---|---|---|
| `private` | built for oneself and used oneself | nothing of placing on the market (CE, RoHS, WEEE …); still, a transmitter only in an allowed band and power – also privately – and nothing dangerous |
| `gift` | given away now and then by a private person | as private: occasional supplies by hobbyists are normally not "making available on the market" ([Blue Guide](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52022XC0629(04)) 2.2); regular giveaways in the course of a business count as `sale` |
| `sale` | sold – also in small series, also as a kit | everything in 15.2: the seller is the manufacturer, of a kit too |

## 15.2 The rules

| Rule | What it asks | Applies to | Source |
|---|---|---|---|
| Frequency use | transmit only in a licence-exempt band within its power and duty cycle: 433.05–434.79 MHz, 863–870 MHz (868.0–868.6 MHz: 25 mW, ≤ 1 %), 2400–2483.5 MHz (100 mW e.i.r.p.), 5 GHz RLAN. 902–928 MHz (US LoRa) is none of them – 880–915 MHz is mobile uplink in Europe. Operating radio equipment that does not comply is prohibited also privately | every board that transmits | [2006/771/EC](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32006D0771) (as amended), [BNetzA Vfg. 91/2025](https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Frequenzen/Allgemeinzuteilungen/_DL/vfg91_2025.pdf), [FuAG § 7](https://www.gesetze-im-internet.de/fuag/__7.html) |
| Radio equipment | anything that transmits or receives: the board with a fixed module is one radio product – the module's certificates are input, not a substitute. Own conformity assessment, EU declaration of conformity, instructions with bands and power. Internet-connected: cybersecurity since 1 Aug 2025; EN 18031 gives no presumption of conformity where the user may skip setting a password – then a notified body | sale | [2014/53/EU](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014L0053), [2022/30](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R0030) |
| EMC | electromagnetic compatibility, no lower voltage limit; a radio product is covered by RED instead | sale | [2014/30/EU](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014L0030) |
| Low voltage | 50–1000 V AC, 75–1500 V DC: a 5 V board is outside, the mains power supply that comes with it is not (its own CE, ecodesign) | sale | [2014/35/EU](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014L0035) |
| Product safety (GPSR) | consumer products: risk analysis and technical file (10 years), type or batch number and the manufacturer's postal and electronic address on the product, instructions in German; online offers show manufacturer, picture, identifier and warnings; accidents are reported. CE-marked products: Art. 19–20 | sale, since 13 Dec 2024 | [(EU) 2023/988](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R0988) |
| RoHS | Pb, Hg, Cr(VI), PBB, PBDE and four phthalates ≤ 0.1 %, Cd ≤ 0.01 % per homogeneous material; exemptions expire (7(c)-I, lead in piezo ceramics as in buzzers: 30 Jun 2027) | sale | [2011/65/EU](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0065), [(EU) 2015/863](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32015L0863) |
| REACH Art. 33, SCIP | a substance of very high concern above 0.1 % in an article: tell the recipient, a consumer on request within 45 days; notify ECHA's SCIP database | sale, also free supply | [1907/2006](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32006R1907), [(EU) 2018/851](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32018L0851) |
| WEEE | register with stiftung ear before the first board is sold – no minimum quantity; the number on offers and invoices; crossed-out bin, manufacturer mark and date on the product | sale | [2012/19/EU](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32012L0019), [ElektroG § 6](https://www.gesetze-im-internet.de/elektrog_2015/__6.html) |
| Batteries | CE and declaration of conformity for batteries (since 18 Aug 2024), collection symbol; from 18 Feb 2027 a portable battery in a product must be removable and replaceable by the user with ordinary tools (exceptions in Art. 11); register with stiftung ear and join a take-back organisation – also for a battery built into or packed with the board | sale | [(EU) 2023/1542](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1542), [BattDG](https://www.gesetze-im-internet.de/battdg/) |
| Common charger | only the listed radio products charged by cable (phones, headphones, portable speakers, keyboards, mice, cameras …): USB-C, USB PD above 15 W | sale | [(EU) 2022/2380](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022L2380) |
| Cyber Resilience Act | products with a data connection: reporting of actively exploited vulnerabilities since 11 Sep 2026, most duties from 11 Dec 2027 | sale | [(EU) 2024/2847](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R2847) |
| Toys | made or meant for play by children under 14: toy safety, electric toys at most 24 V; replaced by Regulation (EU) 2025/2509 on 1 Aug 2030 | sale | [2009/48/EC](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32009L0048), [(EU) 2025/2509](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32025R2509) |
| Packaging | packaging – the shipping box too – registered in LUCID before the first sale, and a take-back system | sale, since 12 Aug 2026 | [(EU) 2025/40](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32025R0040), [VerpackDG](https://www.gesetze-im-internet.de/verpackdg/) |

Commonly missed: a CE mark on a module – genuine or not – never covers the product it is built into; whoever resells
an imported power supply or cell is its importer.

## 15.3 What the review needs

- **Per part** – `compliance` in the parts entry (4.1), filled by the skill part-search: RoHS status
  (and the exemption it relies on), the supplier's REACH SVHC statement, and for a part that transmits its
  bands, maximum power and the EU declaration of conformity. What nobody states is open, not fine.
- **Per project** – `purpose` in the graph and the decision log: who uses the board (children?), the cell in a battery
  holder (chemistry, capacity, soldered or plugged), the power supply that comes with it, whether it connects to the
  internet and which personal data it handles – then also passwords and updates of the firmware.

## 15.4 The sign-off

M-6 has the scope `circuit` (graph with its purpose, parts database, simulation config): a changed part or purpose
needs a new review. The gate requires it even when the sign-off file does not list it (8.2). The agent's findings are
numbered – **block** (may not be sold or operated like this), **important**, **note** – each with the rule, its
source and a proposal, and they go into the decision round with the electrical review. What a program could decide –
a band outside the EU's, a part without a RoHS status – the agent marks as a check candidate (14.4).
