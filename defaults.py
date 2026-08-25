known_types={
            '11bmStd': '11-BM Standard',
            '11bmL': '11-BM Large',
            '17bmStd':'17-BM Standard',
            '11idbStd':'11-ID-B Standard'
        }

default_sizes={
            '11bmStd': 1,
            '11bmL': 1,
            '17bmStd': 20,
            '11idbStd':20
        }

cartridge_types = {
        '11bm': ['11bmStd', '11bmL'],
        '17bm': ['17bmStd'],
        '11idb': ['11idbStd']
        # Add other beamlines and their cartridge types here
    }
    
known_beamlines = {
	'11-BM-B':'11bm',
	'11bm':'11bm',
	'11-BM':'11bm',
	'11BM':'11bm',
	'11-ID-B':'11idb',
	'11IDB':'11idb',
	'11idb':'11idb',
	'17-BM-B':'17bm',
	'17-BM':'17bm',
	'17BM':'17bm',
	'17bm':'17bm'
	}

beamline_info = {
    '11bm': {'i_cat': 'XSD-11', 'i_beamline_id': 90, 'i_technique_id':32, 'i_sector':11, 'station':'b', 'idorbm':'bm', "i_exp_desc":"High resolution high throughput powder diffraction."},
    '11idb': {'i_cat': 'XSD-11', 'i_beamline_id': 16, 'i_technique_id':29, 'i_sector':11, 'station':'b', 'idorbm':'id', "i_exp_desc":"High throughput powder diffraction and PDF."},
    '17bm': {'i_cat': 'XSD-17-BM', 'i_beamline_id': 88, 'i_technique_id':32, 'i_sector':17, 'station':'b', 'idorbm':'bm', "i_exp_desc":"High throughput powder diffraction"},
    # Add other beamlines and their configuration as necessary
}