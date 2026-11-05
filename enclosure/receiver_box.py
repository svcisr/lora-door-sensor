"""Snap-fit enclosure for the LoRa door receiver + Shelly UNI (resin print).

Builds base, lid and a push stick with CadQuery and exports STEP (for Fusion 360) and STL
(for slicing). Every size is a parameter below; change one and rerun:

    cqenv\\Scripts\\python.exe -I enclosure/receiver_box.py

Layout (top view, X = length, Y = width, origin at the outside corner of the USB end):

    USB wall                                                      SMA wall
    |  [boss]                                             [boss]   |
    |  Shelly UNI on edge (harness -> slot A)  (wires -> hole B)   |
    |                                                              |
    |  DX-PJ26 + LR30-A + perfboard, KEY/RST at the USB end         |-> SMA
    |  [boss]  (PB header edge, low Y)                     [boss]   |

The lid snaps on with one tab on each long side and can also be held by four M3 screws
in the corner bosses. Two holes with short guide cylinders sit over KEY and RST for the
push stick. The base/lid split is at the SMA centre height, as on the sensor box.
"""

from pathlib import Path

import cadquery as cq

OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- parameters (mm)
WALL = 2.0
FLOOR = 2.0
TOP = 2.0
R_CORNER = 6.0  # outer vertical corner radius
R_TOP = 6.0  # outer top edge radius (rounded top)
R_BOTTOM = 1.0
R_IN = 1.5  # inner vertical corner radius
FIT = 0.2  # clearance per side around each component

MARGIN = 2.0  # component to inner wall where the lid lip and snap tabs pass
TOP_CLEAR = 2.0  # tallest component to the lid's inner top

# Receiver board (same DX-PJ26 + LR30-A as the sensor). Low-Y edge = PB header side (KEY side).
BRD_L, BRD_W = 72.0, 30.0
BRD_H = 20.0  # stack height above the PCB bottom
PERF_SETBACK = 9.0  # perfboard/header block starts this far from the PCB's USB end (KEY/RST exposed)
HOLE_DX, HOLE_DY = 65.5, 24.5
POST_H, POST_D = 4.0, 5.0
PIN_D, PIN_H = 2.7, 2.5
SMA_Z = 17.0  # SMA centre above the PCB bottom
SMA_D = 6.35
SMA_LEN = 9.0  # beyond the PCB/carrier end  (MEASURE)
SMA_CLEAR = 0.25
SMA_FROM_EDGE = 12.5  # SMA centre from the PB header edge (user-confirmed)
SMA_END_GAP = 0.3
SMA_FACE_D, SMA_FACE_DEPTH = 11.0, 1.0
USB_W, USB_T = 8.94, 3.26  # USB-C receptacle, lying flat on the PCB
USB_PROTRUDE = 1.5  # beyond the PCB's USB end  (MEASURE)
USB_CLEAR = 0.4
USB_FROM_EDGE = 15.0  # receptacle centre from the PB header edge
USB_END_GAP = 0.3  # PCB's USB end to the inner wall
BTN_FROM_END = 3.8  # KEY/RST centres from the PCB's USB end (photo, homography on the mounting holes)
KEY_FROM_EDGE = 7.0  # from the PB header edge (photo)
RST_FROM_EDGE = 22.6  # from the PB header edge (photo)
BTN_H = 2.0  # tact switch top above the PCB top  (MEASURE)
BTN_SIZE = 3.6  # tact switch body (square envelope for the fit check)
# LEDs on the perfboard, seen through holes in the lid: (from the PCB's USB end, from the PB edge).
# From a top photo: homography on the four mounting holes, corrected for the perfboard's height
# (its pitch and its header-pin columns); about +-0.8 mm along the board, +-0.4 mm across.
LEDS = {"LED_A": (21.7, 25.4), "LED_B": (14.2, 8.3)}
LED_HOLE_D = 3.0

