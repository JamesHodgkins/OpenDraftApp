"""
Draftmate settings dialog — allows users to configure Polar Tracking angle,
max tracked points, and which snap types are eligible for tracking.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from app.editor.draftmate import DraftmateSettings
from app.entities.snap_types import SnapType


class DraftmateSettingsDialog(QDialog):
    """Modal dialog for Draftmate configuration.

    Mutates the supplied :class:`DraftmateSettings` in-place when the user
    clicks **OK**.
    """

    def __init__(
        self,
        settings: DraftmateSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Draftmate Settings")
        self.setMinimumWidth(340)
        self._settings = settings

        layout = QVBoxLayout(self)

        # ---- Polar angle increment ----------------------------------------
        polar_group = QGroupBox("Polar Tracking")
        polar_form = QFormLayout()
        self._angle_spin = QSpinBox()
        self._angle_spin.setRange(1, 90)
        self._angle_spin.setSuffix("°")
        self._angle_spin.setValue(int(settings.polar_angle_deg))
        polar_form.addRow("Angle increment:", self._angle_spin)
        polar_group.setLayout(polar_form)
        layout.addWidget(polar_group)

        # ---- Tracking limits ----------------------------------------------
        track_group = QGroupBox("Tracking")
        track_form = QFormLayout()
        self._max_spin = QSpinBox()
        self._max_spin.setRange(1, 20)
        self._max_spin.setValue(settings.max_tracked)
        track_form.addRow("Max tracked points:", self._max_spin)

        self._dwell_spin = QSpinBox()
        self._dwell_spin.setRange(100, 2000)
        self._dwell_spin.setSingleStep(50)
        self._dwell_spin.setSuffix(" ms")
        self._dwell_spin.setValue(settings.acquire_ms)
        track_form.addRow("Acquire dwell time:", self._dwell_spin)
        track_group.setLayout(track_form)
        layout.addWidget(track_group)

        # ---- Trackable snap types -----------------------------------------
        snap_group = QGroupBox("Allowed Snap Targets")
        snap_layout = QVBoxLayout()
        self._snap_checks: dict[SnapType, QCheckBox] = {}
        for st in (SnapType.ENDPOINT, SnapType.MIDPOINT, SnapType.CENTER):
            cb = QCheckBox(st.value)
            cb.setChecked(st in settings.trackable_types)
            snap_layout.addWidget(cb)
            self._snap_checks[st] = cb
        snap_group.setLayout(snap_layout)
        layout.addWidget(snap_group)

        # ---- Button box ---------------------------------------------------
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._apply_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_and_accept(self) -> None:
        """Write values back to the settings object and close."""
        self._settings.polar_angle_deg = float(self._angle_spin.value())
        self._settings.max_tracked = self._max_spin.value()
        self._settings.acquire_ms = self._dwell_spin.value()

        new_types = set()
        for st, cb in self._snap_checks.items():
            if cb.isChecked():
                new_types.add(st)
        self._settings.trackable_types = new_types

        self.accept()
