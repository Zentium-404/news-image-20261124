# main.py — THE WORLD ON ONE PAGE, Tuesday 24 November 2026.
#
# Stage 1 of 3: rendering engine. An RGB framebuffer, a scanline even-odd
# polygon fill, a minimal TrueType glyph-outline parser (cmap format 4, loca,
# glyf quadratic flattening, hmtx advances), text layout helpers, and a PNG
# writer. Stages 2 and 3 add data + the full page.
#
# Standard library only, Python 3.13 (runs on 3.11). Output: entry.png,
# 1024x1024 8-bit RGB.

import struct
import zlib

W = H = 1024

# --- palette -----------------------------------------------------------------
PAPER = (246, 241, 231)   # cream newsprint
INK   = (40, 35, 27)      # near-black ink
RED   = (168, 41, 32)     # signal red for accents and masthead rules
MUT   = (122, 113, 97)    # quiet grey-brown for small text
LINE  = (198, 188, 168)   # hairline rules
HEROT = (240, 232, 216)   # hero panel tint
LAND  = (219, 206, 183)   # map land
SEA   = (208, 223, 233)   # map sea
DARK  = (56, 49, 38)      # heavy headline ink

# --- framebuffer --------------------------------------------------------------
fb = bytearray(bytes(PAPER) * (W * H * 3))


def px(x, y, c):
    xi = int(x)
    yi = int(y)
    if 0 <= xi < W and 0 <= yi < H:
        i = (yi * W + xi) * 3
        fb[i] = c[0]
        fb[i + 1] = c[1]
        fb[i + 2] = c[2]


def hline(x0, x1, y, c, t=1):
    """Horizontal rule, t pixels thick."""
    if t == 1:
        y = int(y)
        if 0 <= y < H:
            xa = max(0, int(x0))
            xb = min(W - 1, int(x1))
            if xb < xa:
                return
            i = (y * W + xa) * 3
            fb[i:i + (xb - xa + 1) * 3] = bytes(c) * (xb - xa + 1)
        return
    for k in range(t):
        hline(x0, x1, y + k, c, 1)


def rect(x0, y0, x1, y1, c):
    xa = max(0, int(x0))
    xb = min(W - 1, int(x1))
    ya = max(0, int(y0))
    yb = min(H - 1, int(y1))
    if xb < xa or yb < ya:
        return
    row = bytes(c) * (xb - xa + 1)
    for y in range(ya, yb + 1):
        i = (y * W + xa) * 3
        fb[i:i + (xb - xa + 1) * 3] = row


# --- scanline even-odd polygon fill -------------------------------------------
def fill_polygon(pts, c):
    n = len(pts)
    if n < 3:
        return
    ys = [p[1] for p in pts]
    ymin = max(0, int(min(ys)))
    ymax = min(H - 1, int(max(ys)))
    if ymax < ymin:
        return
    edges = []
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if y1 != y2:
            edges.append((x1, y1, x2, y2))
    for row in range(ymin, ymax + 1):
        yc = row + 0.5
        xs = []
        for (ex1, ey1, ex2, ey2) in edges:
            if (ey1 <= yc < ey2) or (ey2 <= yc < ey1):
                t = (yc - ey1) / (ey2 - ey1)
                xs.append(ex1 + t * (ex2 - ex1))
        if not xs:
            continue
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = int(xs[k] + 0.5)
            xb = int(xs[k + 1] - 0.5)
            if xb < xa:
                xb = xa
            if xa < 0:
                xa = 0
            if xb > W - 1:
                xb = W - 1
            if xb < xa:
                continue
            i = (row * W + xa) * 3
            fb[i:i + (xb - xa + 1) * 3] = bytes(c) * (xb - xa + 1)


# --- TrueType glyph parser ------------------------------------------------------
# Minimal TrueType reader: cmap (format 4), glyf, loca, head, hmtx, hhea.
# Quadratic outlines are flattened to polylines and filled with the even-odd
# scanline above; DejaVu contours are laid out so even-odd reproduces counters
# (holes in o, e, a) correctly. Per the brief: offsets start at p = g + 10 +
# 2*nc (g = glyph offset, nc = contour count). The instruction-length field
# after the glyph header is a uint16 per the TrueType spec — a 1-byte read
# desyncs the flag stream on hinted glyphs.


