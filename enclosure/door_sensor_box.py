"""Snap-fit enclosure for the LoRa door sensor (resin print).

Builds base + lid with CadQuery and exports STEP (for Fusion 360) and STL (for slicing).
Every size is a parameter below; change one and rerun:

    cqenv\\Scripts\\python.exe -I enclosure/door_sensor_box.py

Layout (top view, X = length, Y = width, origin at the outside corner of the USB end):

    USB wall                                                        SMA wall
    | charger on edge | reed board on edge |   (both against the low-Y, PB-side wall)
    | battery holder 85x25           | gap | DX-PJ26 + LR30-A + perfboard |-> SMA

The base/lid split is at the SMA centre height: the SMA drops into a half-round notch
in the base, the lid closes the other half, and the thread sticks out of the end wall.
The lid top edges are rounded (R_TOP); it snaps on with two tabs per long side. The long
walls have vertical stiffening ribs inside.
"""

from pathlib import Path

import cadquery as cq

OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------- parameters (mm)
WALL = 2.0  # side walls
FLOOR = 2.0
TOP = 2.0  # lid top thickness
R_CORNER = 6.0  # outer vertical corner radius
R_IN = 1.5  # inner vertical corner radius (small, so the charger fits into the USB-end corner)
R_TOP = 6.0  # outer top edge radius (rounded top); must stay below the lid height
R_BOTTOM = 1.0  # outer bottom edge radius
FIT = 0.2  # clearance per side around each component

MARGIN = 2.0  # component to inner wall where the lid lip and snap tabs pass
TOP_CLEAR = 2.0  # tallest component to the lid's inner top

CHG_L, CHG_H, CHG_T = 28.26, 17.3, 1.6  # TP4056 board on its long edge beside the battery, parts toward the wall
# CHG_L includes the two ears at the rear corners (measured); the middle of the rear edge is ~1.3 mm shorter.
CHG_BACK = 1.0  # solder tails behind the PCB (battery side)
CHG_STOP_T = 2.0  # rear stop plate behind the charger, toward the box's middle (1.2 until it broke, print 2)
USB_GAP = 0.9  # USB-C face to the lid lip/tab zone
USB_W, USB_T = 8.94, 3.26  # USB-C receptacle
USB_PROTRUDE = 1.5  # receptacle front beyond the PCB edge  (MEASURE)
USB_CLEAR = 0.4  # across the receptacle
USB_CLEAR_Z = 0.6  # along it
USB_Z_OFF = 1.2  # receptacle centre above the PCB's mid-height (first print: hole opened 1.2 mm up)

BATT_L, BATT_W, BATT_H = 85.0, 25.0, 27.5  # 21700 holder; H = cell top (print 1: 26 mm; print 2 still pressed, +1)
SCREW_BOSS_D = 7.0  # centre screw between the battery holder and the board
SCREW_PILOT = 2.5  # M3 self-tapping into resin (2.2 for M2.5)
SCREW_CLEAR, SCREW_HEAD_D = 3.4, 6.2
SCREW_LEN, SCREW_ENGAGE = 12.0, 9.0  # M3 x 12, 9 mm into the base boss
LID_PILLAR = 4.0  # lid pillar under the screw head, down from the lid's inner top
MID_GAP = SCREW_BOSS_D + 1.4  # battery holder to board: the boss plus room for wires around it

BRD_L, BRD_W = 72.0, 30.0  # DX-PJ26 PCB
BRD_H = 20.0  # stack height above the PCB bottom (perfboard on top)
HOLE_DX, HOLE_DY = 65.5, 24.5  # mounting hole centres, centred on the PCB
POST_H, POST_D = 4.0, 5.0  # printed posts under the holes (clear the header solder tails)
PIN_D, PIN_H = 2.7, 2.5  # locating pins on the posts (M3 holes); height above the post
CARRIER_OVERHANG = 0.0  # LR30-A carrier beyond the PCB at the SMA end (flush in the photos)
PERF_OVERHANG = 3.0  # perfboard beyond the PCB at the battery end  (MEASURE)
SMA_Z = 17.0  # SMA centre above the MCU PCB bottom
SMA_D = 6.35  # SMA thread (1/4-36)
SMA_LEN = 9.0  # SMA length beyond the carrier edge  (MEASURE)
SMA_CLEAR = 0.25
SMA_FROM_EDGE = 12.5  # SMA centre from the PB header edge = low-Y edge (user-confirmed)
SMA_END_GAP = 0.3  # board stack end to the SMA wall
SMA_FACE_D, SMA_FACE_DEPTH = 11.0, 1.0  # outside spot face: thinner wall, more thread outside

