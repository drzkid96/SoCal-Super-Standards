"""Shared topic definitions."""
LABEL = {"std": "Standard", "gui": "Guidance", "opt": "Option", "sup": "Support"}
T = [
 ("crosswalks", "Crosswalks and pedestrian crossings", "Marking, signing and controlling pedestrian crossings: crosswalk patterns, uncontrolled crossings, RRFBs, PHBs, raised crosswalks, limit lines and advance yield lines.",
  r"crosswalk|pedestrian crossing|yield here to|stop here for ped|rectangular rapid|pedestrian hybrid|in-street ped|limit line|stop and yield lines|ped(estrian)? signs?|high-visibility",
  r"crosswalk|pedestrian|RRFB|yield line|stop line|limit line|hybrid beacon", ["R1-5", "R1-6", "R9-2", "R9-3", "R9-4", "R9-8", "R9-9", "R9-10", "R9-11", "R10-15", "W11-2", "W16-7", "W16-9", "SW24-"], r"crosswalk|limit line|crossing island|raised crosswalk|continental|uncontrolled", ["crosswalks"]),
 ("bikeways", "Bikeways and bicycle facilities", "Bike lanes, separated bikeways (Class IV), buffered and green-colored lanes, bike boxes, two-stage turn queue boxes, shared lane markings, bike signals and bicycle signs.",
  r"bicycl|bike|shared lane|separated|two-stage|cycle", r"bicycl|bike|shared lane|separated|cycle", ["R81", "R3-17", "R4-11", "W11-1", "D11-1", "R9-6", "R10-22", "R10-26", "W16-1", "R4-4", "R9-5", "R5-1b"], r"bike|bicycl|sharrow|cycle", ["bikeways"]),
 ("transit", "Transit, bus lanes and bus stops", "Preferential and bus-only lanes, red transit lanes, bus bulbs and stops, queue jumps, transit signals and light rail.",
  r"preferential lane|bus|transit|light rail|hov|high-occupancy", r"bus|transit|preferential|light rail", ["R3-10", "R3-11", "R3-12", "R3-13", "R3-14", "R3-15", "R3-17", "R10-23", "R10-24", "R15-", "W10-7"], r"bus|transit", ["transit"]),
 ("curb-parking-loading", "Curb, parking and loading zones", "Curb paint colors, parking stalls, loading and passenger zones, no-parking and tow-away signs, shared mobility zones, meters and accessible parking.",
  r"parking|curb mark|loading|stopping|standing|tow", r"parking|curb|loading|stall", ["R7-", "R8-", "R26", "R28", "R30", "R99", "R100"], r"parking|stall|meter|loading|curb|tow away|street sweeping|red flag", ["parking-curb"]),
 ("speed-and-calming", "Speed limits, speed zones and traffic calming", "Speed limit signs and speed zones, school and senior speed limits, speed humps, speed tables, traffic circles and roundabouts, and narrowed roadways.",
  r"speed|traffic calming|roundabout|hump|traffic circle", r"speed|calming|roundabout|hump", ["R2-", "W13-", "W17-", "R2-1", "W3-5", "W2-6"], r"speed hump|speed table|traffic circle|roundabout|narrowed roadway|calming", ["speed-calming"]),
 ("signals", "Traffic signals and pedestrian signals", "Signal warrants, signal heads and placement, phasing, pedestrian signal heads and countdowns, accessible pedestrian signals, detection and beacons.",
  r"signal|beacon|warrant|detector|countdown|accessible pedestrian", r"signal|beacon|warrant|detect", ["R10-", "W3-3", "W25-"], r"signal|mastarm|loop|detector|beacon|pull box|conduit|controller", ["signals"]),
 ("striping-intersections", "Lane lines, striping and intersection markings", "Longitudinal markings, centerlines and lane lines, channelization, turn lanes, words and arrows, dotted extension lines and pavement marking materials.",
  r"longitudinal|center ?line|lane line|edge line|channeliz|word|arrow|pavement marking|extension|chevron|raised pavement|markings", r"marking|line|arrow|channeliz", ["R3-", "R3-8", "R3-5", "R3-6", "R3-7", "W24-", "W4-"], r"striping|lane|channelization|pavement marking|arrow|word|left turn|intersection striping", ["striping"]),
 ("school-zones", "School zones", "School area signs, school speed limits, school crosswalks, crossing guards and pick-up/drop-off areas.",
  r"school", r"school", ["S1-", "S3-", "S4-", "S5-", "R26", "SR4"], r"school", []),
 ("street-name-and-guide-signs", "Street name and guide signs", "Street name signs, overhead and mastarm-mounted name signs, advance street name signs, guide and wayfinding signs.",
  r"street name|guide sign|destination|wayfinding|route sign|advance street", r"street name|guide|destination|wayfinding", ["D3-", "D1-", "D11-", "M1-", "M3-", "M5-", "M6-", "E1-"], r"street name|guide sign|overhead", []),
 ("temporary-traffic-control", "Temporary traffic control", "Work zones, closures, detours, tapers, channelizing devices and pedestrian and bicycle accommodation through work zones.",
  r"temporary traffic|work zone|taper|flagger|channelizing|detour|closure|tta", r"temporary traffic|work zone|flagg|detour", ["W20-", "W21-", "G20-", "R11-", "M4-", "W1-6"], r"closure|block party|detour|construction|barricade", []),
 ("accessibility", "Accessibility: curb ramps and accessible signals", "Curb ramps, detectable warnings, accessible pedestrian routes in work zones, accessible pedestrian signals and accessible parking.",
  r"accessib|curb ramp|detectable", r"accessib|curb ramp|detectable", ["R7-8", "R99"], r"curb ramp|accessible|ada|detectable", ["accessibility"]),
 ("rail-crossings", "Railroad and light rail crossings", "Grade crossing signs, markings and signals, and light rail transit crossings.",
  r"grade crossing|railroad|rail|lrt|light rail", r"rail|crossing", ["R15-", "W10-", "R8-8", "I-13"], r"rail", []),
]

CHAPS = {"crosswalks": ["3C", "4J", "4L", "4K"], "bikeways": ["9A", "9B", "9C", "9D", "9E", "9F", "4H"], "transit": ["3E", "2G"],
         "curb-parking-loading": [], "speed-and-calming": ["3D"], "signals": ["4B", "4C", "4D", "4E", "4F", "4I", "4S"],
         "striping-intersections": ["3B", "3J", "3H"], "school-zones": ["7A", "7B", "7C", "7D"], "street-name-and-guide-signs": ["2D"],
         "temporary-traffic-control": ["6A", "6B", "6C", "6F", "6G", "6H", "6K"], "accessibility": ["4K", "6C"], "rail-crossings": ["8A", "8B", "8C", "8D", "8E"]}

# workflow groups for navigation
GROUPS = [
    ("Pedestrians", ["crosswalks", "accessibility", "school-zones"]),
    ("Bikes and transit", ["bikeways", "transit"]),
    ("Curb and street design", ["curb-parking-loading", "speed-and-calming"]),
    ("Intersections, signals and striping", ["signals", "striping-intersections"]),
    ("Signs", ["street-name-and-guide-signs"]),
    ("Work zones and rail", ["temporary-traffic-control", "rail-crossings"]),
]
