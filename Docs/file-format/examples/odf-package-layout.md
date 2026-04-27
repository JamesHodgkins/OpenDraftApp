# OpenDraft `.odx` Package Layout Example

This shows the expected ZIP container structure for native OpenDraft v1 files.

```text
sample-drawing.odx
|- document.json
|- meta.json
`- assets/
```

## Required Entry

- `document.json` (required): canonical drawing payload.
  - Must validate against `Docs/file-format/opendraft-2d-v1.schema.json`.

## Optional Reserved Entries

- `meta.json` (optional): producer/build metadata.
- `assets/` (optional): reserved namespace for future external resources.

## Compatibility Notes

- Production/native persistence should use `.odx` container files.
- Raw `.json` files remain supported for development/debug workflows.
- Existing JSON examples in this folder are valid `document.json` payloads:
  - `minimal-line.json`
  - `comprehensive-sample.json`
