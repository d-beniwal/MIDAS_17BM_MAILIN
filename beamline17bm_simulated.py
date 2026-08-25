import random
import time
import itertools

class Beamline17BMSim:
    def __init__(self):
        print("[SIM] Beamline17BMSim initialized.")

        self.filter_strengths = {
            'XIA1_1': 12.39,
            'XIA1_2': 3.47,
            'XIA1_3': 1.88,
            'XIA1_4': 1.291,
            'XIA2_1': 1.06,
            'XIA2_2': 5012.3,
            'XIA2_3': 5012.3,
            'XIA2_4': 1.11
        }

        self.active_filters = set()
        self.base_intensity = random.uniform(1000, 200000)
        self._fs_open = True
        print(f"[SIM] Base detector intensity set to: {self.base_intensity:.2f}")

    def get_total_attenuation(self):
        attenuation = 1.0
        for f in self.active_filters:
            attenuation *= self.filter_strengths.get(f, 1.0)
        return attenuation

    def GetMaxValOnDet(self):
        attenuation = self.get_total_attenuation()
        max_val = self.base_intensity / attenuation if attenuation > 0 else self.base_intensity
        print(f"[SIM] Detector max value (base {self.base_intensity:.2f} / attenuation {attenuation:.2f}) = {max_val:.2f}")
        return max_val

    def PutInFilter(self, *filters):
        self.active_filters.clear()
        for f in filters:
            if f in self.filter_strengths:
                self.active_filters.add(f)
            else:
                print(f"[SIM] Invalid filter: {f}")
        print(f"[SIM] Filters inserted: {sorted(self.active_filters)}")
        print(f"[SIM] Total attenuation factor: {self.get_total_attenuation():.2f}")

    def SetFilters(self, filters_list):
        self.active_filters = {
            f for f in filters_list if f in self.filter_strengths
        }
        print(f"[SIM] Set filters to: {sorted(self.active_filters)}")
        print(f"[SIM] Total attenuation factor: {self.get_total_attenuation():.2f}")

    def RemoveFilter(self, *filters):
        for f in filters:
            if f in self.active_filters:
                self.active_filters.remove(f)
                print(f"[SIM] Removed filter: {f}")
            else:
                print(f"[SIM] Filter not active or invalid: {f}")
        print(f"[SIM] Current filters: {sorted(self.active_filters)}")
        print(f"[SIM] Total attenuation factor: {self.get_total_attenuation():.2f}")

    def GetFilterStatus(self):
        return sorted(self.active_filters)

    def Measure_Sample(self, exposure_time, sub_frames=1):
        attenuation = self.get_total_attenuation()
        effective_exposure = exposure_time / attenuation
        print(f"[SIM] Measuring sample: {exposure_time}s / attenuation({attenuation:.2f}) = {effective_exposure:.2f}s (sub_frames={sub_frames})")
        time.sleep(0.5)
        print("[SIM] Measurement complete.")

    def MoveToSample(self, cartridge_position, sample_position):
        print(f"[SIM] Moving to sample - Cartridge Position: {cartridge_position}, Sample Position: {sample_position}")
        time.sleep(0.5)
        print("[SIM] Move complete.")

    def Determine_BadPix(self):
         print("[SIM] Starting bad pix determination...")


    def Determine_Exposure(self):
        print("[SIM] Starting exposure determination...")

        # Simulate starting with XIA1_2
        test_filter = ['XIA1_2']
        test_attenuation = self.filter_strengths['XIA1_2']
        self.SetFilters(test_filter)

        # Simulate getting max value on detector with test filter
        attenuation = self.get_total_attenuation()
        max_val = self.base_intensity / attenuation
        print(f"[SIM] Simulated max value with {test_filter[0]}: {max_val:.2f}")

        # Compute equivalent unfiltered exposure
        ideal_val = 25000
        measured_exposure = ideal_val / max_val
        unfiltered_exposure = measured_exposure / test_attenuation

        print(f"[SIM] Unfiltered equivalent exposure: {unfiltered_exposure:.2f}s")

        # Try filter combinations to get final exposure ≈ 1s
        all_filters = list(self.filter_strengths.keys())
        best_combo = []
        best_exp_diff = float("inf")

        for r in range(1, len(all_filters) + 1):
            for combo in itertools.combinations(all_filters, r):
                attenuation = 1.0
                for f in combo:
                    attenuation *= self.filter_strengths[f]
                final_exp = unfiltered_exposure * attenuation
                diff = abs(final_exp - 1.0)
                if diff < best_exp_diff or (abs(diff - best_exp_diff) < 1e-2 and len(combo) < len(best_combo)):
                    best_combo = combo
                    best_exp_diff = diff
                if best_exp_diff < 0.01:
                    break
            if best_exp_diff < 0.01:
                break

        final_attenuation = 1.0
        for f in best_combo:
            final_attenuation *= self.filter_strengths[f]
        best_exposure = unfiltered_exposure * final_attenuation

        print(f"[SIM] Best filter combination: {sorted(best_combo)}")
        print(f"[SIM] Final estimated exposure: {best_exposure:.2f}s (attenuation: {final_attenuation:.2f})")

        return round(best_exposure, 2), sorted(best_combo)


    def Move_detector(self, position):
        print(f"[SIM] Moving detector to position: {position}")
        time.sleep(0.3)
        print("[SIM] Detector move complete.")

    def TurnOnSave(self, filename):
        print(f"[SIM] Starting data save to file: {filename}")
        time.sleep(0.1)
        print("[SIM] Save active.")

    def TurnOffSave(self):
        print("[SIM] Stopping data save...")
        time.sleep(0.1)
        print("[SIM] Save deactivated.")

    def Check_Shutters(self):
        print("[SIM] Checking shutter status...")
        time.sleep(0.1)
        print("[SIM] Shutters are open.")
        return True

    def OpenFS(self):
        print("[SIM] Opening fast shutter...")
        self._fs_open = True
        time.sleep(0.1)
        print("[SIM] Fast shutter open.")

    def CloseFS(self):
        print("[SIM] Closing fast shutter...")
        self._fs_open = False
        time.sleep(0.1)
        print("[SIM] Fast shutter closed.")

    def CheckFSOpen(self):
        status = self._fs_open
        print(f"[SIM] Fast shutter is {'open' if status else 'closed'}")
        return status

    def SetExpTime(self, value):
        self.simulated_exp_time = value
        print(f"[SIM] Exposure time set to: {value}s")

    def SetSubFrame(self, value):
        self.simulated_sub_frames = value
        print(f"[SIM] Number of sub-frames set to: {value}")

    def SetSavingMode(self, flag):
        self.simulated_saving_enabled = bool(flag)
        print(f"[SIM] Saving mode {'enabled' if flag else 'disabled'}")

    def CollectDark(self, exp):
        print(f"[SIM] Collecting dark image with exposure time: {exp}s")
        time.sleep(0.2)
        print("[SIM] Dark frame acquisition complete.")
