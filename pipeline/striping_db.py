"""Caltrans striping detail database (CA MUTCD 2026 Figures 3A-101(CA) to 3A-113(CA)).

Values were read from the dimensioned details in CA MUTCD 2026. Rows are drawn top to bottom.
  line:   {"y": inches from top, "c": "Y"|"W"|"K", "w": width in inches, "pat": None (solid) or [on_ft, off_ft, phase_ft]}
  marker: {"y": inches, "t": marker type, "every": ft, "phase": ft}
Marker types: Y2 two-way yellow retroreflective; Y1 one-way yellow retroreflective; C1 one-way clear retroreflective;
              RC red-clear retroreflective; RY red-yellow retroreflective.
"""
N = 4  # normal line drawn at 4 in (CA: 4 to 6 in local agencies, 6 in on the State Highway System)
L = lambda y, c, pat=None, w=N: {"y": y, "c": c, "w": w, "pat": pat}
M = lambda y, t, every, phase=0: {"y": y, "t": t, "every": every, "phase": phase}

MARKERS = {"Y2": "Two-way yellow retroreflective marker", "Y1": "One-way yellow retroreflective marker",
           "C1": "One-way clear retroreflective marker", "RC": "Red-clear retroreflective marker", "RY": "Red-yellow retroreflective marker"}

