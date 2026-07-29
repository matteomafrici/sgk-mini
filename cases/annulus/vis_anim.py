"""ParaView Python: camera rotation animation — annular sector."""
import math
from paraview.simple import *

case = "/home/matteo-mafrici/work/sgk-mini/cases/annulus"

mesh = XMLUnstructuredGridReader(FileName=[f"{case}/VTK/annulus_200/internal.vtu"])

view = GetActiveViewOrCreate("RenderView")
view.Background = [0.15, 0.15, 0.2]
view.ViewSize = [800, 600]

disp = Show(mesh, view)
ColorBy(disp, ("POINTS", "U"))
rep = GetDisplayProperties(mesh, view)
rep.Representation = "Surface"
rep.LineWidth = 0.0

lut = GetColorTransferFunction("U")
lut.ApplyPreset("Cool to Warm", True)
UpdateScalarBars()

view.ResetCamera()
cam = view.GetActiveCamera()
fp = [0.025, 0, 0.009]
dist = 0.07

n = 36
for i in range(n):
    theta = math.radians(i * 360.0 / n)
    x = fp[0] + dist * math.cos(theta) * 1.1
    y = fp[1] + dist * math.sin(theta) * 0.8
    z = fp[2] + dist * 0.5
    cam.SetPosition(x, y, z)
    cam.SetFocalPoint(fp)
    Render()
    SaveScreenshot(f"{case}/VTK/frame_{i:04d}.png", view, ImageResolution=[800, 600])
    print(f"Frame {i+1}/{n}")

print("Done.")
