"""Shared calibration/integration logic for `calibrate.py` and `integrate.py`.

Ported from `calibration_integration_pipeline.ipynb` (validated against the
17BM mail-in 49 keV LaB6 calibration set -- see .context/DECISIONS.md for the
reasoning behind the choices baked in here, e.g. why BC/Lsd are always
auto-seeded from the image rather than trusted from the .metadata sidecar).
"""
import json
import math
import configparser
from pathlib import Path
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional, Tuple, Dict

import numpy as np
import tifffile
import torch
import contourpy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from midas_calibrate_v2 import calibrate as _midas_calibrate, CALIBRANTS
from midas_calibrate_v2.seed.auto_seed import make_seed
from midas_calibrate_v2.compat import spec_from_calibration_json
from midas_hkls import SpaceGroup, Lattice, generate_hkls
from midas_integrate_v2 import (
    eval_pixel_REta,
    write_csv, write_xye, write_fxye, write_dat, write_esg, write_2d_csv,
    build_provenance,
)
from midas_integrate_v2.binning import (
    HardBinGeometry, integrate_hard,
    SoftBinGeometry, integrate_soft,
    SubpixelBinGeometry, integrate_subpixel,
    PolygonBinGeometry, integrate_polygon,
)
from midas_integrate_v2.binning.variance import (
    integrate_hard_with_variance,
    integrate_subpixel_with_variance,
    integrate_polygon_with_variance,
)

H_C_KEV_A = 12.398419843320026  # keV * Angstrom (hc)


# ============================================================================
# Metadata sidecar parsing
# ============================================================================

def find_metadata_sidecar(tif_path: Path) -> Optional[Path]:
    """Resolve a .tif's metadata sidecar under either of 17BM's two naming
    conventions (`foo.tif.metadata` or `foo.metadata`)."""
    tif_path = Path(tif_path)
    for candidate in (Path(str(tif_path) + '.metadata'), tif_path.with_suffix('.metadata')):
        if candidate.exists():
            return candidate
    return None


def _resolve_wavelength_A(fields: Dict[str, str]) -> Tuple[float, str]:
    """Prefer an explicit Wavelength= (Angstrom); else derive from energy=,
    whose units are ambiguous across this beamline's own files and must be
    disambiguated by magnitude."""
    if 'wavelength' in fields:
        return float(fields['wavelength']), 'metadata Wavelength= (A)'
    if 'energy' in fields:
        e = float(fields['energy'])
        if e > 1000:  # eV, e.g. energy=49000
            return H_C_KEV_A / (e / 1000.0), f'metadata energy={e} (eV)'
        return H_C_KEV_A / e, f'metadata energy={e} (keV)'  # keV, e.g. energy=48.9652
    raise ValueError('no Wavelength= or energy= field found in metadata')


def read_qxrd_metadata(metadata_path: Path, default_px_um: float = 150.0) -> dict:
    """Parse a 17BM QXRD .metadata sidecar (Windows-INI / QSettings style).

    Returns wavelength/pixel-pitch resolved and unit-normalized, plus the raw
    flattened fields for reference. Deliberately does NOT surface
    detectorDistance / centerX / centerY / calibrantName as trustworthy
    geometry -- those fields are stale at this beamline.
    """
    cp = configparser.ConfigParser(strict=False, interpolation=None)  # raw QSettings values contain literal '%' -- no template interpolation
    cp.optionxform = str
    cp.read(metadata_path)

    # Flatten all sections; a real key collision between sections (e.g. both
    # defining wavelength/energy) has not been observed on this beamline.
    flat = {}
    for section in cp.sections():
        for k, v in cp[section].items():
            flat[k.lower()] = v

    wavelength_A, wavelength_source = _resolve_wavelength_A(flat)
    pxY = float(flat.get('detectorxpixelsize', default_px_um))
    pxZ = float(flat.get('detectorypixelsize', pxY))

    return dict(
        wavelength_A=wavelength_A,
        wavelength_source=wavelength_source,
        pxY_um=pxY,
        pxZ_um=pxZ,
        rawWidth=int(flat['rawwidth']) if 'rawwidth' in flat else None,
        rawHeight=int(flat['rawheight']) if 'rawheight' in flat else None,
        metadata_calibrant_name_UNTRUSTED=flat.get('calibrantname'),
        metadata_detector_distance_mm_UNTRUSTED=flat.get('detectordistance'),
        raw=flat,
    )


