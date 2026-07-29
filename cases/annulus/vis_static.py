"""ParaView Python: static image — Ux on annulus sector mesh."""

from paraview.simple import *

case = "/home/matteo-mafrici/work/sgk-mini/cases/annulus"

mesh = XMLUnstructuredGridReader(FileName=[f"{case}/VTK/annulus_200/internal.vtu"])

view = GetActiveViewOrCreate("RenderView")
view.Background = [0.15, 0.15, 0.2]
view.ViewSize = [1400, 1000]

# Show mesh surface colored by U
disp = Show(mesh, view)
ColorBy(disp, ("POINTS", "U"))
rep = GetDisplayProperties(mesh, view)
rep.Representation = "Surface"
rep.LineWidth = 0.0
rep.Ambient = 0.3
rep.Diffuse = 0.7
rep.Specular = 0.1
rep.SpecularPower = 10

# Colormap
lut = GetColorTransferFunction("U")
lut.ApplyPreset("Cool to Warm", True)
UpdateScalarBars()

# Scalar bar
bar = GetScalarBar(lut, view)
bar.Title = "U (m/s)"
bar.TitleFontSize = 14
bar.LabelFontSize = 12
bar.Visibility = 1
bar.Position = [0.85, 0.15]
bar.ScalarBarLength = 0.6

# Camera: 3/4 view looking into the sector
view.ResetCamera()
cam = view.GetActiveCamera()
cam.SetPosition(0.06, -0.025, 0.035)
cam.SetFocalPoint(0.025, 0, 0.009)
cam.SetViewUp(0, 0, 1)
view.ResetCamera()

# Save
out = f"{case}/VTK/annulus_ux.png"
SaveScreenshot(out, view, ImageResolution=[1400, 1000])
print("Saved:", out)
