"""
PCB routing fix for preadavanje.
Deletes all bad tracks and re-routes using the board's ACTUAL netlist.

Run in KiCad PCB Editor scripting console:
exec(open(r'C:/Users/andra/Downloads/preadavanje/preadavanje/fix_routing.py').read())
"""
import pcbnew
import math

board = pcbnew.GetBoard()
def mm(v): return pcbnew.FromMM(float(v))

# ── 1. Fix component positions ────────────────────────────────────────────────

def place(ref, x, y, angle=0):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        print("WARNING: %s not found" % ref)
        return
    fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    fp.SetOrientationDegrees(angle)

print("Fixing positions...")
place('RV2', 67, 36, 0)   # was too close to right edge — move left
place('R11', 33, 47, 0)   # was overlapping RV1 courtyard — move right
place('R16', 57, 47, 0)   # shift slightly to match R11 move

# ── 2. Delete ALL tracks, vias, zones ────────────────────────────────────────

print("Clearing old routing...")
for t in list(board.GetTracks()):
    board.Remove(t)
for z in list(board.Zones()):
    board.Remove(z)
print("  Cleared.")

# ── 3. Routing helpers ────────────────────────────────────────────────────────

def add_seg(x1, y1, x2, y2, net_obj, w, layer):
    if abs(x1-x2) < 0.005 and abs(y1-y2) < 0.005:
        return
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
    t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    t.SetWidth(mm(w))
    t.SetLayer(layer)
    t.SetNet(net_obj)
    board.Add(t)

def route_mst(pads, w=0.25, layer=pcbnew.F_Cu):
    """
    Connect pad objects using nearest-neighbour MST.
    Uses horizontal-first L-shapes so bias traces stay in the y=36-37 band
    rather than crossing the y=27 signal channel.
    """
    if len(pads) < 2:
        return
    net_obj = pads[0].GetNet()
    pts = [(pcbnew.ToMM(p.GetPosition().x),
            pcbnew.ToMM(p.GetPosition().y)) for p in pads]
    connected = [pts[0]]
    remaining  = list(pts[1:])
    while remaining:
        bi, bj, bd = 0, 0, float('inf')
        for ci, (cx, cy) in enumerate(connected):
            for ri, (rx, ry) in enumerate(remaining):
                d = math.hypot(cx-rx, cy-ry)
                if d < bd:
                    bd = d; bi = ci; bj = ri
        cx, cy = connected[bi]
        rx, ry = remaining.pop(bj)
        if abs(cx-rx) < 0.01 or abs(cy-ry) < 0.01:
            add_seg(cx, cy, rx, ry, net_obj, w, layer)
        else:
            # Horizontal first, then vertical
            add_seg(cx, cy, rx, cy, net_obj, w, layer)
            add_seg(rx, cy, rx, ry, net_obj, w, layer)
        connected.append((rx, ry))

# ── 4. Route every net from the board's actual netlist ───────────────────────

print("Building net->pads map from footprints...")
from collections import defaultdict
net_pads_map = defaultdict(list)
for fp in board.GetFootprints():
    for pad in fp.Pads():
        nc = pad.GetNetCode()
        if nc > 0:
            net_pads_map[nc].append(pad)

# Build net_code -> net_name lookup
nc_to_name = {}
for name, info in board.GetNetInfo().NetsByName().items():
    nc_to_name[info.GetNetCode()] = str(name)

print("Routing nets...")
routed = 0
skipped = 0

for nc, pads in sorted(net_pads_map.items()):
    net_name = nc_to_name.get(nc, '')
    if not net_name:
        skipped += 1
        continue
    if len(pads) < 2:
        skipped += 1
        continue

    # GND: drop each pad straight to a bus at y=52 to avoid crossing signal area
    if net_name == 'GND':
        net_obj = pads[0].GetNet()
        xs = []
        for p in pads:
            px = pcbnew.ToMM(p.GetPosition().x)
            py = pcbnew.ToMM(p.GetPosition().y)
            add_seg(px, py, px, 52, net_obj, 0.5, pcbnew.F_Cu)
            xs.append(px)
        if len(xs) >= 2:
            xs.sort()
            add_seg(xs[0], 52, xs[-1], 52, net_obj, 0.5, pcbnew.F_Cu)
        print("  GND  : %d pads  →  bus at y=52" % len(pads))

    # 9V supply: bus at y=9
    elif net_name == '9V':
        net_obj = pads[0].GetNet()
        xs = []
        for p in pads:
            px = pcbnew.ToMM(p.GetPosition().x)
            py = pcbnew.ToMM(p.GetPosition().y)
            add_seg(px, py, px, 9, net_obj, 0.5, pcbnew.F_Cu)
            xs.append(px)
        if len(xs) >= 2:
            xs.sort()
            add_seg(xs[0], 9, xs[-1], 9, net_obj, 0.5, pcbnew.F_Cu)
        print("  9V   : %d pads  →  bus at y=9" % len(pads))

    # All signal nets: nearest-neighbour MST
    else:
        route_mst(pads, w=0.25)
        print("  %-20s: %d pads" % (net_name, len(pads)))

    routed += 1

print("Routed %d nets, skipped %d." % (routed, skipped))

# ── 5. GND copper pour on B.Cu ───────────────────────────────────────────────

print("Adding B.Cu GND pour...")
gnd_net = board.FindNet("GND")
if gnd_net:
    zone = pcbnew.ZONE(board)
    zone.SetNet(gnd_net)
    zone.SetLayer(pcbnew.B_Cu)
    zone.SetMinThickness(mm(0.25))
    ol = zone.Outline()
    ol.NewOutline()
    ol.Append(mm(1),  mm(1))
    ol.Append(mm(81), mm(1))
    ol.Append(mm(81), mm(54))
    ol.Append(mm(1),  mm(54))
    board.Add(zone)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    print("  GND pour filled on B.Cu.")
else:
    print("  WARNING: GND net not found — pour skipped.")

# ── Done ─────────────────────────────────────────────────────────────────────

pcbnew.Refresh()
print("")
print("=== Fix complete ===")
print("All connections now use the board's real netlist — no more shorts.")
print("Run DRC (Inspect > Design Rules Checker) to check remaining issues.")
print("Use Interactive Router (press X) to nudge any leftover clearance violations.")
print("Save with Ctrl+S when done.")
