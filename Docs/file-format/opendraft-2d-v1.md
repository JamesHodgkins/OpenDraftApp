# OpenDraft 2D Native File Format Specification (v1)

## 1. Scope

This specification defines the canonical on-disk representation for OpenDraft 2D drawing files.

- Container format: ZIP archive (`.odx`).
- Canonical payload format: UTF-8 JSON object stored as `document.json` inside the ZIP.
- Purpose: lossless persistence of OpenDraft `DocumentStore` drawing state.
- Out of scope: runtime-only UI/session state (selection, undo stack, transient previews).

## 2. Conformance Language

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" are to be interpreted as described in RFC 2119.

## 3. Container and Payload Layout

An OpenDraft v1 file MUST be a ZIP archive with:

- required root entry: `document.json`
- optional reserved root entry: `meta.json`
- optional reserved directory: `assets/`
- optional preview entry: `assets/thumbnail.png` (PNG image)

Unknown additional ZIP entries MAY be ignored by loaders.

When present, `assets/thumbnail.png` SHOULD be a square PNG preview render of
the drawing (for example 256x256) suitable for shell/file-manager thumbnail
providers.

The `document.json` payload MUST be a JSON object with these top-level keys:

- `version` (required, string): specification version. For this spec, value MUST be `"1.0"`.
- `entities` (required, array): ordered list of entity objects.
- `layers` (required, array): list of layer definitions.
- `activeLayer` (required, string): active layer name.
- `currentActiveColor` (optional, string or null): active per-entity color override.
- `currentActiveLineStyle` (optional, string or null): active per-entity line style override.
- `currentActiveThickness` (optional, number or null): active per-entity thickness override.

### 3.1 Example ZIP Layout

```text
drawing.odx
|- document.json
|- meta.json            # optional, reserved for producer/build metadata
`- assets/              # optional, reserved for future external resources
   `- thumbnail.png     # optional preview image for file-manager thumbnails
```

### 3.2 Example `document.json` Skeleton

```json
{
  "version": "1.0",
  "entities": [],
  "layers": [
    {
      "name": "default",
      "color": "#ffffff",
      "visible": true,
      "lineStyle": "solid",
      "thickness": 1.0
    }
  ],
  "activeLayer": "default",
  "currentActiveColor": null,
  "currentActiveLineStyle": null,
  "currentActiveThickness": null
}
```

## 4. Primitive Data Types

### 4.1 Vector (`Vec2`)

A 2D vector/point MUST be:

```json
{ "x": <number>, "y": <number> }
```

### 4.2 Angle Units

- All angle values in this format are radians.
- `arc.startAngle`, `arc.endAngle`, `ellipse.rotation`, `ellipse.startParam`, `ellipse.endParam`, and `rect.rotation` follow this rule.

### 4.3 Optional Style Overrides

Entity-level style overrides are inherited from `BaseEntity`:

- `color` (string, optional): if omitted/null, interpreted as ByLayer.
- `lineWeight` (number, optional): if omitted/null, interpreted as ByLayer.
- `lineStyle` (string, optional): if omitted/null, interpreted as ByLayer.

## 5. Layer Object

Each entry in `layers` MUST be an object with:

- `name` (string, required)
- `color` (string, required)
- `visible` (boolean, required)
- `lineStyle` (string, required)
- `thickness` (number, required)

Layer names SHOULD be unique within a document.

## 6. Entity Base Contract

Every entity object in `entities` MUST contain:

- `id` (string, required): unique entity identifier.
- `type` (string, required): entity discriminator.
- `layer` (string, required): target layer name.

Every entity MAY also contain:

- `color`
- `lineWeight`
- `lineStyle`

Unknown top-level keys on entities MAY be rejected by strict validators.

## 7. Canonical Entity Definitions

This section is normative. All keys are camelCase as shown.

### 7.1 `line`

- `type`: `"line"`
- Required keys: `p1` (`Vec2`), `p2` (`Vec2`)

### 7.2 `circle`

- `type`: `"circle"`
- Required keys: `center` (`Vec2`), `radius` (number, SHOULD be > 0)

### 7.3 `arc`

- `type`: `"arc"`
- Required keys: `center` (`Vec2`), `radius` (number), `startAngle` (number), `endAngle` (number)
- Optional: `ccw` (boolean, defaults to `true` when absent)

### 7.4 `rect`

- `type`: `"rect"`
- Canonical required keys: `center` (`Vec2`), `width` (number), `height` (number), `rotation` (number)
- Canonical form is center/size/rotation.
- Legacy load alias: older files may use `p1` and `p2` (axis-aligned corners). Writers conforming to this spec MUST write canonical keys only.

