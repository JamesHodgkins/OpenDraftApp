"""
Tests for the ribbon UI framework.

Covers:
- Model ``from_dict()`` parsing and dispatch
- ``ButtonFactory`` button creation dispatch
- ``PanelFactory`` panel content layout
- ``RibbonSplitButton`` in large and small modes
- ``RibbonConfiguration`` round-trip
"""
import pytest
from PySide6.QtWidgets import QWidget, QPushButton, QToolButton, QComboBox

from controls.ribbon.ribbon_constants import ButtonType, SIZE, COLORS
from controls.ribbon.ribbon_models import (
    ToolDefinition,
    SplitButtonDefinition,
    StackDefinition,
    LayerSelectDefinition,
    PropStackDefinition,
    PropStackRowDefinition,
    PanelDefinition,
    TabDefinition,
    RibbonConfiguration,
)
from controls.ribbon.ribbon_factory import (
    ButtonFactory,
    PanelFactory,
    ColorSwatchButton,
    RibbonLargeButton,
)
from controls.ribbon.ribbon_split_button import RibbonSplitButton
from controls.ribbon.ribbon_panel import RibbonPanel
from controls.ribbon.ribbon_panel_widget import RibbonPanelFrame


# ---------------------------------------------------------------------------
# Model parsing tests
# ---------------------------------------------------------------------------


class TestToolDefinitionFromDict:
    """ToolDefinition.from_dict() should dispatch to the correct subclass."""

    def test_large_button(self):
        td = ToolDefinition.from_dict({"label": "Line", "type": "large", "action": "lineCommand"})
        assert isinstance(td, ToolDefinition)
        assert td.label == "Line"
        assert td.type == "large"
        assert td.action == "lineCommand"

    def test_small_button(self):
        td = ToolDefinition.from_dict({"label": "Rect", "type": "small", "icon": "draw_rect"})
        assert td.type == "small"
        assert td.icon == "draw_rect"

    def test_split_button(self):
        td = ToolDefinition.from_dict({
            "label": "Arc",
            "type": "split",
            "mainAction": "arcCommand",
            "items": [
                {"label": "Arc 3P", "action": "arc3PCommand", "icon": "draw_arc"},
                {"label": "Arc CR", "action": "arcCRCommand"},
            ],
        })
        assert isinstance(td, SplitButtonDefinition)
        assert len(td.items) == 2
        assert td.items[0].label == "Arc 3P"
        assert td.mainAction == "arcCommand"

    def test_split_small_button(self):
        td = ToolDefinition.from_dict({
            "label": "Copy", "type": "split-small",
            "items": [{"label": "Copy", "action": "copyCommand"}],
        })
        assert isinstance(td, SplitButtonDefinition)

    def test_stack_button(self):
        td = ToolDefinition.from_dict({
            "label": "Edit",
            "type": "stack",
            "columns": [
                [{"label": "Move", "type": "small", "action": "moveCommand"}],
            ],
        })
        assert isinstance(td, StackDefinition)
        assert len(td.columns) == 1

    def test_layer_select(self):
        td = ToolDefinition.from_dict({"label": "Layer", "type": "layer-select"})
        assert isinstance(td, LayerSelectDefinition)

    def test_prop_stack(self):
        td = ToolDefinition.from_dict({
            "label": "Props",
            "type": "prop-stack",
            "rows": [
                {"label": "Color", "type": "color-swatch"},
                {"label": "Style", "type": "combo", "options": ["Solid", "Dashed"]},
            ],
        })
        assert isinstance(td, PropStackDefinition)
        assert len(td.rows) == 2
        assert td.rows[0].type == "color-swatch"
        assert td.rows[1].options == ["Solid", "Dashed"]

    def test_default_type_is_large(self):
        td = ToolDefinition.from_dict({"label": "Foo"})
        assert td.type == "large"


class TestPanelDefinitionFromDict:
    def test_basic_panel(self):
        pd = PanelDefinition.from_dict("Draw", {
            "tools": [
                {"label": "Line", "type": "large", "action": "lineCommand"},
                {"label": "Rect", "type": "small", "action": "rectCommand"},
            ]
        })
        assert pd.name == "Draw"
        assert len(pd.tools) == 2

    def test_empty_panel(self):
        pd = PanelDefinition.from_dict("Empty", {})
        assert pd.tools == []


