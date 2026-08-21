# 17BM Mail-In

XRD (X-ray diffraction) data analysis for the mail-in program at APS beamline
17BM. Samples are mailed in, run on a fixed lab detector (Varex-style flat
panel, 2880x2880 px, 150 um pitch), and always co-calibrated against a LaB6
standard.

## What's here

- **`calibration_integration_pipeline.ipynb`** — the pipeline. Two reusable
  functions built on [MIDAS](https://github.com/marinerhemant/MIDAS)'s
  `midas_calibrate_v2` / `midas_integrate_v2` packages:
  - `calibrate_lab6(tif_path, ...)` — calibrates a LaB6 frame. Wavelength and
    pixel pitch come from the `.tif`'s `.metadata` sidecar; beam centre and
    sample-to-detector distance are **always** found automatically by
    `midas_calibrate_v2`'s auto-seeder from the ring pattern in the image
    itself (the sidecar's own geometry fields are demonstrably unreliable at
    this beamline — see the notebook's §2 for why). Includes a visual sanity
    check: predicted diffraction rings, computed from the full fitted
    geometry (tilts *and* harmonic distortion), overlaid on the raw image.
  - `integrate_frame(image, calibration_json_path, ...)` — integrates any
    frame (calibrant or sample) against a saved calibration, with a choice
    of 4 binning kernels and export to 7 output formats (csv, xye, fxye/GSAS,
    dat/PDF, esg/MAUD, a full 2D cake, and a multi-frame HDF5 stack).

  The notebook validates both functions against every LaB6 frame in
  `beamline_data/calibration/wavelength/49keV/` (19 frames, 6 nominal
  distances, 3 acquisition sessions) and cross-checks that the auto-seeded
  geometry tracks the nominal distance encoded in each filename.

- **`archive/`** *(gitignored)* — an earlier, simpler draft pipeline, kept
  locally for reference.

- **`beamline_data/`** *(gitignored)* — raw `.tif` detector frames + `.metadata`
  sidecars, organized by acquisition session (`apr/`, `Jun/`, `mar/`) and by
  calibration purpose (`calibration/wavelength/`, `calibration/distance/`).
  Too large for git; lives on the local workstation only.

## Requirements

A conda environment with `midas_calibrate_v2`, `midas_integrate_v2`,
`midas_hkls`, `torch`, `tifffile`, `contourpy`, `plotly`, `pandas`, and
`h5py` (this repo was built/run against `midas_env_dev`).

## Status

Calibration and integration are implemented and validated on the 49 keV LaB6
calibration set. Not yet done: applying a saved calibration to real *sample*
frames (`apr/`/`Jun/`/`mar/`), dark-frame subtraction wiring, and bad-pixel
mask support (`Jun/BadPixel_2026Jun19.json` is present but unused).
