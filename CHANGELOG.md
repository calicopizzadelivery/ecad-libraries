# Changelog

## 0.3.6 (2026-10-07)

- USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal_PegClear: the four
  shell pads carry KiCad's `pad_prop_mechanical` property and the texts turn
  with the part (`unlocked`), as in the library footprint, so the copy is
  the original pad for pad in every field; the tags carry the stake-length
  part numbers again. No pad geometry changes. (A verifier's finding.)

## 0.3.5 (2026-10-07)

- calico.pretty gains USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal_PegClear:
  KiCad's footprint of GCT's recommended layout, rebuilt by the builder pad
  for pad, with the four outer ground pads (A1, A12, B1, B12) 0.1 mm shorter
  at the end facing the 0.65 mm board-lock peg holes, so hole to copper is
  0.29 mm instead of GCT's 0.19 mm and a fab's 0.25 mm minimum holds without
  an exception. It keeps the KiCad part's 3D model: `FP` takes a `model`
  path for a footprint derived from a library one.

## 0.3.4 (2026-10-06)

- calico-ic gains USBLC6-2SC6-IO2up: the ST ESD array drawn with I/O2 on
  the upper row, for receptacles whose D- pad lies on the I/O2 end of the
  package, so the pair runs through the array uncrossed and the sheet stays
  straight (ecad-standards/layout.md 3.8).

## 0.3.1 (2026-10-05)

- CYUSB3304: the crystal pins move to the bottom of the left column, below
  the RREF pins, so the clock source hangs below everything else on that
  side (schematic-style: clock sources flow downward).

## 0.3.0 (2026-10-05)

The Jetson Nano carrier's (mythtv-porg) symbols, from its project library:

- calico-ic: EFM8SB10F2G, GS7116S5-ADJ, MP2152, TPS53015, STUSB4531,
  NCP301LSN20T1, CYUSB3304, AP22811, APL3552, GS7616SC, TPD4E02B04DQA (drawn
  flow-through, one end of each channel per side, which KiCad's own symbol
  cannot do), 2N7002DW (two units, each a pass element: source left, drain
  right, gate on top), NTTFS4C25N, NTTFS4C06N and STL6P3LLH6 (8-pad 3.3x3.3
  power MOSFETs as boxes with their pad stacks, on the house footprints).
- calico-electromechanical: Jetson_Nano_SODIMM (five units, 261 pins, names
  from the Product Design Guide), USB3_A_Stacked2 (two units, one per port,
  Molex 48406-0001 numbering).
- Builder: `units_symbol()` for multi-unit box symbols; no-connect pins are
  hidden (KLC S4.6); `_pin()` takes a length for a pin that has to reach a
  shallower body.
- calico.pretty, the first footprints, from `tools/build_footprints.py`:
  M.2 Key E socket TE 2199230-4 (drawing C-2199230 B4), FPC TE 1-1734248-5
  vertical 15-way (C-1734248 E1), onsemi WDFN8 3.3x3.3 0.65P (case 511AB),
  ST PowerFLAT 3.3x3.3 8L. Each description says what was read from the
  drawing and what still needs verifying.

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