REED_L, REED_H, REED_T = 33.0, 10.0, 5.0  # reed board standing on edge (length from photo)  (MEASURE)
REED_GAP = 1.0  # charger's rear stop to the reed slot (the slot runs along the low-Y wall)
REED_WALL_T = 2.0  # wall behind the reed board, toward the battery
REED_WALL_H = CHG_H - 1.0  # as tall as the charger's stop plate (6 mm until print 2)

LIP_GAP, LIP_T, LIP_DEPTH = 0.15, 1.4, 3.0  # lid alignment lip
TAB_W, TAB_LEN = 8.0, 11.0  # snap tabs (cantilever below the split)
HOOK_H, HOOK_DEPTH = 1.6, 0.8  # hook height and reach into the wall window (0.5 until print 2)
WINDOW_Z_OFF = 0.5  # snap windows raised above the nominal hook position (hooks sat too high to lock in print 1)
TAB_SLOT = 1.0  # slit between tab and lip
# Tab centres from the inner USB wall, (x, side): low-Y over the charger, high-Y over the board, and
# one per side in the battery/board gap (added below as TABS): where a root gusset has room.
TAB_LOW_X, TAB_HIGH_X = 22.0, 140.0
GUSSET_W, GUSSET_D = 1.6, 2.0  # rib inside each tab, from the lid's inner top down to
GUSSET_TO = 0.5  # this fraction of the tab length, tapering to nothing

RIB_T, FENCE_H = 1.2, 3.0  # locating ribs on the floor
WALL_RIB_W, WALL_RIB_D = 3.0, 2.0  # stiffening ribs on the inside of the long walls (2 x 1.2 until print 2)
WALL_RIB_X = (50.0, 80.0, 110.0, 160.0)  # rib centres (low-Y ones at the reed slot are skipped)
WALL_RIB_UP = 4.0  # ribs continue above the base edge into slots in the lid, which keeps the walls in
HOLDDOWN_GAP = 0.5  # lid ribs above the battery holder and the perfboard's blank rear strip
SEP_SLOT_L, SEP_SLOT_W = 10.0, 2.0  # lid slot for a battery isolation tab, across the cell (1.5 wide at first)
HOLDER_END_T = 3.5  # holder end wall + contact plate at the cell's + end (board side); 2.0 + 1.5 per user

# ---------------------------------------------------------------- derived layout
# Interior coordinates: (0,0,0) = inner corner of the USB end, low-Y side, floor top.
BRD_ENV_W = BRD_W + 2 * FIT
BRD_Y0 = MARGIN
BRD_Y1 = BRD_Y0 + BRD_ENV_W

CHG_X1 = CHG_L + FIT  # PCB front edge touches the inner wall, USB-C goes into the wall
USB_Y, USB_Z = MARGIN + USB_GAP + USB_T / 2, CHG_H / 2 + USB_Z_OFF
CHG_Y0 = USB_Y + USB_T / 2  # PCB face with the parts and the USB-C (low-Y wall side)
CHG_Y1 = CHG_Y0 + CHG_T  # PCB back, facing the battery

BATT_X0 = MARGIN + 1.0  # clear of the lid's rounded inner corner at the top
BATT_X1 = BATT_X0 + BATT_L + 2 * FIT
BATT_Y0 = CHG_Y1 + CHG_BACK + 0.2 + RIB_T  # past the charger's solder tails and the corner stops
BATT_Y1 = BATT_Y0 + BATT_W + 2 * FIT
W_IN = max(BRD_Y1, BATT_Y1) + MARGIN

