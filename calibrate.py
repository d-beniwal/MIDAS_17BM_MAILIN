#!/usr/bin/env python3
"""CLI: calibrate one LaB6 (or other configured calibrant) detector frame.

Usage:
    python calibrate.py --infile PATH --outfolder PATH [--overwrite]

Writes, into --outfolder:
    <infile-stem>_midas_calib.json                    -- calibration geometry
    <infile-stem>_midas_calib.png                      -- ring-overlay image
    <infile-stem>_midas_calib_residual_corr.bin         -- (if produced)

All calibrant/tuning parameters come from pipeline_config.py.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import pipeline_config as cfg
import pipeline_lib as lib


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--infile', required=True, type=Path, help='input .tif calibration frame')
    parser.add_argument('--outfolder', required=True, type=Path, help='output folder (created if missing)')
    parser.add_argument('--overwrite', action='store_true', help='recalibrate even if the output .json already exists')
    args = parser.parse_args()

    infile = args.infile
    if not infile.exists():
        sys.exit(f'error: --infile does not exist: {infile}')

    outfolder = args.outfolder
    outfolder.mkdir(parents=True, exist_ok=True)

    stem = infile.stem
    final_json = outfolder / f'{stem}_midas_calib.json'
    final_png = outfolder / f'{stem}_midas_calib.png'
    final_bin = outfolder / f'{stem}_midas_calib_residual_corr.bin'

    if final_json.exists() and not args.overwrite:
        print(f'{final_json} already exists -- skipping (pass --overwrite to redo)')
        return

    scratch_dir = outfolder / f'.{stem}_scratch'
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)
    scratch_dir.mkdir(parents=True)

    try:
        bundle = lib.calibrate_lab6(
            infile, scratch_dir,
            calibrant=cfg.CALIBRANT, overwrite=True, default_px_um=cfg.DEFAULT_PX_UM,
            **cfg.CALIBRATE_KWARGS,
        )

        scratch_json = scratch_dir / 'calibration.json'
        scratch_bin = scratch_dir / 'residual_corr.bin'

        # midas_calibrate_v2 always records a residual_corr_bin path in the
        # JSON (keyed off output_dir), even when build_residual_corr=False
        # never actually wrote the .bin -- null it out in that case, else
        # downstream readers (eval_pixel_REta et al.) try to load a file
        # that was never created (and, after the move below, no longer
        # exists at that path anyway).
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
    print(f'Lsd  = {r.Lsd / 1000:.4f} mm   (seed: {r.seed_Lsd / 1000:.4f} mm)')
    print(f'BC   = ({r.BC_y:.3f}, {r.BC_z:.3f}) px   (seed: ({r.seed_BC_y:.3f}, {r.seed_BC_z:.3f}) px)')
    print(f'tilts: tx={r.tx:+.4f}  ty={r.ty:+.4f}  tz={r.tz:+.4f} deg')
    if r.post_residual_strain_uE is not None:
        print(f'post-residual strain = {r.post_residual_strain_uE:.1f} microstrain')
    if r.unconstrained:
        print(f'params refined but NOT determined by the data (freeze + rerun candidates): {r.unconstrained}')
    if r.at_bounds:
        print(f'params sitting on a bound: {r.at_bounds}')
    print(f'wrote {final_json}')
    print(f'wrote {final_png}')
    if final_bin.exists():
        print(f'wrote {final_bin}')


if __name__ == '__main__':
    main()
