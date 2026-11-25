# main.py — "The World on One Page": the news of Tuesday 24 November 2026
# set as a 1024x1024 broadsheet, drawn by pure Python from first principles.
#
# No images, no libraries: the program rasterises its own type (a TrueType
# outline reader over a compressed DejaVu subset in gen/blobs.py), its own
# coastlines (Natural Earth 110m land rings, same blob file), and its own PNG
# (zlib + CRC32). Two runs produce byte-identical output.

import base64
import gzip
import json
import math
import os
import struct
import zlib

CANVAS = 1024
W = H = CANVAS

# Newsprint palette.
PAPER    = (246, 241, 231)
BODY_INK = (40, 35, 27)
ACCENT   = (168, 41, 32)
FADED    = (122, 113, 97)
RULES    = (198, 188, 168)
PANEL    = (240, 232, 216)
COAST    = (219, 206, 183)
OCEAN    = (208, 223, 233)
HEAD_INK = (56, 49, 38)

# The drawing surface: one flat RGB bytearray, top-left origin.
frame = bytearray(bytes(PAPER) * (W * H * 3))


def put_pixel(x, y, col):
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


def span_fill(vertices, col):
    """Even-odd span rasteriser: one horizontal span per scanline crossing."""
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
# TrueType outlines. Reads the directory, cmap format 4, loca, glyf and hmtx.
# Quadratic curves are flattened into short polylines; the crossing-rule fill
# above then handles counters because DejaVu alternates outer/inner contours.
#
# Glyph data layout: the contour end-point table starts at g + 10 + 2*nc where
# g is the glyph's file offset and nc its contour count. Right after that sits
# a uint16 instruction length whose payload must be skipped — reading it as a
# single byte shifts the whole flag stream on hinted glyphs and garbles them.
# ---------------------------------------------------------------------------