# Shelly UNI standing on its long edge beside the board (as in the photos): capacitor/connector
# side toward the board, MCU/u.FL side toward the wall, harness connector toward the USB wall.
SH_L, SH_H = 38.5, 20.7  # PCB without the harness connector; standing, 20.7 is its height
SH_T = 1.0  # PCB thickness
SH_IN = 7.0  # parts on the board side (150 uF capacitors)  (MEASURE)
SH_OUT = 2.0  # parts on the wall side (MCU, u.FL)  (MEASURE)
SH_CONN_L, SH_CONN_H, SH_CONN_T = 5.0, 17.0, 5.0  # harness connector: beyond the PCB end, height, depth  (MEASURE)
SH_WIRE_END = 8.0  # room for the thick output wires at the other end
PART_T = 1.2  # partition wall between the board and the Shelly (its parts reach the PCB edges)
PART_GAP = 1.2  # board envelope to the partition
SH_GAP = PART_GAP + PART_T + 0.2  # board envelope to Shelly envelope, partition in between

CABLE_A = (0, 0)  # harness slot in the USB wall, w x h; closed (was 6 x 14), 0 = none
CABLE_B = 0  # round hole for the output wires in the SMA wall; closed (was 7), 0 = none

BOSS_D = 7.0  # corner screw bosses (base) and pillars (lid)
SCREW_PILOT = 2.5  # M3 self-tapping into resin (2.2 for M2.5)
SCREW_CLEAR, SCREW_HEAD_D = 3.4, 6.2
SCREW_LEN, SCREW_ENGAGE = 12.0, 9.0  # M3 x 12; the head seat sits SCREW_LEN - SCREW_ENGAGE above the split

LIP_GAP, LIP_T, LIP_DEPTH = 0.15, 1.4, 3.0
TAB_W, TAB_LEN = 8.0, 11.0
HOOK_H, HOOK_DEPTH = 1.6, 0.5
WINDOW_Z_OFF = 0.5  # snap windows raised above the nominal hook position (sensor box print: hooks sat too high to lock)
TAB_SLOT = 1.0


GUIDE_D_IN, GUIDE_WALL, GUIDE_LEN = 3.0, 1.2, 6.0  # stick holes and the short guide cylinders under them
STICK_D = 2.5
STICK_HEAD_D, STICK_HEAD_H = 8.0, 3.0
STICK_PRESS = 0.6  # stick tip below the switch top when the head rests on the lid

# ---------------------------------------------------------------- derived layout
# Interior coordinates: (0,0,0) = inner corner of the USB end, low-Y side, floor top.
BRD_Y0 = BOSS_D + 0.3  # board lane starts past the corner bosses
BRD_Y1 = BRD_Y0 + BRD_W + 2 * FIT
PCB_Y0 = BRD_Y0 + FIT
BRD_X0 = USB_END_GAP
PCB_X0 = BRD_X0 + FIT
BRD_X1 = PCB_X0 + BRD_L + FIT
L_IN = BRD_X1 + SMA_END_GAP

SH_Y0 = BRD_Y1 + SH_GAP  # Shelly envelope, board side
SH_PCB_Y0 = SH_Y0 + FIT + SH_IN
SH_PCB_Y1 = SH_PCB_Y0 + SH_T
SH_Y1 = SH_PCB_Y1 + SH_OUT + FIT
W_IN = SH_Y1 + MARGIN
SH_X0 = BOSS_D + 0.2 + SH_CONN_L + FIT  # connector clears the USB-end boss
SH_X1 = SH_X0 + SH_L + 2 * FIT

H_IN = POST_H + BRD_H + TOP_CLEAR
SPLIT = POST_H + SMA_Z
SMA_Y = PCB_Y0 + SMA_FROM_EDGE
USB_Y, USB_Z = PCB_Y0 + USB_FROM_EDGE, POST_H + 1.6 + USB_T / 2
BTN_X = PCB_X0 + BTN_FROM_END
BTNS = {"KEY": PCB_Y0 + KEY_FROM_EDGE, "RST": PCB_Y0 + RST_FROM_EDGE}
BTN_TOP = POST_H + 1.6 + BTN_H
LED_XY = {name: (PCB_X0 + x, PCB_Y0 + y) for name, (x, y) in LEDS.items()}
HOLES = [
    (PCB_X0 + (BRD_L + sx * HOLE_DX) / 2, PCB_Y0 + (BRD_W + sy * HOLE_DY) / 2)
    for sx in (-1, 1)
    for sy in (-1, 1)
]
BOSSES = [(BOSS_D / 2, BOSS_D / 2), (L_IN - BOSS_D / 2, BOSS_D / 2),
          (BOSS_D / 2, W_IN - BOSS_D / 2), (L_IN - BOSS_D / 2, W_IN - BOSS_D / 2)]

