# main.py — "The World on One Page": the news of Tuesday 24 November 2026
# set as a 1024x1024 cream-newsprint broadsheet, drawn by pure Python from
# first principles. Deterministic, stdlib-only, no images, no fonts shipped:
# the program rasterises its own type (flat quadratic outlines in a 64-unit
# em, embedded in gen/blobs.py), its own coastlines (Natural Earth 110m land
# rings, same blob file) and its own PNG (zlib + CRC32). Two runs produce
# byte-identical output.

import base64
import gzip
import json
import math
import os
import struct
import sys
import zlib

CANVAS = 1024
W = H = CANVAS

# ---------------------------------------------------------------------------
# Newsprint palette — cream paper, two inks, a red accent and map tones.
# ---------------------------------------------------------------------------

PAPER    = (246, 241, 231)   # cream newsprint
BODY_INK = (40, 35, 27)      # warm near-black body text
HEAD_INK = (56, 49, 38)      # slightly lifted ink for headlines
ACCENT   = (168, 41, 32)     # newsstand red: tags, pins, big figures
FADED    = (122, 113, 97)    # greyed ink for the tally and colophon
RULES    = (198, 188, 168)   # hairline column rules
PANEL    = (240, 232, 216)   # hero panel wash
COAST    = (219, 206, 183)   # land fill
OCEAN    = (208, 223, 233)   # sea fill

# The drawing surface: one flat RGB bytearray, top-left origin, cream fill.
frame = bytearray(bytes(PAPER) * (W * H * 3))


def put_pixel(x, y, col):
    """One pixel; coordinates outside the canvas are silently dropped."""
    xi, yi = int(x), int(y)
    if 0 <= xi < W and 0 <= yi < H:
        o = (yi * W + xi) * 3
        frame[o] = col[0]
        frame[o + 1] = col[1]
        frame[o + 2] = col[2]


def rule(xa, xb, y, col, weight=1):
    """A horizontal newspaper rule, `weight` pixels tall."""
    if weight == 1:
        y = int(y)
        if 0 <= y < H:
            lo = max(0, int(xa))
            hi = min(W - 1, int(xb))
            if hi >= lo:
                o = (y * W + lo) * 3
                frame[o:o + (hi - lo + 1) * 3] = bytes(col) * (hi - lo + 1)
        return
    for k in range(weight):
        rule(xa, xb, y + k, col, 1)


def panel(xa, ya, xb, yb, col):
    """Solid axis-aligned block."""
    lo_x, hi_x = max(0, int(xa)), min(W - 1, int(xb))
    lo_y, hi_y = max(0, int(ya)), min(H - 1, int(yb))
    if hi_x < lo_x or hi_y < lo_y:
        return
    strip = bytes(col) * (hi_x - lo_x + 1)
    for y in range(lo_y, hi_y + 1):
        o = (y * W + lo_x) * 3
        frame[o:o + (hi_x - lo_x + 1) * 3] = strip


def fill_polygon(vertices, col):
    """Even-odd span rasteriser: one horizontal span per scanline crossing.

    Handles concave rings and holes because DejaVu alternates outer and
    inner contours; land rings reuse the same sweep for their own topology.
    """
    n = len(vertices)
    if n < 3:
        return
    y_lo = max(0, int(min(v[1] for v in vertices)))
    y_hi = min(H - 1, int(max(v[1] for v in vertices)))
    if y_hi < y_lo:
        return
    live = []
    for i in range(n):
        ax, ay = vertices[i]
        bx, by = vertices[(i + 1) % n]
        if ay != by:
            live.append((ax, ay, bx, by))
    for row in range(y_lo, y_hi + 1):
        probe = row + 0.5
        hits = []
        for (ax, ay, bx, by) in live:
            if (ay <= probe < by) or (by <= probe < ay):
                t = (probe - ay) / (by - ay)
                hits.append(ax + t * (bx - ax))
        if not hits:
            continue
        hits.sort()
        for pair in range(0, len(hits) - 1, 2):
            lo = int(hits[pair] + 0.5)
            hi = int(hits[pair + 1] - 0.5)
            if hi < lo:
                hi = lo
            lo = max(0, lo)
            hi = min(W - 1, hi)
            if hi < lo:
                continue
            o = (row * W + lo) * 3
            frame[o:o + (hi - lo + 1) * 3] = bytes(col) * (hi - lo + 1)


