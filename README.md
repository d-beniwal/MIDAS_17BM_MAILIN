# 17BM Mail-In

XRD (X-ray diffraction) data analysis for the mail-in program at APS beamline
17BM. Samples are mailed in, run on a fixed lab detector (Varex-style flat
panel, 2880x2880 px, 150 um pitch), and always co-calibrated against a LaB6
standard.

## What's here

Two command-line tools built on [MIDAS](https://github.com/marinerhemant/MIDAS)'s
`midas_calibrate_v2` / `midas_integrate_v2` packages, sharing a single editable
config file:

- **`pipeline_config.py`** — edit this to change the calibrant, calibration
  tuning (e.g. distortion model), or integration binning/output settings.
  Both CLIs import it directly.
- **`pipeline_lib.py`** — the shared implementation
  (`calibrate_lab6()`, `integrate_frame()`, output writers, plotting) used by
  both CLIs.
- **`calibrate.py`** — calibrates a LaB6 (or other configured calibrant)
  frame. Wavelength and pixel pitch come from the `.tif`'s `.metadata`
  sidecar; beam centre and sample-to-detector distance are **always** found
  automatically by `midas_calibrate_v2`'s auto-seeder from the ring pattern
  in the image itself (the sidecar's own geometry fields are unreliable at
  this beamline).
- **`integrate.py`** — integrates any frame (calibrant or sample) against a
  saved calibration, with a choice of 4 binning kernels and export to 6
  output formats (csv, xye, fxye/GSAS, dat/PDF, esg/MAUD, full 2D cake).

### Usage

```bash
# Calibrate one LaB6 frame -> <outfolder>/<stem>_midas_calib.{json,png}
python calibrate.py \
    --infile beamline_data/calibration/wavelength/49keV/Lab6_d1000_20260212_49keV-00000.tif \
    --outfolder pipeline_output/calib
#   --overwrite   recalibrate even if the output .json already exists

# Integrate a frame against that calibration -> <outfolder>/<stem>.<ext> per format
python integrate.py \
    --incalibfile pipeline_output/calib/Lab6_d1000_20260212_49keV-00000_midas_calib.json \
    --infile beamline_data/calibration/wavelength/49keV/Lab6_d1000_20260212_49keV-00000.tif \
    --outfolder pipeline_output/integ
#   --plot 1      also save a quick I vs 2theta lineout PNG (default 0 = off)
```

See `test_analysis/commands.md` for a runnable, git-tracked example against
`test_data/` (no `beamline_data/` access needed).

`calibrate.py` always writes a ring-overlay PNG (predicted rings, from the
full fitted geometry, over the raw image) next to the calibration JSON;
`integrate.py` writes it only when `--plot 1` is passed.

- **`archive/`** *(gitignored)* — earlier draft pipelines, kept locally for
  reference, including the exploratory notebook these CLIs were built from
  (`calibration_integration_pipeline.ipynb`). Not part of the maintained
  pipeline.

- **`beamline_data/`** *(gitignored)* — raw `.tif` detector frames + `.metadata`
  sidecars, organized by acquisition session (`apr/`, `Jun/`, `mar/`) and by
  calibration purpose (`calibration/wavelength/`, `calibration/distance/`).
  Too large for git; lives on the local workstation only.

- **`test_data/`** — one LaB6 calibration frame (`.tif` + `.tif.metadata`
  sidecar) copied out of `beamline_data/`, checked into git so the pipeline
  can be exercised without access to the full (gitignored) dataset.

- **`test_analysis/`** — output of running `calibrate.py`/`integrate.py`
  against `test_data/`, checked into git as a reference/smoke-test result.
  `commands.md` documents the exact commands and expected values.

## Requirements

Conda environment `midas_17bm`, defined in `environment.yml`:

```bash
conda env create -f environment.yml
conda activate midas_17bm
```

Provides `midas-suite` (which pulls in `midas_calibrate_v2`,
`midas_integrate_v2`, `midas_hkls`, etc.), `torch`, `tifffile`,
`scikit-image`, `contourpy`, `matplotlib`, `numpy`, `scipy`, `h5py`, and
`hdf5plugin`. `scikit-image` is pinned explicitly because
`midas_calibrate_v2`'s auto-seeder imports `skimage` without declaring it as
a dependency.

## Status

Calibration and integration are implemented and validated on the 49 keV LaB6
calibration set. Not yet done: applying a saved calibration to real *sample*
frames (`apr/`/`Jun/`/`mar/`), dark-frame subtraction wiring, and bad-pixel
mask support (`Jun/BadPixel_2026Jun19.json` is present but unused).