# ============================================================================
# Calibration
# ============================================================================

@dataclass
class CalibrationBundle:
    result: object                  # midas_calibrate_v2.AutoCalibrationResult (or an equivalent loaded from cache)
    seed: object                    # midas_calibrate_v2.seed.auto_seed.Seed (or an equivalent loaded from cache)
    metadata: dict
    image: np.ndarray
    calibration_json_path: Path
    tif_path: Path


def _result_from_cached_json(calibration_json_path: Path):
    """Reconstruct the handful of AutoCalibrationResult fields actually used
    downstream, from a previously-written calibration.json -- avoids
    recalibrating a frame whose result is already on disk."""
    with open(calibration_json_path) as fh:
        c = json.load(fh)
    result = SimpleNamespace(
        Lsd=c['Lsd_um'], BC_y=c['BC_y_px'], BC_z=c['BC_z_px'],
        tx=c.get('tx_deg', 0.0), ty=c['ty_deg'], tz=c['tz_deg'],
        wavelength_A=c['wavelength_A'], pxY=c['pxY_um'], pxZ=c['pxZ_um'],
        NrPixelsY=c['NrPixelsY'], NrPixelsZ=c['NrPixelsZ'],
        distortion=c.get('distortion', {}),
        post_residual_strain_uE=c.get('post_residual_strain_uE'),
        in_loop_strain_uE=c.get('in_loop_strain_uE'),
        residual_corr_bin_path=c.get('residual_corr_bin'),
        seed_BC_y=c.get('seed_BC_y'), seed_BC_z=c.get('seed_BC_z'), seed_Lsd=c.get('seed_Lsd_um'),
        unconstrained=c.get('unconstrained', []), at_bounds=c.get('at_bounds', []),
    )
    seed = SimpleNamespace(BC_y=c.get('seed_BC_y'), BC_z=c.get('seed_BC_z'), Lsd_um=c.get('seed_Lsd_um'))
    return result, seed


def calibrate_lab6(tif_path, output_dir, *, dark_path=None, calibrant='LaB6',
                    overwrite=False, default_px_um=150.0, **calibrate_kwargs) -> CalibrationBundle:
    """Calibrate one LaB6 (or other registered/custom calibrant) frame end to end.

    Beam centre and Lsd are ALWAYS found by auto_seed from the ring pattern in
    `tif_path` itself -- the .metadata sidecar's own detectorDistance /
    centerX / centerY fields are read (see read_qxrd_metadata) but never fed
    in here. Only wavelength and pixel pitch come from metadata.

    `calibrant` is either a registered name (str, key into
    midas_calibrate_v2.CALIBRANTS) or a custom lattice dict
    ({'sg', 'a', 'b', 'c', 'alpha', 'beta', 'gamma'}) -- both flow straight
    into make_seed()/calibrate() unchanged.

    `output_dir` is where midas_calibrate_v2 writes calibration.json (+
    residual_corr.bin) -- the caller owns naming/placement of the final
    output files.
    """
    tif_path = Path(tif_path)
    output_dir = Path(output_dir)

    sidecar = find_metadata_sidecar(tif_path)
    if sidecar is None:
        raise FileNotFoundError(f'no .metadata sidecar found for {tif_path}')
    meta = read_qxrd_metadata(sidecar, default_px_um=default_px_um)

    img = tifffile.imread(tif_path).astype(np.float32)

    calibration_json_path = output_dir / 'calibration.json'
    verbose = calibrate_kwargs.get('verbose', True)

    if not overwrite and calibration_json_path.exists():
        if verbose:
            print(f'[calibrate_lab6] {tif_path.name}: using cached {calibration_json_path}')
        result, seed = _result_from_cached_json(calibration_json_path)
        return CalibrationBundle(result=result, seed=seed, metadata=meta, image=img,
                                  calibration_json_path=calibration_json_path, tif_path=tif_path)

    dark = tifffile.imread(dark_path).astype(np.float32) if dark_path else None

    # --- Step 1: auto-seed -- BC and Lsd from the ring pattern itself.
    seed = make_seed(img, wavelength_A=meta['wavelength_A'], px_um=meta['pxY_um'],
                      calibrant=calibrant, use_diplib=False)
    if verbose:
        print(f'[calibrate_lab6] {tif_path.name}: seed {seed}')

    # --- Step 2: LM-refine the full geometry, starting from that seed.
    result = _midas_calibrate(
        img, wavelength=meta['wavelength_A'], pxY=meta['pxY_um'], pxZ=meta['pxZ_um'],
        dark=dark, calibrant=calibrant,
        initial_BC_y=seed.BC_y, initial_BC_z=seed.BC_z, initial_Lsd=seed.Lsd_um,
        output_dir=output_dir, **calibrate_kwargs,
    )

    return CalibrationBundle(
        result=result, seed=seed, metadata=meta, image=img,
        calibration_json_path=calibration_json_path, tif_path=tif_path,
    )


