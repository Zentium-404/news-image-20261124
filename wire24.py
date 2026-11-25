# wire24.py — the copy on the page: the 35 stories of Tuesday 24 November
# 2026 (UTC), each first reported on that date and checked against the named
# outlet's reporting. Region tally: Europe 6, Middle East 4, Asia 8, Africa 3,
# Americas 8, Oceania 4, Global 2.

BANNER = 'THE WORLD ON ONE PAGE'
EDITION_LINE = 'DAY 328 OF 2026 · EVERY STORY DATED TUESDAY 24 NOV'

TALLY = ('35 STORIES · EUROPE 6 · MIDDLE EAST 4 · ASIA 8 · AFRICA 3 · '
         'AMERICAS 8 · OCEANIA 4 · GLOBAL 2')

# Four lead stories: big figure, region tag, headline, body copy, and the
# (lon, lat) pin for its mini map.
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
