import sys
from PyQt5.QtWidgets import (
    QApplication, QLabel, QWidget, QHBoxLayout, QListWidget,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsEllipseItem
)
from PyQt5.QtWidgets import QPushButton, QVBoxLayout
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PyQt5.QtCore import Qt
from PIL import Image
import numpy as np
import json

def detect_hot_pixels(img_array, factor=5):
    mean_val = np.mean(img_array)
    std_val = np.std(img_array)
    threshold = mean_val + factor * std_val
    mask = img_array > threshold
    coords = np.argwhere(mask)
    return coords, threshold

def convert_array_to_qimage(array):
    norm_array = ((array - array.min()) / np.ptp(array) * 255).astype(np.uint8)
    height, width = norm_array.shape
    return QImage(norm_array.data, width, height, QImage.Format_Grayscale8)

class HotPixelViewer(QWidget):
    def __init__(self, tiff_file):
        super().__init__()
        self.setWindowTitle("Hot Pixel Viewer")

        # Load TIFF and compute hot pixels
        img = Image.open(tiff_file)
        self.img_array = np.array(img)
        self.coords, threshold = detect_hot_pixels(self.img_array)

        # Convert image to QImage and QPixmap
        self.qimage = convert_array_to_qimage(self.img_array)
        self.pixmap = QPixmap.fromImage(self.qimage)

        # Set up QGraphicsScene
        self.scene = QGraphicsScene()
        self.image_item = QGraphicsPixmapItem(self.pixmap)
        self.scene.addItem(self.image_item)

        # Graphics view
        self.view = ZoomableGraphicsView(self.scene)

        self.view.setDragMode(QGraphicsView.ScrollHandDrag)

        # List widget for hot pixels
        self.list_widget = QListWidget()
        self.list_widget.addItem(f"Threshold: {threshold:.2f}")
        for y, x in self.coords:
            value = self.img_array[y, x]
            self.list_widget.addItem(f"x={x}, y={y}, value={value}")
        self.list_widget.currentRowChanged.connect(self.highlight_pixel)

        # Layout
        # Right-hand vertical layout for list + button
        right_panel = QVBoxLayout()
        right_panel.addWidget(self.list_widget)

        # Add export button
        self.export_button = QPushButton("Export 65535 Pixels")
        self.export_button.clicked.connect(self.export_bad_pixels)
        right_panel.addWidget(self.export_button)

        # Set up the main layout
        layout = QHBoxLayout()
        layout.addWidget(self.view, stretch=2)
        right_panel_widget = QWidget()
        right_panel_widget.setLayout(right_panel)
        layout.addWidget(right_panel_widget, stretch=1)
        self.setLayout(layout)

        self.resize(1000, 600)

        self.highlight_item = None  # Red dot overlay

    def highlight_pixel(self, row):
        if row == 0 or row >= len(self.coords) + 1:
            return

        y, x = self.coords[row - 1]  # subtract 1 because of threshold line

        # Remove old highlight
        if self.highlight_item:
            self.scene.removeItem(self.highlight_item)

        # Draw red ellipse (radius 3 px)
        radius = 3
        self.highlight_item = QGraphicsEllipseItem(
            x - radius, y - radius, radius * 2, radius * 2
        )
        self.highlight_item.setPen(QPen(Qt.red, 1))
        self.highlight_item.setBrush(QColor(255, 0, 0, 180))
        self.scene.addItem(self.highlight_item)





    def export_bad_pixels(self):
        _, threshold = detect_hot_pixels(self.img_array)
        coords = np.argwhere(self.img_array > threshold)
        bad_pixel_list = [
            {
                "Pixel": [int(x), int(y)],
                "Median": [2, 2]
            }
            for y, x in coords
        ]

        # Ask user where to save the file
        file_path, _ = QFileDialog.getSaveFileName(self, "Save JSON", "bad_pixels.json", "JSON Files (*.json)")
        if not file_path:
            return  # User cancelled

        data = {"Bad pixels": bad_pixel_list}
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"Exported {len(bad_pixel_list)} bad pixels to {file_path}")



class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.zoom_factor = 1.15  # how fast to zoom
        self.current_zoom = 0   # track zoom level

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            zoom = self.zoom_factor
            self.scale(zoom, zoom)
            self.current_zoom += 1
        else:
            zoom = 1 / self.zoom_factor
            self.scale(zoom, zoom)
            self.current_zoom -= 1

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R:
            self.reset_zoom()

    def reset_zoom(self):
        self.resetTransform()
        self.current_zoom = 0


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = HotPixelViewer("test_218.tif")  # Replace with your TIFF file path
    viewer.show()
    sys.exit(app.exec_())