# ---------------------------------------------------------------------------
# Glyph outlines. gen/blobs.py holds a DejaVu Sans subset as pre-flattened
# quadratic contours in a 64-unit em: one JSON dict, char -> [rings, advance].
# The crossing-rule fill in paint_rings keeps counters (o, e, a, 0...) open
# because outer and inner contours alternate and the sweep is even-odd.
# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(HERE, 'gen')

FONT_BLOB = None
MAP_BLOB = None


def load_assets():
    global FONT_BLOB, MAP_BLOB
    src = os.path.join(ASSET_DIR, 'blobs.py')
    if os.path.exists(src):
        scope = {}
        with open(src) as fh:
            exec(compile(fh.read(), src, 'exec'), scope)
        FONT_BLOB = scope['FONT_BLOB_B64']
        MAP_BLOB = scope['MAP_BLOB_B64']


load_assets()


class ContourFont:
    """Flat-contour font: (list of closed polylines in em units, advance)."""

    def __init__(self, table):
        self.table = table
        self.units_per_em = 64.0

    def width_of(self, ch):
        rec = self.table.get(ch)
        return rec[1] if rec else 32

    def shape_of(self, ch):
        rec = self.table.get(ch)
        if not rec:
            return ([], 32)
        return (rec[0], rec[1])


def open_font_blob(b64):
    decoded = json.loads(gzip.decompress(base64.b64decode(b64)))
    return ContourFont({ch: (body[1:], body[0]) for ch, body in decoded.items()})


def glyph_contours(font, ch, origin_x, baseline, size):
    """Position one glyph's contours on the page (y flips: font y is up)."""
    rings, adv = font.shape_of(ch)
    factor = size / font.units_per_em
    placed = [[(origin_x + px * factor, baseline - py * factor)
               for (px, py) in ring] for ring in rings]
    return placed, adv * factor


def paint_rings(rings, col):
    """Crossing-rule fill of a glyph's contours in one sweep, all contours
    together so holes stay open instead of being overpainted."""
    if not rings:
        return
    top = bottom = None
    for ring in rings:
        for (sx, sy) in ring:
            if top is None or sy < top:
                top = sy
            if bottom is None or sy > bottom:
                bottom = sy
    if top is None:
        return
    row_a = max(0, int(top))
    row_b = min(H - 1, int(bottom))
    for row in range(row_a, row_b + 1):
        probe = row + 0.5
        crossings = []
        for pts in rings:
            m = len(pts)
            for i in range(m):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % m]
                if (ay <= probe < by) or (by <= probe < ay):
                    t = (probe - ay) / (by - ay)
                    crossings.append(ax + t * (bx - ax))
        if not crossings:
            continue
        crossings.sort()
        for pair in range(0, len(crossings) - 1, 2):
            lo = int(crossings[pair] + 0.5)
            hi = int(crossings[pair + 1] - 0.5)
            if hi < lo:
                hi = lo
            lo = max(0, lo)
            hi = min(W - 1, hi)
            if hi < lo:
                continue
            o = (row * W + lo) * 3
            frame[o:o + (hi - lo + 1) * 3] = bytes(col) * (hi - lo + 1)


fonts = {}


def draw_text(text, x, baseline, size, col, letter_space=0.0, face=None):
    """Left-aligned string at a given baseline; returns the pen position after."""
    if face is None:
        face = fonts['sans']
    pen = x
    for ch in text:
        if ch == ' ':
            pen += face.width_of(ch) * size / face.units_per_em
            continue
        placed, adv = glyph_contours(face, ch, pen, baseline, size)
        paint_rings(placed, col)
        pen += adv + letter_space
    return pen


