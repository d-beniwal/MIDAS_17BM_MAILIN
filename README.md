# 17BM Mail-In

XRD (X-ray diffraction) data analysis for the mail-in program at APS beamline
17BM. Samples are mailed in, run on a fixed lab detector (Varex-style flat
panel, 2880x2880 px, 150 um pitch), and always co-calibrated against a LaB6
standard.

## What's here

Calibration and integration (MIDAS `midas_calibrate_v2` / `midas_integrate_v2`)
are **not** part of this repo any more: they live in the separate,
independently maintained [`midas_mailin`](../midas_mailin) package, which runs
in its own conda env. This program only launches it as a detached subprocess
and is responsible for the hand-off -- `mailin.py`'s `launch_batch_pipeline()`
passes it the calibrant frame (`<barcode>_pos0.tif`), the frames to integrate
(every other `<barcode>_posN.tif`, via a `<barcode>_integ_list.txt` file),
the output directory, and the beamline config
(`midas_mailin/configs/beamline_17bm.yaml`). Outputs land next to the raw
frames as `<stem>_calib.*` / `<stem>_integ.*`, plus a
`<pos0 stem>_run_summary.json` with per-file status. See the `midas_mailin`
README for the full contract. No MIDAS/torch packages are needed (or
wanted) in this repo's environment.

The mail-in scan-request GUI:

- **`mailin.py`** — the PyQt5 GUI: barcode search, cartridge/sample tracking
  against the scan-request DB, and the `launch_batch_pipeline()` hook that
  launches `midas_mailin` after each batch.
- **`beamline17bm_real.py`** — EPICS (`pyepics`) control of the real 17-BM
  detector/motors/filters/shutter.
- **`beamline17bm_simulated.py`** — a stand-in for `beamline17bm_real.py`
  used when `BarcodeSearchApp.simulation_mode` is `True` (no EPICS needed).
- **`models.py`** — SQLAlchemy ORM classes for the scan-request DB
  (users, samples, cartridges, proposals, scan requests/params).
- **`defaults.py`** — static lookup tables (`models.py`) draws on:
  cartridge types/sizes and per-beamline metadata.
- **`hotpixel.py`** — standalone PyQt5 tool to view a `.tif` frame and
  flag/export hot pixels; not wired into `mailin.py` or `midas_mailin`.

- **`archive/`** *(gitignored)* — earlier draft pipelines, kept locally for
  reference, including the exploratory notebook these CLIs were built from
  (`calibration_integration_pipeline.ipynb`). Not part of the maintained
  pipeline.

- **`beamline_data/`** *(gitignored)* — raw `.tif` detector frames + `.metadata`
  sidecars, organized by acquisition session (`apr/`, `Jun/`, `mar/`) and by
  calibration purpose (`calibration/wavelength/`, `calibration/distance/`).
  Too large for git; lives on the local workstation only.

## Requirements

Python 3.12. GUI environment `mailin` (PyQt5, pyepics, SQLAlchemy,
mysql-connector-python, pandas, Pillow, numpy):

```bash
conda env create -f environment.yml && conda activate mailin
# or: pip install -r requirements.txt
```

The analysis env (`midas_mailin`) is created separately from the
`midas_mailin` repo's `environment.yml`.

## Beamline workstation setup

The GUI (`mailin.py`) and the analysis pipeline it launches are developed
off-site, so several things are hardcoded to placeholder/dev values and
**must be changed on the actual 17-BM workstation** before a real run:

- **`MIDAS_MAILIN_PYTHON` / `MIDAS_MAILIN_CONFIG` in `mailin.py`** (or the
  environment variables of the same names, which take precedence) —
  currently placeholder Windows paths. `MIDAS_MAILIN_PYTHON` must point at
  the `python.exe` inside the `midas_mailin` conda env **on the workstation**
  (created there from the `midas_mailin` repo's `environment.yml`);
  `MIDAS_MAILIN_CONFIG` at the beamline YAML config in that repo's
  `configs/` (this is also where a bad-pixel mask, `mask_file`, is set --
  point it only at a genuine 0/1 mask, **not** a `BadPixel_*.tif`, which is
  a detector image).
- **`DATABASE_URL` in `BarcodeSearchApp.initDB()`** — hardcoded to
  `mysql+mysqlconnector://11bm:staff11bm@s11bmsrv1/mailin`, i.e. the
  **11-BM** scan-request database host/credentials. This must be updated
  to 17-BM's own MySQL server, user, and password (and that database
  needs the `mailin` schema `models.py` defines already provisioned).
- **`Y:\mail_in\<year>\<Mon>` batch directory** — hardcoded (in both
  `beamline17bm_real.py`'s save/scan routines and duplicated in
  `mailin.py`'s `launch_batch_pipeline()`) as a Windows drive letter. The
  workstation needs a `Y:` drive mapped to wherever detector frames
  actually land, and both files' occurrences of this path must agree if
  it ever changes.
- **EPICS connectivity** — `beamline17bm_real.py` talks to hardcoded
  17-BM PV names (`17bmVarex:...`, `17bm:m10`/`m33`, `17bm:XiaPfcu2:...`,
  `PB:17BM:STA_*`, `17bm:scaler1...`) via `pyepics`. The workstation must
  be on the 17-BM control network with Channel Access reaching those
  IOCs (standard `EPICS_CA_ADDR_LIST`/`EPICS_CA_AUTO_ADDR_LIST` env vars
  set as they are for any other 17-BM control-room machine); confirm
  `BarcodeSearchApp.simulation_mode` in `mailin.py` is `False` so it
  drives `Beamline17BM` (real EPICS) rather than the simulated stand-in.

## Status

Calibration and integration are implemented and validated on the 49 keV LaB6
calibration set. Not yet done: applying a saved calibration to real *sample*
frames (`apr/`/`Jun/`/`mar/`) and dark-frame subtraction wiring.

Bad-pixel masking is configured via `mask_file` in the `midas_mailin` YAML
config (`.tif`/`.tiff` or `.npy`, same shape as the detector image; 1/non-zero
= bad, 0 = good; default: no mask). Note the `BadPixel_*.tif` files under
`apr/`/`Jun/` are **not** masks: they are detector images (median ~12,000
counts, 99.9% non-zero), and `midas_mailin` prints a WARNING (and continues) when a mask excludes
>10% of the pixels. The real bad-pixel lists are the sibling `BadPixel_*.json` files
(512 `[a, b]` pixel coordinates; the axis order is unverified), which would
need converting to a 0/1 array before use.