class TestRibbonConfiguration:
    def test_tab_definition(self):
        td = TabDefinition.from_dict({"name": "Home", "panels": ["Draw", "Edit"]})
        assert td.name == "Home"
        assert td.panels == ["Draw", "Edit"]


# ---------------------------------------------------------------------------
# ButtonFactory tests
# ---------------------------------------------------------------------------


class TestButtonFactory:
    @pytest.fixture()
    def factory(self, qtbot):
        actions = []
        return ButtonFactory(dark=True, action_handler=actions.append), actions

    def test_creates_large_button(self, factory):
        bf, actions = factory
        tool = ToolDefinition(label="Line", type="large", action="lineCommand")
        w = bf.create_button(tool)
        assert isinstance(w, RibbonLargeButton)
        assert w.text() == "Line"

    def test_creates_small_button(self, factory):
        bf, actions = factory
        tool = ToolDefinition(label="Rect", type="small", action="rectCommand")
        w = bf.create_button(tool)
        assert isinstance(w, QPushButton)
        assert w.text() == "Rect"
        assert w.width() == SIZE.SMALL_BUTTON_WIDTH

    def test_creates_split_button(self, factory):
        bf, _ = factory
        tool = SplitButtonDefinition(
            label="Arc", type="split",
            items=[],
            mainAction="arcCommand",
        )
        w = bf.create_button(tool)
        assert isinstance(w, RibbonSplitButton)

    def test_creates_layer_select(self, factory):
        bf, _ = factory
        tool = LayerSelectDefinition(label="Layer", type="layer-select")
        w = bf.create_button(tool)
        combo = w.findChild(QComboBox, "layerSelectCombo")
        assert combo is not None

    def test_creates_prop_stack(self, factory):
        bf, _ = factory
        tool = PropStackDefinition(
            label="Props", type="prop-stack",
            rows=[],
        )
        w = bf.create_button(tool)
        assert isinstance(w, QWidget)

    def test_action_callback_fires(self, factory):
        bf, actions = factory
        tool = ToolDefinition(label="Test", type="large", action="testAction")
        btn = bf.create_button(tool)
        btn.click()
        assert actions == ["testAction"]


# ---------------------------------------------------------------------------
# PanelFactory tests
# ---------------------------------------------------------------------------


class TestPanelFactory:
    def test_creates_content_widget(self, qtbot):
        pf = PanelFactory(dark=True)
        tools = [
            ToolDefinition(label="A", type="large", action="a"),
            ToolDefinition(label="B", type="small", action="b"),
            ToolDefinition(label="C", type="small", action="c"),
        ]
        w = pf.create_panel_content(tools)
        assert isinstance(w, QWidget)
        # Large button + small-button column = at least 2 children
        layout = w.layout()
        assert layout is not None
        assert layout.count() >= 2

    def test_small_buttons_grouped_into_columns(self, qtbot):
        pf = PanelFactory(dark=True)
        tools = [
            ToolDefinition(label="S1", type="small", action="s1"),
            ToolDefinition(label="S2", type="small", action="s2"),
            ToolDefinition(label="S3", type="small", action="s3"),
        ]
        w = pf.create_panel_content(tools)
        # All 3 small buttons should be in a single column widget
        layout = w.layout()
        assert layout.count() == 1  # one column widget (plus no stretch because addStretch isn't called)


# ---------------------------------------------------------------------------
# RibbonSplitButton tests
# ---------------------------------------------------------------------------


class TestRibbonSplitButton:
    def test_large_mode(self, qtbot):
        clicked = []
        sb = RibbonSplitButton(
            main_icon=None,
            main_label="Arc",
            items=[{"label": "Arc 3P", "action": lambda: clicked.append("3p")}],
            main_action=lambda: clicked.append("main"),
            small=False,
        )
        assert sb.width() == SIZE.LARGE_BUTTON_WIDTH

    def test_small_mode(self, qtbot):
        sb = RibbonSplitButton(
            main_icon=None,
            main_label="Copy",
            items=[{"label": "Paste", "action": lambda: None}],
            main_action=lambda: None,
            small=True,
        )
        assert sb.width() == SIZE.SMALL_BUTTON_WIDTH
        assert sb.height() == SIZE.SMALL_BUTTON_HEIGHT


