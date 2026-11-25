# checkpage.py — the broadsheet audits itself before it draws.
#
# The page is assembled from a fixed pool of copy (wire24.py) onto a fixed
# layout grid, so almost every mistake is a counting mistake: a story dropped
# from a list, a region label that no longer matches the tally strip, a
# headline set too large for its column. Auditing those here turns a silently
# wrong page into a loud one.

from wire24 import COLUMNS, LEADS, TALLY, WIRE

REGIONS = ('EUROPE', 'MIDDLE EAST', 'ASIA', 'AFRICA', 'AMERICAS', 'OCEANIA', 'GLOBAL')

PAGE_TOTAL = 35

# Layout constants mirrored from main.py: the audit measures copy against the
# same column widths the compositor will use, so they must stay in step.
LEAD_HEAD_SIZE, LEAD_HEAD_W, LEAD_HEAD_LINES = 16, 350, 2
COLUMN_SIZE, COLUMN_W, COLUMN_LINES = 11, 232, 3
WIRE_SIZE, WIRE_W = 7, 486


def declared_tally():
    """Parse 'EUROPE 6 · ASIA 8 ...' out of the printed tally strip."""
    found = {}
    for chunk in TALLY.split('·'):
        bits = chunk.strip().split()
        if len(bits) >= 2 and bits[-1].isdigit():
            name = ' '.join(bits[:-1])
            if name in REGIONS:
                found[name] = int(bits[-1])
    return found


def counted_stories():
    """Count the stories actually on the page, by region.

    Leads carry tags like 'US · MARKETS' or 'EUROPE · WAR': the region is the
    first separated word that names one of the REGIONS. A lead tagged
    'GLOBAL · CLIMATE' counts under GLOBAL; a purely national tag counts
    nowhere, which the page-total check then catches.
    """
    tally = dict.fromkeys(REGIONS, 0)
    for lead in LEADS:
        for word in lead['tag'].split('·'):
            word = word.strip()
            if word in REGIONS:
                tally[word] += 1
                break
    for place, _story in COLUMNS:
        if place in tally:
            tally[place] += 1
    for item in WIRE:
        head = item.split('—')[0].strip()
        if head in tally:
            tally[head] += 1
    return tally


def audit(face, measure, fold):
    """Raise SystemExit if the page would contradict itself; otherwise pass."""
    declared = declared_tally()
    counted = counted_stories()
    on_page = sum(counted.values())
    if on_page != PAGE_TOTAL:
        raise SystemExit('page holds %d stories, expected %d' % (on_page, PAGE_TOTAL))
    for region in REGIONS:
        if declared.get(region) != counted[region]:
            raise SystemExit('%s: tally says %s but the page holds %d'
                             % (region, declared.get(region), counted[region]))
    for lead in LEADS:
        lines = fold(face, lead['head'], LEAD_HEAD_SIZE, LEAD_HEAD_W, LEAD_HEAD_LINES)
        if len(lines) > LEAD_HEAD_LINES:
            raise SystemExit('lead headline overruns its lines: %r' % lead['head'])
    for place, story in COLUMNS:
        lines = fold(face, story, COLUMN_SIZE, COLUMN_W, COLUMN_LINES)
        if len(lines) > COLUMN_LINES:
            raise SystemExit('%s story overruns its lines: %r' % (place, story))
    for item in WIRE:
        if measure(face, item, WIRE_SIZE) > WIRE_W:
            raise SystemExit('wire item runs past its column: %r' % item)
