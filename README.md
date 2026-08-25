# 17BM Mail-In

XRD (X-ray diffraction) data analysis for the mail-in program at APS beamline
17BM. Samples are mailed in, run on a fixed lab detector (Varex-style flat
panel, 2880x2880 px, 150 um pitch), and always co-calibrated against a LaB6
standard.

## What's here

A batch CLI built on [MIDAS](https://github.com/marinerhemant/MIDAS)'s
`midas_calibrate_v2` / `midas_integrate_v2` packages, driven by a single
editable config file:

- **`midas_17bm_config.py`** — edit this to change the calibrant, calibration
  tuning (e.g. distortion model), or integration binning/output settings.
  `midas_17bm_pipeline.py` imports it directly.
- **`midas_17bm_lib.py`** — the shared implementation
  (`calibrate_lab6()`, `build_integration_context()`/`integrate_with_context()`,
  output writers, plotting) used by the CLI.
- **`midas_17bm_pipeline.py`** — calibrates one batch's LaB6 (or other configured
  calibrant) `pos0` frame, then integrates every other `posN` sample frame in
  that batch against it, building the detector mapping once and reusing it
  across all frames. Wavelength and pixel pitch come from the `.tif`'s
  `.metadata` sidecar; beam centre and sample-to-detector distance are
  **always** found automatically by `midas_calibrate_v2`'s auto-seeder from
  the ring pattern in the image itself (the sidecar's own geometry fields are
  unreliable at this beamline). Integration supports a choice of 4 binning
  kernels and export to 6 output formats (csv, xye, fxye/GSAS, dat/PDF,
  esg/MAUD, full 2D cake). This is also what
  `mailin.py` launches automatically in the background after each batch
  finishes acquisition.

### Usage

```bash
# Calibrate <barcode>_pos0.tif, then integrate every <barcode>_posN.tif (N>0)
# in --batch-dir against it -> outputs written into --batch-dir (or --outfolder)
python midas_17bm_pipeline.py \
    --batch-dir beamline_data/calibration/wavelength/49keV \
    --barcode ANLXRD00012
#   --outfolder PATH        write outputs elsewhere (default: --batch-dir, in place)
#   --overwrite             redo calibration/integration even if outputs already exist
#   --only-full-rings 0     integrate out to the full configured R_MAX instead of
#                           capping at the largest ring that stays on-detector (default 1)
```

`midas_17bm_pipeline.py` always writes a ring-overlay PNG (predicted rings, from
the full fitted geometry, over the raw image) next to the calibration JSON,
and an I vs 2theta lineout PNG next to each integrated sample frame.

Alongside the pipeline, the mail-in scan-request GUI:

- **`mailin.py`** — the PyQt5 GUI: barcode search, cartridge/sample tracking
  against the scan-request DB, and the `launch_batch_pipeline()` hook that
  kicks off `midas_17bm_pipeline.py` after each batch.
- **`beamline17bm_real.py`** — EPICS (`pyepics`) control of the real 17-BM
  detector/motors/filters/shutter.
- **`beamline17bm_simulated.py`** — a stand-in for `beamline17bm_real.py`
  used when `BarcodeSearchApp.simulation_mode` is `True` (no EPICS needed).
- **`models.py`** — SQLAlchemy ORM classes for the scan-request DB
  (users, samples, cartridges, proposals, scan requests/params).
- **`defaults.py`** — static lookup tables (`models.py`) draws on:
  cartridge types/sizes and per-beamline metadata.
- **`hotpixel.py`** — standalone PyQt5 tool to view a `.tif` frame and
  flag/export hot pixels; not wired into `mailin.py` or the batch pipeline.

- **`archive/`** *(gitignored)* — earlier draft pipelines, kept locally for
  reference, including the exploratory notebook these CLIs were built from
  (`calibration_integration_pipeline.ipynb`). Not part of the maintained
  pipeline.

- **`beamline_data/`** *(gitignored)* — raw `.tif` detector frames + `.metadata`
  sidecars, organized by acquisition session (`apr/`, `Jun/`, `mar/`) and by
  calibration purpose (`calibration/wavelength/`, `calibration/distance/`).
  Too large for git; lives on the local workstation only.

## Requirements

Requires Python 3.12. Install via **either** conda or pip:

**Conda** — environment `midas_17bm`, defined in `environment.yml`:

```bash
conda env create -f environment.yml
conda activate midas_17bm
```

**Pip** — into an existing Python 3.12 environment/virtualenv, via
`requirements.txt` (mirrors the pip section of `environment.yml`):

```bash
pip install -r requirements.txt
```

Both provide `midas-suite` (which pulls in `midas_calibrate_v2`,
`midas_integrate_v2`, `midas_hkls`, etc.), `torch`, `tifffile`,
`scikit-image`, `contourpy`, `matplotlib`, `numpy`, `scipy`, `h5py`, and
`hdf5plugin`. `scikit-image` is pinned explicitly because
`midas_calibrate_v2`'s auto-seeder imports `skimage` without declaring it as
a dependency.

They also provide what the scan-request GUI (`mailin.py`, `beamline17bm_real.py`,
`beamline17bm_simulated.py`, `models.py`, `defaults.py`) needs: `PyQt5` (GUI
widgets/drag-drop), `pyepics` (EPICS channel access for
`beamline17bm_real.py`), `SQLAlchemy` + `mysql-connector-python` (the
`mysql+mysqlconnector://` scan-request database in `mailin.py`), `pandas`,
and `Pillow`.

## Beamline workstation setup

The GUI (`mailin.py`) and the analysis pipeline it launches are developed
off-site, so several things are hardcoded to placeholder/dev values and
**must be changed on the actual 17-BM workstation** before a real run:

- **`BATCH_ANALYSIS_PYTHON` in `midas_17bm_config.py`** — currently a
  placeholder Windows path
  (`C:\Users\17bmuser\AppData\Local\miniconda3\envs\midas_17bm\bin\python`).
  `mailin.py` shells out to this interpreter to run
  `midas_17bm_pipeline.py` in the background after each batch (kept
  separate from whatever environment runs the GUI itself, since the GUI
  only needs PyQt5/pyepics/SQLAlchemy while the pipeline needs the much
  heavier `midas-suite`/`torch`/`scikit-image` stack). Confirm it points
  at the actual `python.exe` inside the `midas_17bm` conda env **on the
  workstation** (e.g. `conda env create -f environment.yml` run there).
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
- **`--mask-file` / `MASK_FILE`** in `midas_17bm_config.py` — if a
  bad-pixel mask should be applied by default, point this at that
  workstation's current `BadPixel_*.tif` (dense mask, not the
  coordinate-list `.json` sibling).

## Status

Calibration and integration are implemented and validated on the 49 keV LaB6
calibration set. Not yet done: applying a saved calibration to real *sample*
frames (`apr/`/`Jun/`/`mar/`) and dark-frame subtraction wiring.

Bad-pixel masking is supported: pass `--mask-file` to `midas_17bm_pipeline.py`
(or set `MASK_FILE` in `midas_17bm_config.py`) with a `.tif`/`.tiff` or `.npy`
file the same shape as the detector image, where 1/non-zero = bad pixel and
0 = good pixel (default: no mask). The dense `BadPixel_*.tif` files under
`apr/`/`Jun/` are usable as-is; the sibling `BadPixel_*.json` files (a list of
individual bad-pixel coordinates, not a dense mask array) are not directly
consumable by `--mask-file`.