# ---------------------------------------------------------------------------
# RibbonPanel (top-level widget) tests
# ---------------------------------------------------------------------------


class TestRibbonPanel:
    @pytest.fixture()
    def minimal_config(self):
        return RibbonConfiguration(
            tabs=[TabDefinition(name="Home", panels=["Draw"])],
            panels={
                "Draw": PanelDefinition(
                    name="Draw",
                    tools=[ToolDefinition(label="Line", type="large", action="lineCommand")],
                ),
            },
        )

    def test_creates_tabs(self, minimal_config):
        rp = RibbonPanel(minimal_config, dark=True)
        assert rp.tab_bar.count() == 1
        assert rp.tab_names == ["Home"]

    def test_stacked_pages(self, minimal_config):
        rp = RibbonPanel(minimal_config, dark=True)
        assert rp.stacked.count() == 1

    def test_action_signal_emitted(self, minimal_config, qtbot):
        rp = RibbonPanel(minimal_config, dark=True)
        with qtbot.waitSignal(rp.actionTriggered, timeout=500) as blocker:
            # Find the Line button and click it
            for btn in rp.findChildren(QToolButton):
                if btn.text() == "Line":
                    btn.click()
                    break
        assert blocker.args == ["lineCommand"]

    def test_color_change_signal(self, minimal_config, qtbot):
        """colorChangeRequested should fire when swatch is clicked."""
        config = RibbonConfiguration(
            tabs=[TabDefinition(name="Home", panels=["Props"])],
            panels={
                "Props": PanelDefinition(
                    name="Props",
                    tools=[
                        PropStackDefinition(
                            label="Props", type="prop-stack",
                            rows=[PropStackRowDefinition(label="Color", type="color-swatch")],
                        ),
                    ],
                ),
            },
        )
        rp = RibbonPanel(config, dark=True)
        swatch = rp.findChild(QPushButton, "colorSwatchBtn")
        assert swatch is not None
        with qtbot.waitSignal(rp.colorChangeRequested, timeout=500):
            swatch.click()

    def test_populate_layers(self, minimal_config):
        config = RibbonConfiguration(
            tabs=[TabDefinition(name="Home", panels=["Layers"])],
            panels={
                "Layers": PanelDefinition(
                    name="Layers",
                    tools=[LayerSelectDefinition(label="Layer", type="layer-select")],
                ),
            },
        )
        rp = RibbonPanel(config, dark=True)
        rp.populate_layers(["Layer0", "Layer1", "Layer2"], active_layer="Layer1")
        combo = rp.findChild(QComboBox, "layerSelectCombo")
        assert combo is not None
        assert combo.count() == 3
        assert combo.currentText() == "Layer1"

    def test_set_swatch_color(self, minimal_config):
        config = RibbonConfiguration(
            tabs=[TabDefinition(name="Home", panels=["Props"])],
            panels={
                "Props": PanelDefinition(
                    name="Props",
                    tools=[
                        PropStackDefinition(
                            label="Props", type="prop-stack",
                            rows=[PropStackRowDefinition(label="Color", type="color-swatch")],
                        ),
                    ],
                ),
            },
        )
        rp = RibbonPanel(config, dark=True)
        rp.set_swatch_color("#FF0000")
        swatch = rp.findChild(ColorSwatchButton, "colorSwatchBtn")
        assert swatch._hex_color == "#FF0000"


# ---------------------------------------------------------------------------
# RibbonPanelFrame tests
# ---------------------------------------------------------------------------


class TestRibbonPanelFrame:
    def test_creates_with_title(self, qtbot):
        content = QWidget()
        frame = RibbonPanelFrame("Draw", content, dark=True)
        assert frame.objectName() == "RibbonPanel"


# ---------------------------------------------------------------------------
# Constants sanity tests
# ---------------------------------------------------------------------------


class TestConstants:
    def test_size_has_no_defaults(self):
        """Sizing NamedTuple should not allow construction without args."""
        with pytest.raises(TypeError):
            from controls.ribbon.ribbon_constants import Sizing
            Sizing()  # all fields are required

    def test_colors_required_fields(self):
        assert COLORS.CONTROL_BG == "#3a3a3a"
        assert COLORS.SEPARATOR == "#464646"
        assert COLORS.TAB_TEXT_ACTIVE == "#f3f4f6"
