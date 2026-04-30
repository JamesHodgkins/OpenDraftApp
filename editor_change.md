# Editor/Command Update and Interaction Logic

## 1. Functional Overview
The update system manages the lifecycle of a command from activation to final database commitment. It operates on a "Live Preview" principle where the command's internal state is constantly recalculated as properties are fulfilled in any order.

## 2. The Command Update Loop
The application must implement a high-frequency update loop that follows this sequence:

1.  **Event Capture**: Intercept mouse coordinates, scroll wheel increments, and keyboard strings.
2.  **Input Dispatching**: 
    - If the input contains a shortcut prefix, route the value to the specific property.
    - If the input is a raw coordinate, route it to the first available spatial property.
3.  **State Recalculation**: The command recalculates its internal geometry based on the new property set.
4.  **Validation**: Check if the current state satisfies the "Required" constraints.
5.  **Preview Render**: Draw "Ghost Geometry" (volatile, non-persistent visuals) to the canvas.

## 3. State Management
Commands are treated as state machines with three primary statuses for each property:

| Status | Description | UI Representation |
| :--- | :--- | :--- |
| **Unset** | No data provided yet. | Placeholder or empty field. |
| **Suggested** | Temporary value derived from mouse position or defaults. | Italicized or dimmed text. |
| **Locked** | Explicitly set by the user via click or keyboard. | Bold or highlighted field. |

## 4. Input Resolution Strategy

### Spatial Resolution (Mouse)
- While a command is active, the system generates a "Ghost" point based on the cursor location. 
- If a command requires multiple points (e.g., Start and End), the system prioritizes the "Unset" property. 
- If all required points are "Locked," subsequent clicks act as a "Commit" trigger.

### Property Resolution (Keyboard)
- **Explicit Mapping**: Typing a letter key associated with a property (e.g., 'R' for Radius) shifts focus to that field immediately.
- **Implicit Mapping**: Typing a numeric value without a prefix applies the value to the "Active" property (the one currently being influenced by the mouse).

## 5. Transition to Commitment
A command transitions from "Preview" to "Permanent" when:
- The user presses the **Enter** key.
- A mouse click occurs while all "Required" properties are in a "Locked" state.
- A double-click occurs (optional, based on tool type).

On commitment, the command clears its volatile state, generates a persistent entity in the drawing database, and notifies the Undo/Redo manager.

## 6. Cancellation and Rollback
- Pressing **Escape** must immediately terminate the update loop.
- Any "Ghost Geometry" must be purged from the render buffer.
- The UI Inspector window must close or reset to the default "Ready" state.
"""

# Save as MD file
file_name = "command_update.md"
with open(file_name, "w") as f:
    f.write(md_content)