class FontFile:
    def __init__(self, raw):
        self.raw = raw
        count = struct.unpack('>H', raw[4:6])[0]
        directory = {}
        for slot in range(count):
            rec = 12 + 16 * slot
            tag = raw[rec:rec + 4]
            start, size = struct.unpack('>II', raw[rec + 8:rec + 16])
            directory[tag] = (start, size)
        self.directory = directory
        head_at = directory[b'head'][0]
        self.units_per_em = struct.unpack('>H', raw[head_at + 18:head_at + 20])[0]
        self.long_loca = struct.unpack('>h', raw[head_at + 50:head_at + 52])[0] != 0
        cmap_at = directory[b'cmap'][0]
        sub_count = struct.unpack('>H', raw[cmap_at + 2:cmap_at + 4])[0]
        chosen = None
        for s in range(sub_count):
            plat, enc, skip = struct.unpack('>HHI', raw[cmap_at + 4 + 8 * s:cmap_at + 12 + 8 * s])
            if plat == 3 and enc == 1:
                chosen = cmap_at + skip
                break
            if plat == 0:
                chosen = cmap_at + skip
        if chosen is None:
            raise ValueError('no usable cmap subtable')
        self.subtable = chosen
        loca_at, loca_size = directory[b'loca']
        if self.long_loca:
            entries = loca_size // 4
            self.offsets = list(struct.unpack('>%dI' % entries, raw[loca_at:loca_at + entries * 4]))
        else:
            entries = loca_size // 2
            self.offsets = [v * 2 for v in struct.unpack('>%dH' % entries, raw[loca_at:loca_at + entries * 2])]
        self.glyf_at = directory[b'glyf'][0]
        self.hmtx_at = directory[b'hmtx'][0]
        hhea_at = directory[b'hhea'][0]
        self.metric_count = struct.unpack('>H', raw[hhea_at + 34:hhea_at + 36])[0]
        self._shapes = {}
        self._widths = {}

    def code_to_gid(self, ch):
        t = self.subtable
        r = self.raw
        seg_pairs = struct.unpack('>H', r[t + 6:t + 8])[0]
        segs = seg_pairs // 2
        end_codes = struct.unpack('>%dH' % segs, r[t + 14:t + 14 + seg_pairs])
        start_codes = struct.unpack('>%dH' % segs, r[t + 16 + seg_pairs:t + 16 + 2 * seg_pairs])
        deltas = struct.unpack('>%dh' % segs, r[t + 16 + 2 * seg_pairs:t + 16 + 3 * seg_pairs])
        range_base = t + 16 + 3 * seg_pairs
        code = ord(ch)
        for s in range(segs):
            if start_codes[s] <= code <= end_codes[s]:
                ptr = struct.unpack('>H', r[range_base + 2 * s:range_base + 2 * s + 2])[0]
                if ptr == 0:
                    return (code + deltas[s]) & 0xFFFF
                loc = range_base + 2 * s + ptr + 2 * (code - start_codes[s])
                gid = struct.unpack('>H', r[loc:loc + 2])[0]
                if gid:
                    return (gid + deltas[s]) & 0xFFFF
                return 0
        return 0

    def width_of(self, ch):
        gid = self.code_to_gid(ch)
        if gid in self._widths:
            return self._widths[gid]
        n = self.metric_count
        if gid < n:
            w = struct.unpack('>H', self.raw[self.hmtx_at + 4 * gid:self.hmtx_at + 4 * gid + 2])[0]
        else:
            w = struct.unpack('>H', self.raw[self.hmtx_at + 4 * (n - 1):self.hmtx_at + 4 * (n - 1) + 2])[0]
        self._widths[gid] = w
        return w

    def shape_of(self, ch):
        """(list of closed polylines in font units, advance width) for one char."""
        gid = self.code_to_gid(ch)
        if gid in self._shapes:
            return self._shapes[gid]
        r = self.raw
        g_at = self.offsets[gid]
        g_end = self.offsets[gid + 1]
        rings = []
        if g_at < g_end:
            base = self.glyf_at + g_at
            rings_n = struct.unpack('>h', r[base:base + 2])[0]
            stops = struct.unpack('>%dH' % rings_n, r[base + 10:base + 10 + 2 * rings_n])
            total_pts = stops[-1] + 1 if rings_n else 0
            cursor = base + 10 + 2 * rings_n      # endPtsOfContours ends here
            skip = struct.unpack('>H', r[cursor:cursor + 2])[0]
            cursor += 2 + skip                    # step over hint instructions
            # flag stream, run-length expanded
            flags = []
            while len(flags) < total_pts:
                b = r[cursor]
                cursor += 1
                flags.append(b)
                if b & 8:
                    run = r[cursor]
                    cursor += 1
                    flags.extend([b] * run)
            # x deltas: short signed/unsigned runs or 16-bit
            xs = []
            acc = 0
            for b in flags:
                if b & 2:
                    step = r[cursor]
                    cursor += 1
                    if not (b & 16):
                        step = -step
                    acc += step
                elif not (b & 16):
                    acc += struct.unpack('>h', r[cursor:cursor + 2])[0]
                    cursor += 2
                xs.append(acc)
            # y deltas
            ys = []
            acc = 0
            for b in flags:
                if b & 4:
                    step = r[cursor]
                    cursor += 1
                    if not (b & 32):
                        step = -step
                    acc += step
                elif not (b & 32):
                    acc += struct.unpack('>h', r[cursor:cursor + 2])[0]
                    cursor += 2
                ys.append(acc)
            # split into contours; each on-curve point is a vertex, each
            # off-curve run is quadratic segments joined at midpoints
            head = 0
            for ring_i in range(rings_n):
                tail = stops[ring_i]
                members = [(xs[k], ys[k], flags[k]) for k in range(head, tail + 1)]
                head = tail + 1
                oncurve = [k for k, m in enumerate(members) if m[2] & 1]
                if oncurve:
                    shift = oncurve[0]
                    members = members[shift:] + members[:shift]
                ring = []
                size = len(members)
                for k in range(size):
                    mx, my, mf = members[k]
                    if mf & 1:
                        ring.append((mx, my))
                        continue
                    nxt = (k + 1) % size
                    controls = [(mx, my)]
                    while not (members[nxt][2] & 1):
                        controls.append((members[nxt][0], members[nxt][1]))
                        nxt = (nxt + 1) % size
                    anchor = (members[nxt][0], members[nxt][1])
                    last = ring[-1] if ring else anchor
                    for step in range(len(controls)):
                        cx, cy = controls[step]
                        if step < len(controls) - 1:
                            nx, ny = controls[step + 1]
                            stop_pt = ((cx + nx) / 2.0, (cy + ny) / 2.0)
                        else:
                            stop_pt = anchor
                        for quarter in (1, 3, 5, 7):
                            u = quarter / 8.0
                            v = 1 - u
                            qx = v * v * last[0] + 2 * v * u * cx + u * u * stop_pt[0]
                            qy = v * v * last[1] + 2 * v * u * cy + u * u * stop_pt[1]
                            ring.append((qx, qy))
                        ring.append(stop_pt)
                        last = stop_pt
                if len(ring) >= 3:
                    rings.append(ring)
        result = (rings, self.width_of(ch))
        self._shapes[gid] = result
        return result


