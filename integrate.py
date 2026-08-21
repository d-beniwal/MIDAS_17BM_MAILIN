#!/usr/bin/env python3
"""CLI: radially integrate one detector frame using a saved calibration.

Usage:
    python integrate.py --incalibfile PATH --infile PATH --outfolder PATH

Writes, into --outfolder, one file per format listed in
pipeline_config.INTEGRATION_OUTPUT_FORMATS, named
<infile-stem>.<format-extension>. All binning/output parameters come from
pipeline_config.py.
"""
import argparse
import sys
from pathlib import Path

import tifffile
import numpy as np

import pipeline_config as cfg
import pipeline_lib as lib


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--incalibfile', required=True, type=Path, help='calibration .json (from calibrate.py)')
    parser.add_argument('--infile', required=True, type=Path, help='input .tif frame to integrate')
    parser.add_argument('--outfolder', required=True, type=Path, help='output folder (created if missing)')
    parser.add_argument('--plot', type=int, choices=(0, 1), default=0,
                         help='1 = also save an I vs 2theta lineout PNG (<stem>_lineout.png); default 0')
    args = parser.parse_args()

    if not args.incalibfile.exists():
        sys.exit(f'error: --incalibfile does not exist: {args.incalibfile}')
    if not args.infile.exists():
        sys.exit(f'error: --infile does not exist: {args.infile}')

    args.outfolder.mkdir(parents=True, exist_ok=True)

    image = tifffile.imread(args.infile).astype(np.float32)

    ir = lib.integrate_frame(
        image, args.incalibfile,
        method=cfg.BINNING_METHOD,
        r_bin_size=cfg.R_BIN_SIZE_PX, eta_bin_size=cfg.ETA_BIN_SIZE_DEG,
        r_min=cfg.R_MIN_PX, r_max=cfg.R_MAX_PX,
        eta_min=cfg.ETA_MIN_DEG, eta_max=cfg.ETA_MAX_DEG,
        error_model=cfg.ERROR_MODEL,
        pixel_weighted_averaging=cfg.PIXEL_WEIGHTED_AVERAGING,
        subpixel_k=cfg.SUBPIXEL_K, polygon_n_jobs=cfg.POLYGON_N_JOBS,
    )

    out_stem = args.outfolder / args.infile.stem
    written = lib.write_integration_outputs(
        ir, out_stem, cfg.INTEGRATION_OUTPUT_FORMATS, subpixel_k=cfg.SUBPIXEL_K,
    )
    for fmt, path in written.items():
        print(f'{fmt:8s} -> {path}  ({path.stat().st_size} bytes)')

    if args.plot:
        lineout_png = args.outfolder / f'{args.infile.stem}_lineout.png'
        lib.render_intensity_plot_png(ir, lineout_png, title=f'{args.infile.name} -- integrated profile ({ir.method})')
        print(f'lineout  -> {lineout_png}  ({lineout_png.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
