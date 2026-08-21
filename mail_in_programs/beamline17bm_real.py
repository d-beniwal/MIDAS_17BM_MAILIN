import epics
import time
import itertools
from datetime import datetime
import os
from PIL import Image
import numpy as np
import json


class Beamline17BM:
    def __init__(self):
        print("[REAL] Beamline17BM initialized.")

        self.filter_pvs = {
            #'XIA1_1': "17bm:FltrRak1:Filter1Bo",
            #'XIA1_2': "17bm:FltrRak1:Filter2Bo",
            'XIA1_3': "17bm:FltrRak1:Filter3Bo",
            'XIA1_4': "17bm:FltrRak1:Filter4Bo",
            'XIA2_1': "17bm:FltrRak1:Filter5Bo",
            'XIA2_4': "17bm:FltrRak1:Filter8Bo"
        }
        #49 kEV
        #self.filter_strengths = {
         #   'XIA1_1': 12.39,
         #   'XIA1_2': 3.47,
          #  'XIA1_3': 1.88,
         #   'XIA1_4': 1.29,
         #   'XIA2_1': 1.06,
          #  'XIA2_4': 1.11
        #}
        #35 keV
        self.filter_strengths = {
            #'XIA1_1': 689,
            #'XIA1_2': 24.1,
            'XIA1_3': 5.0,
            'XIA1_4': 1.9,
            'XIA2_1': 1.1,
            'XIA2_4': 1.2
        }


         #35 keV
        self.filter_strengths_35 = {
            #'XIA1_1': 689,
            #'XIA1_2': 24.1,
            'XIA1_3': 5.0,
            'XIA1_4': 1.9,
            'XIA2_1': 1.1,
            'XIA2_4': 1.2
        }

        #27 keV
        self.filter_strengths_27 = {
            #'XIA1_1': 485.48,
            #'XIA1_2': 249.6,
            #'XIA1_3': 26.56,
            'XIA1_4': 3.65,
            'XIA2_1': 1.22,
            'XIA2_4': 1.49
        }

        self.active_filters = set()







    
                
    def SetFilters(self, filters_list):
        for f, pv in self.filter_pvs.items():
            epics.caput(pv, 1 if f in filters_list else 0)
        self.active_filters = set(filters_list)
        print(f"[REAL] Filters set: {sorted(self.active_filters)}")

    def RemoveFilter(self, *filters):
        for f in filters:
            if f in self.active_filters:
                self.active_filters.remove(f)
                epics.caput(self.filter_pvs[f], 0)
                print(f"[REAL] Removed filter: {f}")
        print(f"[REAL] Current filters: {sorted(self.active_filters)}")

    def GetFilterStatus(self):
        return sorted(self.active_filters)

    def get_total_attenuation(self):
        attenuation = 1.0
        for f in self.active_filters:
            attenuation *= self.filter_strengths[f]
        return attenuation

    def GetMaxValOnDet(self):
        attenuation = self.get_total_attenuation()
        base_val = 325400  # Unfiltered count rate
        max_val = base_val / attenuation if attenuation > 0 else base_val
        print(f"[REAL] Detector max value = {max_val:.2f} (attenuation: {attenuation:.2f})")
        return max_val

    def SetExpTime(self, value):
        print(f"[REAL] Setting exposure time to {value}s")
        epics.caput("17bmVarex:cam1:AcquireTime", value)

    def SetSubFrame(self, value):
        print(f"[REAL] Setting number of sub-frames to {value}")
        epics.caput("17bmVarex:cam1:NumImages", value)

    def SetDarkSubFrame(self, value):
        print(f"[REAL] Setting number of dark sub-frames to {value}")
        epics.caput("17bmVarex:cam1:PENumOffsetFrames", value)

    def SetSavingMode(self, flag):
        epics.caput("17bmVarex:TIFF1:EnableCallbacks", 1 if flag else 0)
        print(f"[REAL] Saving mode {'enabled' if flag else 'disabled'}")

    def MoveToSample(self, cartridge_position, sample_position):
        print(f"[REAL] Moving to sample - Cartridge: {cartridge_position}, Position: {sample_position}")
        pos = (cartridge_position - 1) * 72 + sample_position * 3
        epics.caput("17bm:m10.VAL", pos, wait=True)
        time.sleep(0.5)
        final_pos = epics.caget("17bm:m10.VAL")
        if final_pos != pos:
            print("Error: Sample move failed.")
            return False
        print("Move complete.")
        return True

    def Move_detector(self, position):
        print(f"[REAL] Moving detector to position: {position}")
        epics.caput("17bm:m33.VAL", position, wait=True)
        time.sleep(0.5)
        final_pos = epics.caget("17bm:m33.VAL")
        if final_pos != position:
            print("Error: Detector move failed.")
            return False
        print("Move complete.")
        return True

    def OpenFS(self):
        print("[REAL] Opening fast shutter...")
        epics.caput("17bm:XiaPfcu2:Filter2Bo.VAL", 0)
        time.sleep(1.0)
        print("[REAL] Fast shutter open.")

    def CloseFS(self):
        print("[REAL] Closing fast shutter...")
        epics.caput("17bm:XiaPfcu2:Filter2Bo.VAL", 1)
        time.sleep(1.0)
        print("[REAL] Fast shutter closed.")

    def CheckFSOpen(self):
        val = epics.caget("17bm:XiaPfcu2:Filter2Bo.VAL")
        is_open = val == 0
        print(f"[REAL] Fast shutter is {'open' if is_open else 'closed'}")
        return is_open

    def Check_Shutters(self):
        print("[REAL] Checking shutter status...")
        a_closed = epics.caget("PB:17BM:STA_A_FES_CLSD_PL")
        b_closed = epics.caget("PB:17BM:STA_B_SBS_CLSD_PL")
        if a_closed == 0 and b_closed == 0:
            print("[REAL] Shutters are open.")
            return True
        print("[REAL] Shutters are closed.")
        return False

        

    def TurnOnSave(self, filename):
        print(f"[REAL] Starting save to: {filename}")
        prefix_dir=r"Y:\mail_in"
        now = datetime.now()
        current_year=now.year
        current_month=now.strftime("%b")
        dir_path=os.path.join(prefix_dir,str(current_year),current_month)
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        epics.caput("17bmVarex:TIFF1:FilePath", dir_path)
        epics.caput("17bmVarex:TIFF1:FileName", filename)
        self.SetSavingMode(True)

    def TurnOffSave(self):
        print("[REAL] Stopping save...")
        self.SetSavingMode(False)

    def CollectDark(self, exp):
        print(f"[REAL] Collecting dark frame at {exp}s")
        self.CloseFS()
        self.SetExpTime(exp)
        epics.caput("17bmVarex:cam1:PEAcquireOffset", 1, wait=True)
        time.sleep(1)


    def Measure_Sample(self, exp, rockamt=1.0, dark=False):
        print(f"[REAL] Measuring Sample at {exp}s")
        self.CloseFS()
        self.SetExpTime(exp)
        if not dark:
            self.OpenFS()
        
        epics.caput("17bmVarex:cam1:Acquire", 1,wait=False)

        scanDone=False
        first=True
        while (not scanDone):
            curval=float(epics.caget("17bm:m11.RBV"))
            if rockamt>0:
                epics.caput("17bm:m11.VAL",curval+rockamt,wait=True)
                epics.caput("17bm:m11.VAL",curval-rockamt,wait=True)
                epics.caput("17bm:m11.VAL",curval,wait=True)
            if rockamt==0:
                if first:
                    start=False
                    while not start:
                        if epics.caget("17bmVarex:cam1:AcquireBusy")==1:
                            start=True
                        else: time.sleep(0.1)
                    first=False
                else: time.sleep(0.1)
            if epics.caget("17bmVarex:cam1:AcquireBusy")==0:
                scanDone=True
        self.CloseFS()
        time.sleep(1)

    def detect_hot_pixels(self,img_array, factor=3):
        mean_val = np.mean(img_array)
        std_val = np.std(img_array)
        threshold = mean_val + factor * std_val
        mask = img_array > threshold
        coords = np.argwhere(mask)
        return coords, threshold

    def export_bad_pixels(self, dir_path, badpix_name):
        _, threshold = self.detect_hot_pixels(self.img_array)
        coords = np.argwhere(self.img_array > threshold)
        bad_pixel_list = [
            {
                "Pixel": [int(x), int(y)],
                "Median": [3, 3]
                #"Set": 0
            }
            for y, x in coords
        ]

        # Ask user where to save the file
        file_path = os.path.join(dir_path,badpix_name+".json")

        data = {"Bad pixels": bad_pixel_list}
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"Exported {len(bad_pixel_list)} bad pixels to {file_path}")

    def Determine_BadPix(self):
        epics.caput("17bmVarex:TIFF1:NDArrayPort", "PEDET1")
        now = datetime.now()
        current_year=now.year
        current_month=now.strftime("%b")
        current_day=now.day
        prefix_dir=r"Y:\mail_in"
        dir_path=os.path.join(prefix_dir,str(current_year),current_month)

        badpix_name="BadPixel_"+str(current_year)+str(current_month)+str(current_day)
        self.TurnOnSave(badpix_name)
        self.Measure_Sample(exp=2, rockamt=0, dark=True)
        self.TurnOffSave()
        tiff_file=os.path.join(dir_path,badpix_name+".tif")
        img = Image.open(tiff_file)
        
        self.img_array = np.array(img)
        self.coords, threshold = self.detect_hot_pixels(self.img_array)
        self.export_bad_pixels(dir_path,badpix_name)
        epics.caput("17bmVarex:BadPix1:FileName",os.path.join(dir_path, badpix_name+".json"))
        epics.caput("17bmVarex:TIFF1:NDArrayPort", "BADPIX1")

    def get_max_block_median(self, img_array, sizeX=5, sizeY=5):
        """
        Divide the image into blocks of sizeY x sizeX and return the
        highest median block value. Using medians avoids single hot pixels
        dominating the exposure estimate.
        """
        if img_array is None or img_array.size == 0:
            return 0

        height, width = img_array.shape
        max_median = 0

        for y in range(0, height, sizeY):
            for x in range(0, width, sizeX):
                block = img_array[y:y + sizeY, x:x + sizeX]
                if block.size == 0:
                    continue

                block_median = float(np.median(block))
                if block_median > max_median:
                    max_median = block_median

        return max_median

                        
    def Determine_Exposure(self, wavelengthValue, sizeX=2, sizeY=2):
        print("[REAL] Starting exposure determination...")
        
        exptime = 0.2                
        #set filters based on energy
        if wavelengthValue < 0.3:
            test_filter = ['XIA1_2']
            test_attenuation = self.filter_strengths['XIA1_2']
        elif wavelengthValue < 0.4  and wavelengthValue > 0.3:
            test_filter = ['XIA1_4']
            test_attenuation = self.filter_strengths_35['XIA1_4']
        else:
            test_filter = ['XIA1_4']
            test_attenuation = self.filter_strengths_27['XIA1_4']

        # Save image directly from detector, not bad-pixel corrected stream
        epics.caput("17bmVarex:TIFF1:NDArrayPort", "BADPIX1")

        now = datetime.now()
        current_year = now.year
        current_month = now.strftime("%b")
        current_day = now.day
        prefix_dir = r"Y:\mail_in"
        dir_path = os.path.join(prefix_dir, str(current_year), current_month)

        exp_name = f"ExposureCheck_{current_year}{current_month}{current_day}"

        self.SetFilters(test_filter)
        self.SetSubFrame(10)
        self.SetSavingMode(False)

        self.TurnOnSave(exp_name)
        self.CollectDark(exptime)
        self.Measure_Sample(exp=exptime, rockamt=0)
        self.TurnOffSave()

        tiff_file = os.path.join(dir_path, exp_name + ".tif")
        if not os.path.exists(tiff_file):
            print(f"[REAL] Warning: Exposure image not found: {tiff_file}")
            return 1.0, []

        try:
            img = Image.open(tiff_file)
            img_array = np.array(img)
        except Exception as e:
            print(f"[REAL] Warning: Failed to read exposure image: {e}")
            return 1.0, []

        max_val = self.get_max_block_median(img_array, sizeX=sizeX, sizeY=sizeY)
        print(f"[REAL] Max block median ({sizeX}x{sizeY}) = {max_val:.2f}")

        if not max_val or max_val <= 0:
            print("[REAL] Warning: Invalid max value from detector image")
            return 1.0, []

        ideal_val = 15000
        measured_exposure = ideal_val / max_val
        unfiltered_exposure = measured_exposure / test_attenuation

        print(f"[REAL] Measured exposure (with XIA1_2): {measured_exposure:.2f}s")
        print(f"[REAL] Unfiltered equivalent exposure: {unfiltered_exposure:.2f}s")

        if unfiltered_exposure >= 1.0:
            print("[REAL] No filters needed; unfiltered exposure sufficient.")
            return min(round(unfiltered_exposure, 2), 5.0), []

        all_filters = list(self.filter_strengths.keys())
        best_combo = []
        best_exp = 0
        min_attenuation = float("inf")

        for r in range(1, len(all_filters) + 1):
            for combo in itertools.combinations(all_filters, r):
                attenuation = 1.0
                for f in combo:
                    attenuation *= self.filter_strengths[f]

                final_exp = unfiltered_exposure * attenuation

                if 0.8 <= final_exp <= 5.0 and attenuation < min_attenuation:
                    best_combo = combo
                    best_exp = final_exp
                    min_attenuation = attenuation

        if not best_combo:
            fallback = min(unfiltered_exposure, 5.0)
            print("[REAL] No suitable filter combo found; using no filters.")
            return round(fallback, 2), []

        print(f"[REAL] Best filter combination: {sorted(best_combo)}")
        print(f"[REAL] Final estimated exposure: {best_exp:.2f}s (attenuation: {min_attenuation:.2f})")
        return round(best_exp, 2), sorted(best_combo)




    def get_pv_values(self):
        # Replace with real PV reads
        return {
           # i00=print(epics.caget("17BM:SCALER1.s3"))
            #"PV2": 4.56,
            #"PV3": 7.89
        }


    #def write_single_entry(output_file, filename_tag, exposure_time, averaged_exposures, wavelength):
    def write_single_entry(self,filename,exposure,wavelengthValue,filters):
        pv_values = self.get_pv_values()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
 
        #HARD CODED VALUES
        averaged_exposures=10
        # Calculate energy (keV)
        energy = 12.398 / wavelengthValue
        i00 = epics.caget("17bm:scaler1.S3")
        ddistance=epics.caget("17bm:m33.RBV")
        #outputfile=filename + ".metadata"
        prefix_dir = r"Y:\mail_in"
        now = datetime.now()
        current_year=now.year
        current_month=now.strftime("%b")
        dir_path = os.path.join(prefix_dir, str(current_year), current_month)
        outputfile = os.path.join(dir_path, filename + ".metadata")
        with open(outputfile, "w", newline="") as f:
            # ---- metadata section ----
            f.write("[metadata]\n")
            f.write(f"fileName={filename}\n")
            f.write(f"{timestamp}\n")
            f.write("Polarization=0.90000\n")
            f.write(f"exposureTime={exposure}\n")
            f.write(f"averagedExposures={averaged_exposures}\n")
            f.write(f"Wavelength={wavelengthValue}\n")
            f.write(f"energy={energy:.4f}\n")
            f.write(f"i00={i00:.1f}\n")
            f.write(f"detectorDistance={ddistance:.1f}\n")
            f.write(f"filters={filters}\n")
        
            for pv, value in pv_values.items():
                f.write(f"{pv}={value}\n")


            # ---- blank line before next section ----
            f.write("\n")


            # ---- centerfinder section ----
            f.write("[centerfinder]\n")
            f.write("detectorXPixelSize=150\n")
            f.write("detectorYPixelSize=150\n")

    #print(f"metadata file written to: {output_file}")
#if __name__ == "__main__":
#    output_file = "pv_log.txt"
#    filename = "sample_run_001.tif"
#    exposure_time = 1.0
#    averaged_exposures = 5
#    wavelength = 0.248  # Å


    #write_single_entry(filename)
   




