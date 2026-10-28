#!/usr/bin/env python3
"""Build one categorized "Free TV" playlist from the free US channel lists, with one matching guide.

  python3 build.py [out_dir]     writes free-tv.m3u, guide.xml.gz and summary.txt (default: ./site)

Every source is read as plain text; nothing downloaded is run. A channel offered by several services is kept
once, from the first source in SOURCES that has it (the ones with a guide come first), and takes its category
from whichever copy has one. Edit CATEGORIES, RULES, LOCAL_KEEP or PLACES below to change the result.
"""
import gzip
import io
import re
import sys
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

PAGES = "https://astrodyneresearch.github.io/free-tv"
BUDDY = "https://raw.githubusercontent.com/BuddyChewChew/app-m3u-generator/main/playlists"
MJH = "https://github.com/matthuisman/i.mjh.nz/raw/master"
APS = "https://www.apsattv.com"

# (label, playlist, guide or None, category for channels the source leaves untagged). Earlier wins a duplicate.
SOURCES = [
    ("Pluto", f"{BUDDY}/plutotv_us.m3u", f"{MJH}/PlutoTV/us.xml.gz", None),
    ("Samsung", f"{BUDDY}/samsungtvplus_us.m3u", f"{MJH}/SamsungTVPlus/us.xml.gz", None),
    ("Roku", f"{BUDDY}/roku_all.m3u", f"{MJH}/Roku/all.xml.gz", None),
    ("Tubi", f"{BUDDY}/tubi_all.m3u", f"{BUDDY}/tubi_epg.xml", None),
    ("Plex", f"{BUDDY}/plex_us.m3u", f"{MJH}/Plex/us.xml.gz", None),
    ("Xumo", f"{APS}/xumo.m3u", None, None),
    ("Vizio", f"{APS}/vizio.m3u", None, None),
    ("LG", f"{APS}/uslg.m3u", None, None),
    ("TCL", f"{APS}/tclplus.m3u", None, None),
    ("Local Now", f"{APS}/localnow.m3u", None, None),
    ("Distro", f"{APS}/distro.m3u", None, None),
    ("Whale", f"{APS}/whaletvplus_us.m3u", None, None),
    ("Fire TV", f"{APS}/firetv.m3u", None, None),
    ("Tablo", f"{APS}/tablo.m3u", None, None),
    ("Cineverse", f"{APS}/cineverse.m3u", None, "Movies"),
    ("Free Live Sports", f"{APS}/freelivesports.m3u", None, "Sports"),
    ("Sports TV", f"{APS}/sportstv.m3u", None, "Sports"),
]

# The groups TiviMate shows, in this order.
CATEGORIES = ["News", "Local", "Sports", "Movies", "Drama & Crime", "Reality", "Comedy", "Classic TV",
              "Game Shows", "Food & Home", "Travel & Nature", "Entertainment", "Kids & Family", "Music",
              "Español", "International", "Other Cities"]