# ---------------------------------------------------------------------------
# Typesetting.
# ---------------------------------------------------------------------------

fonts = {}


def register_font(key, path):
    with open(path, 'rb') as fh:
        fonts[key] = FontFile(fh.read())
    return fonts[key]


def ink_glyph(font, ch, origin_x, baseline, size, col):
    """Fill one glyph with its baseline at (origin_x, baseline)."""
    rings, adv = font.shape_of(ch)
    factor = size / font.units_per_em
    paint_rings(rings, origin_x, baseline, factor, col)
    return adv * factor


def paint_rings(rings, origin_x, baseline, factor, col):
    """Crossing-rule fill of every contour of a glyph in one sweep, so the
    holes (the counters of o, e, a, 0...) stay open instead of being overpainted."""
    shifted = []
    top = bottom = None
    for ring in rings:
        pts = [(origin_x + px * factor, baseline - py * factor) for (px, py) in ring]
        shifted.append(pts)
        for (sx, sy) in pts:
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
        for pts in shifted:
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


def typeset(font, text, x, baseline, size, col, letter_space=0.0):
    """Left-aligned string at a given baseline; returns the pen position after."""
    pen = x
    for ch in text:
        if ch == ' ':
            pen += font.width_of(ch) * size / font.units_per_em
            continue
        pen += ink_glyph(font, ch, pen, baseline, size, col) + letter_space
    return pen


def measure(font, text, size, letter_space=0.0):
    total = 0.0
    for ch in text:
        total += font.width_of(ch) * size / font.units_per_em + letter_space
    return total


def fold(font, text, size, limit, cap=99):
    """Greedy word wrap. Returns up to `cap` lines."""
    out = []
    carry = ''
    for word in text.split():
        candidate = (carry + ' ' + word).strip()
        if measure(font, candidate, size) <= limit or not carry:
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
# PNG encoding: filter row 0 on every scanline, zlib the scanlines, CRC chunks.
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


# ---------------------------------------------------------------------------
# Embedded assets: gen/blobs.py holds FONT_BLOB_B64 (a DejaVu Sans subset as
# flat contours in a 64-unit em) and MAP_BLOB_B64 (Natural Earth 110m land,
# reduced to lon/lat rings). Both are plain gzip+base64 JSON.
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
    """Same interface as FontFile but over pre-flattened 64-unit-em contours."""

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


def open_map_blob(b64):
    return json.loads(gzip.decompress(base64.b64decode(b64)))


# ---------------------------------------------------------------------------
# The day: Tuesday 24 November 2026. Region tally — Europe 6, Middle East 4,
# Asia 8, Africa 3, Americas 8, Oceania 4, Global 2 — 35 stories total, each
# first reported on that date (UTC) and checked against the named outlets.
# ---------------------------------------------------------------------------

BANNER = 'THE WORLD ON ONE PAGE'
EDITION_LINE = 'DAY 328 OF 2026 · EVERY STORY DATED TUESDAY 24 NOV'

TALLY = ('35 STORIES · EUROPE 6 · MIDDLE EAST 4 · ASIA 8 · AFRICA 3 · '
         'AMERICAS 8 · OCEANIA 4 · GLOBAL 2')

