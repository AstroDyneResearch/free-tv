# Free TV

One playlist of the free, ad-supported US channels from Pluto TV, Samsung TV Plus, Roku, Tubi, Plex, Xumo, Vizio,
LG, TCL, Local Now, Distro, Whale, Fire TV, Tablo, Cineverse and two sports services, with each channel listed
once and sorted into categories (News, Sports, Movies, Reality, Kids & Family and so on), plus one matching guide.

Rebuilt every morning by a GitHub Action from community-maintained lists
([BuddyChewChew/app-m3u-generator](https://github.com/BuddyChewChew/app-m3u-generator),
[i.mjh.nz](https://github.com/matthuisman/i.mjh.nz) guides, [apsattv.com](https://www.apsattv.com)).

| | Address |
|---|---|
| Playlist | `https://astrodyneresearch.github.io/free-tv/free-tv.m3u` |
| Guide (EPG) | `https://astrodyneresearch.github.io/free-tv/guide.xml.gz` |

The latest build's counts are in [summary.txt](summary.txt). Categories, duplicate matching and which local
stations are kept are set at the top of [build.py](build.py). Run it yourself with `python3 build.py`.

The streams belong to the services that carry them; this repository only lists their public addresses.
