# Static SVG to PNG export contract 1

This separate export contract does not extend document-plan protocol version 1 or make PNG a native editable document. Only Inkscape SVG-to-PNG is supported. Use `ccb export export.json --preflight` to inspect readiness without creating files, then `ccb export export.json` to execute explicitly.

```json
{"export_version":1,"format":"png","source":"drawing.svg","output":"drawing.png","receipt":"drawing-receipt.json","width":640,"height":480}
```

Paths resolve relative to the job. All four job/input/output/receipt paths must differ; output and receipt need existing directories and new destinations. Only exact fields and version 1 are accepted, without duplicate keys. Jobs are limited to 64 KB, SVG inputs to 4 MB, output to 32 MB, dimensions to 8192 per side and 16 million pixels. The output canvas uses the requested dimensions; the SVG viewBox controls scaling and framing.

The static subset supports SVG/g/defs, basic shapes, paths, text/tspan, gradients/stops and clip paths. Unsupported elements or attributes fail closed. Scripts, events, CSS/style, images, href resources, foreign objects, entities and document declarations are refused. Only local `url(#id)` fragment references are accepted. This deliberately excludes many existing SVGs; simplify a copy before exporting. System font availability can change appearance. No Blender/GIMP or other export format is claimed.

Execution renders a staged, validated snapshot through a bounded native subprocess. Source content hashes must remain unchanged. PNG structure, chunk CRCs and requested dimensions are checked before output and receipt are linked into new destinations. Hard-link support in both destination directories is required; failures preserve existing files and roll back the newly published PNG when possible. Concurrent unrelated processes can still change published files after completion. The receipt contains local paths and content hashes; review it before sharing. This proves local file integrity, not pixel-level visual fidelity or publisher identity. No network or automatic export is introduced, and existing document-plan execution remains unchanged.
