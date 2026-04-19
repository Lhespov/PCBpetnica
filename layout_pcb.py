"""
PCB auto-layout for preadavanje project.
Run inside KiCad PCB Editor: Tools > Scripting Console
Then type: exec(open(r'C:/Users/andra/Downloads/preadavanje/preadavanje/layout_pcb.py').read())
"""
import pcbnew
import math

board = pcbnew.GetBoard()

def mm(v):
    return pcbnew.FromMM(float(v))

# ── PLACEMENT ────────────────────────────────────────────────────────────────

def place(ref, x, y, angle=0):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        print("WARNING: %s not found" % ref)
        return None
    fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    fp.SetOrientationDegrees(angle)
    return fp

print("Placing components...")

# Input section (left)
place('RV1',  14,  44,   0)   # input volume pot
place('R1',    7,  38,   0)   # 1k  (RV1 pin3 -> GND)
place('R2',   14,  27,   0)   # 10k (RV1 wiper -> Q1)

# Q1 first stage
place('C4',   21,  27,   0)   # 100n input coupling
place('Q1',   28,  27,   0)   # MMBT5551L
place('C5',   25,  17,  90)   # 470p base HF bypass
place('C6',   21,  11,   0)   # 1u   supply bypass
place('R8',   21,  36,   0)   # 100k base bias lower
place('R9',   28,  36,  90)   # 470k bias/feedback
place('R11',  28,  47,   0)   # 150  collector -> GND
place('D3',   34,  17,   0)   # 1N4148 clipping
place('D5',   34,  11, 180)   # 1N4148 clipping (anti-parallel)
place('R10',  38,  11,  90)   # 10k  emitter -> VCC
place('R12',  38,  27,  90)   # 10k  interstage

# Q2 second stage
place('C7',   44,  27,   0)   # 100n coupling Q1->Q2
place('Q2',   51,  27,   0)   # MMBT5551L
place('C8',   44,  11,   0)   # 1u   supply bypass
place('C9',   55,  27,  90)   # 470p base HF bypass
place('R13',  44,  36,   0)   # 100k base bias lower
place('R14',  51,  36,  90)   # 470k bias/feedback
place('R16',  51,  47,   0)   # 150  collector -> GND
place('D1',   57,  17,   0)   # 1N4148 clipping
place('D4',   57,  11, 180)   # 1N4148 clipping (anti-parallel)
place('R15',  61,  11,  90)   # 10k  -> VCC

# Output section (right)
place('C12',  63,  20,  90)   # 4.7n output coupling
place('R22',  63,  44,   0)   # 22k  output bias
place('R17',  63,  36,  90)   # 39k  tone
place('C13',  69,  44,   0)   # 10n  tone cap
place('RV2',  73,  36,   0)   # output tone/volume pot

print("Placement done.")
pcbnew.Refresh()

# ── BOARD EDGE ────────────────────────────────────────────────────────────────

def edge(x1, y1, x2, y2):
    ln = pcbnew.PCB_SHAPE(board)
    # SHAPE_T_SEGMENT is the correct constant in KiCad 8+
    for attr in ('SHAPE_T_SEGMENT', 'SHAPE_T_LINE', 'S_SEGMENT'):
        if hasattr(pcbnew, attr):
            ln.SetShape(getattr(pcbnew, attr))
            break
    ln.SetLayer(pcbnew.Edge_Cuts)
    ln.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
    ln.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    ln.SetWidth(mm(0.05))
    board.Add(ln)

edge(0, 0, 82, 0)
edge(82, 0, 82, 55)
edge(82, 55, 0, 55)
edge(0, 55, 0, 0)

# ── ROUTING HELPERS ───────────────────────────────────────────────────────────

def get_pad(ref, num):
    fp = board.FindFootprintByReference(ref)
    if fp is None:
        print("WARN: fp %s missing" % ref)
        return None
    for p in fp.Pads():
        if p.GetNumber() == str(num):
            return p
    print("WARN: pad %s/%s missing" % (ref, num))
    return None

def seg(x1, y1, x2, y2, net, w=0.25, layer=pcbnew.F_Cu):
    if abs(x1-x2) < 0.001 and abs(y1-y2) < 0.001:
        return
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
    t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    t.SetWidth(mm(w))
    t.SetLayer(layer)
    t.SetNet(net)
    board.Add(t)

def route_l(x1, y1, x2, y2, net, w=0.25, layer=pcbnew.F_Cu):
    """L-shaped route: horizontal first, then vertical."""
    if abs(x1-x2) < 0.001 or abs(y1-y2) < 0.001:
        seg(x1, y1, x2, y2, net, w, layer)
    else:
        seg(x1, y1, x2, y1, net, w, layer)
        seg(x2, y1, x2, y2, net, w, layer)