### 7.5 `polyline`

- `type`: `"polyline"`
- Required keys: `points` (array of `Vec2`)
- Optional: `closed` (boolean, defaults to `false`)

### 7.6 `spline`

- `type`: `"spline"`
- Required keys: `points` (array of `Vec2`)

### 7.7 `ellipse`

- `type`: `"ellipse"`
- Required keys:
  - `center` (`Vec2`)
  - `radiusX` (number, SHOULD be > 0)
  - `radiusY` (number, SHOULD be > 0)
  - `rotation` (number)
  - `startParam` (number)
  - `endParam` (number)

### 7.8 `point`

- `type`: `"point"`
- Required keys: `position` (`Vec2`)

### 7.9 `text`

- `type`: `"text"`
- Required keys:
  - `text` (string)
  - `position` (`Vec2`)
  - `height` (number)
  - `align` (`"left" | "center" | "right"`)
  - `verticalAlign` (`"top" | "middle" | "bottom" | "baseline"`)
  - `justify` (`"left" | "center" | "right"`)
  - `fontFamily` (string)
  - `fontStyle` (string)
  - `letterSpacing` (number)
  - `rotation` (number)

### 7.10 `dimension`

- `type`: `"dimension"`
- Required keys:
  - `p1` (`Vec2`)
  - `p2` (`Vec2`)
  - `p3` (`Vec2`)
  - `dimType` (`"linear" | "aligned"`)
  - `textHeight` (number)
  - `markType` (`"arrow" | "mark" | "none"`)
  - `arrowSize` (number)
  - `textPosition` (`"above" | "inline" | "below"`)
  - `textOffset` (number)
  - `extOffset` (number)
  - `dimOffset` (number)
- Legacy load aliases:
  - `arrowheadType` accepted as alias of `markType`
  - `arrowheadSize` accepted as alias of `arrowSize`
- Writers conforming to this spec MUST emit `markType` and `arrowSize`.

### 7.11 `hatch`

- `type`: `"hatch"`
- Required keys:
  - `pattern` (string)
  - `patternScale` (number)
  - `patternAngle` (number)
  - `boundary` (object or `null`)

`boundary` stores an inline serialized entity object or `null`.

## 8. Unknown and Invalid Data Handling

### 8.1 Unknown Entity Type

- Strict mode: MUST reject with validation error `unknown_entity_type`.
- Lenient mode (current runtime-compatible behavior): MAY deserialize as a generic base entity; however, this can drop unknown type-specific payload. For round-trip fidelity, strict mode is recommended for tooling.

### 8.2 Unknown Keys

- For v1 conformance validation, unknown keys SHOULD be treated as errors.
- Runtime loaders MAY accept unknown keys but are not required to preserve them.

### 8.3 Type Errors

If required keys are missing or value types mismatch expected contracts, loaders/validators MUST report an invalid document.

### 8.4 Container Errors

Container-aware loaders SHOULD report specific failures:

- `invalid_zip`: file is not a valid ZIP archive.
- `missing_document_json`: required `document.json` entry is absent.
- `invalid_document_json`: `document.json` is not valid UTF-8 JSON object payload.

Suggested error identifiers:

- `invalid_root`
- `unsupported_version`
- `invalid_layer`
- `invalid_entity`
- `missing_required_key`
- `type_mismatch`
- `unknown_entity_type`
- `invalid_zip`
- `missing_document_json`
- `invalid_document_json`

## 9. Load and Save Compatibility Policy

- Production/native save target SHOULD be `.odx` (ZIP container).
- Loaders SHOULD support both:
  - `.odx` ZIP container with `document.json` payload.
  - raw `.json` payload files for development/debug interchange.
- "Save as JSON" MAY be offered as a debug/export convenience path.
- The canonical schema applies to the `document.json` payload regardless of container.

## 10. Versioning and Migration

- `version` is mandatory and currently fixed at `"1.0"`.
- Future revisions MUST increment `version` and define deterministic migration rules.
- A migration step SHOULD transform legacy payloads to the canonical shape before normal deserialization.
- Canonical write policy: writers MUST output v1 canonical keys even when readers accept legacy aliases.

## 11. Validation Artifact

The companion JSON Schema file for this specification is:

- `Docs/file-format/opendraft-2d-v1.schema.json`

When schema and prose disagree, this document is the normative source and schema MUST be updated to match it.

## 12. Reference Examples

Reference files:

- `Docs/file-format/examples/minimal-line.json`
- `Docs/file-format/examples/comprehensive-sample.json`
- `Docs/file-format/examples/odx-package-layout.md`
