# Changelog

## 0.3.0 (2026-10-05)

The Jetson Nano carrier's (mythtv-porg) symbols, from its project library:

- calico-ic: EFM8SB10F2G, GS7116S5-ADJ, MP2152, TPS53015, STUSB4531,
  NCP301LSN20T1, CYUSB3304, AP22811, APL3552, GS7616SC, TPD4E02B04DQA (drawn
  flow-through, one end of each channel per side, which KiCad's own symbol
  cannot do), 2N7002DW (two units, each a pass element: source left, drain
  right, gate on top).
- calico-electromechanical: Jetson_Nano_SODIMM (five units, 261 pins, names
  from the Product Design Guide), USB3_A_Stacked2 (two units, one per port,
  Molex 48406-0001 numbering).
- Builder: `units_symbol()` for multi-unit box symbols; no-connect pins are
  hidden (KLC S4.6); `_pin()` takes a length for a pin that has to reach a
  shallower body.

## 0.2.2 (2026-10-05)

- USB2517: the crystal pins move to the bottom of the left column so the
  clock source hangs below the other lanes, and VBUS_DET gets clear rows on
  both sides for the upstream connector's lower pins.

## 0.2.1 (2026-10-05)

- USB2517: two gap rows between the upstream pair and VBUS_DET, so the
  VBUS_DET lane clears the upstream connector's D+ rows when the ESD array
  sits on the pair.

## 0.2.0 (2026-10-05)

- MK64FN1M0VLL12, USB2517: every USB pair is ordered D- above D+, the order
  of the lines on a USBLC6-2SC6 array, so an array placed on the rows wires
  straight. Pin positions within each pair swap.

## 0.1.2 (2026-10-05)

- TPS2553DBV: a gap row between FAULT and OUT, so a label on the OUT row
  (whose text prints above the wire) clears the FAULT label.

## 0.1.1 (2026-10-05)

- Reference text above the top pins' numbers on symbols with top pins.
- USB_A_Stacked2: VBUS and GND rows 12.7 mm below the data rows, so an ESD
  array on the data rows keeps its GND symbol clear of the switched VBUS row.

## 0.1.0 (2026-10-05)

First release: the seven symbols that sbc-development-baseboard had in its
project library, moved here and brought to the KiCad Library Conventions
(pins on the 100 mil grid, 20 mil name offset, keywords, footprint filters,
datasheet links).

- calico-ic: MK64FN1M0VLL12, USB2517, TPS2553DBV, PCA9517A, TPS54560BDDA
- calico-electromechanical: USB_A_Stacked2 (two units, one per port), JW1FSN