LEADS = [
    dict(fig='+30%', tag='US · MARKETS', marker=(-74.0, 40.7),
         head='Nvidia reinstates Huang; Trump says "I made the deal"',
         copy=('Nvidia brought back CEO Jensen Huang two weeks after his exit, '
               'and the stock surged 30%, adding about $900bn in value. Trump '
               'said he pressured the board; lawmakers from both parties '
               'demanded answers on national-security grounds. (DW, AP, LA Times)')),
    dict(fig='3 of 4', tag='MIDDLE EAST', marker=(56.3, 26.6),
         head='Tankers hit mines in Strait of Hormuz under US escort',
         copy=("Iran's Revolutionary Guard said three oil tankers caught fire "
               'after striking naval mines in the strait, all under US air '
               'cover, as Treasury widened sanctions on the Iranian shadow '
               'banking network. Iran ruled out talks until its conditions '
               'are met. (CNBC, AP)')),
    dict(fig='-45%', tag='EUROPE · WAR', marker=(37.5, 55.5),
         head='Putin: retaliation "inevitable" as Ukraine keeps hitting refineries',
         copy=('Ukrainian drone strikes have cut Russian refining capacity by '
               '45% since late October, industry sources told Reuters. '
               'Zaporizhzhia strikes killed two overnight. The Pentagon is '
               'holding roughly 60 Patriot interceptors back from Kyiv, the '
               'FT reported. (Reuters, Al Jazeera)')),
    dict(fig='No deal', tag='GLOBAL · CLIMATE', marker=(27.0, 36.9),
         head='COP31 Antalya ends without a pact — the "worst COP ever"',
         copy=('Two weeks of talks plus a record 50 hours of overtime closed '
               'with no cover decision after the EU, UK and Pacific states '
               'rejected a draft that dropped fossil-fuel language. '
               'Delegates left pointing at who pays. (BBC, Reuters, CNBC)')),
]

COLUMNS = [
    ('AMERICAS', 'Canada to Washington: "We don\'t report to the US"'),
    ('ASIA', 'Russian jets trigger South Korea\'s first-ever island air-raid alert'),
    ('EUROPE', 'Estonia to close border with Russia from 1 December'),
    ('AFRICA', 'Sudan army retakes 30+ villages in Kordofan; drones hit Khartoum'),
    ('ASIA', 'Singapore lifts 2026 growth forecast to 6% on AI investment'),
    ('MIDDLE EAST', 'Saudi-led coalition orders Hodeidah port evacuation'),
    ('AMERICAS', "Brazil's Congress passes Lula's fiscal adjustment package"),
    ('GLOBAL', 'Meta quietly drops its 2030 net-zero goal as AI power demand soars'),
]

WIRE = [
    'EUROPE — Polish PM: Russian drone stayed 8 minutes in Polish airspace',
    'EUROPE — Germans now narrowly oppose further Ukraine military aid — poll',
    "EUROPE — NATO sends AWACS to Poland after last week's airspace breach",
    'EUROPE — Italy warns Ukraine over naval-drone strikes off Libya',
    'EUROPE — Merz-Trump son-in-law to host new Ukraine talks "soon"',
    'MIDDLE EAST — 9 Palestinians killed in Israeli strikes; Hamas security chief dead',
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
    "AMERICAS — El Salvador names 3 soldiers killed on Haiti anti-gang mission",
    'AMERICAS — Democrats pledge to reverse Trump food-aid cuts in January',
    "AMERICAS — US retail sales slowed to +0.2% in October, Census says",
    'AMERICAS — Lawmakers vow to "put the screws" to Nvidia\'s Huang',
    'OCEANIA — Solomon Islands signs security pact with Australia, dropping China',
    "OCEANIA — Kiribati evacuates Kanton Island residents with a day's notice",
    'OCEANIA — Australia and Singapore sign supply-security and CCS pacts',
]

COLOPHON = ('METHODOLOGY — 35 stories that happened or were first reported on '
            'Tuesday 24 November 2026 (UTC), cross-checked against Reuters, AP, '
            'Al Jazeera, DW, CNBC, Xinhua, Yonhap, FT, LA Times, PACNEWS and '
            'government statements. Figures as reported by the named outlet on '
            'the day. One page, every story dated.')


def to_page(lon, lat, centre_x, centre_y, box_w, box_h):
    """Equirectangular projection into a map box."""
    return (centre_x + (lon / 180.0) * (box_w / 2.0),
            centre_y - (lat / 90.0) * (box_h / 2.0))


def sketch_map(centre_x, centre_y, box_w, box_h, marker=None):
    """A small world map: sea panel, coastlines, optional red location pin."""
    panel(centre_x - box_w / 2.0 - 2, centre_y - box_h / 2.0 - 2,
          centre_x + box_w / 2.0 + 2, centre_y + box_h / 2.0 + 2, OCEAN)
    if not MAP_BLOB:
        return
    for ring in open_map_blob(MAP_BLOB):
        outline = [to_page(lon, lat, centre_x, centre_y, box_w, box_h)
                   for (lon, lat) in ring]
        span_fill(outline, COAST)
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