# Reed board on edge against the low-Y (PB side) wall, right after the charger, beside the battery.
REED_X0 = CHG_X1 + CHG_STOP_T + REED_GAP
REED_X1 = REED_X0 + REED_L + 2 * FIT
REED_Y1 = REED_T + 2 * FIT

BRD_X0 = BATT_X1 + MID_GAP  # board stack envelope: perfboard overhang + PCB + carrier overhang
BRD_X1 = BRD_X0 + PERF_OVERHANG + BRD_L + CARRIER_OVERHANG + 2 * FIT
L_IN = BRD_X1 + SMA_END_GAP
PCB_X0 = BRD_X0 + FIT + PERF_OVERHANG
PCB_Y0 = BRD_Y0 + FIT
HOLES = [
    (PCB_X0 + (BRD_L + sx * HOLE_DX) / 2, PCB_Y0 + (BRD_W + sy * HOLE_DY) / 2)
    for sx in (-1, 1)
    for sy in (-1, 1)
]

H_IN = max(BATT_H, POST_H + BRD_H) + TOP_CLEAR
SPLIT = POST_H + SMA_Z  # interior height of the base/lid joint
SMA_Y = BRD_Y0 + FIT + SMA_FROM_EDGE

L_OUT = L_IN + 2 * WALL
W_OUT = W_IN + 2 * WALL
HB = FLOOR + SPLIT  # base outer height
HO = FLOOR + H_IN + TOP  # overall height
CAP = WALL + LIP_GAP + LIP_T  # lid side thickness above the split
SMA_OUT = SMA_LEN - FIT - SMA_END_GAP - (WALL - SMA_FACE_DEPTH)  # thread past the spot face
SCREW_X, SCREW_Y = BATT_X1 + MID_GAP / 2, W_IN / 2
TABS = ((TAB_LOW_X, -1), (SCREW_X, -1), (SCREW_X, 1), (TAB_HIGH_X, 1))
SEP_X = BATT_X1 - FIT - HOLDER_END_T  # where the cell's + end meets the holder's contact
SEP_Y = BATT_Y0 + FIT + BATT_W / 2
SCREW_MEET = H_IN - LID_PILLAR  # where the base boss and the lid pillar meet (interior z)

assert HO - HB > R_TOP, "lid too short for R_TOP"
assert MARGIN >= LIP_GAP + LIP_T + 0.3, "lip would touch components"
assert W_IN - BATT_Y1 >= MARGIN, "battery holder too close to the wall"
assert CHG_H < SPLIT - LIP_DEPTH, "charger would hit the lid lip"
assert REED_Y1 + REED_WALL_T < BATT_Y0 - RIB_T and REED_X1 < BATT_X1, "reed slot runs into the battery stops"
assert all(not REED_X0 - TAB_W / 2 - 1 < t < REED_X1 + TAB_W / 2 + 1 for t, s in TABS if s < 0), "tab over the reed board"
assert all(abs(r - t) > (WALL_RIB_W + TAB_W) / 2 + 2 for r in WALL_RIB_X for t, s in TABS), "wall rib on a tab"


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


def end_cut(x0, y, z, w, h, depth, r):
    """Rounded rectangle cut through an end wall, starting at x0 and going +X."""
    return cq.Workplane("YZ", origin=(x0, y, z)).rect(w, h).extrude(depth).edges("|X").fillet(r)


def hook(x_center, outward):
    """Hook profile on a tab; outward = -1 (low-Y wall) or +1 (high-Y wall)."""
    zb = HB - TAB_LEN
    if outward < 0:
        y_face, y_tip = WALL + LIP_GAP, WALL - HOOK_DEPTH
    else:
        y_face, y_tip = W_OUT - WALL - LIP_GAP, W_OUT - WALL + HOOK_DEPTH
    lead = abs(y_face - y_tip)  # 45 degree lead-in on the bottom
    pts = [(y_face, zb), (y_tip, zb + lead), (y_tip, zb + HOOK_H), (y_face, zb + HOOK_H)]
    x0 = x_center - TAB_W / 2
    return cq.Workplane("YZ", origin=(x0, 0, 0)).polyline(pts).close().extrude(TAB_W)