# A source's own group name, or failing that the channel's name, is matched against these in order.
RULES = [
    ("Español", r"espa|latino|spanish|en vivo|novela|\bcine\b|noticias|deportes|cl[aá]sico|familia|telemundo|internacional|ahora|bodas|raza|m[aá]s\b|viajar|naturaleza|\brcn\b|"
                r"canela|azteca|caso cerrado|\bideas en\b|\blatv\b|\bpara\b|\bde la\b|\bdel\b"),
    ("International", r"punjab|haryana|hindi|tamil|telugu|bangla|bengal|india|desi|bollywood|asia|kalyan|nakshatra|"
                      r"\b9x|\babp\b|afro|nollywood|africa|cctv|cgtn|arirang|mediacorp|chinese|kannada|tolly|zindagi|khabar|anand|jubao|mahua|sony|\baaj\b|kartavya|spokesman|krsna|trace uk|soleil|blossom|korea|k-?drama|arab|urdu|pakistan|filipino|pinoy|\bitv\b"),
    ("Local", r"\blocal\b|my city|more cities"),
    ("News", r"news|opinion|weather|politic|\bcnn\b|bloomberg|headlines|america's voice|newsmax|\bcheddar\b"),
    ("Sports", r"sport|fight|combat|wrestl|boxing|racing|golf|soccer|football|nfl|nba|mlb|nhl|poker|fishing|"
               r"hunting|\bufc\b|rugby|\baew\b|pickleball|tennis|\btour\b|locked on|\bf1\b|billiard|score|sooner|\bpga\b|\bwwe\b|motocross|surf|skate|\bski"),
    ("Kids & Family", r"kid|family|faith|\banime\b|cartoon|toon|junior|\bjr\b|baby|inspiration|garfield|smurf|mr\.? bean|"
                      r"rainbow|dino|fgteev|ryan|pok[eé]mon|lego|barney|teletubb|sesame|bluey|paw|tayo|caillou|baby shark"),
    ("Music", r"music|radio|concert|karaoke|\bhits\b|mood|ambian|relax|fireplace|aquarium|\bzen\b|slow ?tv|rlx|vinyl|stingray|hip-?hop|r&b|"
              r"\balternative\b|country network|\bvevo\b|\bmtv\b|\bxite\b|\bqello\b|jazz|classical|\brock\b"),
    ("Game Shows", r"game|competition|daytime|price is right|family feud|deal or no deal|jeopardy|wheel|match|press your luck"),
    ("Reality", r"reality|pop culture|creator|showtime at|masked singer|court|dr\.? phil|dr\.? pol|bar rescue|survivor|keeping up|love|bride|"
                r"below zero|housewives|kardashian|wetv|we tv|bravo|\be!|tlc|lifetime|real emergency|storage|pawn|"
                r"hoarders|intervention|catfish|ink master|top model|big brother|bachelor|shark tank|wild ?'n ?out"),
    ("Drama & Crime", r"crime|myster|dateline|nypd|thriller|drama|action|detective|cops|forensic|unsolved|murder|first 48|patrol|"
                      r"sheriff|lockup|\bcsi\b|ncis|law ?& ?order|criminal|heat of the night|practice|silent witness|"
                      r"new tricks|mi-5|baywatch|nip/tuck|degrassi|walker|\b24\b|\bfbi\b|\bcops\b|\b48 hours"),
    ("Movies", r"movie|film|cinema|romance|fright|\bsaw\b|western|horror|sci-?fi|cult|kung fu|grindhouse|monsters|stargate|\balien|35mm|"
               r"\bt2\b|scream|outlaw|magnolia|encore|flick|cinevault|filmrise|shout|\bmgm\b|samurai"),
    ("Classic TV", r"classic|retro|replay|vintage|\b[5-9]0s\b|nostalg"),
    ("Comedy", r"comedy|sitcom|laugh|funny|stand-?up|three's company|carson|green acres|love boat|cheers|"
               r"seinfeld|office|parks|always sunny|30 rock|frasier|family guy|simpsons|futurama|south park|snl|conan"),
    ("Food & Home", r"food|cook|kitchen|chef|home|design|diy|garden|renovat|automotive|\bcar\b|motor|emeril|"
                    r"craft|mecum|power ?nation|bake|grill|bbq|recipe|tasty|martha|gordon|\bhgtv\b|house"),
    ("Travel & Nature", r"travel|nature|science|history|documentar|docs|docu|animal|\bdog|\bpets?\b|wild|discovery|explor|ocean|"
                        r"planet|space|learn|earth|genealogy|innovation|tech|beyond belief|unexplained|ancient|nasa|"
                        r"national geographic|nat ?geo|smithsonian|curiosity|pbs|bbc earth|weather"),
    ("Entertainment", r"entertainment|lifestyle|\btv\b|featured|recommended|black voices|new on"),
]

