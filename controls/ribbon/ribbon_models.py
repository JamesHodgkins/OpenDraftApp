"""
Data models for Ribbon UI configuration.

Provides type-safe dataclasses for defining ribbon components, reducing
the reliance on untyped dictionaries throughout the codebase.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any

from controls.ribbon.ribbon_constants import ButtonType


@dataclass
class RibbonAction:
    """An action that can be triggered from the ribbon."""
    name: str
    handler: Optional[Callable] = None

    def execute(self) -> None:
        if self.handler:
            self.handler()
        else:
            print(f"Action triggered: {self.name}")


@dataclass
class MenuItem:
    """A single item in a dropdown menu."""
    label: str
    action: str
    icon: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"label": self.label, "action": self.action}
        if self.icon:
            result["icon"] = self.icon
        return result


@dataclass
class ToolDefinition:
    """Base definition for a ribbon tool/button."""
    label: str
    type: str
    action: Optional[str] = None
    icon: Optional[str] = None
    status: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolDefinition":
        tool_type = data.get("type", "large")
        if tool_type in [ButtonType.SPLIT.value, ButtonType.SPLIT_SMALL.value]:
            return SplitButtonDefinition.from_dict(data)
        elif tool_type == ButtonType.STACK.value:
            return StackDefinition.from_dict(data)
        elif tool_type == ButtonType.SELECT.value:
            return SelectDefinition.from_dict(data)
        elif tool_type == ButtonType.COLOR_PICKER.value:
            return ColorPickerDefinition.from_dict(data)
        else:
            return cls(
                label=data["label"],
                type=tool_type,
                action=data.get("action"),
                icon=data.get("icon"),
                status=data.get("status"),
            )


@dataclass
class SplitButtonDefinition(ToolDefinition):
    """Definition for a split button with dropdown menu."""
    items: List[MenuItem] = field(default_factory=list)
    mainAction: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SplitButtonDefinition":
        items = [
            MenuItem(label=i["label"], action=i["action"], icon=i.get("icon"))
            for i in data.get("items", [])
        ]
        return cls(
            label=data["label"],
            type=data.get("type", "split"),
            action=data.get("action"),
            icon=data.get("icon"),
            status=data.get("status"),
            items=items,
            mainAction=data.get("mainAction"),
        )


@dataclass
class StackDefinition(ToolDefinition):
    """Definition for a stacked group of buttons."""
    columns: List[List[Dict[str, Any]]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StackDefinition":
        return cls(
            label=data.get("label", ""),
            type=ButtonType.STACK.value,
            columns=data.get("columns", []),
        )


@dataclass
class SelectDefinition(ToolDefinition):
    """Definition for a select/dropdown control."""
    options: Optional[List[str]] = None
    source: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelectDefinition":
        return cls(
            label=data["label"],
            type=ButtonType.SELECT.value,
            options=data.get("options"),
            source=data.get("source"),
        )


@dataclass
class ColorPickerDefinition(ToolDefinition):
    """Definition for a colour-picker control."""
    source: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColorPickerDefinition":
        return cls(
            label=data["label"],
            type=ButtonType.COLOR_PICKER.value,
            source=data.get("source"),
        )


@dataclass
class PanelDefinition:
    """A ribbon panel containing multiple tools."""
    name: str
    tools: List[ToolDefinition] = field(default_factory=list)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "PanelDefinition":
        return cls(
            name=name,
            tools=[ToolDefinition.from_dict(t) for t in data.get("tools", [])],
        )


@dataclass
class TabDefinition:
    """A ribbon tab containing multiple panels."""
    name: str
    panels: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TabDefinition":
        return cls(name=data["name"], panels=data.get("panels", []))


@dataclass
class RibbonConfiguration:
    """Complete ribbon configuration: structure + panel definitions."""
    tabs: List[TabDefinition] = field(default_factory=list)
    panels: Dict[str, PanelDefinition] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        structure: List[Dict[str, Any]],
        panel_defs: Dict[str, Dict[str, Any]],
    ) -> "RibbonConfiguration":
        tabs = [TabDefinition.from_dict(t) for t in structure]
        panels = {
            name: PanelDefinition.from_dict(name, data)
            for name, data in panel_defs.items()
        }
        return cls(tabs=tabs, panels=panels)

    def get_panel(self, name: str) -> Optional[PanelDefinition]:
        return self.panels.get(name)