def mst_route(pad_specs, w=0.25, layer=pcbnew.F_Cu):
    """Connect all pads in a net using nearest-neighbour MST."""
    pts = []
    net = None
    for ref, num in pad_specs:
        p = get_pad(ref, num)
        if p:
            pts.append((pcbnew.ToMM(p.GetPosition().x),
                        pcbnew.ToMM(p.GetPosition().y)))
            if net is None:
                net = p.GetNet()
    if net is None or len(pts) < 2:
        return
    connected = [pts[0]]
    remaining = pts[1:]
    while remaining:
        best_ci, best_ri, best_d = 0, 0, float('inf')
        for ci, (cx, cy) in enumerate(connected):
            for ri, (rx, ry) in enumerate(remaining):
                d = math.hypot(cx-rx, cy-ry)
                if d < best_d:
                    best_d = d; best_ci = ci; best_ri = ri
        cx, cy = connected[best_ci]
        rx, ry = remaining.pop(best_ri)
        route_l(cx, cy, rx, ry, net, w, layer)
        connected.append((rx, ry))

def add_via(x, y, net, drill=0.8, size=1.6):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    v.SetWidth(mm(size))
    v.SetDrill(mm(drill))
    v.SetNet(net)
    try:
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    except Exception:
        v.SetTopLayer(pcbnew.F_Cu)
        v.SetBottomLayer(pcbnew.B_Cu)
    board.Add(v)

# ── ROUTE ALL NETS ────────────────────────────────────────────────────────────

print("Routing nets...")

# GND — route bus along bottom then add B.Cu pour
mst_route([('R22','1'),('R13','2'),('R11','2'),('R8','2'),
           ('R1','2'),('C13','2'),('R16','2')], w=0.4)

# Q1 base bias node
mst_route([('C4','1'),('C5','2'),('C6','2'),('Q1','1'),('R8','1'),('R9','2')])

# Input coupling: R2 out -> C4 in
mst_route([('C4','2'),('R2','1')])

# RV1 wiper -> R2
mst_route([('R2','2'),('RV1','2')])

# RV1 GND side -> R1
mst_route([('R1','1'),('RV1','3')])

# Q1 emitter node (C5, D3, D5, R10, R12, R9, Q1 emitter)
mst_route([('Q1','3'),('R9','1'),('R10','2'),('R12','2'),('C5','1'),('D3','1'),('D5','2')])

# Q1 VCC/supply node (C6, D3 cathode, D5 anode)
mst_route([('C6','1'),('D3','2'),('D5','1')])

# Q1 collector -> R11
mst_route([('Q1','2'),('R11','1')])

# Interstage: R12 -> C7
mst_route([('C7','2'),('R12','1')])

# Q2 base bias node
mst_route([('C7','1'),('C8','2'),('C9','2'),('Q2','1'),('R13','1'),('R14','2')])

# Q2 emitter node
mst_route([('Q2','3'),('R14','1'),('R15','2'),('R17','2'),('C12','2'),('C9','1'),('D1','2'),('D4','1')])

# Q2 VCC/supply node
mst_route([('C8','1'),('D1','1'),('D4','2')])

# Q2 collector -> R16
mst_route([('Q2','2'),('R16','1')])

# Tone control node (R17, C13, RV2 pin3)
mst_route([('C13','1'),('R17','1'),('RV2','3')])

# Output node (C12, R22, RV2 pin1)
mst_route([('C12','1'),('R22','2'),('RV2','1')])

print("Routing done.")

# ── GND COPPER POUR (B.Cu) ────────────────────────────────────────────────────

print("Adding GND copper pour on B.Cu...")

# Find GND net from one of the known GND pads
gnd_net = None
p = get_pad('R8', 2)
if p:
    gnd_net = p.GetNet()

if gnd_net:
    # Add stitching vias at every GND pad
    gnd_pads = [('R22','1'),('R13','2'),('R11','2'),('R8','2'),
                ('R1','2'),('C13','2'),('R16','2')]
    for ref, num in gnd_pads:
        pad = get_pad(ref, num)
        if pad:
            vx = pcbnew.ToMM(pad.GetPosition().x)
            vy = pcbnew.ToMM(pad.GetPosition().y) + 1.5  # offset below pad
            add_via(vx, vy, gnd_net)

    # Copper zone
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
    print("GND pour filled.")
else:
    print("WARN: GND net not found — pour skipped.")

# ── DESIGN RULES SETUP ────────────────────────────────────────────────────────

try:
    settings = board.GetDesignSettings()
    if hasattr(settings, 'SetMinTrackWidth'):
        settings.SetMinTrackWidth(mm(0.2))
    if hasattr(settings, 'SetMinClearance'):
        settings.SetMinClearance(mm(0.2))
except Exception as e:
    print("Design settings skipped: %s" % e)

# ── DONE ─────────────────────────────────────────────────────────────────────

pcbnew.Refresh()
print("")
print("=== PCB LAYOUT COMPLETE ===")
print("Board: 82 x 55 mm")
print("")
print("Next steps:")
print("  1. Inspect > Design Rules Checker (DRC)")
print("  2. Fix any clearance violations manually")
print("  3. File > Save  (Ctrl+S)")