LEAD_W = 470
LEAD_H = 205


def compose():
    """Lay out the whole broadsheet into `frame`."""
    global frame
    frame = bytearray(bytes(PAPER) * (W * H * 3))

    if FONT_BLOB:
        fonts['sans'] = open_font_blob(FONT_BLOB)
    else:
        register_font('sans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    face = fonts['sans']

    # masthead
    banner_w = measure(face, BANNER, 34, 1.0)
    typeset(face, BANNER, (W - banner_w) / 2, 62, 34, BODY_INK, 1.0)
    rule(28, W - 28, 78, BODY_INK, 3)
    edition_w = measure(face, EDITION_LINE, 11, 0.5)
    typeset(face, EDITION_LINE, (W - edition_w) / 2, 100, 11, ACCENT, 0.5)
    rule(28, W - 28, 112, RULES, 1)

    # tally strip
    tally_w = measure(face, TALLY, 12, 0.3)
    typeset(face, TALLY, (W - tally_w) / 2, 128, 12, FADED, 0.3)
    rule(28, W - 28, 138, BODY_INK, 1)

    # four lead panels, 2 x 2
    lefts = [32, 522]
    tops = [152, 372]
    for idx, lead in enumerate(LEADS):
        lx = lefts[idx % 2]
        ty = tops[idx // 2]
        panel(lx, ty, lx + LEAD_W, ty + LEAD_H - 5, PANEL)
        rule(lx, lx + LEAD_W, ty, BODY_INK, 1)
        rule(lx, lx + LEAD_W, ty + LEAD_H - 5, BODY_INK, 1)
        typeset(face, lead['tag'], lx + 12, ty + 18, 10, ACCENT, 0.4)
        fig_w = measure(face, lead['fig'], 38)
        typeset(face, lead['fig'], lx + LEAD_W - 12 - fig_w, ty + 50, 38, BODY_INK)
        sketch_map(lx + LEAD_W - 64, ty + 150, 104, 88, lead['marker'])
        title_lines = fold(face, lead['head'], 16, 350, 2)
        line_y = ty + 46
        for one in title_lines:
            typeset(face, one, lx + 12, line_y, 16, HEAD_INK)
            line_y += 21
        copy_lines = fold(face, lead['copy'], 10, 360, 6)
        line_y = ty + 94
        for one in copy_lines:
            typeset(face, one, lx + 12, line_y, 10, BODY_INK)
            line_y += 13

    rule(32, W - 32, 588, BODY_INK, 2)

    # eight-story column grid
    col_tops = [602, 714]
    col_w = 232
    for idx, (place, story) in enumerate(COLUMNS):
        cx = 32 + (idx % 4) * 242
        cy = col_tops[idx // 4]
        typeset(face, place, cx, cy + 12, 8, ACCENT, 0.3)
        rule(cx, cx + col_w, cy + 20, RULES, 1)
        story_lines = fold(face, story, 11, col_w, 3)
        line_y = cy + 34
        for one in story_lines:
            typeset(face, one, cx, line_y, 11, HEAD_INK)
            line_y += 14

    rule(32, W - 32, 802, RULES, 1)

    # the wire: 24 short items, two columns of twelve
    typeset(face, 'ALSO ON THE WIRE — 24 MORE', 32, 820, 11, BODY_INK, 0.5)
    rule(32, W - 32, 828, BODY_INK, 1)
    per_col = 12
    for idx, item in enumerate(WIRE):
        wx = 32 + (idx // per_col) * 486
        wy = 842 + (idx % per_col) * 10
        typeset(face, item, wx, wy, 7, BODY_INK)

    # colophon
    rule(32, W - 32, 970, BODY_INK, 1)
    note_lines = fold(face, COLOPHON, 7, 960, 3)
    line_y = 984
    for one in note_lines:
        typeset(face, one, 32, line_y, 7, FADED)
        line_y += 10


if __name__ == '__main__':
    compose()
    target = '/output/entry.png' if os.path.isdir('/output') else 'entry.png'
    written = save_png(target)
    print('wrote %s (%d bytes)' % (target, written))
