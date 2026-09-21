# Morpheus UI

React (Vite) examiner workspace for Morpheus digital forensics.

## Run

```bash
cd morpheus-ui
cp .env.example .env   # set VITE_API_BASE if needed
npm install
npm run dev
```

Open http://localhost:5173 — API default `http://localhost:8000`.

## Structure

```
src/
  App.jsx                 # screens + API wiring
  main.jsx
  lib/api.js              # fetch helper
  lib/format.js           # pickReport, formatBytes, DEMO_PATH
  components/
    FindingsReport.jsx    # DOI / suspicious / emails / web / images tabs
    ItemGroup.jsx
    PreviewBody.jsx
    Modal.jsx, Toast.jsx, TopBar.jsx, ProgressBar.jsx
  styles/global.css       # Source Sans 3 + lab chrome
```

## Demo flow

1. Sign in  
2. Create / open case  
3. Add data source (Fill demo path)  
4. Analyze → Key findings  
5. Verify integrity → certificate  

Ensure backend `build_presentation` / `export_report_json(presentation_only=True)` attaches full lists on job `result`.

## Electron (desktop) — native file paths

The browser cannot give you a real filesystem path from `<input type="file">`.
Electron can, via a native open dialog.

### Install

```bash
cd morpheus-ui
npm install
```

### Dev (Vite + Electron together)

```bash
npm run electron:dev
```

This starts Vite on http://localhost:5173 and opens an Electron window pointed at it.
In **Add data source**, use **Browse…** to pick a disk image — the full absolute path is filled in automatically.

### Manual two-terminal (optional)

```bash
# terminal 1
npm run dev

# terminal 2
npm run electron
```

### Security notes

- `contextIsolation: true`, `nodeIntegration: false`
- File dialog runs in the main process; only the chosen path is sent to the UI via `preload` + `contextBridge` (`window.electronAPI.openFile`)
- The browser/web build still works; the Browse button only appears inside Electron
