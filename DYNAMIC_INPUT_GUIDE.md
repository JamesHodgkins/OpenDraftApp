# Dynamic Input Quick Reference

## How to Use Dynamic Input

### During Point Selection (vector input)

When a command asks you to **"select a point"** or **"pick a point"**:

```
┌─ Dynamic Input Box ─┐
│ X: 50.00  Y: 75.00 │
│ Format: relative    │
└────────────────────┘
```

1. **Type to override:** Just start typing the coordinates
2. **Press Tab:** Move between X and Y input fields
3. **Press Shift+Tab:** Switch between coordinate formats
4. **Press Enter:** Confirm your input
5. **Left-click:** Select the point visually (if not using dynamic input)

### During Numeric Input (integer/float)

When a command asks for a **number**:

```
┌─ Dynamic Input Box ─┐
│ Value: ▯ 42       │
└────────────────────┘
```

1. Type the number
2. Press **Enter** to confirm

## Input Format Cheat Sheet

### Format 1: Relative (Default)
```
10,20    →  10 units right, 20 units up from previous point
10 20    →  (space separator also works)
```

### Format 2: Absolute
```
#100,50   →  Absolute coordinates X=100, Y=50
#100 50   →  (space separator also works)
```

### Format 3: Polar (Distance + Angle)
```
100<45    →  100 units at 45° angle
100@45    →  (@ also works as separator)
```

## Common Workflows

### Drawing a Rectangle with Precise Dimensions

1. **Start Line Command**
   - First corner: Type `#0,0` (top-left)
   - Press Tab → shows absolute format
   - Confirm

2. **Second Corner**
   - Type `#100,0` (top-right, 100 units to the right)
   - Confirm

3. **Continue** as needed

### Drawing from Current Point with Offset

1. **After placing first point**
   - Widget shows relative format by default
   - Type `50,30` (50 right, 30 up)
   - Press Enter

### Using Polar Coordinates

For a line 50 units long at 30° angle:

1. **When in polar format:**
   - Type `50<30`
   - Press Enter

## Tips and Tricks

| Action | Keyboard |
|--------|----------|
| Move between X and Y fields | **Tab** |
| Cycle input formats | **Shift+Tab** |
| Confirm input | **Enter** |
| Cancel input | **Esc** |
| Show cursor coordinates in status bar | Just move mouse |

## Format Cycling Order

Press Shift+Tab repeatedly to cycle backwards through:
1. **Relative** (dx, dy) ← default
2. **Absolute** (#x, y)
3. **Polar** (distance<angle)
4. Back to Relative...

Press Tab to move between the X and Y input fields (focus is locked between them).

## Angle Reference (Polar)

```
        90°
        ▲
        │
180° ←──●──→ 0°
        │
        ▼
       270°
```

- **0°** = East (right)
- **45°** = Northeast
- **90°** = North (up)
- **135°** = Northwest
- **180°** = West (left)
- **225°** = Southwest
- **270°** = South (down)
- **315°** = Southeast

## Common Input Examples

| Want to do... | Type... |
|---|---|
| Move 20 units right, 10 units up | `20,10` |
| Go to absolute position X=50, Y=75 | `#50,75` |
| Move 100 units at 45° angle | `100<45` |
| Move 50 units straight right | `50,0` or `50<0` |
| Move 50 units straight up | `0,50` or `50<90` |
| Move back 30 units | `30<180` |

## Troubleshooting

**Widget doesn't appear?**
- Make sure you're in a command that asks for input (look at status bar)
- The widget appears near the cursor during point selection

**Input not accepted?**
- Check the format indicator at bottom of widget
- Ensure numbers are valid (no letters, etc.)
- Commas, spaces, and semicolons work as separators

**Angle not right?**
- Angle is measured counter-clockwise from the positive X-axis (right)
- 0° points right, 90° points up

**Want to cancel?**
- Press Escape at any time to cancel input and return to cursor selection

## Need to select precisely without typing?

Even with dynamic input available, you can still:
- Click on the canvas to select points visually
- Use OSNAP (hover over snap points — endpoint, midpoint, center, etc.)
- The coordinates show in the status bar as you move
