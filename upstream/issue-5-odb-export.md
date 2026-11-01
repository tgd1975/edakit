# Issue #798 – as posted

Posted on 2026-11-01 (https://github.com/oaslananka/easyeda-mcp-pro/issues/798), shortened the same day on the owner's word to the length of the short contributions
there (#468, #527).

### Title

```text
export: ODB++ export (PCB_ManufactureData.getOpenDatabaseDoublePlusFile) as a tool
```

### Body

````markdown
Some assemblers take ODB++ instead of Gerber – AISLER assembles only from ODB++ or native design files. EasyEDA Pro exports ODB++ (File > Export > ODB++) and its API has `PCB_ManufactureData.getOpenDatabaseDoublePlusFile` (BETA), but the server has no tool for it, and `easyeda_api_call` can't return a file.

**Proposal:** a tool `easyeda_export_odb` next to `easyeda_export_gerbers`, through a new bridge method `export.odb`. What we saw trying it on EasyEDA Pro 3.2.206 with a local stand-in:

- the archive holds the component layers with package, pins and part number;
- the API writes inch only (its `unit` type admits `ESYS_Unit.INCH`), the dialog writes mm;
- without a file name EasyEDA names the archive `undefined`.

Implementation in #799.
````
