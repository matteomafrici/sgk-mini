#!/usr/bin/env python3
"""Regenerate the widegap benchmark JSON with correct velocity profile."""

import json, math

Ri = 8.002998076523836e-3
Ro = 0.030
mu = 0.001
rho = 1000
Q = 1e-6
L = 0.050
k = Ri / Ro

# Correct dpL from flow rate
denom = (Ro**4 - Ri**4 - (Ro**2 - Ri**2)**2 / math.log(Ro/Ri))
dpL = 8 * mu * Q / (math.pi * denom)  # 0.00919 Pa/m

def U(r):
    return (dpL / (4*mu)) * (Ro**2 - r**2 + (Ro**2 - Ri**2) * math.log(r/Ro) / math.log(Ro/Ri))

# Find Umax
import numpy as np
r_fine = np.linspace(Ri*1.001, Ro*0.999, 10000)
u_fine = np.array([U(r) for r in r_fine])
imax = np.argmax(u_fine)
Umax = u_fine[imax]
Rmax = r_fine[imax]

# Shear stress
def dUdr(r):
    return (dpL / (4*mu)) * (-2*r + (Ro**2 - Ri**2) / (r * math.log(Ro/Ri)))

tau_inner = mu * abs(dUdr(Ri))
tau_outer = mu * abs(dUdr(Ro))

with open("/home/matteo-mafrici/work/sgk-mini/output/hollow-cylinder-widegap.physical-case.json") as f:
    bench = json.load(f)

bench["MaxVelocityMPerS"] = Umax
bench["MaxVelocityRadiusMm"] = Rmax * 1000
bench["InnerWallShearStressPa"] = -tau_inner
bench["OuterWallShearStressPa"] = -tau_outer

for s in bench["VelocityProfileSamples"]:
    r = s["RadiusMm"] / 1000
    s["AxialVelocityMPerS"] = U(r)

with open("/home/matteo-mafrici/work/sgk-mini/output/hollow-cylinder-widegap.physical-case.json", "w") as f:
    json.dump(bench, f, indent=2)

print("Fixed benchmark:")
print(f"  Umax = {Umax:.8f} m/s @ r={Rmax*1000:.4f} mm")
print(f"  tau_inner = {-tau_inner:.8f} Pa")
print(f"  tau_outer = {-tau_outer:.8f} Pa")
print(f"  Inner wall: U(Ri) = {U(Ri):.2e} m/s")
print(f"  Outer wall: U(Ro) = {U(Ro):.2e} m/s")
