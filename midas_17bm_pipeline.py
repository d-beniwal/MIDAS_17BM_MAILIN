#!/usr/bin/env python3
"""CLI: calibrate + integrate one whole mail-in batch (one cartridge/barcode).

A batch is a set of frames sharing one barcode in the same folder:
    <barcode>_pos0.tif        -- always the LaB6 calibrant
    <barcode>_pos1.tif ..     -- sample frames

Usage:
    python midas_17bm_pipeline.py --batch-dir PATH --barcode ANLXRD00012 [--outfolder PATH] [--overwrite]

Calibrates <barcode>_pos0.tif, then integrates every other <barcode>_posN.tif
in --batch-dir against that one calibration, building the detector mapping
(spec + geometry) only ONCE for the whole batch and reusing it across every
frame -- see midas_17bm_lib.build_integration_context().

--outfolder defaults to --batch-dir (write in place, alongside the raw data).
All calibrant/tuning/binning/output-format parameters come from
midas_17bm_config.py.
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import tifffile
import numpy as np

import midas_17bm_config as cfg
import midas_17bm_lib as lib

POS_RE_TEMPLATE = r'^{barcode}_pos(\d+)\.tif$'


def _calibrate_pos0(pos0_tif: Path, outfolder: Path, overwrite: bool, seed_kwargs=None):
    """Calibrate the batch's pos0 (LaB6) frame, including the
    residual_corr_bin null-out fix (see midas_17bm_lib.calibrate_lab6).

    `seed_kwargs` -- optional override forwarded to lib.calibrate_lab6's own
    `seed_kwargs` (auto_seed.make_seed tuning); see that function's docstring."""
    stem = pos0_tif.stem
    final_json = outfolder / f'{stem}_midas_calib.json'
    final_png = outfolder / f'{stem}_midas_calib.png'
    final_bin = outfolder / f'{stem}_midas_calib_residual_corr.bin'

    if final_json.exists() and not overwrite:
        print(f'{final_json} already exists -- skipping calibration (pass --overwrite to redo)')
        return final_json

    scratch_dir = outfolder / f'.{stem}_scratch'
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)
    scratch_dir.mkdir(parents=True)

    try:
        bundle = lib.calibrate_lab6(
            pos0_tif, scratch_dir,
            calibrant=cfg.CALIBRANT, overwrite=True, default_px_um=cfg.DEFAULT_PX_UM,
            seed_kwargs=seed_kwargs,
            **cfg.CALIBRATE_KWARGS,
        )

        scratch_json = scratch_dir / 'calibration.json'
        scratch_bin = scratch_dir / 'residual_corr.bin'

        with open(scratch_json) as fh:
            summary = json.load(fh)
        if scratch_bin.exists():
            shutil.move(str(scratch_bin), str(final_bin))
            summary['residual_corr_bin'] = str(final_bin)
        else:
            summary['residual_corr_bin'] = None
        with open(scratch_json, 'w') as fh:
            json.dump(summary, fh, indent=2)

        shutil.move(str(scratch_json), str(final_json))
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)

    lib.render_calibration_overlay_png(
        bundle, final_json, final_png,
        calibrant=cfg.CALIBRANT, two_theta_max_deg=cfg.RING_TWO_THETA_MAX_DEG,
    )

    r = bundle.result
    print(f'calibrated {pos0_tif.name}:')
    print(f'  Lsd  = {r.Lsd / 1000:.4f} mm   (seed: {r.seed_Lsd / 1000:.4f} mm)')
    print(f'  BC   = ({r.BC_y:.3f}, {r.BC_z:.3f}) px   (seed: ({r.seed_BC_y:.3f}, {r.seed_BC_z:.3f}) px)')
    if r.post_residual_strain_uE is not None:
        print(f'  post-residual strain = {r.post_residual_strain_uE:.1f} microstrain')
    print(f'  wrote {final_json}')
    print(f'  wrote {final_png}')
    if final_bin.exists():
        print(f'  wrote {final_bin}')

    return final_json


def _find_sample_frames(batch_dir: Path, barcode: str):
    """All <barcode>_posN.tif in batch_dir except pos0, sorted numerically by N."""
    pos_re = re.compile(POS_RE_TEMPLATE.format(barcode=re.escape(barcode)))
    frames = []
    for tif_path in batch_dir.glob(f'{barcode}_pos*.tif'):
        m = pos_re.match(tif_path.name)
        if not m:
            continue
        pos = int(m.group(1))
        if pos == 0:
            continue
        frames.append((pos, tif_path))
    frames.sort(key=lambda t: t[0])
    return frames


