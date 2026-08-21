import sys
import time
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QComboBox, QMessageBox, QMenu, QInputDialog, QDoubleSpinBox, QDialogButtonBox,
    QLabel, QTableWidgetItem, QMainWindow, QSplitter, QTableWidget, QHeaderView, QHBoxLayout, QDialog, QTextEdit, QVBoxLayout, QProgressBar
)
from PyQt5.QtCore import Qt, QMimeData, pyqtSignal
from PyQt5.QtGui import QDrag, QColor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import *
from beamline17bm_simulated import Beamline17BMSim
from beamline17bm_real import Beamline17BM
from collections import defaultdict
import pandas as pd




class DraggableTableWidget(QTableWidget):
    orderChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_app = None
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTableWidget.InternalMove)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.drag_start_position = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
           # print("[DEBUG] Mouse press at:", self.drag_start_position)
        super().mousePressEvent(event)

    def set_main_app(self, app):
        self.main_app = app

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            if (event.pos() - self.drag_start_position).manhattanLength() > QApplication.startDragDistance():
               # print("[DEBUG] Starting drag...")
                self.startDrag(Qt.MoveAction)
        super().mouseMoveEvent(event)

    def startDrag(self, supportedActions):
        index = self.indexAt(self.drag_start_position)
        if not index.isValid():
           # print("[DEBUG] Invalid index for drag start.")
            return

        #print("[DEBUG] Drag started from row:", index.row())

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText("cartridge_drag")
        drag.setMimeData(mime)
        drag.exec_(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() == "cartridge_drag":
           # print("[DEBUG] dragEnterEvent accepted")
            event.acceptProposedAction()
        

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text() == "cartridge_drag":
            event.acceptProposedAction()

    def dropEvent(self, event):
       # print("[DEBUG] dropEvent triggered")

        if event.source() != self:
           # print("[DEBUG] Drop source not this widget")
            return

        drop_row = self.drop_on(event)
        selected_row = self.currentRow()
       # print(f"[DEBUG] Drop at row {drop_row}, selected row {selected_row}")

        if selected_row < 0:
           # print("[DEBUG] No row selected during drop")
            return

        item = self.item(selected_row, 0)
        if not item:
         #   print("[DEBUG] No item found in selected row")
            return

        scan_id = item.data(Qt.UserRole)
        #print("[DEBUG] Dragged scan_request_id:", scan_id)

        parent = self.main_app
        if not hasattr(parent, 'data'):
           # print("[DEBUG] Parent has no 'data'")
            return

        original_entry = next((entry for entry in parent.data if entry["scan_request_id"] == scan_id), None)
        if not original_entry:
           # print("[DEBUG] Could not find entry in self.data")
            return

        cartridge_position = original_entry["cartridge_position"]
       # print("[DEBUG] Dragged cartridge_position:", cartridge_position)

        moving_group = [entry for entry in parent.data if entry["cartridge_position"] == cartridge_position]
        remaining_data = [entry for entry in parent.data if entry["cartridge_position"] != cartridge_position]

        if drop_row >= self.rowCount():
            drop_index = len(remaining_data)
        else:
            target_item = self.item(drop_row, 0)
            target_id = target_item.data(Qt.UserRole)
            target_entry = next((entry for entry in parent.data if entry["scan_request_id"] == target_id), None)
            if not target_entry:
                drop_index = len(remaining_data)
            else:
                target_pos = target_entry["cartridge_position"]
                for i, entry in enumerate(remaining_data):
                    if entry["cartridge_position"] == target_pos:
                        drop_index = i
                        break
                else:
                    drop_index = len(remaining_data)

        #print(f"[DEBUG] drop_index: {drop_index}, moving {len(moving_group)} entries")

        parent.data = remaining_data[:drop_index] + moving_group + remaining_data[drop_index:]
        parent.populate_table()
        self.orderChanged.emit()
        #print("[DEBUG] Drop and reorder complete.")
        event.accept()

    def drop_on(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return self.rowCount()
        return index.row() + 1 if self.is_below(event.pos(), index) else index.row()

    def is_below(self, pos, index):
        rect = self.visualRect(index)
        margin = 2
        if pos.y() - rect.top() < margin:
            return False
        elif rect.bottom() - pos.y() < margin:
            return True
        return pos.y() >= rect.center().y()

        



class BarcodeSearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Barcode Sample Viewer")
        self.setGeometry(100, 100, 800, 600)
        self.initDB()
        self.initUI()
        self.data = []
        self.full_data = []
        self.simulation_mode = False  # Set to False to use real beamline
        self.beamline_driver = None
        self.paused = False
        self.abort_requested = False

        if self.simulation_mode:
            self.beamline_driver = Beamline17BMSim()
        else:
            self.beamline_driver = Beamline17BM()


    def initDB(self):
        DATABASE_URL = 'mysql+mysqlconnector://11bm:staff11bm@s11bmsrv1/mailin'
        engine = create_engine(DATABASE_URL)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top input layout
        input_layout = QHBoxLayout()
        self.barcode_input = QLineEdit()
        self.beamline_selector = QComboBox()
        self.beamline_selector.addItem("17-BM", "17bm")
        self.beamline_selector.addItem("11-ID-B", "11idb")
        self.find_button = QPushButton("Find Samples")
        self.find_button.clicked.connect(self.find_samples)

        self.clear_button = QPushButton("Clear Table")
        self.clear_button.clicked.connect(self.clear_table)
        self.beamline_selector.currentIndexChanged.connect(self.clear_table)

        input_layout.addWidget(QLabel("Enter Barcode:"))
        input_layout.addWidget(self.barcode_input)
        input_layout.addWidget(QLabel("Beamline:"))
        input_layout.addWidget(self.beamline_selector)
        input_layout.addWidget(self.find_button)
        input_layout.addWidget(self.clear_button)
        main_layout.addLayout(input_layout)

        # Draggable table
        self.table = DraggableTableWidget(self)
        self.table.set_main_app(self)
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.setHorizontalHeaderLabels([])
        self.table.setSortingEnabled(False)
        self.table.orderChanged.connect(self.update_data_from_table)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_context_menu)
        self.table.cellDoubleClicked.connect(self.show_details_popup)
        main_layout.addWidget(self.table)

        self.energy_filter_box = QComboBox()
        self.energy_filter_box.addItem("All")
        self.energy_filter_box.currentTextChanged.connect(self.apply_energy_filter)

        energy_filter_layout = QHBoxLayout()
        energy_filter_layout.addStretch()
        energy_filter_layout.addWidget(QLabel("Filter by Energy:"))
        energy_filter_layout.addWidget(self.energy_filter_box)
        energy_filter_layout.addStretch()
        main_layout.addLayout(energy_filter_layout)

        # Bottom control buttons
        button_row = QHBoxLayout()
        self.badpix_button = QPushButton("BadPixs")
        self.prescan_button = QPushButton("Prescan")
        self.run_button = QPushButton("Run")
        self.prescan_run_button = QPushButton("Prescan && Run")
        self.wavelengthBox = QLineEdit("0.2754")
        self.badpix_button.clicked.connect(self.badpixScan)
        self.prescan_button.clicked.connect(self.placeholder_prescan)
        self.run_button.clicked.connect(self.placeholder_run)
        self.prescan_run_button.clicked.connect(self.placeholder_prescan_and_run)
        

        self.name_label=QLabel("Wavelength")

        # Initially disabled
        self.prescan_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.prescan_run_button.setEnabled(False)

        button_row.addStretch()
        button_row.addWidget(self.name_label)
        button_row.addWidget(self.wavelengthBox)
        button_row.addWidget(self.badpix_button)
        button_row.addWidget(self.prescan_button)
        button_row.addWidget(self.run_button)
        button_row.addWidget(self.prescan_run_button)
        button_row.addStretch()

        main_layout.addLayout(button_row)

                              

        # Pause/Abort button row
        pause_abort_layout = QHBoxLayout()
        pause_abort_layout.addStretch()

        self.pause_button = QPushButton("Pause")
        self.pause_button.hide()
        self.pause_button.clicked.connect(self.toggle_pause)

        self.abort_button = QPushButton("Abort")
        self.abort_button.hide()
        self.abort_button.clicked.connect(self.abort_process)

        pause_abort_layout.addWidget(self.pause_button)
        pause_abort_layout.addWidget(self.abort_button)

        pause_abort_layout.addStretch()
        main_layout.addLayout(pause_abort_layout)


        self.status_label = QLabel("Status: Idle")
        main_layout.addWidget(self.status_label)

        # Add progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

    def get_wavelength_value(self):
        try:
            return float(self.wavelengthBox.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Wavelength", "Please enter a valid wavelength.")
            return None  
    
            
    def update_status(self, message):
        self.status_label.setText(f"Status: {message}")
        QApplication.processEvents()  # ensure immediate GUI update

    def clear_table(self):
        self.data = []
        self.full_data = []
        self.populate_table()

        # Reset energy filter
        self.energy_filter_box.blockSignals(True)
        self.energy_filter_box.clear()
        self.energy_filter_box.addItem("All")
        self.energy_filter_box.setCurrentIndex(0)
        self.energy_filter_box.blockSignals(False)

        self.update_control_buttons()

    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.update_status("Paused… click Resume to continue or Abort to cancel")
            self.pause_button.setText("Resume")
            self.abort_button.show()
        else:
            self.update_status("Resumed")
            self.pause_button.setText("Pause")
            self.abort_button.hide()

    def abort_process(self):
        self.abort_requested = True
        self.update_status("Abort requested. Finishing current operation...")
        self.paused=False
        self.pause_button.setEnabled(False)
        self.abort_button.setEnabled(False)


    def set_processing_mode(self, active):
        if active:
            self.prescan_button.hide()
            self.run_button.hide()
            self.prescan_run_button.hide()
            self.badpix_button.hide()
            self.pause_button.show()
            self.abort_button.hide()
            self.pause_button.setText("Pause")
            self.pause_button.setEnabled(True)
            self.abort_button.setEnabled(True)
            self.paused = False
            self.abort_requested = False
        else:
            self.pause_button.hide()
            self.abort_button.hide()
            self.prescan_button.show()
            self.run_button.show()
            self.prescan_run_button.show()
            self.badpix_button.show()
            self.update_control_buttons()
            self.paused = False
            self.abort_requested = False


    def wait_if_paused(self, row_idx=None):
        if row_idx is not None:
            # Highlight paused row (light red/orange)
            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item:
                    item.setBackground(QColor(255, 200, 150))  # soft orange

            entry = self.data[row_idx]
            self.update_status(f"Paused at {entry['barcode']} position {entry['position']}")
            QApplication.processEvents()

        while self.paused:
            QApplication.processEvents()
            time.sleep(0.1)

        if row_idx is not None:
            # Clear pause highlight after resume
            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item:
                    item.setBackground(QColor("white"))


    def find_samples(self):
        barcode = self.barcode_input.text().strip()
        if not barcode:
            return
        selected_beamline = self.beamline_selector.currentData()
        self.table.clear()
        self.table.setRowCount(0)

        # Look up cartridge
        cartridge = self.session.query(Cartridge).filter_by(barcode=barcode).first()

        if not cartridge:
            self.display_message("No cartridge found with this barcode.")
            return

        # Get sample cartridges
        sample_cartridges = self.session.query(SampleCartridge).filter_by(cartridge_id=cartridge.cartridge_id).all()
        sample_ids = [sc.sample_id for sc in sample_cartridges]

        if not sample_ids:
            self.display_message("No samples found in this cartridge.")
            return

        # Collect scan requests one-by-one for better error handling
        scan_requests = []
        for sample_id in sample_ids:
            requests = (
                self.session.query(ScanRequest)
                .filter_by(sample_id=sample_id)
                .filter(ScanRequest.beamline == selected_beamline)
                .all()
            )
            scan_requests.extend(requests)

        if not scan_requests:
            self.display_message("No scan requests found for these samples.")
            return

        # Set up table headers
        headers = [
                    "Barcode", "Cartridge Position", "Position", "Proposal Number", "ESAF Number",
                    "Sample Name", "Chemical Description", "Distance", "Energy",
                    "Exposure", "Filters", "Status"
                    ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(scan_requests))
        existing_ids = {entry["scan_request_id"] for entry in self.data}

        cartridge_position_map = {}
        
        
        for sr in scan_requests:
            if sr.scan_request_id in existing_ids:
                continue
            sample = self.session.get(Sample, sr.sample_id)
            sample_cartridge = self.session.query(SampleCartridge).filter_by(sample_id=sample.sample_id).first()
            cartridge = self.session.get(Cartridge, sample_cartridge.cartridge_id) if sample_cartridge else None
            if cartridge and cartridge.barcode not in cartridge_position_map:
                # First check existing self.data
                existing_position = next(
                    (entry["cartridge_position"] for entry in self.data if entry["barcode"] == cartridge.barcode),
                    None
                )
                if existing_position is not None:
                    cartridge_position_map[cartridge.barcode] = existing_position
                else:
                    next_position = self.get_next_available_cartridge_position()
                    cartridge_position_map[cartridge.barcode] = next_position


            cartridge_position = cartridge_position_map.get(cartridge.barcode, "")
            proposal = self.session.get(Proposal, sample.proposal_id) if sample and sample.proposal_id else None

            if sr.beamline.lower() == "17bm":
                params = self.session.get(ScanParams_17BM, sr.scan_params_id)
            elif sr.beamline.lower() == "11idb":
                params = self.session.get(ScanParams_11IDB, sr.scan_params_id)
            else:
                params = None

            row_data = {
                "scan_request_id": sr.scan_request_id,
                "cartridge_position": cartridge_position,
                "exposure": "TBD",
                "filters": "None",
                "barcode": cartridge.barcode if cartridge else "",
                "position": sample_cartridge.position if sample_cartridge else "",
                "proposal_number": proposal.proposal_number if proposal else "",
                "esaf_number": sample.ESAF_number if sample else "",
                "sample_name": sample.sample_name if sample else "",
                "chemical_description": f"{sample.chemical_name or ''} ({sample.chemical_formula or ''})" if sample else "",
                "distance": params.distance if params else "",
                "energy": params.energy if params else "",
                "status": sr.status
            }

            self.data.append(row_data)
            self.full_data.append(row_data)
            #print(self.full_data)
           
            
        df=pd.DataFrame(self.full_data)
        #scdistance=df["distance"].unique().tolist()
        scdistance=df.drop_duplicates(subset=['distance', 'energy'])
        #print("here", scdistance)
        #print("here 2", str(scdistance.loc[0,'distance']))
        #print("here 3", str(scdistance.loc[0,'energy']))
        for i in range(0,len(scdistance)):
            LaB6_dis="LaB6_" + str(int(scdistance.loc[i,'distance'])) + "_" + str(int(scdistance.loc[i,'energy']))
            #print(LaB6_dis)
            row_data = {
             "scan_request_id": -1,
             "cartridge_position": cartridge_position,
             "exposure": str(0.8),
             "filters": "None",
             "barcode": cartridge.barcode if cartridge else "",
             "position": 0,
             "proposal_number": proposal.proposal_number if proposal else "",
             "esaf_number": sample.ESAF_number if sample else "",
             "sample_name": LaB6_dis,
             "chemical_description": f"LaB6 ",
             "distance": scdistance.loc[i,'distance'],
             "energy": scdistance.loc[i,'energy'],
             "status": 0
            }
            self.data.append(row_data)
            self.full_data.append(row_data)

        
        # Build energy filter dropdown
        energies = sorted(set(str(entry["energy"]) for entry in self.full_data if entry["energy"]))
        self.energy_filter_box.blockSignals(True)  # prevent triggering during update
        self.energy_filter_box.clear()
        self.energy_filter_box.addItem("All")
        for energy in energies:
            self.energy_filter_box.addItem(energy)
        self.energy_filter_box.blockSignals(False)    
        self.populate_table()

    def apply_energy_filter(self, selected_energy):
        if selected_energy == "All":
            self.data = self.full_data[:]
        else:
            self.data = [entry for entry in self.full_data if str(entry["energy"]) == selected_energy]
        self.populate_table()
        self.update_control_buttons()

    def populate_table(self):
        self.table.clear()
        if not self.data:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        headers = [
                    "Barcode", "Cartridge Position", "Position", "Proposal Number", "ESAF Number",
                    "Sample Name", "Chemical Description", "Distance", "Energy",
                    "Exposure", "Filters", "Status"
                    ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.data))

        for row_idx, row_data in enumerate(self.data):
            values = [
                        row_data["barcode"],
                        str(row_data["cartridge_position"]),
                        str(row_data["position"]),
                        str(row_data["proposal_number"]),
                        str(row_data["esaf_number"]),
                        row_data["sample_name"],
                        row_data["chemical_description"],
                        str(row_data["distance"]),
                        str(row_data["energy"]),
                        row_data["exposure"],
                        row_data["filters"],  # NEW
                        str(row_data["status"])
                        ]
            for col_idx, value in enumerate(values):
                #print(col_idx, value)
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                if col_idx == 0:
                    # Store scan_request_id in the first column's user data
                    item.setData(Qt.UserRole, row_data["scan_request_id"])
                self.table.setItem(row_idx, col_idx, item)
        # Auto-adjust column widths
        self.table.resizeColumnsToContents()

        # Auto-adjust row heights (optional)
        self.table.resizeRowsToContents()

        # Update run-related button states
        self.update_control_buttons()




    def display_message(self, message):
        QMessageBox.information(self, message, message)

    def show_details_popup(self, row, column):
        row_info = self.data[row]  # Dictionary of everything we know

        sr = self.session.get(ScanRequest, row_info["scan_request_id"])
        sample = self.session.get(Sample, sr.sample_id) if sr else None
        proposal = self.session.get(Proposal, sample.proposal_id) if sample and sample.proposal_id else None
        users = []
        if sample:
            sample_users = self.session.query(SampleUser).filter_by(sample_id=sample.sample_id).all()
            users = [self.session.get(User, su.user_id) for su in sample_users]

        details = [f"Scan Request ID: {sr.scan_request_id}"]
        details.append(f"Beamline: {sr.beamline}")
        details.append(f"Scan Params ID: {sr.scan_params_id}")
        details.append(f"Status: {sr.status}")
        details.append("")

        if sample:
            details.append("Sample Info:")
            details.append(f"  Name: {sample.sample_name}")
            details.append(f"  Chemical: {sample.chemical_name} ({sample.chemical_formula})")
            details.append(f"  ESAF #: {sample.ESAF_number}")
            details.append("")

        if proposal:
            details.append("Proposal:")
            details.append(f"  Number: {proposal.proposal_number}")
            details.append(f"  Title: {proposal.title}")
            details.append("")

        if users:
            details.append("Users:")
            for user in users:
                details.append(f"  {user.name} ({user.email}) - ORCID: {user.orcid}")
            details.append("")

        dialog = QDialog(self)
        dialog.setWindowTitle("Scan Request Details")
        layout = QVBoxLayout(dialog)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setText("\n".join(details))
        layout.addWidget(text)

        dialog.resize(600, 400)
        dialog.exec_()

    def open_context_menu(self, position):
        index = self.table.indexAt(position)
        if not index.isValid():
            return

        clicked_row = index.row()

        # If right-clicked row is not part of current selection, select just it
        selected_rows = self.get_selected_rows()
        if clicked_row not in selected_rows:
            self.table.clearSelection()
            self.table.selectRow(clicked_row)
            selected_rows = [clicked_row]

        menu = QMenu()
        delete_action = menu.addAction("Delete Scan")
        change_cartridge_action = menu.addAction("Change Cartridge Position")
        set_exposure_action = menu.addAction("Set Exposure Time")

        # Keep your rescan logic as single-row (or upgrade later)
        entry = self.data[clicked_row]
        rescan_action = None
        if entry["status"] != 0:
            rescan_action = menu.addAction("Rescan")

        action = menu.exec_(self.table.viewport().mapToGlobal(position))

        if action == delete_action:
            self.delete_scan_rows(selected_rows)
        elif action == change_cartridge_action:
            # keep existing single-row behavior for now
            self.change_cartridge_position(clicked_row)
        elif action == set_exposure_action:
            self.set_exposure_time_rows(selected_rows)
        elif rescan_action is not None and action == rescan_action:
            self.mark_as_rescan(clicked_row)


    def change_cartridge_position(self, row):
        if row < 0 or row >= len(self.data):
            return

        old_position = self.data[row]["cartridge_position"]

        new_position, ok = QInputDialog.getInt(
            self, "Change Cartridge Position",
            f"Enter new cartridge position for all entries with position {old_position}:",
            value=old_position, min=1
        )

        if not ok or new_position == old_position:
            return

        # Check if new_position is already used
        new_position_exists = any(entry["cartridge_position"] == new_position for entry in self.data)

        if new_position_exists:
            # Swap positions
            for entry in self.data:
                if entry["cartridge_position"] == old_position:
                    entry["cartridge_position"] = -1  # temporary marker
            for entry in self.data:
                if entry["cartridge_position"] == new_position:
                    entry["cartridge_position"] = old_position
            for entry in self.data:
                if entry["cartridge_position"] == -1:
                    entry["cartridge_position"] = new_position
        else:
            # Simple assignment
            for entry in self.data:
                if entry["cartridge_position"] == old_position:
                    entry["cartridge_position"] = new_position

        self.populate_table()


    def get_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()})
        return rows

    def delete_scan_rows(self, rows):
        if not rows:
            return

        # Collect scan_request_ids for the selected rows
        scan_ids = set()
        for r in rows:
            if 0 <= r < len(self.data):
                scan_ids.add(self.data[r]["scan_request_id"])

        if not scan_ids:
            return

        # Remove from both data lists so filtering doesn't "bring them back"
        self.data = [e for e in self.data if e["scan_request_id"] not in scan_ids]
        self.full_data = [e for e in self.full_data if e["scan_request_id"] not in scan_ids]

        self.populate_table()

    def update_data_from_table(self):
        new_order = []

        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)  # First column stores the scan_request_id as user data
            if item is None:
                continue
            scan_id = item.data(Qt.UserRole)
            match = next((entry for entry in self.data if entry["scan_request_id"] == scan_id), None)
            if match:
                new_order.append(match)

        if len(new_order) == len(self.data):
            self.data = new_order
            
    def get_next_available_cartridge_position(self):
        used_positions = {entry["cartridge_position"] for entry in self.data if entry.get("cartridge_position")}
        pos = 1
        while pos in used_positions:
            pos += 1
        return pos


    def mark_as_rescan(self, row):
        if row < 0 or row >= len(self.data):
            return

        self.data[row]["status"] = 0
        item = self.table.item(row, 11)  # "Status" column
        if item:
            item.setText("0")

        self.update_status(f"Marked {self.data[row]['barcode']} position {self.data[row]['position']} for rescan.")


    def set_exposure_time_rows(self, rows):
        rows = [r for r in rows if 0 <= r < len(self.data)]
        if not rows:
            return

        # Use first selected row as the "current" value seed
        current_value = self.data[rows[0]].get("exposure", "TBD")
        try:
            current_value = float(current_value)
        except:
            current_value = 1.0

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Set Exposure Time ({len(rows)} selected)")

        layout = QVBoxLayout(dialog)

        spin_box = QDoubleSpinBox()
        spin_box.setDecimals(2)
        spin_box.setMinimum(0.1)
        spin_box.setMaximum(8.0)
        spin_box.setSingleStep(0.1)
        spin_box.setValue(current_value)
        layout.addWidget(spin_box)

        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        reset_button = QPushButton("Reset")
        cancel_button = QPushButton("Cancel")

        button_layout.addWidget(ok_button)
        button_layout.addWidget(reset_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        def handle_accept():
            new_val = str(round(spin_box.value(), 2))
            for r in rows:
                self.data[r]["exposure"] = new_val
            dialog.accept()
            self.sort_by_exposure_within_cartridges()

        def handle_reset():
            for r in rows:
                self.data[r]["exposure"] = "TBD"
            dialog.accept()
            self.sort_by_exposure_within_cartridges()

        ok_button.clicked.connect(handle_accept)
        reset_button.clicked.connect(handle_reset)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()
        

    def sort_by_exposure_within_cartridges(self):
        from collections import defaultdict

        grouped = defaultdict(list)
        for entry in self.data:
            grouped[entry["cartridge_position"]].append(entry)

        # Maintain visible cartridge order
        ordered_positions = []
        seen = set()
        for entry in self.data:
            pos = entry["cartridge_position"]
            if pos not in seen:
                seen.add(pos)
                ordered_positions.append(pos)

        sorted_data = []
        for pos in ordered_positions:
            group = grouped[pos]

            def sort_key(entry):
                # Try parsing distance and exposure
                try:
                    distance = float(entry.get("distance", 0))
                except:
                    distance = -1  # lowest if invalid

                try:
                    exposure = float(entry.get("exposure", -9999))
                    exposure_sort_val = (0, -exposure)  # higher exposure comes first
                except:
                    exposure_sort_val = (1, 0)  # TBD comes last

                return (-distance, exposure_sort_val)

            group.sort(key=sort_key)
            sorted_data.extend(group)

        self.data = sorted_data
        self.populate_table()

    def badpixScan(self):
        self.set_processing_mode(True)
        self.beamline_driver.Determine_BadPix()
        self.set_processing_mode(False)
        return True

    def placeholder_prescan(self):
        self.set_processing_mode(True)
        prescan_entries = [i for i, e in enumerate(self.data) if e["status"] == 0 and e["exposure"] == "TBD"]
        total = len(prescan_entries)
        self.update_progress(0)

        if total == 0:
            self.update_progress(0)
            return
        first=True
        for i, row_idx in enumerate(prescan_entries):
            self.wait_if_paused(row_idx)

            if self.abort_requested:
                self.update_status("Operation aborted.")
                self.set_processing_mode(False)
                self.update_progress(0)
                return


            entry = self.data[row_idx]
            if entry["status"] == 1 or entry["exposure"] != "TBD":
                continue
            # Highlight this row
            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item:
                    item.setBackground(QColor("yellow"))
            self.update_status(f"Prescanning sample {entry['barcode']} pos {entry['position']}")
            QApplication.processEvents()
            time.sleep(0.3)
            if first:
                first=True
            else:
                time.sleep(20)

            # Move to sample
            self.beamline_driver.MoveToSample(entry["cartridge_position"], entry["position"])
            self.beamline_driver.Move_detector(entry["distance"])
            #determine wavelength
            wavelengthValue = self.get_wavelength_value()
            if wavelengthValue is None:
                self.set_processing_mode(False)
                return
            # Determine exposure and filters together
            
            exposure, filters = self.beamline_driver.Determine_Exposure(wavelengthValue)

            entry["exposure"] = str(exposure)
            entry["filters"] = ", ".join(filters) if filters else "None"

            # Update the table
            self.table.item(row_idx, 9).setText(entry["exposure"])
            self.table.item(row_idx, 10).setText(entry["filters"])
            # after prescan completes:
            print(i, total)
            progress = (i + 1) / total * 100
            self.update_progress(progress)
            # Clear highlight
            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item:
                    item.setBackground(QColor("white"))
            QApplication.processEvents()

        self.sort_by_exposure_within_cartridges()
        self.update_progress(100)
        self.set_processing_mode(False)

        self.update_status("Prescan complete")

    def update_control_buttons(self):
        selected_energy = self.energy_filter_box.currentText()
        if selected_energy == "All":
            self.prescan_button.setEnabled(False)
            self.run_button.setEnabled(False)
            self.prescan_run_button.setEnabled(False)
            return

        has_data = len(self.data) > 0
        all_have_exposure = all(entry["exposure"] != "TBD" for entry in self.data if entry["status"] == 0)

        self.prescan_button.setEnabled(has_data)
        self.prescan_run_button.setEnabled(has_data)
        self.run_button.setEnabled(has_data and all_have_exposure)

    def update_progress(self, value):
        self.progress_bar.setValue(int(value))
        QApplication.processEvents()



    def placeholder_run(self):
        self.set_processing_mode(True)

        run_entries = [i for i, e in enumerate(self.data) if e["status"] == 0]
        total = len(run_entries)
        if total == 0:
            self.update_progress(0)
            return
        self.update_progress(0)
        print("=== RUN START ===")
        self.update_status("Running all scans")
        first=True

        for i, row_idx in enumerate(run_entries):
            self.wait_if_paused(row_idx)

            if self.abort_requested:
                self.update_status("Operation aborted.")
                self.set_processing_mode(False)
                self.update_progress(0)
                return


            entry = self.data[row_idx]
            if entry["status"] == 1 or entry["exposure"] == "TBD":
                continue
            self.update_status(f"Running sample {entry['barcode']} position {entry['position']}")
            print(f"Running: Barcode: {entry['barcode']}, "
                  f"Cartridge Pos: {entry['cartridge_position']}, "
                  f"Position: {entry['position']}, "
                  f"Exposure: {entry['exposure']}")

            # Highlight row in green
            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item:
                    item.setBackground(QColor("lightgreen"))
            QApplication.processEvents()

            # Move to the sample
            self.beamline_driver.MoveToSample(entry["cartridge_position"], entry["position"])
            self.beamline_driver.Move_detector(entry["distance"])
            if first:
                first=False
            else:
                time.sleep(20)
            # Apply filters (if any)
            filters = entry["filters"]
            if filters and filters != "None":
                self.beamline_driver.SetFilters(filters.split(", "))
            else:
                self.beamline_driver.SetFilters([])

            # Set exposure time
            try:
                exposure = float(entry["exposure"])
            except:
                exposure = 0.2
            self.beamline_driver.SetExpTime(exposure)
            self.beamline_driver.SetSubFrame(10) #This is likely wrong!
            self.beamline_driver.SetDarkSubFrame(10) 
            self.beamline_driver.CollectDark(exposure)
            self.beamline_driver.SetSavingMode(True)

            # Generate filename (placeholder logic)
            filename = f"{entry['barcode']}_pos{entry['position']}"
            self.beamline_driver.TurnOnSave(filename)

            # Run the measurement
            self.beamline_driver.Measure_Sample(exposure)

            self.beamline_driver.TurnOffSave()

            #metadata
            wavelengthValue = self.get_wavelength_value()
            self.beamline_driver.write_single_entry(filename,exposure,wavelengthValue,filters)

            entry["status"] = 1
            self.table.item(row_idx, 11).setText("1")  # update "Status" column
            
            progress = (i + 1) / total * 100
            self.update_progress(progress)

            # Clear highlight
            for col in range(self.table.columnCount()):
                item = self.table.item(row_idx, col)
                if item:
                    item.setBackground(QColor("white"))

            QApplication.processEvents()

        self.update_progress(100)
        self.update_status("Run complete")
        self.set_processing_mode(False)

        print("=== RUN END ===")



    def placeholder_prescan_and_run(self):

        self.set_processing_mode(True)
        self.update_progress(0)

        print("=== PRESCAN & RUN START ===")
        self.update_status("Prescan & Run started")

        # Group entries by cartridge_position
        grouped = defaultdict(list)


        
        for idx, entry in enumerate(self.data):
            grouped[entry["cartridge_position"]].append((idx, entry))

        total_time = 0
        

        for cartridge_position in sorted(grouped.keys()):
            group = grouped[cartridge_position]
            for row_idx, entry in group:
                if entry["status"] != 1:
                    if entry["exposure"] == "TBD":
                        total_time += 10  # seconds
                       
                    total_time += 300  # run time
                    

        time_done = 0

        # Sort cartridge positions
        for cartridge_position in sorted(grouped.keys()):
            group = grouped[cartridge_position]
            print(f"\n--- Processing Cartridge {cartridge_position} ---")

            # === Prescan phase ===
            self.update_status(f"Prescanning cartridge {cartridge_position}")
            for row_idx, entry in group:
                self.wait_if_paused(row_idx)

                if self.abort_requested:
                    self.update_status("Operation aborted.")
                    self.set_processing_mode(False)
                    self.update_progress(0)
                    return


                if entry["status"] == 1 or entry["exposure"] != "TBD":
                    continue
                # Highlight yellow
                for col in range(self.table.columnCount()):
                    item = self.table.item(row_idx, col)
                    if item:
                        item.setBackground(QColor("yellow"))

                self.update_status(f"Prescanning sample {entry['barcode']} pos {entry['position']}")
                QApplication.processEvents()

                # Move to sample
                self.beamline_driver.MoveToSample(entry["cartridge_position"], entry["position"])

                
                #determine wavelength
                wavelengthValue = self.get_wavelength_value()
                if wavelengthValue is None:
                    self.set_processing_mode(False)
                    return
                
                # Determine exposure and filters together
                exposure, filters = self.beamline_driver.Determine_Exposure(wavelengthValue)
                time_done += 10

                entry["exposure"] = str(exposure)
                entry["filters"] = ", ".join(filters) if filters else "None"
                
                self.update_progress((time_done / total_time) * 100)

                # Update table
                self.table.item(row_idx, 9).setText(entry["exposure"])
                self.table.item(row_idx, 10).setText(entry["filters"])

                # Clear highlight
                for col in range(self.table.columnCount()):
                    item = self.table.item(row_idx, col)
                    if item:
                        item.setBackground(QColor("white"))

                QApplication.processEvents()

            # === Run phase ===
            self.update_status(f"Running cartridge {cartridge_position}")
            print(f"--- Running Cartridge {cartridge_position} ---")

            for row_idx, entry in group:
                self.wait_if_paused(row_idx)

                if self.abort_requested:
                    self.update_status("Operation aborted.")
                    self.set_processing_mode(False)
                    self.update_progress(0)
                    return


                if entry["status"] == 1  or entry["exposure"] == "TBD":
                    continue
                print(f"Running: Barcode {entry['barcode']} Pos {entry['position']} Exposure {entry['exposure']}")
                self.update_status(f"Running sample {entry['barcode']} pos {entry['position']}")

                # Highlight green
                for col in range(self.table.columnCount()):
                    item = self.table.item(row_idx, col)
                    if item:
                        item.setBackground(QColor("lightgreen"))

                QApplication.processEvents()

                # Move to sample
                self.beamline_driver.MoveToSample(entry["cartridge_position"], entry["position"])

                # Set filters
                filters = entry["filters"]
                if filters and filters != "None":
                    self.beamline_driver.SetFilters(filters.split(", "))
                else:
                    self.beamline_driver.SetFilters([])

                # Set exposure
                try:
                    exposure = float(entry["exposure"])
                except:
                    exposure = 1.0
                self.beamline_driver.SetExpTime(exposure)
                self.beamline_driver.SetSubFrame(1) #Probably WRong!
                self.beamline_driver.CollectDark(exposure)
                self.beamline_driver.SetSavingMode(True)

                # Start save and measure
                filename = f"{entry['barcode']}_pos{entry['position']}"
                self.beamline_driver.TurnOnSave(filename)
                self.beamline_driver.Measure_Sample(exposure)
                self.beamline_driver.TurnOffSave()

                entry["status"] = 1
                self.table.item(row_idx, 11).setText("1")
                time_done += 300
                self.update_progress((time_done / total_time) * 100)
                
                # Clear green highlight
                for col in range(self.table.columnCount()):
                    item = self.table.item(row_idx, col)
                    if item:
                        item.setBackground(QColor("white"))

                QApplication.processEvents()
                
        self.update_progress(100)
        self.update_status("Prescan & Run Complete")
        print("=== PRESCAN & RUN COMPLETE ===")
        self.set_processing_mode(False)

        self.sort_by_exposure_within_cartridges()

        




if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = BarcodeSearchApp()
    window.show()
    sys.exit(app.exec_())