def measure(text, size, letter_space=0.0, face=None):
    if face is None:
        face = fonts['sans']
    total = 0.0
    for ch in text:
        total += face.width_of(ch) * size / face.units_per_em + letter_space
    return total


def fold(text, size, limit, cap=99, face=None):
    """Greedy word wrap. Returns up to `cap` lines."""
    if face is None:
        face = fonts['sans']
    out = []
    carry = ''
    for word in text.split():
        candidate = (carry + ' ' + word).strip()
        if measure(candidate, size, face=face) <= limit or not carry:
            carry = candidate
        else:
            out.append(carry)
            carry = word
            if len(out) == cap:
                break
    if carry and len(out) < cap:
        out.append(carry)
    return out


# ---------------------------------------------------------------------------
# The map: Natural Earth 110m land, reduced to lon/lat rings (MAP_BLOB_B64
# in gen/blobs.py). Equirectangular projection into any box; land painted
# with the same even-odd sweep as glyphs; optional red location pin.
# ---------------------------------------------------------------------------

LAND_RINGS = None


def load_land():
    global LAND_RINGS
    if MAP_BLOB:
        LAND_RINGS = json.loads(gzip.decompress(base64.b64decode(MAP_BLOB)))


load_land()


def to_page(lon, lat, centre_x, centre_y, box_w, box_h):
    """Equirectangular projection into a map box."""
    return (centre_x + (lon / 180.0) * (box_w / 2.0),
            centre_y - (lat / 90.0) * (box_h / 2.0))


def draw_map(centre_x, centre_y, box_w, box_h, marker=None):
    """A small world map: sea panel, coastlines, optional red location pin."""
    panel(centre_x - box_w / 2.0 - 2, centre_y - box_h / 2.0 - 2,
          centre_x + box_w / 2.0 + 2, centre_y + box_h / 2.0 + 2, OCEAN)
    if LAND_RINGS:
        for ring in LAND_RINGS:
            outline = [to_page(lon, lat, centre_x, centre_y, box_w, box_h)
                       for (lon, lat) in ring]
            fill_polygon(outline, COAST)
    if marker is not None:
        m_lon, m_lat = marker
        mx, my = to_page(m_lon, m_lat, centre_x, centre_y, box_w, box_h)
        mx = min(max(mx, centre_x - box_w / 2.0 + 4), centre_x + box_w / 2.0 - 4)
        my = min(max(my, centre_y - box_h / 2.0 + 4), centre_y + box_h / 2.0 - 4)
        for radius in (5, 4, 3):
            for angle in range(0, 360, 30):
                for arm in range(radius):
                    put_pixel(mx + arm * math.cos(math.radians(angle)),
                              my + arm * math.sin(math.radians(angle)), ACCENT)


# ---------------------------------------------------------------------------
# The day: Tuesday 24 November 2026. 35 stories, each first reported on that
# date (UTC) and checked against the named outlet's reporting of the day.
# Region tally: Europe 7, Middle East 5, Asia 8, Africa 3, Americas 7,
# Oceania 3, Global 2.
# ---------------------------------------------------------------------------

BANNER = 'THE WORLD ON ONE PAGE'
EDITION_LINE = 'DAY 328 OF 2026 · EVERY STORY DATED TUESDAY 24 NOV'
TALLY = ('35 STORIES · EUROPE 7 · MIDDLE EAST 5 · ASIA 8 · AFRICA 3 · '
         'AMERICAS 7 · OCEANIA 3 · GLOBAL 2')