def gusset(x_center, outward):
    """Rib inside a tab: full depth from the lid's inner top to the split, then tapering to the tab."""
    top, tip = HO - TOP + 0.5, HB - TAB_LEN * GUSSET_TO
    yi = CAP if outward < 0 else W_OUT - CAP  # tab's inner face
    yo = yi - outward * GUSSET_D
    pts = [(yi, top), (yo, top), (yo, HB), (yi, tip)]
    return cq.Workplane("YZ", origin=(x_center - GUSSET_W / 2, 0, 0)).polyline(pts).close().extrude(GUSSET_W)


def wall_rib(x_center, outward):
    """Wall rib from the floor to WALL_RIB_UP above the split, chamfered on the wall side at the top
    so it slides into its slot in the lid."""
    top = HB + WALL_RIB_UP
    yw = WALL if outward < 0 else W_OUT - WALL  # inner face of the wall
    yi = yw - outward * WALL_RIB_D
    c = 0.6
    pts = [(yw, FLOOR - 0.01), (yi, FLOOR - 0.01), (yi, top), (yw - outward * c, top), (yw, top - c)]
    return cq.Workplane("YZ", origin=(WALL + x_center - WALL_RIB_W / 2, 0, 0)).polyline(pts).close().extrude(WALL_RIB_W)


def wall_rib_sides(x):
    """Long walls that get a rib at x (none on the low-Y wall along the reed slot)."""
    skip_low = REED_X0 - RIB_T - WALL_RIB_W < x < REED_X1 + RIB_T + WALL_RIB_W
    return [side for side in (-1, 1) if not (side < 0 and skip_low)]


def tab_y(outward):
    return WALL + LIP_GAP if outward < 0 else W_OUT - WALL - LIP_GAP - LIP_T


def sma_cuts():
    """Notch for the SMA thread plus the outside spot face, shared by base and lid."""
    r = SMA_D / 2 + SMA_CLEAR
    y, z = WALL + SMA_Y, HB
    notch = cq.Workplane("YZ", origin=(L_OUT - WALL - 1, y, z)).circle(r).extrude(WALL + 2)
    face = cq.Workplane("YZ", origin=(L_OUT - SMA_FACE_DEPTH, y, z)).circle(SMA_FACE_D / 2).extrude(SMA_FACE_DEPTH + 1)
    return notch.union(face)


