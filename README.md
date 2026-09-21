# Morpheus

Morpheus is an integrity-first digital forensics investigation workspace for registering forensic images, analyzing disk contents, reviewing artifacts, tracking chain of custody, and producing investigator-friendly reports.

It is designed for examiner-led investigations. Morpheus surfaces observed artifacts and automated indicators; the examiner remains responsible for validation, interpretation, and conclusions.

## Contents

- [Architecture](#architecture)
- [Requirements](#requirements)
- [Run the application](#run-the-application)
- [Default accounts](#default-accounts)
- [How to use Morpheus](#how-to-use-morpheus)
- [Features](#features)
- [Reports](#reports)
- [Configuration](#configuration)
- [Limitations](#limitations)
- [Development checks](#development-checks)
- [Security and forensic cautions](#security-and-forensic-cautions)

## Architecture

```text
Morpheus/
├── backend/     FastAPI API, database, hashing, analysis engine, reports
├── frontend/    React/Vite examiner workspace
├── cli/         CLI utilities and case workflows
├── docs/        Project documentation
└── nightmare_case.json  Example/demo case data
```

The frontend communicates with the backend over HTTP. The backend stores case metadata and custody records in the configured SQLAlchemy database and reads evidence from paths on the Morpheus host.

## Technical processing details

### Evidence registration and integrity

1. The examiner registers an image path for a case.
2. Morpheus verifies that the path exists and has a supported forensic-image extension.
3. The hashing service reads the file and calculates SHA-256, with MD5 retained where available for identification compatibility.
4. The fingerprint, size, filename, path, collector, and collection time are stored as the integrity baseline.
5. A duplicate SHA-256 cannot be registered twice in the same case.
6. Later integrity checks re-read the registered path and compare the current SHA-256 with the stored fingerprint.
7. A moved file can only have its path updated when the new path produces the same SHA-256.

The original image is not modified by registration or analysis. Generated reports, manifests, and extracted files are separate outputs and should be preserved with the case record.

### Image identification and volume handling

Analysis is coordinated by `AnalysisOrchestrator`:

1. The target path is validated.
2. `DataSourceIdentifier` identifies the container type, partition scheme, operating-system likelihood, and discovered volumes.
3. The image is opened once using the appropriate reader:
   - `pyewf` for E01/Ex01/S01
   - `pyvhdi` for VHD/VHDX
   - `pytsk3.Img_Info` for raw images
4. Each recognized volume is converted from a sector start to a byte offset using the volume start sector.
5. Unknown filesystems are recorded as skipped rather than treated as successfully scanned.
6. Per-volume errors are retained in the analysis report and surfaced as processing limitations.

### Filesystem scanning

`FilesystemScanner` uses `pytsk3` to open each recognized filesystem and recursively walk directories. For each directory entry it records available metadata such as:

- Full source path
- Filename and extension
- File size
- Created, modified, and accessed timestamps when exposed by the filesystem
- Allocated/deleted status
- Artifact category

The scanner classifies files into categories including documents, images, emails, browser artifacts, registry hives, event logs, archives, executables, databases, encryption-related files, deleted files, and suspicious files. Suspicious classifications are based on configured filename/path indicators, double extensions, executable types in unusual user locations, and encryption-related terms. These are review indicators, not conclusions.

### Specialized analyzers

After the filesystem inventory is built, the orchestrator passes relevant candidates to specialized analyzers:

- Browser analysis parses supported browser history artifacts and normalizes URL/timestamp information.
- Email analysis parses supported EML, MSG, PST/OST, and related candidates when the required parser support is available.
- Text analysis extracts bounded previews, detects BCTextEncoder markers, and reports factual indicators such as credential terms, email addresses, IP addresses, and URLs.
- Virtual-disk handling extracts discovered nested VHD/VHDX content to a temporary location, identifies its volumes, and recursively scans recognized filesystems.

A parser failure or unsupported format does not silently become a positive finding; it is retained as an error or limitation where the analysis path reports it.

### Artifact normalization, extraction, and provenance

`ArtifactCollector` converts analyzer-specific records into normalized artifact records. The presentation layer adds deterministic artifact IDs and provenance fields including evidence target, source path, source volume, artifact type, deleted status, and any hash supplied by an upstream analyzer or extraction step.

Artifact extraction reads bytes from the forensic image through the image/filesystem reader and writes a separate output file. The extraction action is recorded in chain of custody. Exported artifact manifests include extraction status, size, and SHA-256 for the exported bytes when extraction succeeds.

### Reports and presentation

The raw analysis report retains identification data, volume results, nested disks, summary counts, and processing errors. The presentation report provides investigator-facing categories and full available lists for the UI. Human-readable case PDFs are generated from stored case data and include integrity status, executive summary, categorized findings, limitations, and custody history.

Summary exports may intentionally show selected items. Full report modes and machine-readable JSON should be used when the complete artifact set is required. The report does not independently reinterpret evidence; automated detection rules explain why an item was highlighted for examiner review.

## Requirements

- Python 3.10+ recommended
- Node.js 18+ and npm
- A supported forensic-analysis environment for `pytsk3`, `libewf`, `libvhdi`, and `libesedb`
- Read access to the forensic image files
- Sufficient disk space for optional extracted artifacts and temporary nested-disk analysis

The analysis engine currently targets forensic disk images such as E01/Ex01/S01, VHD/VHDX, and raw image formats.

## Run the application

### 1. Configure the backend

```bash
cd Morpheus
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp backend/.env.example backend/.env
```

Review `backend/.env` before running in a real environment. At minimum, configure the database and authentication settings required by your deployment.

### 2. Start the API

From the repository root:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The command must be run with `backend` as the working directory, or with `backend` on `PYTHONPATH`:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API documentation is available at:

- http://localhost:8000/docs
- http://localhost:8000/redoc

### 3. Start the Morpheus desktop application (recommended)

Use Electron as the normal way to run the examiner workspace. It provides the native file picker required for selecting evidence paths safely and avoids browser filesystem limitations.

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run electron:dev
```

This starts the Vite API client and opens the Morpheus Electron window. Use **Browse...** in **Add data source** to select a disk image.

The frontend defaults to `http://localhost:8000`. To use another API URL, set this in `frontend/.env`:

```env
VITE_API_BASE=http://localhost:8000
```

### 4. Build the desktop package

Electron provides a native file picker, which is useful because a normal browser cannot reliably provide the host filesystem path needed by the backend.

```bash
cd frontend
npm run electron:build
```

### Optional browser-only development mode

The browser UI is available for frontend development and troubleshooting, but it is **not the recommended way to use Morpheus**. Browser file inputs cannot provide a reliable host filesystem path, so you must enter a path accessible to the backend manually.

```bash
cd frontend
npm run dev
```

Open http://localhost:5173 only when you specifically need browser-mode development.

To build the desktop package:

```bash
npm run electron:build
```

## Default accounts

The development startup process seeds these accounts if they do not already exist:

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | Full administration |
| `examiner` | `exam123` | Create and analyze cases |
| `viewer` | `view123` | Read-only access |

Change or disable development credentials before deploying beyond a local/demo environment.

## How to use Morpheus

### Create and open a case

1. Sign in.
2. Select **Create case**.
3. Enter the case name, examiner, organization, and description.
4. Open the case workspace.

### Register a forensic image

1. Select **Add data source**.
2. Choose a supported image file or enter its absolute path on the backend host.
3. Add the collector and optional notes.
4. Morpheus calculates and stores SHA-256 and MD5 fingerprints.
5. Review the registered path, image type, and fingerprint.

The same SHA-256 data source cannot be registered twice in the same case. If the file moved, use **Update path** after an integrity check; the new file must have the same SHA-256.

### Analyze a data source

1. Select **Analyze** beside a registered data source.
2. Wait for the analysis progress to complete.
3. Open **Key findings** to review the stored presentation.
4. Use the category tabs to inspect documents, suspicious files, deleted files, email, web history, images, and nested virtual disks.
5. Preview or extract artifacts where available.

Analysis is read-only against the source image. Extracted files are recorded in custody and appear in the **Extracted files** sidebar section.

### Verify integrity

1. Select **Verify integrity** from the case overview.
2. Review each data source and evidence item.
3. A matching SHA-256 is reported as unchanged.
4. A missing file or hash mismatch is reported as a warning/problem.
5. If a file moved but its fingerprint is unchanged, use **Update path**.

Do not treat a hash-mismatch file as original evidence without investigating the discrepancy.

### Review custody

- **Recent custody** provides a compact overview.
- **Chain of custody** provides the complete case event log.
- **Extracted files** lists extraction events separately while retaining them in the full custody history.

### Generate a report

Select **Reports** or **Download report** from the case overview. The case PDF includes:

- Branded case cover and metadata
- Executive summary
- Evidence integrity status and SHA-256 values
- Categorized findings
- Artifact paths, IDs, deleted status, and detection rules where available
- Processing limitations
- Chain of custody

The analysis export functions also support summary and full report modes for Markdown, PDF, and JSON exports.

## Features

### Case and evidence management

- Case creation, opening, closing, reopening, and deletion workflow
- Role-based access for admin, examiner, and viewer users
- Data-source registration with SHA-256/MD5 fingerprints
- Duplicate data-source detection within a case
- Evidence and data-source path updates with hash verification
- Audit and chain-of-custody logging

### Forensic analysis

- E01/Ex01/S01 image identification
- Raw image and VHD/VHDX support
- Partition and filesystem identification
- Filesystem inventory
- Deleted-file discovery
- Suspicious-file indicators
- Documents, images, registry hives, event logs, archives, executables, and databases
- Browser artifacts and history
- Email artifacts and attachments
- Text-file analysis and BCTextEncoder indicators
- Nested virtual disk discovery and analysis

### Finding review

- Categorized finding tabs
- Artifact provenance and deterministic artifact IDs
- Source path, source volume, artifact type, and deleted status
- Existing hash visibility without falsely claiming unavailable hashes
- Named detection rules explaining why selected items were highlighted
- File preview and extraction actions
- Dedicated extracted-file history

### Reporting

- Executive-summary report template
- Categorized PDF findings
- Colored integrity and status indicators
- Markdown export
- JSON export
- Summary and full report modes
- Processing error and limitation reporting
- Chain-of-custody report section

### Optional AI assistance

The UI can request a plain-language summary for non-technical readers when an OpenAI-compatible API configuration is supplied. AI output is an aid to communication and must be reviewed by the examiner before inclusion in a formal report.

## Configuration

### Detection keywords

Filesystem suspicious-file and encryption indicators are configured in:

```text
backend/app/config/keywords.txt
```

The report renderer uses named rules in:

```text
backend/app/analysis/report_rules.py
```

These rules classify observed artifacts for review. They do not establish intent, attribution, or guilt.

### Analysis outputs

Analysis jobs may create output files such as:

- Presentation JSON
- Artifact manifests
- Extracted artifact files
- Timeline JSONL output

Do not place generated output inside the original evidence directory. Preserve generated outputs with the case record and custody documentation.

## Limitations

- This is an active development project, not a validated forensic suite.
- It does not replace examiner review, independent verification, or laboratory procedures.
- The browser, email, text, and filesystem analyzers cover a limited set of artifact formats and parsers.
- Some filesystem metadata and timestamps depend on what the underlying library exposes.
- Unsupported, encrypted, corrupted, or unusual files may be skipped or only partially parsed.
- Content hashes are available for registered evidence and exported artifacts where calculated; a deterministic artifact ID is not a content hash.
- Automated suspicious/high-signal classifications can produce false positives and false negatives.
- Detection rules are indicators for review, not conclusions.
- The current report is generated from stored analysis results and does not independently re-analyze the image while rendering.
- Browser-based file selection cannot provide a reliable host path; use Electron or enter the path on the backend host.
- The current architecture expects the API and evidence files to be reachable from the same trusted analysis environment.
- Default credentials, permissive development CORS, and local HTTP configuration are not production-ready.
- Multi-machine synchronization, mobile acquisition, cloud acquisition, and broad artifact coverage are not yet complete.
- The application does not currently provide a formal court validation, digital-signature workflow, or independent reproducibility package for every parser.

## Development checks

Frontend production build:

```bash
cd frontend
npm run build
```

Backend syntax check:

```bash
cd backend
python -m compileall -q app
```

For a production or courtroom workflow, add project-specific automated tests, independent hash verification, parser validation, access control review, and documented examiner procedures.

## Security and forensic cautions

- Work from verified forensic copies whenever possible.
- Do not analyze the only copy of evidence.
- Record acquisition details and preserve original hash values.
- Restrict access to evidence paths and generated exports.
- Review every automated finding before including it in a conclusion.
- Preserve the complete custody log, report output, manifests, and processing errors together.
- Replace development passwords and configure authenticated, encrypted deployment before handling sensitive cases.
