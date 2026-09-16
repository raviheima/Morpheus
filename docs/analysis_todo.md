# Morpheus Analysis Service – Todo List

## Phase 1: Foundation
- [x] Create modular analysis package structure (`analysis/`)
- [x] Define abstract base class for all analyzers (`base.py`)
- [x] Implement **Data Source Identifier**
  - [x] Detect image type (E01, raw, VHD, VHDX, etc.)
  - [x] List all volumes / partitions
  - [x] Identify filesystem of each volume (NTFS, FAT32, exFAT, Ext…)
  - [x] Determine if it is a full Operating System or a simple data drive
  - [x] Detect embedded virtual disks (VHD/VHDX)
- [x] Create Analysis Orchestrator (decides which analyzers to run)

## Phase 2: Core Filesystem Analysis (works for both OS and non-OS)
- [x] Deleted files recovery
- [x] Suspicious file pattern matching
- [x] Image / media file discovery
- [ ] Embedded VHD/VHDX detection + recursive analysis
- [ ] Basic file metadata extraction
- [ ] File hashing (already partially done)

## Phase 3: Operating System Specific Analysis
- [ ] Registry analysis (NTUSER.DAT, SYSTEM, SOFTWARE…)
- [ ] Event Logs (EVTX) analysis
- [ ] Browser history & search terms
- [ ] Recycle Bin analysis
- [ ] Email artifacts (.eml, Windows Mail, etc.)
- [ ] User accounts & login information
- [ ] Prefetch / execution artifacts
- [ ] Encryption software detection

## Phase 4: Specific Analyzers (from your list)
- [ ] EmailTimezoneAnalyzer
- [ ] PartitionCapacityAnalyzer
- [ ] EmailTimestampAnalyzer
- [ ] VHDSizeAnalyzer
- [ ] DiskGUIDAnalyzer
- [ ] ClusterSizeAnalyzer
- [ ] SystemUptimeAnalyzer
- [ ] FileHashAnalyzer
- [ ] AccountPasswordAnalyzer
- [ ] PartitionSchemaAnalyzer
- [ ] EmailIPAnalyzer
- [ ] PartitionGUIDAnalyzer
- [ ] FileMetadataAnalyzer
- [ ] RecycleBinAnalyzer
- [ ] RIDUserAnalyzer
- [ ] LastLoginAnalyzer
- [ ] EmailSenderAnalyzer
- [ ] LogonProgramAnalyzer
- [ ] EncryptionSoftwareAnalyzer
- [ ] BrowserSearchAnalyzer
- [ ] WindowsMailExecutionAnalyzer
- [ ] EvidenceHashAnalyzer

## Phase 5: Timeline & Advanced
- [ ] Integrate Plaso for super timeline
- [ ] Generate unified timeline across all artifacts
- [ ] AI-generated Case Overview (later phase)

## Phase 6: Integration
- [ ] Expose Analysis Service through FastAPI endpoints
- [ ] Store analysis results in the database
- [ ] Link results back to Case + Evidence
- [ ] Add progress reporting for long-running analysis