class TTF:
    def __init__(self, data):
        self.d = data
        num_tables = struct.unpack('>H', data[4:6])[0]
        tables = {}
        for i in range(num_tables):
            o = 12 + 16 * i
            tag = data[o:o + 4]
            off, ln = struct.unpack('>II', data[o + 8:o + 16])
            tables[tag] = (off, ln)
        self.tables = tables
        ho = tables[b'head'][0]
        self.upem = struct.unpack('>H', data[ho + 18:ho + 20])[0]
        self.index_fmt = struct.unpack('>h', data[ho + 50:ho + 52])[0]
        co = tables[b'cmap'][0]
        ntab = struct.unpack('>H', data[co + 2:co + 4])[0]
        sub = None
        for i in range(ntab):
            pid, eid, soff = struct.unpack('>HHI', data[co + 4 + 8 * i:co + 12 + 8 * i])
            if pid == 3 and eid == 1:
                sub = co + soff
                break
            if pid == 0:
                sub = co + soff
        if sub is None:
            raise ValueError('no usable cmap subtable')
        self.cmap_sub = sub
        lo = tables[b'loca'][0]
        if self.index_fmt == 0:
            cnt = tables[b'loca'][1] // 2
            self.loca = [v * 2 for v in struct.unpack('>%dH' % cnt, data[lo:lo + cnt * 2])]
        else:
            cnt = tables[b'loca'][1] // 4
            self.loca = list(struct.unpack('>%dI' % cnt, data[lo:lo + cnt * 4]))
        self.glyf_off, _ = tables[b'glyf']
        self.hmtx_off, _ = tables[b'hmtx']
        hh = tables[b'hhea'][0]
        self.num_hmetrics = struct.unpack('>H', data[hh + 34:hh + 36])[0]
        self._c = {}
        self._ac = {}

    def glyph_index(self, ch):
        s = self.cmap_sub
        d = self.d
        seg_x2 = struct.unpack('>H', d[s + 6:s + 8])[0]
        seg = seg_x2 // 2
        ends = struct.unpack('>%dH' % seg, d[s + 14:s + 14 + seg_x2])
        starts = struct.unpack('>%dH' % seg, d[s + 16 + seg_x2:s + 16 + 2 * seg_x2])
        deltas = struct.unpack('>%dh' % seg, d[s + 16 + 2 * seg_x2:s + 16 + 3 * seg_x2])
        ro_base = s + 16 + 3 * seg_x2
        cp = ord(ch)
        for i in range(seg):
            if starts[i] <= cp <= ends[i]:
                ro = struct.unpack('>H', d[ro_base + 2 * i:ro_base + 2 * i + 2])[0]
                if ro == 0:
                    return (cp + deltas[i]) & 0xFFFF
                addr = ro_base + 2 * i + ro + 2 * (cp - starts[i])
                gid = struct.unpack('>H', d[addr:addr + 2])[0]
                if gid:
                    return (gid + deltas[i]) & 0xFFFF
                return 0
        return 0

    def advance(self, ch):
        gid = self.glyph_index(ch)
        if gid in self._ac:
            return self._ac[gid]
        n = self.num_hmetrics
        if gid < n:
            aw = struct.unpack('>H', self.d[self.hmtx_off + 4 * gid:self.hmtx_off + 4 * gid + 2])[0]
        else:
            aw = struct.unpack('>H', self.d[self.hmtx_off + 4 * (n - 1):self.hmtx_off + 4 * (n - 1) + 2])[0]
        self._ac[gid] = aw
        return aw

    def glyph_contours(self, ch):
        """Return (contours, advance); each contour is a flat polyline (x, y)."""
        gid = self.glyph_index(ch)
        if gid in self._c:
            return self._c[gid]
        g = self.loca[gid]
        g2 = self.loca[gid + 1]
        d = self.d
        contours = []
        if g >= g2:
            out = ([], self.advance(ch))
            self._c[gid] = out
            return out
        off = self.glyf_off + g
        nc = struct.unpack('>h', d[off:off + 2])[0]
        end_pts = struct.unpack('>%dH' % nc, d[off + 10:off + 10 + 2 * nc])
        npts = end_pts[-1] + 1 if nc else 0
        # header is 10 bytes; p = g + 10 + 2*nc lands on instructionLength
        p = off + 10 + 2 * nc
        ilen = struct.unpack('>H', d[p:p + 2])[0]
        p += 2 + ilen
        flags = []
        while len(flags) < npts:
            f = d[p]
            p += 1
            flags.append(f)
            if f & 8:
                rep = d[p]
                p += 1
                flags.extend([f] * rep)
        xs = []
        xv = 0
        for f in flags:
            if f & 2:
                dx = d[p]
                p += 1
                if not (f & 16):
                    dx = -dx
                xv += dx
            elif not (f & 16):
                xv += struct.unpack('>h', d[p:p + 2])[0]
                p += 2
            xs.append(xv)
        ys = []
        yv = 0
        for f in flags:
            if f & 4:
                dy = d[p]
                p += 1
                if not (f & 32):
                    dy = -dy
                yv += dy
            elif not (f & 32):
                yv += struct.unpack('>h', d[p:p + 2])[0]
                p += 2
            ys.append(yv)
        start = 0
        for ci in range(nc):
            end = end_pts[ci]
            idxs = list(range(start, end + 1))
            start = end + 1
            raw = [(xs[i], ys[i], flags[i]) for i in idxs]
            on = [k for k, r in enumerate(raw) if r[2] & 1]
            if on:
                k0 = on[0]
                raw = raw[k0:] + raw[:k0]
            poly = []
            ln = len(raw)
            for k in range(ln):
                x0, y0, f0 = raw[k]
                if f0 & 1:
                    poly.append((x0, y0))
                    continue
                j = (k + 1) % ln
                chain = [(x0, y0)]
                while not (raw[j][2] & 1):
                    chain.append((raw[j][0], raw[j][1]))
                    j = (j + 1) % ln
                anchor = (raw[j][0], raw[j][1])
                prev = poly[-1] if poly else anchor
                for q in range(len(chain)):
                    c = chain[q]
                    if q < len(chain) - 1:
                        nx, ny = chain[q + 1]
                        endp = ((c[0] + nx) / 2.0, (c[1] + ny) / 2.0)
                    else:
                        endp = anchor
                    for s in (1, 3, 5, 7):
                        t = s / 8.0
                        mt = 1 - t
                        bx = mt * mt * prev[0] + 2 * mt * t * c[0] + t * t * endp[0]
                        by = mt * mt * prev[1] + 2 * mt * t * c[1] + t * t * endp[1]
                        poly.append((bx, by))
                    poly.append(endp)
                    prev = endp
            if len(poly) >= 3:
                contours.append(poly)
        out = (contours, self.advance(ch))
        self._c[gid] = out
        return out


