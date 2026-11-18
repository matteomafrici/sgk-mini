# Environment and visualization references for SGK

Recorded on 2026-11-19. This is a project handoff for later SGK work. The
main SGK repository README defines the wider product scope and remains
the source for application choices. The current SGK Mini milestone is
GINO verification on the existing annulus batch.

## Tools and when they would enter

| Tool | Role | Relevance to SGK |
|---|---|---|
| PyTorch and NeuralOperator | Numerical training and inference library and operator implementations | Current MLP and FNO implementation. Use the same environment for the first GINO experiment and keep the established evaluator. |
| NVIDIA PhysicsNeMo | Python framework for physics ML, with model components, geometry processing and physics constraints | A candidate for later experiments if it simplifies a specific task. Version 2.2.2 imports locally in `~/data/venvs/sgk-pnm`. A synthetic FNO completed forward and backward on the local CUDA GPU. The recorded SGK Mini MLP and FNO runs did not use this environment. |
| Isaac Sim | Robotics simulation and scene inspection, with scene assets and sensors | A reference for inspectable scenes and sensor placement. Consider a connection if a later task actually needs robotics simulation, motion, contacts or optical sensors. |
| Isaac Lab | Robot learning framework with supported simulation backends | Relevant if a later case needs a learned robot policy in a simulator. The first SGK search policy proposes geometry parameter changes and can use the existing numerical evaluators. |
| Workbench and VTK.js | Local browser UI and candidate browser renderer for scientific meshes and volumes | The workbench already shows case state, logs and prepared annulus geometry. Add a scientific scene viewer when a real facility case needs sections, scalar fields and sensor inspection. |
| Omniverse Kit and OpenUSD | Toolkit for custom 3D applications and an exchange format for scene assets | Consider an export or viewer integration when a case needs richer scenes, RTX rendering or a partner's OpenUSD assets. Keep the SGK case and solver records independent of this rendering choice. |

Official references: [PhysicsNeMo for PyTorch users](https://docs.nvidia.com/physicsnemo/latest/user-guide/physicsnemo_for_pytorch.html),
[PhysicsNeMo physics constraints](https://docs.nvidia.com/physicsnemo/latest/user-guide/physics_addition.html),
[Isaac Sim overview](https://docs.isaacsim.omniverse.nvidia.com/latest/overview/overview.html),
[Isaac Lab](https://isaac-sim.github.io/IsaacLab/),
[VTK.js](https://kitware.github.io/vtk-js/docs/) and
[Omniverse Kit OpenVDB volume rendering](https://docs.omniverse.nvidia.com/kit/docs/omni.index.kit.rtx_scientific/1.0.0/Overview.html).

## Four reusable sources for later cases

| Environment component | Source | What it contributes |
|---|---|---|
| Space scenes, frames and trajectories | [NASA SPICE and Cosmographia](https://naif.jpl.nasa.gov/naif/cosmographia_details.html), [Solar System Treks](https://trek.jpl.nasa.gov/), [NASA Astrobee worlds](https://github.com/nasa/astrobee/blob/master/simulation/running_the_sim.md) | Ephemerides, orientation and scene examples. Treks adds planetary terrain. Astrobee provides existing Gazebo scenes of the ISS and the Ames testbed. |
| Planetary atmosphere | [NASA GRAM suite](https://software.nasa.gov/software/MFS-33888-1), [Mars Climate Database](https://www-mars.lmd.jussieu.fr/mcd_python/) | GRAM supplies engineering profiles of density, pressure, temperature, winds and composition, with variability. The Mars database provides atmospheric scenarios and fields. The supplying model and its applicability travel with the physical case. |
| Space plasma and magnetic field | [NASA SPDF, OMNIWeb and CDAWeb](https://spdf.gsfc.nasa.gov/about.html) | Measured time series and mission data. OMNI is mapped to near-Earth conditions by the source. These measurements can supply conditions and comparison data. A volumetric field requires an explicit reconstruction or solver model. |
| Vacuum test facility | [ESA ESTEC EPL and CORONA](https://technology.esa.int/lab/tec-m-epl-esa-propulsion-laboratory), [NASA VF-5 gas-flow study](https://ntrs.nasa.gov/api/citations/20150023083/downloads/20150023083.pdf), [NASA VF-5 HERMeS measurements](https://ntrs.nasa.gov/api/citations/20170000953/downloads/20170000953.pdf?attachment=true) | Published chamber dimensions, pumping configurations, gas-flow analyses and measurements. Useful for a simplified, traceable case. No calibrated chamber twin was identified in these sources. |

Keep three things explicit in a future case: scene geometry and frames;
environmental conditions supplied to the physical model; and sensor response
applied to the resulting fields. A facility can change those fields.
Moving a sensor can change the signal on the same field. Preserve the
data source, units, frame, applicable range and uncertainty at each step.
Calibration and independent experimental validation require separate data.

For the first facility proof, use a simplified chamber and one measured
observable. Vary probe position on the same field, then separately vary one
physical condition such as pumping. A viewer should display the chamber,
field and probe together, identify the source of each and show predicted
and recorded signals with units. The workbench can remain read-only while
the agent runs the underlying case.
