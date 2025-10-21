# Elect_Enginv1
An AI designer


## New: DXF → PDF export (v3.1)
Use the new endpoint to convert any generated DXF under `/outputs/list` into a PDF:
```
GET /export/pdf?file=one_line_XXXXXXXX.dxf
```
The service will render the DXF using ezdxf's Matplotlib backend and save a peer PDF in the `out/` folder.
