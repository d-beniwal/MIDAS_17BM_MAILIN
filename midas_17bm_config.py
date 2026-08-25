"""Single editable knobs file for `midas_17bm_pipeline.py`.

Edit this file to change calibrant, calibration tuning, or integration
binning/output settings -- the CLI imports it directly.
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
# midas_17bm_lib.py) -- these knobs only affect the refinement stage, never the
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
R_BIN_SIZE_PX            = 0.5
ETA_BIN_SIZE_DEG         = 5.0
R_MIN_PX                 = 10.0
R_MIN_2THETA_DEG         = 1       # if set (deg), overrides R_MIN_PX -- converted to px via the calibration's own Lsd/pxY
R_MAX_PX                 = None       # None -> auto: beam-centre-to-farthest-corner (midas_17bm_pipeline.py's --only-full-rings further caps this -- see its own help text)
ETA_MIN_DEG              = -180.0
ETA_MAX_DEG              = 180.0
BINNING_METHOD           = 'subpixel' # 'hard' | 'soft' | 'subpixel' | 'polygon'  (MIDAS_GUI default: subpixel K=2)
SUBPIXEL_K               = 2          # only used when BINNING_METHOD == 'subpixel'
POLYGON_N_JOBS           = -1         # only used when BINNING_METHOD == 'polygon'
ERROR_MODEL              = 'poisson'  # 'poisson' | 'azimuthal' | 'hybrid'  (hard/subpixel/polygon only)
PIXEL_WEIGHTED_AVERAGING = True       # weight each eta slice by its pixel/area coverage when collapsing to 1D

# --- Bad-pixel mask (optional) -------------------------------------------------
# Path to a bad-pixel mask file (.tif/.tiff or .npy), same shape as the
# detector image. Convention: 1/non-zero = bad pixel (excluded from
# integration), 0 = good pixel -- matches midas_integrate_v2's own mask
# convention, so no inversion is needed. None (default) -> no mask.
# Overridable per run with midas_17bm_pipeline.py's --mask-file flag.
MASK_FILE = None

# --- Azimuthal (eta) exclusion wedges (optional) -------------------------------
# Blank out one or more angular wedges from the integration -- e.g. a
# beamstop-arm shadow or a detector-tile seam that always falls at the same
# eta -- WITHOUT cropping the overall ETA_MIN_DEG/ETA_MAX_DEG coverage above
# (that pair sets a single contiguous window; this instead punches a hole(s)
# out of whatever window is active). Internally this is just another
# bad-pixel mask: the excluded wedge(s) are OR'd together with MASK_FILE
# above and passed to the same `mask=` machinery, so excluded pixels are
# treated exactly like bad pixels (dropped from every bin they'd otherwise
# fall in).
#
# eta convention -- this is THE eta used everywhere else in this pipeline
# (ETA_MIN_DEG/ETA_MAX_DEG above, ETA_BIN_SIZE_DEG binning,
# POLARIZATION_PLANE_ETA_DEG below, and the eta axis of the '2d_csv' cake
# output), because midas_17bm_lib.build_eta_exclusion_mask() computes these
# wedges from midas_integrate_v2's own per-pixel eval_pixel_REta(spec) field
# -- the exact same array HardBinGeometry/SubpixelBinGeometry/etc. bin
# against. This was verified numerically (not assumed) against
# midas_calibrate_v2.forward.geometry.pixel_to_REta with zero tilts:
#   eta =    0 deg -> straight DOWN from the beam centre (as drawn on screen
#                     by render_calibration_overlay_png(), i.e. increasing
#                     row/Z)
#   eta =  +90 deg -> RIGHT (increasing column/Y)
#   eta = +/-180   -> UP
#   eta =  -90 deg -> LEFT
# eta increases counterclockwise on screen. NOTE: this is NOT the same eta
# as midas_integrate_v2.dac.build_gasket_mask (a DAC-gasket-specific helper)
# -- that function's eta is a mirror image of this one
# (eta_gasket = 90 - eta_here), so do not reuse gasket-mask angles here or
# vice versa.
#
# None (default) -> no exclusion. Otherwise a list of wedges, each either
#   (eta_min_deg, eta_max_deg)
# or
#   (eta_min_deg, eta_max_deg, symmetry)
# `symmetry` (default 'single' when omitted):
#   'single'    -- only the given wedge
#   'two_fold'  -- also excludes the 180 deg-opposite wedge
#   'four_fold' -- also excludes the +/-90 deg wedges
#
# Example -- exclude +/-5 deg about horizontal on the right side only
# (the case this knob was added for -- note the wedge is centred on +90,
# NOT 0, since +90 is "right" in this convention):
#   ETA_EXCLUDE_DEG = [(85.0, 95.0)]
#
# Example -- same +/-5 deg band on BOTH the right and left (mirror-image
# shadow, e.g. a beamstop arm crossing straight through the beam centre):
#   ETA_EXCLUDE_DEG = [(85.0, 95.0, 'two_fold')]
#
# Example -- two independent wedges (right-horizontal shadow + a separate
# seam near the bottom of the detector, eta~0):
#   ETA_EXCLUDE_DEG = [(85.0, 95.0), (-5.0, 5.0)]
ETA_EXCLUDE_DEG = [(75,105)]

# --- Ring-overlay display -----------------------------------------------------
RING_TWO_THETA_MAX_DEG = 25.0   # how far out (2theta, deg) to draw predicted rings

# --- Polarization correction ---------------------------------------------------
# Matches midas_integrate_v2.corrections.intensity.polarization_factor /
# PolarizationCorrection: corrected = raw / (1 - PF*sin^2(2theta)*cos^2(eta-plane)).
POLARIZATION_CORRECTION    = True
POLARIZATION_FRACTION      = 0.99   # midas package default (PolarizationCorrection default)
POLARIZATION_PLANE_ETA_DEG = 0.0    # midas package default

# --- Integration output formats ------------------------------------------------
# Any subset of: 'csv', 'xye', 'fxye', 'dat', 'esg', '2d_csv'  (see FORMAT_EXT
# in midas_17bm_lib.py for the file extension each one writes).
INTEGRATION_OUTPUT_FORMATS = ['csv', 'xye', 'fxye', 'dat', 'esg', '2d_csv']

# --- CLI-overridable batch pipeline flags ---------------------------------------
# Defaults used when the corresponding midas_17bm_pipeline.py flag is NOT passed
# on the command line. Precedence (lowest to highest): hardcoded fallback in
# midas_17bm_pipeline.py < this config value < an explicit CLI flag.
OVERWRITE        = True   # --overwrite: redo calibration/integration even if outputs already exist
ONLY_FULL_RINGS  = 1       # --only-full-rings: 1 = cap integration R_MAX to the radius where rings are
                            # still fully on-detector; 0 = use the full configured/auto range (R_MAX_PX above)

# --- Batch pipeline (mail-in acquisition hook) ---------------------------------
# Absolute path to the python interpreter of THIS analysis conda env (the one
# with midas_calibrate_v2/midas_integrate_v2/torch installed, i.e. `midas_17bm`
# per environment.yml). The mail-in acquisition GUI (mail_in_programs/mailin.py)
# runs in a DIFFERENT env (PyQt5 + epics, no midas/torch packages), so it must
# launch midas_17bm_pipeline.py with this explicit interpreter rather than its own
# sys.executable. On the real beamline control PC this will be a Windows path
# to .../envs/midas_17bm/python.exe -- UPDATE THIS before deploying.
BATCH_ANALYSIS_PYTHON = r"C:\Users\17bmuser\AppData\Local\miniconda3\envs\midas_17bm\bin\python"