# ---------------------------------------------------------------- base
def make_base():
    base = rrect(0, 0, 0, L_OUT, W_OUT, HB, R_CORNER).faces("<Z").edges().fillet(R_BOTTOM)
    base = base.cut(rrect(WALL, WALL, FLOOR, L_IN, W_IN, HB, R_IN))

    # Charger on its long edge beside the battery, parts toward the wall. Nothing touches
    # the parts side (a floor rib there lifted the board in the first print): a rib on the
    # flat back, and a plate behind the rear edge that both ears rest against and that takes
    # the plug force. The wire pads (B+/B-/OUT+/OUT-) sit right at that edge, through-hole,
    # so nothing reaches onto either face there.
    base = base.union(box(11.0, CHG_Y1 + 0.15, 0, 5.0, RIB_T, 8.0))
    base = base.union(box(CHG_X1, CHG_Y0 - 0.5, 0, CHG_STOP_T, CHG_T + 2.0, CHG_H - 1.0))

    # USB-C opening (long side vertical), plus a counterbore so a plug overmold
    # reaches the receptacle face.
    usb_y, usb_z = WALL + USB_Y, FLOOR + USB_Z
    w = USB_T + 2 * USB_CLEAR
    base = base.cut(end_cut(-1, usb_y, usb_z, w, USB_W + 2 * USB_CLEAR_Z, WALL + 2, w / 2 - 0.05))
    cb_depth = WALL - USB_PROTRUDE
    if cb_depth > 0:
        base = base.cut(end_cut(-1, usb_y, usb_z, 7.0, 12.5 + 2 * (USB_CLEAR_Z - USB_CLEAR), 1 + cb_depth, 3.0))

    # Battery holder: four L-shaped corner stops (wires can leave at the ends).
    leg = 8.0
    for cx, sx in ((BATT_X0, -1), (BATT_X1, 1)):
        for cy, sy in ((BATT_Y0, -1), (BATT_Y1, 1)):
            x_out = cx if sx > 0 else cx - RIB_T
            y_out = cy if sy > 0 else cy - RIB_T
            x_leg = cx - leg if sx > 0 else cx
            y_leg = cy - leg if sy > 0 else cy
            base = base.union(box(x_out, y_leg, 0, RIB_T, leg, FENCE_H))
            base = base.union(box(x_leg, y_out, 0, leg, RIB_T, FENCE_H))

    # Board: posts with locating pins through its four mounting holes.
    for x, y in HOLES:
        post = cq.Workplane("XY", origin=(WALL + x, WALL + y, FLOOR)).circle(POST_D / 2).extrude(POST_H)
        pin = (
            cq.Workplane("XY", origin=(WALL + x, WALL + y, FLOOR + POST_H))
            .circle(PIN_D / 2)
            .extrude(PIN_H)
            .faces(">Z")
            .edges()
            .chamfer(0.4)
        )
        base = base.union(post).union(pin)

    # Reed board slot against the low-Y wall (magnet acts through that wall).
    base = base.union(box(REED_X0 - RIB_T, REED_Y1, 0, REED_X1 - REED_X0 + 2 * RIB_T, REED_WALL_T, REED_WALL_H))
    for x in (REED_X0 - RIB_T, REED_X1):
        base = base.union(box(x, 0, 0, RIB_T, REED_Y1, 6.0))

    # Stiffening ribs on the long walls, clear of the tabs and the reed board. They rise above the
    # base edge into slots in the lid, where the lid's outer wall stops the base walls bowing out.
    for x in WALL_RIB_X:
        for side in wall_rib_sides(x):
            base = base.union(wall_rib(x, side))

    # Snap windows (also release holes: push the hook in with a pin).
    zb = HB - TAB_LEN
    for xc, side in TABS:
        x = WALL + xc - TAB_W / 2 - 0.5
        y = -1 if side < 0 else W_OUT - WALL - 0.01
        base = base.cut(abox(x, y, zb - 0.3 + WINDOW_Z_OFF, TAB_W + 1, WALL + 1.01, HOOK_H + 0.4))

    # Centre screw boss between the battery holder and the board, up to the lid pillar
    # (0.1 mm short, so the screw pulls the lid down onto the walls).
    boss = cq.Workplane("XY", origin=(WALL + SCREW_X, WALL + SCREW_Y, FLOOR)).circle(SCREW_BOSS_D / 2).extrude(SCREW_MEET - 0.1)
    pilot = (cq.Workplane("XY", origin=(WALL + SCREW_X, WALL + SCREW_Y, FLOOR + SCREW_MEET - SCREW_ENGAGE - 2))
             .circle(SCREW_PILOT / 2).extrude(SCREW_ENGAGE + 3))
    base = base.union(boss).cut(pilot)

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

    # Alignment lip below the split.
    lip_out = rrect(
        WALL + LIP_GAP, WALL + LIP_GAP, HB - LIP_DEPTH,
        L_IN - 2 * LIP_GAP, W_IN - 2 * LIP_GAP, LIP_DEPTH, R_IN - LIP_GAP,
    )
    lip_in = rrect(CAP, CAP, HB - LIP_DEPTH - 1, L_OUT - 2 * CAP, W_OUT - 2 * CAP, LIP_DEPTH + 2, cav_r)
    lid = lid.union(lip_out.cut(lip_in))

    # Snap tabs with slits so they flex independently of the lip, each with a root gusset.
    for xc, side in TABS:
        x = WALL + xc
        y = tab_y(side)
        for sx in (x - TAB_W / 2 - TAB_SLOT, x + TAB_W / 2):
            lid = lid.cut(abox(sx, y - 0.5, HB - LIP_DEPTH - 1, TAB_SLOT, LIP_T + 1, LIP_DEPTH + 1))
        lid = lid.union(abox(x - TAB_W / 2, y, HB - TAB_LEN, TAB_W, LIP_T, TAB_LEN))
        lid = lid.union(hook(x, side))
        lid = lid.union(gusset(x, side))

    # Slots for the wall ribs, through the lip and the lid's inner thickening, up to the rib tops.
    for x in WALL_RIB_X:
        for side in wall_rib_sides(x):
            depth = max(WALL_RIB_D, CAP - WALL) + 0.2
            y0 = WALL if side < 0 else W_OUT - WALL - depth
            lid = lid.cut(abox(WALL + x - WALL_RIB_W / 2 - 0.2, y0, HB - LIP_DEPTH - 1, WALL_RIB_W + 0.4,
                               depth, LIP_DEPTH + 1 + WALL_RIB_UP + 0.3))

    # SMA end: no lip, thickening or inner top fillet; the board stack and SMA body
    # reach right up to the wall.
    # Rounded like the outside so it can't break through the curved corners.
    end_l, z0 = CAP - WALL + 8.0, HB - LIP_DEPTH - 1
    end_relief = rrect(L_OUT - WALL - end_l, WALL, z0, end_l, W_IN, HO - TOP - z0, R_CORNER - WALL)
    lid = lid.cut(end_relief.faces(">Z").edges().fillet(3.0))
    lid = lid.cut(sma_cuts())

    # Hold-down ribs over the battery holder.
    z_rib = FLOOR + BATT_H + HOLDDOWN_GAP
    for x in (BATT_X0 + 18, BATT_X1 - 18):
        lid = lid.union(abox(WALL + x - 1.5, WALL + BATT_Y0, z_rib, 3.0, BATT_Y1 - BATT_Y0, HO - TOP - z_rib + 0.5))

    # Hold-down rib on the perfboard's blank rear strip, so the board can't lift off its pins
    # (the SMA end is held by the lid's SMA notch).
    z_rib = FLOOR + POST_H + BRD_H + HOLDDOWN_GAP
    x = WALL + BRD_X0 + FIT + 0.5
    lid = lid.union(abox(x, WALL + BRD_Y0, z_rib, 2.5, BRD_Y1 - BRD_Y0, HO - TOP - z_rib + 0.5))

    # Slot over the cell's + contact: an isolation tab pushed in from outside disconnects the battery.
    lid = lid.cut(abox(WALL + SEP_X - SEP_SLOT_W / 2, WALL + SEP_Y - SEP_SLOT_L / 2, HO - TOP - 1,
                       SEP_SLOT_W, SEP_SLOT_L, TOP + 2))

    # Centre screw: pillar down to the base boss, clearance hole, counterbore for the head.
    cx, cy = WALL + SCREW_X, WALL + SCREW_Y
    seat = FLOOR + SCREW_MEET + SCREW_LEN - SCREW_ENGAGE
    lid = lid.union(cq.Workplane("XY", origin=(cx, cy, FLOOR + SCREW_MEET)).circle(SCREW_BOSS_D / 2).extrude(LID_PILLAR + 0.5))
    lid = lid.cut(cq.Workplane("XY", origin=(cx, cy, FLOOR + SCREW_MEET - 1)).circle(SCREW_CLEAR / 2).extrude(LID_PILLAR + TOP + 2))
    lid = lid.cut(cq.Workplane("XY", origin=(cx, cy, seat)).circle(SCREW_HEAD_D / 2).extrude(HO - seat + 1))
    return lid