# --- text drawing ---------------------------------------------------------------
FONTS = {}


def load_font(name, path):
    with open(path, 'rb') as f:
        FONTS[name] = TTF(f.read())
    return FONTS[name]


def draw_glyph(fnt, ch, ox, oy, size, color):
    """Draw one glyph, baseline origin (ox, oy). Returns advance in px."""
    contours, adv = fnt.glyph_contours(ch)
    scale = size / fnt.upem
    fill_glyph(contours, ox, oy, scale, color)
    return adv * scale


def fill_glyph(contours, ox, oy, scale, color):
    """Even-odd fill across all contours of one glyph, single pass."""
    polys = []
    ymin, ymax = None, None
    for poly in contours:
        pts = [(ox + x * scale, oy - y * scale) for (x, y) in poly]
        polys.append(pts)
        for (x, y) in pts:
            if ymin is None or y < ymin:
                ymin = y
            if ymax is None or y > ymax:
                ymax = y
    if ymin is None:
        return
    y0 = max(0, int(ymin))
    y1 = min(H - 1, int(ymax))
    for row in range(y0, y1 + 1):
        yc = row + 0.5
        xs = []
        for pts in polys:
            n = len(pts)
            for i in range(n):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % n]
                if (y1 <= yc < y2) or (y2 <= yc < y1):
                    t = (yc - y1) / (y2 - y1)
                    xs.append(x1 + t * (x2 - x1))
        if not xs:
            continue
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = int(xs[k] + 0.5)
            xb = int(xs[k + 1] - 0.5)
            if xb < xa:
                xb = xa
            if xa < 0:
                xa = 0
            if xb > W - 1:
                xb = W - 1
            if xb < xa:
                continue
            i = (row * W + xa) * 3
            fb[i:i + (xb - xa + 1) * 3] = bytes(color) * (xb - xa + 1)


