# Orchestra

Presentation timing manager for multi-presenter events. Keeps speakers on schedule with a live timeline, per-block countdowns, and haptic alerts delivered to presenters' phones.

> **Windows only.** Orchestra uses the Windows COM API to control PowerPoint. It requires:
> - Windows 10 or later
> - Microsoft PowerPoint installed (any edition that supports COM automation)

---

## Features

- Build timelines with multiple presenters and timed blocks
- Import slide structure directly from a `.pptx` file
- Live countdown per block with budget tracking
- Haptic/vibration alerts sent to presenters' phones via a local web app (no internet required)
- Scan a QR code on the presenter panel to join from any phone on the same Wi-Fi network
- PowerPoint slide advance control via COM

## Running the exe

1. Download the `Orchestra` folder from the latest release.
2. Run `Orchestra.exe` inside that folder — **do not move the exe out of the folder**.
3. On first launch, a `data/` folder is created next to the exe to store your config and timelines.

> The entire `Orchestra/` folder must stay together. The exe cannot run without `_internal/`.

## Building from source

**Requirements:** Python 3.12, all packages in `requirements.txt`, PowerPoint installed.

```bash
pip install -r requirements.txt
python main.py
```

**Build the exe:**

```bash
pip install pyinstaller
pyinstaller orchestra.spec
# Output: dist/Orchestra/Orchestra.exe
```

## Notes

- The built exe only runs on Windows machines that have PowerPoint installed.
- The Flask server binds to `0.0.0.0` by default so phones on the same network can connect. The port can be changed in Settings.
- Timeline and config data are stored in `data/` next to the exe (or next to `main.py` when running from source).