# ---------------------------------------------------------------- dummy components (fit check only)
def make_dummies():
    d = {}
    usb = end_cut(WALL - USB_PROTRUDE, WALL + USB_Y, FLOOR + USB_Z, USB_T, USB_W, 7.3 + USB_PROTRUDE, USB_T / 2 - 0.01)
    parts = box(7.0, CHG_Y0 - 1.8, 0.5, CHG_L - 7.0 - 1.5, 1.8, CHG_H - 1.0)  # chips etc.
    # Solder tails on the back: USB-C legs at the front, wire pads ~2.5 mm from the rear edge.
    tails = box(0, CHG_Y1, 0, 7.0, CHG_BACK, CHG_H).union(box(CHG_L - 5.0, CHG_Y1, 0, 3.5, CHG_BACK, CHG_H))
    d["charger"] = box(0, CHG_Y0, 0, CHG_L, CHG_T, CHG_H).union(usb).union(parts).union(tails)
    d["battery_holder"] = box(BATT_X0 + FIT, BATT_Y0 + FIT, 0, BATT_L, BATT_W, BATT_H)
    stack = box(BRD_X0 + FIT, BRD_Y0 + FIT, POST_H, BRD_X1 - BRD_X0 - 2 * FIT, BRD_W, BRD_H)
    for x, y in HOLES:
        stack = stack.cut(cq.Workplane("XY", origin=(WALL + x, WALL + y, 0)).circle(PIN_D / 2 + 0.2).extrude(FLOOR + 40))
    d["board_stack"] = stack
    d["sma"] = (
        cq.Workplane("YZ", origin=(WALL + BRD_X1 - FIT, WALL + SMA_Y, HB))
        .circle(SMA_D / 2)
        .extrude(SMA_LEN)
    )
    d["reed_board"] = box(REED_X0 + FIT, FIT, 0, REED_L, REED_T, REED_H)
    return d