def ring_radii_px(calibrant, wavelength_A, Lsd_um, pxY_um, two_theta_max_deg=25.0):
    """Ideal (undistorted, flat-panel) ring radii in px, deduplicated by
    2theta -- distinct hkl families can share the same 2theta.

    `calibrant` is either a registered name (str) or a custom lattice dict.
    """
    cal = CALIBRANTS[calibrant] if isinstance(calibrant, str) else calibrant
    lat = Lattice(a=cal['a'], b=cal.get('b', cal['a']), c=cal.get('c', cal['a']),
                  alpha=cal.get('alpha', 90.0), beta=cal.get('beta', 90.0), gamma=cal.get('gamma', 90.0))
    sg = SpaceGroup.from_number(cal['sg'])
    refs = generate_hkls(sg, lat, wavelength_A=wavelength_A, two_theta_max_deg=two_theta_max_deg)
    return sorted(set(round(Lsd_um / pxY_um * math.tan(math.radians(ref.two_theta_deg)), 3) for ref in refs))


def render_calibration_overlay_png(bundle: CalibrationBundle, calibration_json_path, out_png, *,
                                    calibrant, two_theta_max_deg=25.0, downsample=4) -> Path:
    """Raw image (downsampled for display) + predicted ring overlay from the
    full fitted geometry (tilts + harmonic distortion), via eval_pixel_REta
    contoured at each ring's ideal flat-panel radius. Saved directly to PNG
    (matplotlib/Agg -- no display needed, no plotly/kaleido dependency)."""
    calibration_json_path = Path(calibration_json_path)
    out_png = Path(out_png)

    spec = spec_from_calibration_json(calibration_json_path, RBinSize=1.0)  # binning unused for the overlay itself
    R_px = eval_pixel_REta(spec)[0].detach().numpy()   # (NrPixelsZ, NrPixelsY), px; tilts+distortion baked in
    NZ, NY = R_px.shape

    radii = ring_radii_px(calibrant, float(spec.Wavelength), float(spec.Lsd), spec.pxY, two_theta_max_deg)
    cg = contourpy.contour_generator(z=R_px, line_type=contourpy.LineType.Separate)
    segments = [line for lvl in radii if 0 < lvl < min(NY, NZ) for line in cg.lines(lvl)]

    # Downsample the raw image for a lighter heatmap; the ring overlay itself
    # stays at full detector resolution.
    img = bundle.image
    d = downsample
    NZf, NYf = (img.shape[0] // d) * d, (img.shape[1] // d) * d
    img_ds = img[:NZf, :NYf].reshape(NZf // d, d, NYf // d, d).mean(axis=(1, 3))
    disp = np.log1p(np.clip(img_ds, 0, None))
    vmin, vmax = np.percentile(disp, 50), np.percentile(disp, 99.9)

    fig, ax = plt.subplots(figsize=(8, 8.6), dpi=100)
    ax.imshow(disp, cmap='gray', vmin=vmin, vmax=vmax, origin='upper',
              extent=[0, NY, NZ, 0], aspect='equal')
    if segments:
        ax.add_collection(LineCollection(segments, colors='#00E5FF', linewidths=0.8,
                                          label='predicted rings (tilt+distortion)'))
    ax.plot(float(spec.BC_y), float(spec.BC_z), marker='o', markersize=8, linestyle='none',
            markerfacecolor='red', markeredgecolor='yellow', markeredgewidth=1.2,
            label='refined beam centre')
    ax.set_xlim(0, NY)
    ax.set_ylim(NZ, 0)
    ax.set_xlabel('Y (px, column)')
    ax.set_ylabel('Z (px, row)')
    ax.set_title(f'{bundle.tif_path.name}\n'
                 f'Lsd={float(spec.Lsd) / 1000:.3f} mm   BC=({float(spec.BC_y):.1f}, {float(spec.BC_z):.1f}) px')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.08), ncol=2, frameon=False, fontsize=9)
    fig.tight_layout()

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png


