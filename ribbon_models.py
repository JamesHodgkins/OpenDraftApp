"""
Data models for Ribbon UI configuration.

This module provides type-safe data structures for defining ribbon
components, making the configuration more maintainable and less error-prone.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from ribbon_constants import ButtonType


@dataclass
class RibbonAction:
    """Represents an action that can be triggered from the ribbon."""
    name: str
    handler: Optional[Callable] = None
    
    def execute(self) -> None:
        """Execute the action."""
        if self.handler:
            self.handler()
        else:
            print(f"Action triggered: {self.name}")


@dataclass
class MenuItem:
    """Represents an item in a dropdown menu."""
    label: str
    action: str
    icon: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for compatibility."""
        result = {"label": self.label, "action": self.action}
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
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolDefinition':
        """Create ToolDefinition from dictionary."""
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
                status=data.get("status")
            )


@dataclass
class SplitButtonDefinition(ToolDefinition):
    """Definition for a split button with dropdown menu."""
    items: List[MenuItem] = field(default_factory=list)
    mainAction: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SplitButtonDefinition':
        """Create SplitButtonDefinition from dictionary."""
        items = [
            MenuItem(
                label=item["label"],
                action=item["action"],
                icon=item.get("icon")
            )
            for item in data.get("items", [])
        ]
        return cls(
            label=data["label"],
            type=data.get("type", "split"),
            action=data.get("action"),
            icon=data.get("icon"),
            status=data.get("status"),
            items=items,
            mainAction=data.get("mainAction")
        )


@dataclass
class StackDefinition(ToolDefinition):
    """Definition for a stacked group of buttons."""
    columns: List[List[Dict[str, Any]]] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StackDefinition':
        """Create StackDefinition from dictionary."""
        return cls(
            label=data.get("label", ""),
            type=ButtonType.STACK.value,
            columns=data.get("columns", [])
        )


@dataclass
class SelectDefinition(ToolDefinition):
    """Definition for a select/dropdown control."""
    options: Optional[List[str]] = None
    source: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SelectDefinition':
        """Create SelectDefinition from dictionary."""
        return cls(
            label=data["label"],
            type=ButtonType.SELECT.value,
            options=data.get("options"),
            source=data.get("source")
        )


@dataclass
class ColorPickerDefinition(ToolDefinition):
    """Definition for a color picker control."""
    source: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColorPickerDefinition':
        """Create ColorPickerDefinition from dictionary."""
        return cls(
            label=data["label"],
            type=ButtonType.COLOR_PICKER.value,
            source=data.get("source")
        )


@dataclass
class PanelDefinition:
    """Definition for a ribbon panel containing multiple tools."""
    name: str
    tools: List[ToolDefinition] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'PanelDefinition':
        """Create PanelDefinition from dictionary."""
        tools = [
            ToolDefinition.from_dict(tool_data)
            for tool_data in data.get("tools", [])
        ]
        return cls(name=name, tools=tools)


@dataclass
class TabDefinition:
    """Definition for a ribbon tab containing multiple panels."""
    name: str
    panels: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TabDefinition':
        """Create TabDefinition from dictionary."""
        return cls(
            name=data["name"],
            panels=data.get("panels", [])
        )


@dataclass
class RibbonConfiguration:
    """Complete ribbon configuration including structure and panel definitions."""
    tabs: List[TabDefinition] = field(default_factory=list)
    panels: Dict[str, PanelDefinition] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, structure: List[Dict[str, Any]], 
                  panel_defs: Dict[str, Dict[str, Any]]) -> 'RibbonConfiguration':
        """Create RibbonConfiguration from dictionary data."""
        tabs = [TabDefinition.from_dict(tab_data) for tab_data in structure]
        panels = {
            name: PanelDefinition.from_dict(name, data)
            for name, data in panel_defs.items()
        }
        return cls(tabs=tabs, panels=panels)
    
    def get_panel(self, name: str) -> Optional[PanelDefinition]:
        """Get a panel definition by name."""
        return self.panels.get(name)