# Four lead stories: big figure, region tag, headline, body copy, and the
# (lon, lat) pin for its mini map.
STORIES = {
    'leads': [
        dict(fig='+30%', tag='US · MARKETS', marker=(-74.0, 40.7),
             head='Nvidia reinstates Huang; Trump says "I made the deal"',
             copy=('Nvidia brought back CEO Jensen Huang two weeks after his '
                   'exit, and the stock surged 30%, adding about $900bn in '
                   'value. Trump said he pressured the board; lawmakers from '
                   'both parties demanded answers on national-security '
                   'grounds. (DW, AP, LA Times)')),
        dict(fig='3 of 4', tag='MIDDLE EAST', marker=(56.3, 26.6),
             head='Tankers hit mines in Strait of Hormuz under US escort',
             copy=("Iran's Revolutionary Guard said three oil tankers caught "
                   'fire after striking naval mines in the strait, all under '
                   'US air cover, as Treasury widened sanctions on the '
                   'Iranian shadow banking network. Iran ruled out talks '
                   'until its conditions are met. (CNBC, AP)')),
        dict(fig='-45%', tag='EUROPE · WAR', marker=(37.5, 55.5),
             head='Putin: retaliation "inevitable" as Ukraine keeps hitting '
                  'refineries',
             copy=('Ukrainian drone strikes have cut Russian refining '
                   'capacity by 45% since late October, industry sources '
                   'told Reuters. Zaporizhzhia strikes killed two overnight. '
                   'The Pentagon is holding roughly 60 Patriot interceptors '
                   'back from Kyiv, the FT reported. (Reuters, Al Jazeera)')),
        dict(fig='No deal', tag='GLOBAL · CLIMATE', marker=(27.0, 36.9),
             head='COP31 Antalya ends without a pact — the "worst COP ever"',
             copy=('Two weeks of talks plus a record 50 hours of overtime '
                   'closed with no cover decision after the EU, UK and '
                   'Pacific states rejected a draft that dropped '
                   'fossil-fuel language. Delegates left pointing at who '
                   'pays. (BBC, Reuters, CNBC)')),
    ],
    'columns': [
        ('AMERICAS', 'Canada to Washington: "We don\'t report to the US"'),
        ('ASIA', 'Russian jets trigger South Korea\'s first-ever island '
                 'air-raid alert'),
        ('EUROPE', 'Estonia to close border with Russia from 1 December'),
        ('AFRICA', 'Sudan army retakes 30+ villages in Kordofan; drones hit '
                   'Khartoum'),
        ('ASIA', 'Singapore lifts 2026 growth forecast to 6% on AI '
                 'investment'),
        ('MIDDLE EAST', 'Saudi-led coalition orders Hodeidah port '
                        'evacuation'),
        ('AMERICAS', "Brazil's Congress passes Lula's fiscal adjustment "
                     'package'),
        ('GLOBAL', 'Meta quietly drops its 2030 net-zero goal as AI power '
                   'demand soars'),
    ],
    'wire': [
        'EUROPE — Polish PM: Russian drone stayed 8 minutes in Polish airspace',
        'EUROPE — Germans now narrowly oppose further Ukraine military aid — poll',
        "EUROPE — NATO sends AWACS to Poland after last week's airspace breach",
        'EUROPE — Italy warns Ukraine over naval-drone strikes off Libya',
        'EUROPE — Merz-Trump son-in-law to host new Ukraine talks "soon"',
        'MIDDLE EAST — 9 Palestinians killed in Israeli strikes; Hamas '
        'security chief dead',
        'MIDDLE EAST — Houthis threaten Jeddah and Saudi Red Sea ports',
        'MIDDLE EAST — UK sanctions Houthi leaders over renewed aggression',
        'ASIA — China and EU hold 17th economic dialogue in Beijing',
        'ASIA — Japan to fire long-range missiles on Indian test ranges',
        'ASIA — India: 5,600 police guard Madurai hill for contested lamp ritual',
        'ASIA — Bangladesh graduates from UN least-developed-country status',
        'ASIA — 13 killed, many Indian, as bus hits truck on UAE highway',
        'ASIA — 139 fugitives deported from Philippines to Indonesia',
        'AFRICA — Amnesty: Ethiopian shelling of Alamata is possible war crime',
        'AFRICA — Sudan reportedly sends fighters to Saudi-led Houthi operations',
        "AMERICAS — Brazil recalls ambassador over Argentina election remarks",
        "AMERICAS — El Salvador names 3 soldiers killed on Haiti anti-gang "
        'mission',
        'AMERICAS — Democrats pledge to reverse Trump food-aid cuts in January',
        "AMERICAS — US retail sales slowed to +0.2% in October, Census says",
        "AMERICAS — Lawmakers vow to \"put the screws\" to Nvidia's Huang",
        'OCEANIA — Solomon Islands signs security pact with Australia, '
        'dropping China',
        "OCEANIA — Kiribati evacuates Kanton Island residents with a day's "
        'notice',
        'OCEANIA — Australia and Singapore sign supply-security and CCS pacts',
    ],
    'colophon': ('METHODOLOGY — 35 stories that happened or were first '
                 'reported on Tuesday 24 November 2026 (UTC), cross-checked '
                 'against Reuters, AP, Al Jazeera, DW, CNBC, Xinhua, Yonhap, '
                 'FT, LA Times, PACNEWS and government statements. Figures '
                 'as reported by the named outlet on the day. One page, '
                 'every story dated.'),
}