L_OUT = L_IN + 2 * WALL
W_OUT = W_IN + 2 * WALL
HB = FLOOR + SPLIT
HO = FLOOR + H_IN + TOP
CAP = WALL + LIP_GAP + LIP_T
TAB_X = (L_IN / 2,)
STICK_LEN = HO - (FLOOR + BTN_TOP - STICK_PRESS)  # shaft below the head
SMA_OUT = SMA_LEN - FIT - SMA_END_GAP - (WALL - SMA_FACE_DEPTH)

assert HO - HB > R_TOP, "lid too short for R_TOP"
assert SH_X1 + SH_WIRE_END < L_IN - BOSS_D, "Shelly + wires run into the SMA-end bosses"
assert MARGIN >= LIP_GAP + LIP_T + 0.3, "Shelly would touch the lip and snap tabs"


# ---------------------------------------------------------------- helpers
def box(x, y, z, lx, ly, lz):
    """Box in interior coordinates."""
    return cq.Workplane("XY").box(lx, ly, lz, centered=False).translate((WALL + x, WALL + y, FLOOR + z))


def abox(x, y, z, lx, ly, lz):
    """Box in absolute coordinates."""
    return cq.Workplane("XY").box(lx, ly, lz, centered=False).translate((x, y, z))


def rrect(x, y, z, lx, ly, lz, r):
    """Absolute box with rounded vertical edges."""
    return abox(x, y, z, lx, ly, lz).edges("|Z").fillet(r)


def cyl(x, y, z, d, h):
    """Vertical cylinder in interior coordinates, base at z."""
    return cq.Workplane("XY", origin=(WALL + x, WALL + y, FLOOR + z)).circle(d / 2).extrude(h)


def end_cut(x0, y, z, w, h, depth, r):
    """Rounded rectangle cut through an end wall, starting at x0 (absolute) and going +X."""
    return cq.Workplane("YZ", origin=(x0, y, z)).rect(w, h).extrude(depth).edges("|X").fillet(r)


def hook(x_center, outward):
    """Hook profile on a tab; outward = -1 (low-Y wall) or +1 (high-Y wall)."""
    zb = HB - TAB_LEN
    if outward < 0:
        y_face, y_tip = WALL + LIP_GAP, WALL - HOOK_DEPTH
    else:
        y_face, y_tip = W_OUT - WALL - LIP_GAP, W_OUT - WALL + HOOK_DEPTH
    lead = abs(y_face - y_tip)
    pts = [(y_face, zb), (y_tip, zb + lead), (y_tip, zb + HOOK_H), (y_face, zb + HOOK_H)]
    return cq.Workplane("YZ", origin=(x_center - TAB_W / 2, 0, 0)).polyline(pts).close().extrude(TAB_W)


def tab_y(outward):
    return WALL + LIP_GAP if outward < 0 else W_OUT - WALL - LIP_GAP - LIP_T


def sma_cuts():
    r = SMA_D / 2 + SMA_CLEAR
    y, z = WALL + SMA_Y, HB
    notch = cq.Workplane("YZ", origin=(L_OUT - WALL - 1, y, z)).circle(r).extrude(WALL + 2)
    face = cq.Workplane("YZ", origin=(L_OUT - SMA_FACE_DEPTH, y, z)).circle(SMA_FACE_D / 2).extrude(SMA_FACE_DEPTH + 1)
    return notch.union(face)