def overlap(a, b):
    r = a.intersect(b)
    return r.val().Volume() if r.vals() else 0.0


def main():
    base, lid = make_base(), make_lid()
    dummies = make_dummies()

    cq.exporters.export(base, str(OUT / "door_sensor_box_base.step"))
    cq.exporters.export(lid, str(OUT / "door_sensor_box_lid.step"))
    cq.exporters.export(base, str(OUT / "door_sensor_box_base.stl"), tolerance=0.02, angularTolerance=0.1)
    cq.exporters.export(lid, str(OUT / "door_sensor_box_lid.stl"), tolerance=0.02, angularTolerance=0.1)

    asm = cq.Assembly(name="door_sensor_box")
    asm.add(base, name="base", color=cq.Color(0.85, 0.85, 0.82))
    asm.add(lid, name="lid", color=cq.Color(0.55, 0.7, 0.9, 0.6))
    for name, shape in dummies.items():
        asm.add(shape, name=f"ref_{name}", color=cq.Color(0.9, 0.4, 0.2))
    asm.save(str(OUT / "door_sensor_box_assembly.step"))

    # Fit check: no component may overlap the printed parts.
    for name, shape in dummies.items():
        for part_name, part in (("base", base), ("lid", lid)):
            v = overlap(shape, part)
            if v > 0.01:  # dummies are sharp boxes; ignore corner slivers
                print(f"OVERLAP {name} x {part_name}: {v:.3f} mm3")
    v = overlap(base, lid)
    if v > 1e-3:
        print(f"OVERLAP base x lid: {v:.3f} mm3")

    print(f"outside {L_OUT:.1f} x {W_OUT:.1f} x {HO:.1f} mm (base {HB:.1f}, lid {HO - HB:.1f})")
    print(f"inside  {L_IN:.1f} x {W_IN:.1f} x {H_IN:.1f} mm")
    print(f"SMA centre {HB:.1f} mm above the outside bottom; thread outside the spot face {SMA_OUT:.1f} mm")
    print(f"base {base.val().Volume() / 1000:.1f} cm3, lid {lid.val().Volume() / 1000:.1f} cm3")


if __name__ == "__main__":
    main()