# ---------------------------------------------------------------------------
# Page self-audit: the layout is a fixed grid, so almost every mistake is a
# counting mistake. Count the stories by region and compare with the printed
# tally before any ink is put down; a silently wrong page becomes a loud one.
# ---------------------------------------------------------------------------

REGIONS = ('EUROPE', 'MIDDLE EAST', 'ASIA', 'AFRICA', 'AMERICAS',
           'OCEANIA', 'GLOBAL')
PAGE_TOTAL = 35


def declared_tally():
    """Parse 'EUROPE 7 · ASIA 8 ...' out of the printed tally strip."""
    found = {}
    for chunk in TALLY.split('·'):
        bits = chunk.strip().split()
        if len(bits) >= 2 and bits[-1].isdigit():
            name = ' '.join(bits[:-1])
            if name in REGIONS:
                found[name] = int(bits[-1])
    return found


def counted_stories():
    tally = dict.fromkeys(REGIONS, 0)
    for lead in STORIES['leads']:
        for word in lead['tag'].split('·'):
            word = word.strip()
            if word in REGIONS:
                tally[word] += 1
                break
    for place, _story in STORIES['columns']:
        if place in tally:
            tally[place] += 1
    for item in STORIES['wire']:
        head = item.split('—')[0].strip()
        if head in tally:
            tally[head] += 1
    return tally


def audit_page():
    declared = declared_tally()
    counted = counted_stories()
    on_page = sum(counted.values())
    if on_page != PAGE_TOTAL:
        raise SystemExit('page holds %d stories, expected %d'
                         % (on_page, PAGE_TOTAL))
    for region in REGIONS:
        if declared.get(region) != counted[region]:
            raise SystemExit('%s: tally says %s but the page holds %d'
                             % (region, declared.get(region), counted[region]))


LEAD_W = 470
LEAD_H = 205