# ---------------------------------------------------------------- base
def make_base():
    base = rrect(0, 0, 0, L_OUT, W_OUT, HB, R_CORNER).faces("<Z").edges().fillet(R_BOTTOM)
    base = base.cut(rrect(WALL, WALL, FLOOR, L_IN, W_IN, HB, R_IN))

    # Corner screw bosses up to the split, pilot holes for M3 self-tapping screws.
    for x, y in BOSSES:
        base = base.union(cyl(x, y, 0, BOSS_D, SPLIT))
        base = base.cut(cyl(x, y, SPLIT - SCREW_ENGAGE - 2, SCREW_PILOT, SCREW_ENGAGE + 3))

    # Board: posts with locating pins through its four mounting holes.
    for x, y in HOLES:
        base = base.union(cyl(x, y, 0, POST_D, POST_H))
        pin = cyl(x, y, POST_H, PIN_D, PIN_H).faces(">Z").edges().chamfer(0.4)
        base = base.union(pin)

    # Shelly UNI on edge in its own lane: a partition along its length separates it from the
    # board (open at both ends for the wires). Its parts reach the PCB edges, so nothing grips it.
    base = base.union(box(SH_X0, BRD_Y1 + PART_GAP, 0, SH_X1 - SH_X0, PART_T, SPLIT))

    # USB-C opening (+ counterbore so a plug overmold reaches the receptacle face).
    usb_y, usb_z = WALL + USB_Y, FLOOR + USB_Z
    w, h = USB_W + 2 * USB_CLEAR, USB_T + 2 * USB_CLEAR
    base = base.cut(end_cut(-1, usb_y, usb_z, w, h, WALL + 2, h / 2 - 0.05))
    cb_depth = WALL - (USB_PROTRUDE - PCB_X0)
    if cb_depth > 0:
        base = base.cut(end_cut(-1, usb_y, usb_z, 12.5, 7.0, 1 + cb_depth, 3.0))

    # Cable exits for the Shelly: harness slot A (USB wall), output wires hole B (SMA wall).
    # Slot A sits in front of the connector, but no closer to the high-Y wall than the corner boss.
    sh_yc = WALL + min(SH_PCB_Y0 - SH_CONN_T / 2, W_IN - BOSS_D - CABLE_A[0] / 2 - 0.2)
    sh_zc = FLOOR + SH_H / 2
    if CABLE_A[0] > 0:
        base = base.cut(end_cut(-1, sh_yc, sh_zc, CABLE_A[0], CABLE_A[1], WALL + 2, min(CABLE_A) / 2 - 0.05))
    if CABLE_B > 0:
        base = base.cut(cq.Workplane("YZ", origin=(L_OUT - WALL - 1, sh_yc, sh_zc)).circle(CABLE_B / 2).extrude(WALL + 2))

    # Snap windows (also release holes: push the hook in with a pin).
    zb = HB - TAB_LEN
    for xc in TAB_X:
        x = WALL + xc - TAB_W / 2 - 0.5
        for y in (-1, W_OUT - WALL - 0.01):
            base = base.cut(abox(x, y, zb - 0.3 + WINDOW_Z_OFF, TAB_W + 1, WALL + 1.01, HOOK_H + 0.4))

    return base.cut(sma_cuts())


