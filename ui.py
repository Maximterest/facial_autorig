from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import logging
import os

from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets

LOG = logging.getLogger(__name__)

INSTANCE = None  # type: MainWindow | None

STYLE = """
    QWidget {
        background: #242527
    }
    QLabel {
        color: #3AD27D;
        font-weight: bold;
        font-family: "Roboto";
        font-size: 18px;
    }
    QTextEdit {
        color: white;
        font-weight: bold;
        font-family: "Roboto";
        font-size: 16px;
    }
    QLineEdit {
        border: 2px solid #3AD27D;
        padding: 4px;
        border-radius: 8px;
        font-weight: bold;
        font-family: "Roboto";
        font-size: 14px;
        color: white;
    }
"""

HEADERS = """
    QLabel {
        color: white;
        font-weight: bold;
        font-family: "Roboto";
        font-size: 16px;
    }
"""


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent=parent or get_maya_window())
        self.name = "Facial AutoRig"

        self.setup_win()
        self.build_ui()

        self.setStyleSheet(STYLE)

    def build_ui(self):
        widget = QtWidgets.QWidget(self)
        self.setCentralWidget(widget)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 0, 10, 10)
        layout.setSpacing(5)
        widget.setLayout(layout)

        # config
        self.config = Config(self)

        layout.addWidget(self.config)

    def check_instance(self):
        for each in self.parent().children():
            if each.objectName() == self.name:
                each.deleteLater()

    def setup_win(self):
        if self.parent():
            self.check_instance()

        self.setObjectName(self.name)
        self.setWindowTitle(self.name)


class Config(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(Config, self).__init__(parent)
        self.build()

    def build(self):
        main_layout  = QtWidgets.QVBoxLayout(self)
        self.setLayout(main_layout )

        # asset
        asset_layout = QtWidgets.QVBoxLayout()

        asset_label = QtWidgets.QLabel("ASSET")
        asset_input = QtWidgets.QLineEdit(self)
        asset_input.setPlaceholderText("e.g zizi")

        asset_layout.addWidget(asset_label)
        asset_layout.addWidget(asset_input)

        # config
        config_layout = QtWidgets.QVBoxLayout(self)
        headers_layout = QtWidgets.QHBoxLayout(self)

        config_label = QtWidgets.QLabel("| CONFIG")
        geo = QtWidgets.QLabel("GEO")
        geo.setStyleSheet(HEADERS)
        compil = QtWidgets.QLabel("COMP")
        compil.setStyleSheet(HEADERS)
        bs = QtWidgets.QLabel("BS")
        bs.setStyleSheet(HEADERS)
        rig = QtWidgets.QLabel("RIG")
        rig.setStyleSheet(HEADERS)
        tool = QtWidgets.QLabel("TOOL")
        tool.setStyleSheet(HEADERS)
        anim = QtWidgets.QLabel("ANIM")
        anim.setStyleSheet(HEADERS)
        data = QtWidgets.QLabel("DATA")
        data.setStyleSheet(HEADERS)

        config_layout.addWidget(config_label)
        headers_layout.addWidget(geo)
        headers_layout.addWidget(compil)
        headers_layout.addWidget(bs)
        headers_layout.addWidget(rig)
        headers_layout.addWidget(tool)
        headers_layout.addWidget(anim)
        headers_layout.addWidget(data)

        # add all layouts
        main_layout.addLayout(asset_layout)
        main_layout.addSpacing(20)
        main_layout.addLayout(config_layout)
        main_layout.addLayout(headers_layout)


class Header(QtWidgets.QLabel):
    def __init__(self, title, parent=None):
        super(Header, self).__init__(parent=parent)
        self.setTitle(title)

def get_maya_window():
    """Find Maya main window."""
    wdg = QtWidgets.QApplication.topLevelWidgets()
    return ([x for x in wdg if x.objectName() == "MayaWindow"] or [None])[0]


def show():
    # type: () -> MainWindow
    global INSTANCE

    maya_win = get_maya_window()
    INSTANCE = MainWindow(maya_win)
    INSTANCE.show()
    return INSTANCE
