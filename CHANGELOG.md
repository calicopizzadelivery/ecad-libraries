# Changelog

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