# ============================================================================
# Integration
# ============================================================================

_BINNING_METHODS = {
    'hard':     dict(geometry=HardBinGeometry,     integrate=integrate_hard,     integrate_var=integrate_hard_with_variance),
    'soft':     dict(geometry=SoftBinGeometry,      integrate=integrate_soft,     integrate_var=None),
    'subpixel': dict(geometry=SubpixelBinGeometry,  integrate=integrate_subpixel, integrate_var=integrate_subpixel_with_variance),
    'polygon':  dict(geometry=PolygonBinGeometry,   integrate=integrate_polygon,  integrate_var=integrate_polygon_with_variance),
}


@dataclass
class IntegrationResult:
    spec: object
    r_axis_px: np.ndarray
    two_theta_deg: np.ndarray
    q_invA: np.ndarray
    intensity: np.ndarray
    sigma: np.ndarray
    cake_2d: np.ndarray
    eta_axis_deg: np.ndarray
    method: str


def integrate_frame(image, calibration_json_path, *,
                     method='subpixel',
                     r_bin_size=1.0, eta_bin_size=5.0,
                     r_min=10.0, r_max=None, eta_min=-180.0, eta_max=180.0,
                     error_model='poisson',
                     pixel_weighted_averaging=True,
                     subpixel_k=2, polygon_n_jobs=-1) -> IntegrationResult:
    """Integrate `image` using the geometry saved in `calibration_json_path`.

    Returns a 1D profile (R px / 2theta deg / Q 1/A axes, intensity, sigma)
    plus the full 2D (eta, R) cake. `image` can be any frame on this
    detector -- a fresh sample exposure, not just the calibrant.
    """
    spec = spec_from_calibration_json(
        calibration_json_path, RBinSize=r_bin_size, EtaBinSize=eta_bin_size,
        RMin=r_min, RMax=r_max, EtaMin=eta_min, EtaMax=eta_max,
    )
    cfg = _BINNING_METHODS[method]
    build_kwargs = {'K': subpixel_k} if method == 'subpixel' else ({'n_jobs': polygon_n_jobs} if method == 'polygon' else {})
    geom = cfg['geometry'].from_spec(spec, **build_kwargs)
    image_t = torch.as_tensor(np.asarray(image, dtype=np.float64))

    if cfg['integrate_var'] is not None:
        mean_cake, sigma_cake = cfg['integrate_var'](image_t, geom, error_model=error_model, empty_bin_value=0.0)
    else:
        mean_cake = cfg['integrate'](image_t, geom)
        sigma_cake = torch.sqrt(torch.clamp(mean_cake, min=0.0))  # Poisson approx: no variance kernel for 'soft'

    if pixel_weighted_averaging:
        norm_kwargs = {'normalize': False} if method != 'soft' else {}
        weight_cake = cfg['integrate'](torch.ones_like(image_t), geom, **norm_kwargs)
        wsum = weight_cake.sum(dim=0).clamp(min=1e-12)
        intensity = (weight_cake * mean_cake).sum(dim=0) / wsum
        sigma = torch.sqrt((weight_cake ** 2 * sigma_cake ** 2).sum(dim=0)) / wsum
    else:
        intensity = mean_cake.mean(dim=0)
        sigma = torch.sqrt((sigma_cake ** 2).mean(dim=0))

    n_r = spec.n_r_bins
    r_axis_px = spec.RMin + spec.RBinSize * (np.arange(n_r) + 0.5)
    Lsd_um, pxY, wl_A = float(spec.Lsd), spec.pxY, float(spec.Wavelength)
    two_theta_deg = np.degrees(np.arctan(r_axis_px * pxY / Lsd_um))
    q_invA = 4 * np.pi * np.sin(np.radians(two_theta_deg / 2.0)) / wl_A
    eta_axis_deg = spec.EtaMin + spec.EtaBinSize * (np.arange(spec.n_eta_bins) + 0.5)

    return IntegrationResult(
        spec=spec, r_axis_px=r_axis_px, two_theta_deg=two_theta_deg, q_invA=q_invA,
        intensity=intensity.numpy(), sigma=sigma.numpy(),
        cake_2d=mean_cake.numpy(), eta_axis_deg=eta_axis_deg, method=method,
    )