def _integrate_sample_frame(tif_path: Path, context, outfolder: Path, overwrite: bool):
    out_stem = outfolder / tif_path.stem
    lineout_png = outfolder / f'{tif_path.stem}_lineout.png'
    expected = [Path(str(out_stem) + '.' + lib.FORMAT_EXT[fmt]) for fmt in cfg.INTEGRATION_OUTPUT_FORMATS]
    if not overwrite and lineout_png.exists() and all(p.exists() for p in expected):
        print(f'{tif_path.name}: outputs already exist -- skipping (pass --overwrite to redo)')
        return

    image = tifffile.imread(tif_path).astype(np.float32)
    ir = lib.integrate_with_context(
        image, context,
        error_model=cfg.ERROR_MODEL,
        pixel_weighted_averaging=cfg.PIXEL_WEIGHTED_AVERAGING,
    )
    written = lib.write_integration_outputs(ir, out_stem, cfg.INTEGRATION_OUTPUT_FORMATS, subpixel_k=cfg.SUBPIXEL_K)
    for fmt, path in written.items():
        print(f'  {fmt:8s} -> {path}  ({path.stat().st_size} bytes)')

    lib.render_intensity_plot_png(ir, lineout_png, title=f'{tif_path.name} -- integrated profile ({ir.method})')
    print(f'  lineout  -> {lineout_png}  ({lineout_png.stat().st_size} bytes)')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--batch-dir', required=True, type=Path, help='folder holding the batch\'s .tif/.metadata files')
    parser.add_argument('--barcode', required=True, help='batch barcode, e.g. ANLXRD00012')
    parser.add_argument('--outfolder', type=Path, default=None, help='output folder (default: --batch-dir, i.e. write in place)')
    parser.add_argument('--overwrite', action='store_true', default=None,
                         help='redo calibration/integration even if outputs already exist '
                              f'(default: midas_17bm_config.OVERWRITE, currently {cfg.OVERWRITE})')
    parser.add_argument('--only-full-rings', type=int, choices=(0, 1), default=None,
                         help='1 = cap integration R_MAX to the radius where rings are still fully '
                              'on-detector (nearest-edge distance from the beam centre); 0 = use the full '
                              'configured/auto range (midas_17bm_config.R_MAX_PX) '
                              f'(default: midas_17bm_config.ONLY_FULL_RINGS, currently {cfg.ONLY_FULL_RINGS})')
    parser.add_argument('--mask-file', type=Path, default=None,
                         help='bad-pixel mask file (.tif/.tiff or .npy), same shape as the detector image; '
                              '1/non-zero = bad pixel, 0 = good pixel '
                              f'(default: midas_17bm_config.MASK_FILE, currently {cfg.MASK_FILE})')
    args = parser.parse_args()

    overwrite = cfg.OVERWRITE if args.overwrite is None else args.overwrite
    only_full_rings = cfg.ONLY_FULL_RINGS if args.only_full_rings is None else args.only_full_rings
    mask_file = cfg.MASK_FILE if args.mask_file is None else args.mask_file

    batch_dir = args.batch_dir
    if not batch_dir.is_dir():
        sys.exit(f'error: --batch-dir does not exist or is not a directory: {batch_dir}')

    outfolder = args.outfolder if args.outfolder is not None else batch_dir
    outfolder.mkdir(parents=True, exist_ok=True)

    pos0_tif = batch_dir / f'{args.barcode}_pos0.tif'
    if not pos0_tif.exists():
        sys.exit(f'error: calibrant frame not found: {pos0_tif}')

    if mask_file is not None:
        mask_file = Path(mask_file)
        if not mask_file.exists():
            sys.exit(f'error: --mask-file does not exist: {mask_file}')

    calib_json = _calibrate_pos0(pos0_tif, outfolder, overwrite)

    sample_frames = _find_sample_frames(batch_dir, args.barcode)
    if not sample_frames:
        sys.exit(f'error: no sample frames ({args.barcode}_posN.tif, N>0) found in {batch_dir}')

    r_min = lib.resolve_r_min_px(calib_json, cfg.R_MIN_PX, cfg.R_MIN_2THETA_DEG)
    if only_full_rings:
        full_r_max = lib.full_ring_r_max_px(calib_json)
        r_max = full_r_max if cfg.R_MAX_PX is None else min(cfg.R_MAX_PX, full_r_max)
    else:
        r_max = cfg.R_MAX_PX
    print(f'\nintegration range: r_min={r_min:.2f} px, r_max={r_max} px '
          f'(--only-full-rings={only_full_rings})')
    print(f'mask file: {mask_file if mask_file is not None else "(none)"}')
    print(f'eta exclude wedges (deg): {cfg.ETA_EXCLUDE_DEG if cfg.ETA_EXCLUDE_DEG else "(none)"}')

    print(f'integrating {len(sample_frames)} sample frame(s) against {calib_json.name} '
          f'(detector mapping built once, reused for all)...')
    context = lib.build_integration_context(
        calib_json,
        method=cfg.BINNING_METHOD,
        r_bin_size=cfg.R_BIN_SIZE_PX, eta_bin_size=cfg.ETA_BIN_SIZE_DEG,
        r_min=r_min, r_max=r_max,
        eta_min=cfg.ETA_MIN_DEG, eta_max=cfg.ETA_MAX_DEG,
        subpixel_k=cfg.SUBPIXEL_K, polygon_n_jobs=cfg.POLYGON_N_JOBS,
        polarization=cfg.POLARIZATION_CORRECTION, pol_fraction=cfg.POLARIZATION_FRACTION,
        pol_plane_eta_deg=cfg.POLARIZATION_PLANE_ETA_DEG,
        mask=mask_file, eta_exclude_deg=cfg.ETA_EXCLUDE_DEG,
    )

    print(f'\n[pos0] {pos0_tif.name} (calibrant)')
    try:
        _integrate_sample_frame(pos0_tif, context, outfolder, overwrite)
    except Exception as exc:
        print(f'  ERROR integrating {pos0_tif.name}: {exc}', file=sys.stderr)

    failures = []
    for pos, tif_path in sample_frames:
        print(f'\n[pos{pos}] {tif_path.name}')
        try:
            _integrate_sample_frame(tif_path, context, outfolder, overwrite)
        except Exception as exc:
            print(f'  ERROR integrating {tif_path.name}: {exc}', file=sys.stderr)
            failures.append(tif_path.name)

    print(f'\ndone: {len(sample_frames) - len(failures)}/{len(sample_frames)} sample frame(s) integrated successfully')
    if failures:
        print(f'failed: {failures}', file=sys.stderr)


if __name__ == '__main__':
    main()
