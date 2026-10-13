# ytgrab

A small desktop app for downloading videos and playlists, built on [yt-dlp](https://github.com/yt-dlp/yt-dlp).
Paste a link, see every available quality with its size, pick, download. It runs on Windows, macOS and Linux.

![The ytgrab window listing a playlist with a quality and size for each video](docs/screenshot.png)

## Install

You need Python 3.10 or newer. Everything else comes with it: yt-dlp, an ffmpeg binary, and the Deno
JavaScript runtime that yt-dlp uses for YouTube.

With [uv](https://docs.astral.sh/uv/):

```
uv tool install git+https://github.com/Sankey001/ytgrab
```

or with [pipx](https://pipx.pypa.io/):

```
pipx install git+https://github.com/Sankey001/ytgrab
```

Then start it:

```
ytgrab
```

To have it in the Start menu, the applications menu or the Applications folder, press
**Add to …** in the bottom bar of the window, or run `ytgrab --add-to-menu`.

## Use

1. **Links**: paste or drag in a video or playlist link. A badge shows what it was recognised as.
   **+ Add another link** takes more; pasting several links at once spreads them over rows.
2. **Download location**: type a folder or press **Browse…**. It is remembered, and the free space on that drive is shown.
3. Press **Next: show videos**. Each video gets a row with a dropdown of every available quality and its size.
4. Press **Download**. The line under the progress bar shows how many are done, the speed and the time left.

### Which quality is preselected

- The **Preferred quality** (1080p unless you change it), or the next one down when a video lacks it.
- With **1440p when under 300 MB** ticked, a video whose 1440p version is smaller than 300 MB gets 1440p.

Any row can still be changed by hand.

### Where files go

- A single video lands directly in the download folder.
- A playlist gets its own subfolder, with files numbered in playlist order (`01 - …`, or `001 - …` for
  100 videos or more) so they sort correctly by name.
- File names avoid characters that Windows does not allow, so a folder can move between systems.
- Videos already in the folder are skipped. A failed or cancelled download resumes when you press Download again.

**Show commands** in the bottom bar reveals the exact yt-dlp commands being run.

## Platform support

| | Tested |
|---|---|
| Linux (GNOME, Wayland) | By hand: listing, downloading, the launcher |
| Windows, macOS | By the automated tests only, which run on all three systems in GitHub Actions |

On Windows on ARM there is no bundled Deno; install [Deno](https://deno.com/) or [Node.js](https://nodejs.org/) yourself.

## Troubleshooting

```
python -m ytgrab --check
```

starts yt-dlp, ffmpeg and the JavaScript runtime once each and says which one fails.

Video sites change often, and an old yt-dlp is the usual reason a download stops working.
Update with `uv tool upgrade ytgrab` or `pipx upgrade ytgrab`.

| Setting | What it does |
|---|---|
| `YTGRAB_THEME=light` or `dark` | Use that look instead of following the system |
| `YTGRAB_FFMPEG=/path/to/ffmpeg` | Use this ffmpeg. By default a system ffmpeg is preferred, then the bundled one |
| `YTGRAB_YTDLP=/path/to/yt-dlp` | Use this yt-dlp instead of the bundled one |
| `YTGRAB_SETTINGS=/path/to/file.ini` | Keep the saved choices in this file |

## Development

```
git clone https://github.com/Sankey001/ytgrab
cd ytgrab
uv run ytgrab        # start the app from the source tree
uv run pytest        # run the tests; they need no display and no network
```

| File | What it holds |
|---|---|
| `src/ytgrab/app.py` | The window and the download logic |
| `src/ytgrab/tools.py` | Finding yt-dlp, ffmpeg and a JavaScript runtime on each system |
| `src/ytgrab/ytdlp.py` | The yt-dlp commands, file naming, progress parsing |
| `src/ytgrab/formats.py` | Qualities, sizes and the preselection rules |
| `src/ytgrab/launcher.py` | The Start menu shortcut, `.desktop` entry and `.app` bundle |
| `src/ytgrab/theme.py` | Colours and stylesheet for light and dark |
| `src/ytgrab/mascot.py` | The header figurine, drawn in code |
| `src/ytgrab/urls.py` | Video or playlist detection |
| `src/ytgrab/eta.py` | Speed and time-left estimate |
| `tools/make_assets.py` | Regenerates the icon files from the mascot drawing |

## Use it responsibly

Download only what you have the right to save, and follow the terms of the site you download from.

## Licence

[MIT](LICENSE). ytgrab drives yt-dlp, ffmpeg and Deno, and is built with Qt for Python; each has its own licence.