D = [
 # ---------------- Centerlines, two-lane (3A-101(CA))
 dict(d="1", fn="Centerline", sub="Two-lane, passing permitted", color="Yellow", type="Broken", speed="40 mph or less", seg=7, gap=17, cycle=24,
      markers="None", fig="3A-101(CA)", rows=[L(0, "Y", [7, 17, 0])]),
 dict(d="2", fn="Centerline", sub="Two-lane, passing permitted, with markers", color="Yellow", type="Broken + markers", speed="40 mph or less", seg=7, gap=17, cycle=24,
      markers="Two-way yellow, 48 ft, in alternate gaps", fig="3A-101(CA)", rows=[L(0, "Y", [7, 17, 8.5]), M(0, "Y2", 48, 0)]),
 dict(d="5", fn="Centerline", sub="Two-lane, passing permitted", color="Yellow", type="Broken", speed="45 mph or more", seg=12, gap=36, cycle=48,
      markers="None", fig="3A-101(CA)", rows=[L(0, "Y", [12, 36, 0])]),
 dict(d="6", fn="Centerline", sub="Two-lane, passing permitted, with markers", color="Yellow", type="Broken + markers", speed="45 mph or more", seg=12, gap=36, cycle=48,
      markers="Two-way yellow, 48 ft, mid-gap", fig="3A-101(CA)", rows=[L(0, "Y", [12, 36, 18]), M(0, "Y2", 48, 0)]),
 # ---------------- Lane lines (3A-102(CA))
 dict(d="8", fn="Lane line", sub="Multilane, same direction", color="White", type="Broken", speed="40 mph or less", seg=7, gap=17, cycle=24,
      markers="None", fig="3A-102(CA)", rows=[L(0, "W", [7, 17, 0])]),
 dict(d="9", fn="Lane line", sub="Multilane, with markers", color="White", type="Broken + markers", speed="40 mph or less", seg=7, gap=17, cycle=24,
      markers="One-way clear, 48 ft, in alternate gaps", fig="3A-102(CA)", rows=[L(0, "W", [7, 17, 8.5]), M(0, "C1", 48, 0)]),
 dict(d="9A", fn="Lane line", sub="Multilane and freeway ramps, with red-clear markers", color="White", type="Broken + markers", speed="40 mph or less", seg=7, gap=17, cycle=24,
      markers="Red-clear, 48 ft, in alternate gaps", fig="3A-102(CA)", rows=[L(0, "W", [7, 17, 8.5]), M(0, "RC", 48, 0)]),
 dict(d="11", fn="Lane line", sub="Multilane, same direction", color="White", type="Broken", speed="45 mph or more", seg=12, gap=36, cycle=48,
      markers="None", fig="3A-102(CA)", rows=[L(0, "W", [12, 36, 0])]),
 dict(d="12", fn="Lane line", sub="Multilane conventional highways, expressways, collectors, with markers", color="White", type="Broken + markers", speed="45 mph or more", seg=12, gap=36, cycle=48,
      markers="One-way clear, 48 ft, mid-gap", fig="3A-102(CA)", rows=[L(0, "W", [12, 36, 18]), M(0, "C1", 48, 0)]),
 dict(d="12A", fn="Lane line", sub="Multilane highways, freeways, ramps, connectors, with red-clear markers", color="White", type="Broken + markers", speed="45 mph or more", seg=12, gap=36, cycle=48,
      markers="Red-clear, 48 ft, mid-gap", fig="3A-102(CA)", rows=[L(0, "W", [12, 36, 18]), M(0, "RC", 48, 0)]),
 # ---------------- No-passing, one direction (3A-103(CA))
 dict(d="15", fn="No-passing zone, one direction", sub="Broken yellow beside solid yellow", color="Yellow", type="Broken + solid", speed="40 mph or less", seg=7, gap=17, cycle=24, spacing="3 in",
      markers="None", fig="3A-103(CA)", rows=[L(0, "Y", [7, 17, 0]), L(7, "Y")]),
 dict(d="16", fn="No-passing zone, one direction", sub="With markers", color="Yellow", type="Broken + solid + markers", speed="40 mph or less", seg=7, gap=17, cycle=24, spacing="3 in",
      markers="Two-way and one-way yellow in the broken line; one-way yellow every 24 ft beside the solid line", fig="3A-103(CA)",
      rows=[L(0, "Y", [7, 17, 8.5]), M(0, "Y2", 48, 0), M(0, "Y1", 48, 24), L(7, "Y"), M(13, "Y1", 24, 0)]),
 dict(d="18", fn="No-passing zone, one direction", sub="Broken yellow beside solid yellow", color="Yellow", type="Broken + solid", speed="45 mph or more", seg=12, gap=36, cycle=48, spacing="3 in",
      markers="None", fig="3A-103(CA)", rows=[L(0, "Y", [12, 36, 0]), L(7, "Y")]),
 dict(d="19", fn="No-passing zone, one direction", sub="With markers", color="Yellow", type="Broken + solid + markers", speed="45 mph or more", seg=12, gap=36, cycle=48, spacing="3 in",
      markers="Two-way yellow every 48 ft in the broken line; one-way yellow every 24 ft beside the solid line", fig="3A-103(CA)",
      rows=[L(0, "Y", [12, 36, 18]), M(0, "Y2", 48, 0), L(7, "Y"), M(13, "Y1", 24, 0)]),
 # ---------------- No-passing, two direction (3A-104(CA))
 dict(d="21", fn="No-passing zone, two direction", sub="Double solid yellow", color="Yellow", type="Double solid", speed="All", spacing="3 in",
      markers="None", fig="3A-104(CA)", plan="Caltrans Std. Plan A20A (cited by Burbank BT-414 and BT-417)", rows=[L(0, "Y"), L(7, "Y")]),
 dict(d="22", fn="No-passing zone, two direction", sub="Double solid yellow with markers", color="Yellow", type="Double solid + markers", speed="All", spacing="3 in",
      markers="Two-way yellow every 24 ft, 2 in outside each line", fig="3A-104(CA)", rows=[M(0, "Y2", 24, 0), L(6, "Y"), L(13, "Y"), M(19, "Y2", 24, 0)]),
 # ---------------- Left edge lines (3A-105(CA))
 dict(d="24", fn="Left edge line", sub="Divided highways, local streets", color="Yellow", type="Solid", speed="All",
      markers="None", fig="3A-105(CA)", rows=[L(0, "Y"), L(6, "K", None, 1)]),
 dict(d="25", fn="Left edge line", sub="State highways", color="Yellow", type="Solid + markers", speed="All",
      markers="One-way yellow every 48 ft, beyond the edge of traveled way", fig="3A-105(CA)", rows=[L(0, "Y"), L(6, "K", None, 1), M(9, "Y1", 48, 0)]),
 dict(d="25A", fn="Left edge line", sub="Highways, freeways, ramps and connectors", color="Yellow", type="Solid + markers", speed="All",
      markers="Red-yellow every 24 ft", fig="3A-105(CA)", rows=[L(0, "Y"), L(6, "K", None, 1), M(9, "RY", 24, 0)]),
 dict(d="26", fn="Left edge line", sub="Markers only, where traveled way and shoulder contrast", color="Yellow", type="Markers only", speed="All",
      markers="One-way yellow every 48 ft", fig="3A-105(CA)", rows=[L(0, "K", None, 1), M(3, "Y1", 48, 0)]),
 dict(d="27", fn="Left edge line", sub="Double solid yellow alternate to Detail 25", color="Yellow", type="Double solid + markers", speed="All", spacing="3 in",
      markers="One-way yellow every 48 ft", fig="3A-105(CA)", rows=[L(0, "Y"), L(7, "Y"), L(13, "K", None, 1), M(16, "Y1", 48, 0)]),
 # ---------------- Right edge (3A-106(CA))
 dict(d="27B", fn="Right edge line", sub="All State highways; may be used on local streets", color="White", type="Solid", speed="All",
      markers="None", fig="3A-106(CA)", plan="Caltrans Std. Plan A20B (cited by Burbank BT-416)", rows=[L(0, "W"), L(6, "K", None, 1)]),
 dict(d="27C", fn="Right edge line extension", sub="Through intersections, e.g. heavy fog areas", color="White", type="Dotted", speed="All", seg=3, gap=12, cycle=15,
      markers="None", fig="3A-106(CA)", rows=[L(0, "W", [3, 12, 0])]),
 # ---------------- Median islands (3A-107(CA))
 dict(d="28", fn="Median island (painted)", sub="Double left edge lines, all-paved sections", color="Yellow", type="Two double solid lines", speed="All", spacing="3 in pairs, 2 ft min. between pairs",
      markers="None", fig="3A-107(CA)", rows=[L(0, "Y"), L(7, "Y"), L(35, "Y"), L(42, "Y")]),
 dict(d="29", fn="Median island (painted)", sub="With markers", color="Yellow", type="Two double solid lines + markers", speed="All", spacing="3 in pairs, 2 ft between pairs",
      markers="Two-way yellow every 24 ft, outside each pair", fig="3A-107(CA)", rows=[M(0, "Y2", 24, 0), L(6, "Y"), L(13, "Y"), L(41, "Y"), L(48, "Y"), M(54, "Y2", 24, 0)]),
 # ---------------- TWLTL (3A-108(CA))
 dict(d="31", fn="Two-way left-turn lane", sub="Solid outer lines, broken inner lines", color="Yellow", type="Solid + broken pair", speed="All", seg=12, gap=36, cycle=48,
      markers="None", fig="3A-108(CA)", rows=[L(0, "Y"), L(16, "Y", [12, 36, 0]), L(23, "Y", [12, 36, 0]), L(40, "Y")]),
 dict(d="32", fn="Two-way left-turn lane", sub="With markers", color="Yellow", type="Solid + broken pair + markers", speed="All", seg=12, gap=36, cycle=48,
      markers="Two-way yellow every 24 ft outside the solid lines and every 48 ft in the broken lines", fig="3A-108(CA)",
      rows=[M(0, "Y2", 24, 0), L(6, "Y"), M(18, "Y2", 48, 0), L(18, "Y", [12, 36, 18]), L(25, "Y", [12, 36, 18]), M(25, "Y2", 48, 0), L(37, "Y"), M(43, "Y2", 24, 0)]),
 # ---------------- Intersection approaches (3A-109(CA))
 dict(d="34", fn="Centerline at intersection approach", sub="Solid yellow on approach (100 ft min.), with markers", color="Yellow", type="Broken + solid + markers", speed="45 mph or more", seg=12, gap=36, cycle=48,
      markers="Two-way yellow in the broken line, one-way yellow every 24 ft beside the solid line", fig="3A-109(CA)",
      rows=[L(0, "Y", [12, 36, 18]), M(0, "Y2", 48, 0), L(7, "Y"), M(13, "Y1", 24, 0)]),
 dict(d="34A", fn="Centerline at intersection approach", sub="Solid yellow on approach (100 ft min.)", color="Yellow", type="Broken + solid", speed="45 mph or more", seg=12, gap=36, cycle=48,
      markers="None", fig="3A-109(CA)", rows=[L(0, "Y", [12, 36, 0]), L(7, "Y")]),
 dict(d="35", fn="Centerline at intersection approach", sub="Solid yellow on approach (100 ft min.), with markers", color="Yellow", type="Broken + solid + markers", speed="40 mph or less", seg=7, gap=17, cycle=24,
      markers="Two-way and one-way yellow in the broken line, one-way yellow every 24 ft beside the solid line", fig="3A-109(CA)",
      rows=[L(0, "Y", [7, 17, 8.5]), M(0, "Y2", 48, 0), M(0, "Y1", 48, 24), L(7, "Y"), M(13, "Y1", 24, 0)]),
 dict(d="35A", fn="Centerline at intersection approach", sub="Solid yellow on approach (100 ft min.)", color="Yellow", type="Broken + solid", speed="40 mph or less", seg=7, gap=17, cycle=24,
      markers="None", fig="3A-109(CA)", rows=[L(0, "Y", [7, 17, 0]), L(7, "Y")]),
 # ---------------- Ramps (3A-110(CA)) - layouts, drawn from the source only
 dict(d="36", fn="Ramp channelizing", sub="Exit ramp neutral area (gore)", color="White", type="12 in solid lines + markers", speed="Freeway",
      markers="Red-clear every 24 ft", fig="3A-110(CA)", rows=None),
 dict(d="36A", fn="Ramp channelizing", sub="Entrance ramp neutral area (merge)", color="White", type="12 in solid lines + markers", speed="Freeway",
      markers="Red-clear every 24 ft", fig="3A-110(CA)", rows=None),
 dict(d="36B", fn="Ramp channelizing", sub="Entrance ramp neutral area (acceleration lane)", color="White", type="12 in solid lines + markers", speed="Freeway",
      markers="Red-clear every 24 ft", fig="3A-110(CA)", rows=None),
 # ---------------- Lane drops (3A-111(CA))
 dict(d="37", fn="Lane drop", sub="Freeway exit ramps and connectors; repeat at 1/2 mile", color="White", type="8 in dotted + markers", speed="Freeway",
      markers="One-way clear and red-clear", fig="3A-111(CA)", rows=None),
 dict(d="37B", fn="Lane drop", sub="Mandatory turn lanes at conventional highway intersections", color="White", type="8 in dotted + markers", speed="All",
      markers="One-way clear (optional on local streets)", fig="3A-111(CA)", rows=None),
 dict(d="37D", fn="Lane drop", sub="Mandatory exiting lanes at two-lane roundabouts", color="White", type="8 in dotted", speed="All", seg=2, gap=4, cycle=6,
      markers="None", fig="3A-111(CA)", rows=[L(0, "W", [2, 4, 0], 8)]),
 # ---------------- Channelizing and extensions (3A-112(CA))
 dict(d="38", fn="Channelizing line", sub="Left- or right-turn lanes on State highways", color="White", type="8 in solid + markers", speed="All",
      markers="One-way clear every 24 ft, through-traffic side only", fig="3A-112(CA)", plan="Caltrans Std. Plan A20D (cited by City of Roseville)",
      rows=[L(0, "W", None, 8), M(12, "C1", 24, 0)]),
 dict(d="38A", fn="Channelizing line", sub="Turn lanes on local streets and freeway off-ramp terminals", color="White", type="8 in solid", speed="All",
      markers="None", fig="3A-112(CA)", rows=[L(0, "W", None, 8)]),
 dict(d="38B", fn="Channelizing line", sub="Exit ramps, markers both sides", color="White", type="8 in solid + markers", speed="Freeway",
      markers="Red-clear every 24 ft, both sides", fig="3A-112(CA)", rows=[M(0, "RC", 24, 0), L(6, "W", None, 8), M(18, "RC", 24, 0)]),
 dict(d="38D", fn="Channelizing line", sub="Exit ramps, markers one side", color="White", type="8 in solid + markers", speed="Freeway",
      markers="Red-clear every 24 ft, one side", fig="3A-112(CA)", rows=[L(0, "W", None, 8), M(12, "RC", 24, 0)]),
 dict(d="39", fn="Bike lane line", sub="Class II bike lane", color="White", type="6 in solid", speed="All",
      markers="None", fig="3A-112(CA)", plan="Caltrans Std. Plan A20D (cited by Burbank BT-416)", rows=[L(0, "W", None, 6)]),
 dict(d="39A", fn="Bike lane intersection line", sub="50 to 200 ft before an intersection, where vehicles cross to turn", color="White", type="6 in broken", speed="All", seg=4, gap=8, cycle=12,
      markers="None", fig="3A-112(CA)", plan="Caltrans Std. Plan A20D (cited by Burbank BT-416)", rows=[L(0, "W", [4, 8, 0], 6)]),
 dict(d="40", fn="Lane line extension", sub="Through intersections", color="White", type="Dotted", speed="All", seg=1, gap=6, cycle=7,
      markers="None", fig="3A-112(CA)", rows=[L(0, "W", [1, 6, 0])]),
 dict(d="41", fn="Centerline extension", sub="Through intersections", color="Yellow", type="Dotted", speed="All", seg=1, gap=6, cycle=7,
      markers="None", fig="3A-112(CA)", rows=[L(0, "Y", [1, 6, 0])]),
 # ---------------- Preferential lanes (3A-113(CA))
 dict(d="42", fn="Preferential lane line", sub="Contiguous, continuous access (Figure 3E-3.C)", color="White", type="8 in broken + markers", speed="All", seg=12, gap=36, cycle=48,
      markers="One-way clear pair, mid-gap every 48 ft", fig="3A-113(CA)", rows=[L(0, "W", [12, 36, 0], 8), M(-3, "C1", 48, 24), M(7, "C1", 48, 24)]),
 dict(d="44A", fn="Preferential lane line", sub="Contiguous, access prohibited (Figure 3E-3.A)", color="White", type="Double 8 in solid + markers", speed="All", spacing="4 in",
      markers="One-way clear every 24 ft, outside both lines", fig="3A-113(CA)", rows=[M(0, "C1", 24, 0), L(6, "W", None, 8), L(18, "W", None, 8), M(30, "C1", 24, 0)]),
 dict(d="44B", fn="Preferential lane line", sub="Buffer-separated, access prohibited (Figure 3E-2.A)", color="White", type="Double 8 in solid (buffer) + markers", speed="All", spacing="Buffer space",
      markers="One-way clear every 24 ft, outside both lines", fig="3A-113(CA)", rows=[M(0, "C1", 24, 0), L(6, "W", None, 8), L(30, "W", None, 8), M(42, "C1", 24, 0)]),
 dict(d="45", fn="Preferential lane line", sub="Buffer-separated, access prohibited, wide buffer; chevrons required if buffer over 4 ft", color="White", type="Two double 8 in solid lines + markers", speed="All", spacing="3 in pairs, buffer area",
      markers="One-way clear every 24 ft", fig="3A-113(CA)",
      rows=[M(0, "C1", 24, 0), L(6, "W", None, 8), L(17, "W", None, 8), M(30, "C1", 24, 0), L(40, "W", None, 8), L(51, "W", None, 8), M(63, "C1", 24, 0)]),
]