# Local stations from here go in "Local"; those from everywhere else go in "Other Cities", at the end.
LOCAL_KEEP = r"chicago|illinois|\bwgn\b|\bwls\b|\bwbbm\b|\bwmaq\b|\bwfld\b|\bwttw\b"
# A news channel named after one of these is a local station: states and the larger cities.
PLACES = (r"alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|"
          r"idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|"
          r"minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|"
          r"carolina|dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|tennessee|texas|utah|vermont|"
          r"virginia|washington|wisconsin|wyoming|atlanta|austin|baltimore|boston|buffalo|charlotte|chicago|"
          r"cincinnati|cleveland|columbus|dallas|denver|detroit|el paso|fort myers|fresno|houston|"
          r"indianapolis|jacksonville|kansas city|las vegas|los angeles|\bla\b|louisville|memphis|miami|"
          r"milwaukee|minneapolis|nashville|new orleans|norfolk|oakland|omaha|orlando|philadelphia|phoenix|"
          r"pittsburgh|portland|raleigh|sacramento|salt lake|san antonio|san diego|san francisco|bay area|"
          r"sarasota|seattle|spokane|st\.? louis|tampa|tucson|tulsa|twin cities|\bdc\b|\bnyc\b|bakersfield|"
          r"albuquerque|birmingham|boise|charleston|des moines|grand rapids|green bay|greenville|hartford|"
          r"honolulu|knoxville|lexington|little rock|madison|mobile|oklahoma city|providence|richmond|"
          r"rochester|savannah|syracuse|toledo|wichita|first coast|gulf coast|central valley|hudson valley")
# Names that mention a place but are national: never moved to a local group.
NATIONAL = r"\bpost\b|\btimes\b|journal|bloomberg|\bcnn\b|walker|ranger|\bvice\b|housewives|hot bench"
# "ABC7 Sarasota", "NBC 5 Chicago News", "FOX 32": a network affiliate.
AFFILIATE = r"\b(abc|nbc|cbs|fox|cw|pbs)\s?\d{1,2}\b"
# Groups dropped entirely.
DROP_GROUPS = r"shopping"
# A US station's call sign ("KSHB", "WGN-TV") or "FOX 2 Oakland": a local station, kept only for LOCAL_KEEP.
CALL_SIGN = r"^[KW][A-Z]{2,3}(-(TV|DT|CD))?\b|^(FOX|NBC|ABC|CBS) \d+ "
# Channels dropped by name: shopping and the services' own test or promo feeds.
DROP_NAMES = r"test channel|\bqvc\b|\bhsn\b|shop|spotlight|life's good on lg|^lg channels"

ATTR = re.compile(r'([\w-]+)="([^"]*)"')
SUFFIX = re.compile(r"\b(tv|channel|network|hd|us|usa|the|by .*|presented by .*)\b")


