# Portable font mappings

Map each requested family to application-specific names. Blender requires a local font file, resolved relative to the map file; Inkscape and GIMP use their installed family names.

```json
{"version":1,"families":{"Portable Sans":{"blender":{"family":"DejaVu Sans","file":"fonts/DejaVuSans.ttf"},"inkscape":{"family":"DejaVu Sans"},"gimp":{"family":"DejaVu Sans"}}}}
```

The optional inventory is a JSON array of available family names, gathered by the operator for the target application. Without it, name resolution is explicitly unverified. Missing mappings and files block writing a resolved plan. TTF/OTF files are capped at 20 MB. No font is downloaded, redistributed or licensed by this tool. Native font decoding can still fail despite successful preflight. The mapped plan contains an absolute local font reference for Blender; rerun mapping on another machine. Inkscape/GIMP plans retain family names. `font_file` is only supported for Blender text operations and appears in its capability manifest.

See the Blender [font loading API](https://docs.blender.org/api/4.4/bpy.types.BlendDataFonts.html). Native rendering evidence is collected by the required CI test, not inferred from a requested-family metadata field.
