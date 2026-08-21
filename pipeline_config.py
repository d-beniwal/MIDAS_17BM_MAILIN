"""Single editable knobs file for `calibrate.py` and `integrate.py`.

Edit this file to change calibrant, calibration tuning, or integration
binning/output settings -- both CLI tools import it directly.
"""

# --- Calibrant ----------------------------------------------------------------
# Either:
#   (a) a registered name string -- a key into midas_calibrate_v2.CALIBRANTS
#       (e.g. 'LaB6', 'CeO2', 'Si', 'Al2O3'), or
#   (b) a custom dict with your own lattice parameters, for a calibrant that
#       isn't registered:
#           {'sg': <int space group number>,
#            'a': <float, Angstrom>, 'b': <float, Angstrom>, 'c': <float, Angstrom>,
#            'alpha': <float, deg>, 'beta': <float, deg>, 'gamma': <float, deg>}
#       Both midas_calibrate_v2.calibrate()/make_seed() and this project's own
#       ring_radii_px() accept either form directly -- no extra wrapping needed.
#
# Example custom-lattice override (cubic, a=5.4310 A, space group 227 / Fd-3m):
#   CALIBRANT = {'sg': 227, 'a': 5.4310, 'b': 5.4310, 'c': 5.4310,
#                'alpha': 90.0, 'beta': 90.0, 'gamma': 90.0}
#
# 17BM mail-in calibration frames are today always LaB6 (NIST SRM 660c,
# a=4.1569 A, space group 221, Pm-3m) -- see .context/DECISIONS.md for why the
# .metadata sidecar's own calibrantName field must NOT be trusted instead.
CALIBRANT = 'LaB6'

# --- Detector pixel pitch fallback (used only if a .metadata sidecar omits it)
DEFAULT_PX_UM = 150.0

# --- calibrate() tuning ------------------------------------------------------
# BC/Lsd are ALWAYS auto-seeded from the image itself (see calibrate_lab6 in
# pipeline_lib.py) -- these knobs only affect the refinement stage, never the
# seed.
#
# refine_distortion controls how many of the 15 harmonic distortion
# coefficients midas_calibrate_v2 refines. Accepts:
#   - True                -> 'full' (all 15 coefficients)
#   - False / None        -> 'none' (no distortion refinement)
#   - a named block (str): 'none', 'radial', 'radial+1fold', 'radial+2fold',
#     'radial+3fold', 'radial+4fold', 'full'
#       'radial'       -> iso_R2, iso_R4, iso_R6 only (isotropic radial terms)
#       'radial+Nfold' -> adds the N-fold azimuthal amplitude/phase pairs on
#                         top of the radial terms (e.g. 'radial+2fold' adds
#                         a2/phi2 -- an elliptical/2-fold distortion term)
#   - an explicit sequence of v2 coefficient names, e.g. ('iso_R2', 'a2', 'phi2')
# Default here is 'radial' -- isotropic radial distortion only, no azimuthal
# (N-fold) terms, since those need more/cleaner ring coverage to constrain.
CALIBRATE_KWARGS = dict(
    n_iter=4,
    lm_max_iter=200,
    refine_tilts=True,
    refine_distortion='radial',
    build_residual_corr=False,
    max_2theta_deg=28.0,
    verbose=True,
)

# --- Integration binning defaults (mirrors MIDAS_GUI's own spin-box defaults)
R_BIN_SIZE_PX            = 1.0
ETA_BIN_SIZE_DEG         = 5.0
R_MIN_PX                 = 10.0
R_MAX_PX                 = None       # None -> auto: beam-centre-to-farthest-corner
ETA_MIN_DEG              = -180.0
ETA_MAX_DEG              = 180.0
BINNING_METHOD           = 'subpixel' # 'hard' | 'soft' | 'subpixel' | 'polygon'  (MIDAS_GUI default: subpixel K=2)
SUBPIXEL_K               = 2          # only used when BINNING_METHOD == 'subpixel'
POLYGON_N_JOBS           = -1         # only used when BINNING_METHOD == 'polygon'
ERROR_MODEL              = 'poisson'  # 'poisson' | 'azimuthal' | 'hybrid'  (hard/subpixel/polygon only)
PIXEL_WEIGHTED_AVERAGING = True       # weight each eta slice by its pixel/area coverage when collapsing to 1D

# --- Ring-overlay display -----------------------------------------------------
RING_TWO_THETA_MAX_DEG = 25.0   # how far out (2theta, deg) to draw predicted rings

# --- Integration output formats ------------------------------------------------
# Any subset of: 'csv', 'xye', 'fxye', 'dat', 'esg', '2d_csv'  (see FORMAT_EXT
# in pipeline_lib.py for the file extension each one writes).
INTEGRATION_OUTPUT_FORMATS = ['csv', 'xye', 'fxye', 'dat', 'esg', '2d_csv']