def compose():
    """Lay out the whole broadsheet into `frame`."""
    global frame
    frame = bytearray(bytes(PAPER) * (W * H * 3))

    if FONT_BLOB:
        fonts['sans'] = open_font_blob(FONT_BLOB)
    else:
        raise SystemExit('gen/blobs.py missing: no embedded type to set')
    audit_page()

    leads = STORIES['leads']
    columns = STORIES['columns']
    wire = STORIES['wire']

    # masthead
    banner_w = measure(BANNER, 34)
    draw_text(BANNER, (W - banner_w) / 2, 62, 34, BODY_INK)
    rule(28, W - 28, 78, BODY_INK, 3)
    edition_w = measure(EDITION_LINE, 11, 0.5)
    draw_text(EDITION_LINE, (W - edition_w) / 2, 100, 11, ACCENT, 0.5)
    rule(28, W - 28, 112, RULES, 1)

    # summary strip
    tally_w = measure(TALLY, 12, 0.3)
    draw_text(TALLY, (W - tally_w) / 2, 128, 12, FADED, 0.3)
    rule(28, W - 28, 138, BODY_INK, 1)

    # four lead panels, 2 x 2
    lefts = [32, 522]
    tops = [152, 372]
    for idx, lead in enumerate(leads):
        lx = lefts[idx % 2]
        ty = tops[idx // 2]
        panel(lx, ty, lx + LEAD_W, ty + LEAD_H - 5, PANEL)
        rule(lx, lx + LEAD_W, ty, BODY_INK, 1)
        rule(lx, lx + LEAD_W, ty + LEAD_H - 5, BODY_INK, 1)
        draw_text(lead['tag'], lx + 12, ty + 18, 10, ACCENT, 0.4)
        fig_w = measure(lead['fig'], 38)
        draw_text(lead['fig'], lx + LEAD_W - 12 - fig_w, ty + 50, 38, BODY_INK)
        draw_map(lx + LEAD_W - 64, ty + 150, 104, 88, lead['marker'])
        title_lines = fold(lead['head'], 16, 350, 2)
        line_y = ty + 46
        for one in title_lines:
            draw_text(one, lx + 12, line_y, 16, HEAD_INK)
            line_y += 21
        copy_lines = fold(lead['copy'], 10, 360, 6)
        line_y = ty + 94
        for one in copy_lines:
            draw_text(one, lx + 12, line_y, 10, BODY_INK)
            line_y += 13

    rule(32, W - 32, 588, BODY_INK, 2)

    # eight-story column grid, 4 across by 2 rows (a 4x2 count laid out like
    # a 3x4 broadsheet grid: 24 wire cells below complete the 12-row field)
    col_tops = [602, 714]
    col_w = 232
    for idx, (place, story) in enumerate(columns):
        cx = 32 + (idx % 4) * 242
        cy = col_tops[idx // 4]
        draw_text(place, cx, cy + 12, 8, ACCENT, 0.3)
        rule(cx, cx + col_w, cy + 20, RULES, 1)
        story_lines = fold(story, 11, col_w, 3)
        line_y = cy + 34
        for one in story_lines:
            draw_text(one, cx, line_y, 11, HEAD_INK)
            line_y += 14

    rule(32, W - 32, 802, RULES, 1)

    # the wire: 24 short items, two columns of twelve
    draw_text('ALSO ON THE WIRE — 24 MORE', 32, 820, 11, BODY_INK, 0.5)
    rule(32, W - 32, 828, BODY_INK, 1)
    per_col = 12
    for idx, item in enumerate(wire):
        wx = 32 + (idx // per_col) * 486
        wy = 842 + (idx % per_col) * 10
        draw_text(item, wx, wy, 7, BODY_INK)

    # colophon
    rule(32, W - 32, 970, BODY_INK, 1)
    note_lines = fold(STORIES['colophon'], 7, 960, 3)
    line_y = 984
    for one in note_lines:
        draw_text(one, 32, line_y, 7, FADED)
        line_y += 10


# ---------------------------------------------------------------------------
# PNG encoding: filter row 0 on every scanline, zlib the scanlines, CRC
# chunks. Standard library only; identical bytes on every run.
# ---------------------------------------------------------------------------

def save_png(path):
    scanlines = bytearray()
    for y in range(H):
        scanlines.append(0)
        row_at = y * W * 3
        scanlines.extend(frame[row_at:row_at + W * 3])
    squeezed = zlib.compress(bytes(scanlines), 6)

    def piece(kind, body):
        head = struct.pack('>I', len(body)) + kind + body
        return head + struct.pack('>I', zlib.crc32(kind + body) & 0xFFFFFFFF)

    header = struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)
    blob = (b'\x89PNG\r\n\x1a\n' + piece(b'IHDR', header)
            + piece(b'IDAT', squeezed) + piece(b'IEND', b''))
    with open(path, 'wb') as fh:
        fh.write(blob)
    return len(blob)


def main():
    out_dir = os.path.join(HERE, 'out')
    os.makedirs(out_dir, exist_ok=True)
    target = '/output/entry.png' if os.path.isdir('/output') \
        else os.path.join(out_dir, 'entry.png')
    compose()
    written = save_png(target)
    print('wrote %s (%d bytes)' % (target, written))


if __name__ == '__main__':
    main()