def fetch(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 free-tv-builder"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
        except Exception as e:  # noqa: BLE001 - a failed source is reported and skipped
            err = e
            time.sleep(5 * (i + 1))
    print(f"  ! {url}: {err}", file=sys.stderr)
    return None


def parse_m3u(text):
    """[(attrs, name, url)] from an #EXTM3U playlist."""
    out, info = [], None
    for line in text.splitlines():
        line = line.strip().lstrip("﻿")
        if line.startswith("#EXTINF"):
            cut = line.find(",", line.rfind('"') + 1)  # the name follows the comma after the last attribute
            info = (dict(ATTR.findall(line[:cut])), line[cut + 1:].strip())
        elif line and not line.startswith("#") and info:
            out.append((info[0], info[1], line))
            info = None
    return out


def key(name):
    """A channel's name reduced so the same channel on two services matches."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("+", " and ")
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = SUFFIX.sub(" ", s)
    return re.sub(r"\s+", "", s)


def classify(text):
    if not text:
        return None
    t = text.lower()
    t = re.sub(r"^.*?: ", "", t)  # "XUMO🇺🇸: News" -> "news"
    if t in ("undefined", "uncategorized (us)", "united states", "other", "freelivesports", "tv & entertainment"):
        return None if t != "tv & entertainment" else "Entertainment"
    for cat, pat in RULES:
        if re.search(pat, t):
            return cat
    return None


def place_local(name, cat):
    """A local station goes in "Local" when it is from LOCAL_KEEP, else in "Other Cities"; others keep cat."""
    newsy = cat in ("News", "Local") or re.search(r"news|weather", name, re.I)
    local = (cat == "Local" or re.search(CALL_SIGN, name) or re.search(AFFILIATE, name, re.I)
             or (newsy and re.search(PLACES, name, re.I) and not re.search(NATIONAL, name, re.I)))
    if not local:
        return cat
    return "Local" if re.search(LOCAL_KEEP, name, re.I) else "Other Cities"


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "site")
    out.mkdir(parents=True, exist_ok=True)
    chosen = {}      # key -> channel dict, first source wins
    counts = {}
    for label, url, guide, default in SOURCES:
        raw = fetch(url)
        if raw is None:
            counts[label] = "failed"
            continue
        entries = parse_m3u(raw.decode("utf-8", "replace"))
        # Some services put their own channel number before every name ("100 Sweet Escapes"): drop it.
        if entries and sum(bool(re.match(r"\d{1,4} \S", n)) for _, n, _ in entries) > 0.8 * len(entries):
            entries = [(a, re.sub(r"^\d{1,4} ", "", n), u) for a, n, u in entries]
        kept = 0
        for attrs, name, stream in entries:
            group = attrs.get("group-title", "")
            if re.search(DROP_GROUPS, group, re.I) or re.search(DROP_NAMES, name, re.I):
                continue
            cat = classify(group)
            if cat in (None, "Entertainment"):  # a general group says little: the name may say more
                cat = classify(name) or cat or default
            cat = place_local(name, cat)
            k = key(name) or name.lower()
            if k in chosen:
                if cat and chosen[k]["cat"] in (None, "Entertainment"):
                    chosen[k]["cat"] = cat
                continue
            chosen[k] = {"name": name, "url": stream, "cat": cat, "src": label,
                         "id": attrs.get("tvg-id", "") if guide else "", "logo": attrs.get("tvg-logo", ""),
                         "guide": guide}
            kept += 1
        counts[label] = f"{kept} of {len(entries)}"

    for ch in chosen.values():
        ch["cat"] = place_local(ch["name"], ch["cat"] or classify(ch["name"]) or "Entertainment")

    order = {c: i for i, c in enumerate(CATEGORIES)}
    chans = sorted(chosen.values(), key=lambda c: (order.get(c["cat"], 99), c["name"].lower()))

    lines = [f'#EXTM3U url-tvg="{PAGES}/guide.xml.gz" x-tvg-url="{PAGES}/guide.xml.gz"']
    for n, ch in enumerate(chans, 1):
        a = f'tvg-chno="{n}" tvg-name="{ch["name"]}"'
        if ch["id"]:
            a = f'tvg-id="{ch["id"]}" ' + a
        if ch["logo"]:
            a += f' tvg-logo="{ch["logo"]}"'
        a += f' group-title="{ch["cat"]}"'
        lines += [f'#EXTINF:-1 {a},{ch["name"]}', ch["url"]]
    (out / "free-tv.m3u").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # One guide with only the channels kept.
    want = {c["id"] for c in chans if c["id"]}
    root = ET.Element("tv", {"generator-info-name": "free-tv"})
    progs = 0
    for label, _, guide, _ in SOURCES:
        if not guide:
            continue
        raw = fetch(guide)
        if raw is None:
            continue
        for _, el in ET.iterparse(io.BytesIO(raw)):
            if el.tag in ("channel", "programme"):
                if (el.get("id") if el.tag == "channel" else el.get("channel")) in want:
                    root.append(el)
                    progs += el.tag == "programme"
                elif el.tag == "programme":
                    el.clear()
    with gzip.open(out / "guide.xml.gz", "wb", compresslevel=9) as f:
        ET.ElementTree(root).write(f, encoding="utf-8", xml_declaration=True)

    per_cat = {}
    for c in chans:
        per_cat[c["cat"]] = per_cat.get(c["cat"], 0) + 1
    summary = [f"Built {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
               f"{len(chans)} channels, {len(want)} with a guide, {progs} guide entries", "",
               "By category:"] + [f"  {c}: {per_cat.get(c, 0)}" for c in CATEGORIES] + \
              ["", "By source (kept of offered; the rest were duplicates):"] + \
              [f"  {k}: {v}" for k, v in counts.items()]
    (out / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