FORMAT_WRITERS = {
    'csv':    lambda path, ir, meta: write_csv(path, r_axis=ir.r_axis_px, intensity=ir.intensity, sigma=ir.sigma, metadata=meta),
    'xye':    lambda path, ir, meta: write_xye(path, r_axis=ir.two_theta_deg, intensity=ir.intensity, sigma=ir.sigma, metadata=meta),
    'fxye':   lambda path, ir, meta: write_fxye(path, r_axis=ir.two_theta_deg, intensity=ir.intensity, sigma=ir.sigma, metadata=meta, x_unit='degrees_2theta'),
    'dat':    lambda path, ir, meta: write_dat(path, q_axis_invA=ir.q_invA, intensity=ir.intensity, sigma=ir.sigma, metadata=meta),
    'esg':    lambda path, ir, meta: write_esg(path, two_theta_deg=ir.two_theta_deg, intensity=ir.intensity, sigma=ir.sigma, wavelength_A=float(ir.spec.Wavelength), metadata=meta),
    '2d_csv': lambda path, ir, meta: write_2d_csv(path, int2d=ir.cake_2d, r_axis_px=ir.r_axis_px, eta_axis_deg=ir.eta_axis_deg, metadata=meta),
}
FORMAT_EXT = {'csv': 'csv', 'xye': 'xye', 'fxye': 'fxye', 'dat': 'dat', 'esg': 'esg', '2d_csv': '2d.csv'}


def write_integration_outputs(ir: IntegrationResult, out_stem, formats, *, subpixel_k=2) -> Dict[str, Path]:
    meta = build_provenance(ir.spec, integrate_mode=ir.method,
                             integrate_K=(subpixel_k if ir.method == 'subpixel' else None))
    out_stem = Path(out_stem)
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    written = {}
    for fmt in formats:
        path = Path(str(out_stem) + '.' + FORMAT_EXT[fmt])
        FORMAT_WRITERS[fmt](path, ir, meta)
        written[fmt] = path
    return written


def render_intensity_plot_png(ir: IntegrationResult, out_png, *, title=None) -> Path:
    """I vs 2theta lineout (+/-1 sigma band), saved directly to PNG
    (matplotlib/Agg) -- a quick visual check of the integrated profile."""
    out_png = Path(out_png)

    fig, ax = plt.subplots(figsize=(9.5, 4.6), dpi=100)
    ax.fill_between(ir.two_theta_deg, ir.intensity - ir.sigma, ir.intensity + ir.sigma,
                     color='#1f77b4', alpha=0.20, linewidth=0, label='+/-1 sigma')
    ax.plot(ir.two_theta_deg, ir.intensity, color='#1f77b4', linewidth=1.3, label='intensity')
    ax.set_xlabel('2theta (deg)')
    ax.set_ylabel('Intensity (a.u.)')
    ax.set_title(title if title is not None else f'integrated profile ({ir.method})')
    ax.legend(loc='upper right', frameon=False, fontsize=9)
    fig.tight_layout()

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png