# ---------------------------------------------------------------- lid
def make_lid():
    lid = rrect(0, 0, HB, L_OUT, W_OUT, HO - HB, R_CORNER).faces(">Z").edges().fillet(R_TOP)
    cav_r = R_CORNER - CAP
    cavity = (
        rrect(CAP, CAP, HB - 1, L_OUT - 2 * CAP, W_OUT - 2 * CAP, HO - TOP - HB + 1, cav_r)
        .faces(">Z")
        .edges()
        .fillet(3.0)
    )
    lid = lid.cut(cavity)

    # Alignment lip below the split, cleared around the base's corner bosses.
    lip_out = rrect(WALL + LIP_GAP, WALL + LIP_GAP, HB - LIP_DEPTH, L_IN - 2 * LIP_GAP, W_IN - 2 * LIP_GAP,
                    LIP_DEPTH, R_IN - LIP_GAP)
    lip_in = rrect(CAP, CAP, HB - LIP_DEPTH - 1, L_OUT - 2 * CAP, W_OUT - 2 * CAP, LIP_DEPTH + 2, cav_r)
    lip = lip_out.cut(lip_in)
    for x, y in BOSSES:
        lip = lip.cut(cyl(x, y, SPLIT - LIP_DEPTH - 1, BOSS_D + 0.6, LIP_DEPTH + 1))
    lid = lid.union(lip)

    # Snap tabs, one per long side, with slits so they flex independently of the lip.
    for xc in TAB_X:
        x = WALL + xc
        for side in (-1, 1):
            y = tab_y(side)
            for sx in (x - TAB_W / 2 - TAB_SLOT, x + TAB_W / 2):
                lid = lid.cut(abox(sx, y - 0.5, HB - LIP_DEPTH - 1, TAB_SLOT, LIP_T + 1, LIP_DEPTH + 1))
            lid = lid.union(abox(x - TAB_W / 2, y, HB - TAB_LEN, TAB_W, LIP_T, TAB_LEN))
            lid = lid.union(hook(x, side))

    # SMA end of the board lane: no lip, thickening or inner top fillet (the stack reaches the wall).
    end_l, z0 = CAP - WALL + 8.0, HB - LIP_DEPTH - 1
    relief = rrect(L_OUT - WALL - end_l, WALL + BRD_Y0 - 0.2, z0, end_l, BRD_Y1 - BRD_Y0 + 0.4, HO - TOP - z0, 0.3)
    lid = lid.cut(relief.faces(">Z").edges().fillet(3.0))

    # Corner pillars over the bosses: screw clearance hole and a counterbore for the head.
    seat = HB + SCREW_LEN - SCREW_ENGAGE
    for x, y in BOSSES:
        lid = lid.union(cyl(x, y, SPLIT, BOSS_D, H_IN - SPLIT + 0.5))
        lid = lid.cut(cyl(x, y, SPLIT - 1, SCREW_CLEAR, H_IN - SPLIT + TOP + 2))
        lid = lid.cut(cq.Workplane("XY", origin=(WALL + x, WALL + y, seat)).circle(SCREW_HEAD_D / 2).extrude(HO - seat + 1))

    lid = lid.cut(sma_cuts())

    # Holes over the two perfboard LEDs, with a small chamfer on top.
    for x, y in LED_XY.values():
        lid = lid.cut(cyl(x, y, H_IN - 1, LED_HOLE_D, TOP + 2))
        lid = lid.cut(cq.Workplane("XY", origin=(WALL + x, WALL + y, HO - 0.5)).circle(LED_HOLE_D / 2)
                      .workplane(offset=0.51).circle(LED_HOLE_D / 2 + 0.5).loft())

    # Push-stick holes over KEY and RST, each with a short guide cylinder under the lid.
    for y in BTNS.values():
        lid = lid.union(cyl(BTN_X, y, H_IN - GUIDE_LEN, GUIDE_D_IN + 2 * GUIDE_WALL, GUIDE_LEN + 0.5))
        lid = lid.cut(cyl(BTN_X, y, H_IN - GUIDE_LEN - 1, GUIDE_D_IN, GUIDE_LEN + TOP + 2))
        lid = lid.cut(cq.Workplane("XY", origin=(WALL + BTN_X, WALL + y, HO - 0.6)).circle(GUIDE_D_IN / 2)
                      .workplane(offset=0.61).circle(GUIDE_D_IN / 2 + 0.6).loft())
    return lid


# ---------------------------------------------------------------- push stick (printed lying down)
def make_stick():
    head = cq.Workplane("XY").circle(STICK_HEAD_D / 2).extrude(STICK_HEAD_H).edges().fillet(0.8)
    shaft = cq.Workplane("XY").circle(STICK_D / 2).extrude(-STICK_LEN).faces("<Z").edges().fillet(0.6)
    return head.union(shaft)


