# Sensor enclosure (resin print, snap-fit lid)

![closed](preview_closed.png)
![charger slot](preview_charger.png)

Box for the battery sensor: 21700 holder (85 x 25 x 25) and the DX-PJ26 (72 x 30 PCB) + LR30-A +
perfboard stack (20 high) in line. The TP4056 USB-C charger stands on edge beside the battery
holder, and the reed board stands on edge beside the board, on opposite long walls.
Outside 171.1 x 43 x 31 mm.

| File | Use |
|---|---|
| `door_sensor_box_base.step`, `door_sensor_box_lid.step` | Open in Fusion 360 (solid bodies) |
| `door_sensor_box_assembly.step` | Base + lid + orange reference blocks for the components |
| `door_sensor_box_base.stl`, `door_sensor_box_lid.stl` | Print |
| `door_sensor_box.py` | Parametric source (CadQuery); every size is at the top |

## Design

- **Lid**: R6 rounded top edges and corners. It snaps on with six cantilever tabs (1.4 mm thick,
  11 mm long, 0.5 mm hook, ~1.1% strain) into windows in the long walls. To open, push the hooks
  in through the windows with a pin. A 3 mm lip aligns it. Two ribs hold the battery holder down
  (0.5 mm gap; add foam tape for a tight fit).
- **SMA**: the base/lid split is at the SMA centre height, so the board drops in with the SMA in a
  half-round notch and the lid closes the top half. Its centre is 12.5 mm from the PCB edge away
  from the reed board (measured), and the carrier is flush with the PCB end. An 11 mm spot face thins
  the wall to 1 mm around it, leaving ~7.5 mm of thread outside for the antenna.
- **USB-C**: the charger stands on its long edge beside the battery holder, components and
  USB-C toward the wall, with its PCB edge against the end wall. The receptacle (vertical) goes
  into a rounded opening whose centre is 1.2 mm above the PCB's mid-height (the receptacle is
  off-centre; measured on the first print), with 0.6 mm clearance top and bottom. A 0.5 mm
  outside counterbore lets the plug overmold reach it. Nothing touches the
  component side: a rib holds the flat back, and a plate behind the rear edge takes the plug
  insertion force. The board is 28.26 mm long including the two ears at its rear corners
  (measured); the plate is 16.3 mm tall so both ears rest on it. Nothing reaches onto the faces
  at the rear edge, where the through-hole wire pads (B+/B-/OUT+/OUT-) are. The inner corners are 1.5 mm radius so the charger fits
  right into the corner.
- **First print (2026-11-02)**: the USB hole had to be opened 1.2 mm upward (now in
  `USB_Z_OFF`). The charger had been designed with its components toward the battery and a low
  rib on the wall side, which would touch the components once the board was mounted the other
  way. There was also no rear stop where the board actually sat. All fixed as above, not
  reprinted yet. The PCB length was 27 mm in the model; the real board is 28.26 with its ears.
- **Board**: no standoffs. Its four mounting holes (65.5 x 24.5 mm centres) drop onto 2.7 mm
  pins on 4 mm printed posts, which clear the header solder tails. A lid rib on the perfboard's
  blank rear strip keeps it on the pins, and the lid's SMA notch holds the other end.
- **Reed board**: slot against the high-Y wall (opposite the charger), so the magnet goes on that
  face.

## Measure before printing

These are estimates from photos; set them in `door_sensor_box.py` and rerun:

| Parameter | Now | What |
|---|---|---|
| `POST_H` | 4.0 | Must exceed the longest solder tail under the PCB |
| `PIN_D` | 2.7 | Mounting hole diameter minus ~0.4 (assumes 3.1-3.2 mm M3 holes) |
| `PERF_OVERHANG` | 3.0 | Perfboard beyond the PCB at the battery end (the lid rib lands 0.5-3 mm in from its edge) |
| `SMA_LEN` | 9.0 | SMA length beyond the carrier edge |
| `USB_PROTRUDE` | 1.5 | USB-C front beyond the charger PCB edge |
| `REED_L/H/T` | 33/10/5 | Reed board size, standing on edge (length from a photo) |

## Rebuild

```
python -m venv cqenv
cqenv\Scripts\python.exe -m pip install cadquery
cqenv\Scripts\python.exe -I door_sensor_box.py
```

It rewrites the STEP/STL files and prints any overlap between the parts and the component blocks.

## Printing (resin)

Use a tough or ABS-like resin for the tabs; standard resin may crack them. Tilt each part
~30-45 degrees, support from the outside, and keep supports off the tabs and the lid's
top. Rinse and cure fully before the first snap.