def draw_text(fnt, text, x, y, size, color, tracking=0.0):
    cx = x
    for ch in text:
        if ch == ' ':
            cx += fnt.advance(ch) * size / fnt.upem
            continue
        cx += draw_glyph(fnt, ch, cx, y, size, color) + tracking
    return cx


def text_width(fnt, text, size, tracking=0.0):
    w = 0.0
    for ch in text:
        w += fnt.advance(ch) * size / fnt.upem + tracking
    return w


def wrap_text(fnt, text, size, max_w, max_lines=99):
    words = text.split()
    lines = []
    cur = ''
    for wd in words:
        trial = (cur + ' ' + wd).strip()
        if text_width(fnt, trial, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    return lines


# --- PNG writer -------------------------------------------------------------------
def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        i = y * W * 3
        raw.extend(fb[i:i + W * 3])
    comp = zlib.compress(bytes(raw), 6)

    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', comp) + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)
    return len(png)


# --- stage 2: runtime blob loaders ------------------------------------------------
# The program runs with no network, so the glyph outlines (a DejaVu Sans
# subset re-encoded as flat contours in a 64-unit em) and the Natural Earth
# 110m land rings (lon/lat, reduced) are embedded as base64 gzip blobs in
# gen/blobs.py, packed from sources by gen_pack.py.

import base64
import gzip
import json
import math
import os

GEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen')

FONT_BLOB = None
MAP_BLOB = None


class PackedFont:
    """Duck-types TTF: contours pre-flattened in a 64-unit em, y-up."""

    def __init__(self, glyphs):
        self.glyphs = glyphs
        self.upem = 64.0

    def advance(self, ch):
        g = self.glyphs.get(ch)
        return g[1] if g else 32

    def glyph_contours(self, ch):
        g = self.glyphs.get(ch)
        if not g:
            return ([], 32)
        return (g[0], g[1])


def unpack_font(blob):
    data = json.loads(gzip.decompress(base64.b64decode(blob)))
    return {ch: (v[1:], v[0]) for ch, v in data.items()}


def unpack_map(blob):
    return json.loads(gzip.decompress(base64.b64decode(blob)))


def _load_blobs():
    global FONT_BLOB, MAP_BLOB
    gen = os.path.join(GEN_DIR, 'blobs.py')
    if os.path.exists(gen):
        ns = {}
        with open(gen) as fh:
            exec(compile(fh.read(), gen, 'exec'), ns)
        FONT_BLOB = ns['FONT_BLOB_B64']
        MAP_BLOB = ns['MAP_BLOB_B64']


_load_blobs()

# --- stage 3: the day's news, 35 stories ------------------------------------------
# Every story happened or was first reported on Tuesday 24 November 2026 UTC.
# Region counts: Europe 6, Middle East 4, Asia 8, Africa 3, Americas 8,
# Oceania 4, Global 2 = 35.

MASTHEAD = 'THE WORLD ON ONE PAGE'
DAYLINE = 'DAY 328 OF 2026 · EVERY STORY DATED TUESDAY 24 NOV'

SUMMARY = ('35 STORIES · EUROPE 6 · MIDDLE EAST 4 · ASIA 8 · AFRICA 3 · '
           'AMERICAS 8 · OCEANIA 4 · GLOBAL 2')

# 4 heroes: big figure, region tag, headline, body, map marker (lon, lat)
HEROES = [
    dict(fig='+30%', tag='US · MARKETS', dot=(-74.0, 40.7),
         head='Nvidia reinstates Huang; Trump says "I made the deal"',
         body=('Nvidia brought back CEO Jensen Huang two weeks after his exit, '
               'and the stock surged 30%, adding about $900bn in value. Trump '
               'said he pressured the board; lawmakers from both parties '
               'demanded answers on national-security grounds. (DW, AP, LA Times)')),
    dict(fig='3 of 4', tag='MIDDLE EAST', dot=(56.3, 26.6),
         head='Tankers hit mines in Strait of Hormuz under US escort',
         body=("Iran's Revolutionary Guard said three oil tankers caught fire "
               'after striking naval mines in the strait, all under US air '
               'cover, as Treasury widened sanctions on the Iranian shadow '
               'banking network. Iran ruled out talks until its conditions '
               'are met. (CNBC, AP)')),
    dict(fig='-45%', tag='EUROPE · WAR', dot=(37.5, 55.5),
         head='Putin: retaliation "inevitable" as Ukraine keeps hitting refineries',
         body=('Ukrainian drone strikes have cut Russian refining capacity by '
               '45% since late October, industry sources told Reuters. '
               'Zaporizhzhia strikes killed two overnight. The Pentagon is '
               'holding roughly 60 Patriot interceptors back from Kyiv, the '
               'FT reported. (Reuters, Al Jazeera)')),
    dict(fig='No deal', tag='GLOBAL · CLIMATE', dot=(27.0, 36.9),
         head='COP31 Antalya ends without a pact — the "worst COP ever"',
         body=('Two weeks of talks plus a record 50 hours of overtime closed '
               'with no cover decision after the EU, UK and Pacific states '
               'rejected a draft that dropped fossil-fuel language. '
               'Delegates left pointing at who pays. (BBC, Reuters, CNBC)')),
]

GRID = [
    ('AMERICAS', 'Canada to Washington: "We don\'t report to the US"'),
    ('ASIA', 'Russian jets trigger South Korea\'s first-ever island air-raid alert'),
    ('EUROPE', 'Estonia to close border with Russia from 1 December'),
    ('AFRICA', 'Sudan army retakes 30+ villages in Kordofan; drones hit Khartoum'),
    ('ASIA', 'Singapore lifts 2026 growth forecast to 6% on AI investment'),
    ('MIDDLE EAST', 'Saudi-led coalition orders Hodeidah port evacuation'),
    ('AMERICAS', "Brazil's Congress passes Lula's fiscal adjustment package"),
    ('GLOBAL', 'Meta quietly drops its 2030 net-zero goal as AI power demand soars'),
]

ALSO = [
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

FOOTER = ('METHODOLOGY — 35 stories that happened or were first reported on '
          'Tuesday 24 November 2026 (UTC), cross-checked against Reuters, AP, '
          'Al Jazeera, DW, CNBC, Xinhua, Yonhap, FT, LA Times, PACNEWS and '
          'government statements. Figures as reported by the named outlet on '
          'the day. One page, every story dated.')


# --- map projection ----------------------------------------------------------------
def project_equirect(lon, lat, cx, cy, w, h):
    px_x = cx + (lon / 180.0) * (w / 2.0)
    px_y = cy - (lat / 90.0) * (h / 2.0)
    return px_x, px_y


def draw_world_map(cx, cy, w, h, dot=None):
    """Draw land polygons from the packed blob into a box; optional marker."""
    rect(cx - w / 2.0 - 2, cy - h / 2.0 - 2, cx + w / 2.0 + 2, cy + h / 2.0 + 2, SEA)
    if not MAP_BLOB:
        return
    for ring in unpack_map(MAP_BLOB):
        pts = [project_equirect(lon, lat, cx, cy, w, h) for (lon, lat) in ring]
        fill_polygon(pts, LAND)
    if dot is not None:
        dlon, dlat = dot
        dx, dy = project_equirect(dlon, dlat, cx, cy, w, h)
        dx = min(max(dx, cx - w / 2.0 + 4), cx + w / 2.0 - 4)
        dy = min(max(dy, cy - h / 2.0 + 4), cy + h / 2.0 - 4)
        for r in (5, 4, 3):
            for a in range(0, 360, 30):
                for rr in range(r):
                    px(dx + rr * math.cos(math.radians(a)),
                       dy + rr * math.sin(math.radians(a)), RED)


# --- page layout ---------------------------------------------------------------------
HERO_BOX_W = 470
HERO_BOX_H = 205


def render_page():
    """Compose the whole broadsheet into the framebuffer."""
    global fb
    fb = bytearray(bytes(PAPER) * (W * H * 3))

    if FONT_BLOB:
        FONTS['sans'] = PackedFont(unpack_font(FONT_BLOB))
    else:
        load_font('sans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    f = FONTS['sans']

    # ---- masthead ----
    mw = text_width(f, MASTHEAD, 34, 1.0)
    draw_text(f, MASTHEAD, (W - mw) / 2, 62, 34, INK, 1.0)
    hline(28, W - 28, 78, INK, 3)
    lw = text_width(f, DAYLINE, 11, 0.5)
    draw_text(f, DAYLINE, (W - lw) / 2, 100, 11, RED, 0.5)
    hline(28, W - 28, 112, LINE, 1)

    # ---- summary strip ----
    sw = text_width(f, SUMMARY, 12, 0.3)
    draw_text(f, SUMMARY, (W - sw) / 2, 128, 12, MUT, 0.3)
    hline(28, W - 28, 138, INK, 1)

    # ---- heroes: 2 x 2 ----
    hx = [32, 522]
    hy = [152, 372]
    for i, hero in enumerate(HEROES):
        x0 = hx[i % 2]
        y0 = hy[i // 2]
        rect(x0, y0, x0 + HERO_BOX_W, y0 + HERO_BOX_H - 5, HEROT)
        hline(x0, x0 + HERO_BOX_W, y0, INK, 1)
        hline(x0, x0 + HERO_BOX_W, y0 + HERO_BOX_H - 5, INK, 1)
        draw_text(f, hero['tag'], x0 + 12, y0 + 18, 10, RED, 0.4)
        fw = text_width(f, hero['fig'], 38)
        draw_text(f, hero['fig'], x0 + HERO_BOX_W - 12 - fw, y0 + 50, 38, INK)
        # mini map, bottom-right
        draw_world_map(x0 + HERO_BOX_W - 64, y0 + 150, 104, 88, hero['dot'])
        # headline, max 2 lines, left of the map column
        lines = wrap_text(f, hero['head'], 16, 350, 2)
        yy = y0 + 46
        for ln in lines:
            draw_text(f, ln, x0 + 12, yy, 16, DARK)
            yy += 21
        # body
        blines = wrap_text(f, hero['body'], 10, 360, 6)
        yy = y0 + 94
        for ln in blines:
            draw_text(f, ln, x0 + 12, yy, 10, INK)
            yy += 13

    hline(32, W - 32, 588, INK, 2)

    # ---- 8-story grid: 4 cols x 2 rows ----
    gy = [602, 714]
    gw = 232
    for i, (tag, head) in enumerate(GRID):
        col = i % 4
        row = i // 4
        x0 = 32 + col * 242
        y0 = gy[row]
        draw_text(f, tag, x0, y0 + 12, 8, RED, 0.3)
        hline(x0, x0 + gw, y0 + 20, LINE, 1)
        lines = wrap_text(f, head, 11, gw, 3)
        yy = y0 + 34
        for ln in lines:
            draw_text(f, ln, x0, yy, 11, DARK)
            yy += 14

    hline(32, W - 32, 802, LINE, 1)

    # ---- ALSO list: 2 columns of 12 ----
    draw_text(f, 'ALSO ON THE WIRE — 24 MORE', 32, 820, 11, INK, 0.5)
    hline(32, W - 32, 828, INK, 1)
    half = 12
    for i, item in enumerate(ALSO):
        col = i // half
        row = i % half
        x0 = 32 + col * 486
        y0 = 842 + row * 10
        draw_text(f, item, x0, y0, 7, INK)

    # ---- footer ----
    hline(32, W - 32, 970, INK, 1)
    flines = wrap_text(f, FOOTER, 7, 960, 3)
    yy = 984
    for ln in flines:
        draw_text(f, ln, 32, yy, 7, MUT)
        yy += 10


if __name__ == '__main__':
    render_page()
    out = '/output/entry.png' if os.path.isdir('/output') else 'entry.png'
    n = write_png(out)
    print('wrote %s (%d bytes)' % (out, n))