# ---------------------------------------------------------------- dummy components (fit check only)
def make_dummies():
    d = {}
    d["pcb"] = box(PCB_X0, PCB_Y0, POST_H, BRD_L, BRD_W, 1.6)
    for x, y in HOLES:
        d["pcb"] = d["pcb"].cut(cyl(x, y, 0, PIN_D + 0.4, 20))
    d["stack"] = box(PCB_X0 + PERF_SETBACK, PCB_Y0, POST_H + 1.6, BRD_L - PERF_SETBACK, BRD_W, BRD_H - 1.6)
    for x, y in HOLES:  # pin tips poke 0.9 mm above the PCB beside the carrier, not into it
        d["stack"] = d["stack"].cut(cyl(x, y, 0, PIN_D + 0.4, POST_H + PIN_H + 0.1))
    d["usb"] = end_cut(WALL + PCB_X0 - USB_PROTRUDE, WALL + USB_Y, FLOOR + USB_Z, USB_W, USB_T, 7.3, USB_T / 2 - 0.01)
    for name, y in BTNS.items():
        d[name] = box(BTN_X - BTN_SIZE / 2, y - BTN_SIZE / 2, POST_H + 1.6, BTN_SIZE, BTN_SIZE, BTN_H)
    d["sma"] = cq.Workplane("YZ", origin=(WALL + BRD_X1 - FIT, WALL + SMA_Y, HB)).circle(SMA_D / 2).extrude(SMA_LEN)
    sx = SH_X0 + FIT
    # Parts on both faces right up to the PCB edges.
    d["shelly"] = (
        box(sx, SH_PCB_Y0 - SH_IN, 0, SH_L, SH_IN + SH_T + SH_OUT, SH_H)
        .union(box(sx - SH_CONN_L, SH_PCB_Y0 - SH_CONN_T, (SH_H - SH_CONN_H) / 2, SH_CONN_L, SH_CONN_T, SH_CONN_H))
    )
    # Stick inserted, head on the lid: may only touch the switch.
    for name, y in BTNS.items():
        d[f"stick_{name}"] = make_stick().translate((WALL + BTN_X, WALL + y, HO))
    return d


def overlap(a, b):
    r = a.intersect(b)
    return r.val().Volume() if r.vals() else 0.0


def main():
    base, lid, stick = make_base(), make_lid(), make_stick()
    dummies = make_dummies()

    for name, part in (("base", base), ("lid", lid)):
        cq.exporters.export(part, str(OUT / f"receiver_box_{name}.step"))
        cq.exporters.export(part, str(OUT / f"receiver_box_{name}.stl"), tolerance=0.02, angularTolerance=0.1)
    flat_stick = stick.rotate((0, 0, 0), (1, 0, 0), 90)
    cq.exporters.export(flat_stick, str(OUT / "receiver_box_stick.step"))
    cq.exporters.export(flat_stick, str(OUT / "receiver_box_stick.stl"), tolerance=0.01, angularTolerance=0.1)

    asm = cq.Assembly(name="receiver_box")
    asm.add(base, name="base", color=cq.Color(0.85, 0.85, 0.82))
    asm.add(lid, name="lid", color=cq.Color(0.55, 0.7, 0.9, 0.6))
    for name, shape in dummies.items():
        asm.add(shape, name=f"ref_{name}", color=cq.Color(0.9, 0.4, 0.2))
    asm.save(str(OUT / "receiver_box_assembly.step"))

    # Fit check: no component may overlap the printed parts; the sticks may only touch their switch.
    for name, shape in dummies.items():
        for part_name, part in (("base", base), ("lid", lid)):
            v = overlap(shape, part)
            if v > 0.01:  # dummies are sharp boxes; ignore corner slivers
                print(f"OVERLAP {name} x {part_name}: {v:.3f} mm3")
    for name in BTNS:
        for other, shape in dummies.items():
            if other.startswith("stick") or other == name:
                continue
            v = overlap(dummies[f"stick_{name}"], shape)
            if v > 0.01:
                print(f"OVERLAP stick_{name} x {other}: {v:.3f} mm3")
        press = overlap(dummies[f"stick_{name}"], dummies[name])
        print(f"stick on {name}: presses {STICK_PRESS} mm into the switch top ({press:.2f} mm3 overlap)")
    v = overlap(base, lid)
    if v > 1e-3:
        print(f"OVERLAP base x lid: {v:.3f} mm3")

    print(f"outside {L_OUT:.1f} x {W_OUT:.1f} x {HO:.1f} mm (base {HB:.1f}, lid {HO - HB:.1f})")
    print(f"inside  {L_IN:.1f} x {W_IN:.1f} x {H_IN:.1f} mm")
    print(f"SMA thread outside the spot face {SMA_OUT:.1f} mm; stick shaft {STICK_LEN:.1f} mm")
    print(f"screws: 4 x M3 x {SCREW_LEN:.0f} (pilot {SCREW_PILOT} mm, {SCREW_ENGAGE:.0f} mm into the base)")


if __name__ == "__main__":
    main()
