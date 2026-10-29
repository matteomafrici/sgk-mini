# SGK Mini

SGK Mini tests the toolchain proposed for [SGK](https://github.com/matteomafrici/sgk): geometry generation, data exchange, reference analysis and eventually learned-model inference. The current example uses a hollow cylinder and an analytical annular-flow calculation.

## Current pipeline

```text
fixed hollow-cylinder parameters
    -> PicoGK voxel geometry
    -> VDB save/reload and voxel equality check
    -> volume and bounding-box extraction
    -> feature JSON write/read
    -> equivalent-annulus calculation
    -> physical-case JSON write/read
    -> geometry displayed in the PicoGK viewer
```

The implementation is in [Program.cs](src/SGK.Geometry/Program.cs). Geometry parameters and reference fluid conditions are defined in the source. CFD execution, dataset generation, model training and optimization are pending.

## Test case

| Parameter | Value |
|---|---|
| Nominal outer / inner diameter | 20 mm / 16 mm |
| Nominal length | 50 mm |
| Voxel size | 0.3 mm |
| Reference density | 1000 kg/m3 |
| Dynamic viscosity | 0.001 Pa s |
| Volumetric flow rate | 1e-6 m3/s |
| Velocity-profile samples | 17 radial locations, including both walls |

**Flow assumptions:** steady, incompressible, Newtonian, laminar, fully developed axial flow in a concentric annulus; no-slip walls; entry and exit effects neglected.

The calculation reconstructs an equivalent annulus from the measured voxel volume and bounding box. Its area is volume divided by length; the inner radius follows from that area and the inferred outer radius. Consequently, the radii used by the analytical calculation may differ from the nominal geometry parameters.

The voxel ring defines the annular domain used in this calculation. The code does not extract a separate fluid region from an enclosing solid wall; the current `GeometryInterpretation` string needs to be corrected to match this convention.

## Build and run

| Dependency | Current configuration |
|---|---|
| .NET SDK | 9.x (`net9.0`) |
| PicoGK managed package | 2.2.0, referenced in [SGK.Geometry.csproj](src/SGK.Geometry/SGK.Geometry.csproj) |
| PicoGK native runtime | Compatible native library installed separately and available to the application |
| Graphics | Working environment for the PicoGK viewer |

The recorded development setup was Fedora 44, with the native PicoGK runtime built from source. The repository does not yet provide a reproducible native-runtime setup procedure or automate copying that library into the build output.

Once these dependencies are available, run from the repository root:

```bash
cd src/SGK.Geometry
dotnet run
```

This working directory places the generated files in the repository's `output/` directory. Output paths currently resolve two levels above the process working directory.

## Outputs

| File in `output/` | Contents |
|---|---|
| `hollow-cylinder.vdb` | Generated voxel field, reloaded for comparison |
| `hollow-cylinder.features.json` | Schema and case identifiers, source path, volume and bounding box |
| `hollow-cylinder.physical-case.json` | Reconstructed radii, flow assumptions and properties, mean velocity, Reynolds number, pressure gradient/drop, radial velocity samples and wall shear values |

`MaxVelocityMPerS` and its radius identify the largest of the 17 sampled velocities. Wall shear values use the signed quantity mu du/dr at the two radii. Generated files are excluded from version control.

## Checks

| Check | Current implementation |
|---|---|
| Geometry serialization | Saves/reloads the VDB and compares voxel equality; prints volumes and bounding boxes |
| Feature record | Reads the JSON and checks schema/case identifiers, positive volume and axial extent |
| Physical record | Checks identifiers, selected geometric/physical ranges, sample count and zero velocity at both walls |
| Analytical reference | Calculates the fully developed annular-flow solution using reconstructed geometry |
| CFD comparison | Archived OpenFOAM cases; execution and comparison are outside the current program |

The JSON checks test data consistency. Independent verification of the analytical calculation and comparison with CFD remain separate steps.

### OpenFOAM comparison

Earlier work used `simpleFoam` for narrow- and wide-gap annuli. The case files and comparison scripts are available in [commit f02b242](https://github.com/matteomafrici/sgk-mini/tree/f02b242/cases), including a refined periodic case driven by `meanVelocityForce`.

A reproducible benchmark still needs one selected case, portable paths, a documented solver environment and explicit error definitions. Quantitative accuracy claims should be attached to that benchmark and its generated results.

## Known limitations

| Item | Consequence / correction needed |
|---|---|
| Equivalent-annulus interpretation | The JSON description calls the voxel ring a solid wall; align it with the actual analytical domain and verify reconstructed dimensions against nominal inputs. |
| Sampled peak velocity | Use the continuous analytical maximum for a peak-error comparison, or compare CFD and reference at matched sample locations. |
| Working-directory-dependent output path | Use the run commands above. Running with `--project` from the root currently places outputs outside the repository. |
| Exception handling | Exceptions are printed without setting a failure exit code; exit code zero alone does not confirm successful checks. |
| Native-runtime setup | Installation is currently environment-dependent and needs a reproducible procedure. |
| CFD benchmark availability | Restore and rerun the selected archived case before reporting numerical accuracy or attributing the near-wall discrepancy to discretization. |

## Next steps

1. Resolve the domain description, output-path behavior, failure status and analytical peak calculation.
2. Restore one reproducible OpenFOAM comparison with independent analytical checks and defined error metrics.
3. Vary a small set of geometric/flow parameters and generate a checked dataset.
4. Test geometry-to-model conversion and train a first predictor, comparing accuracy and cost with the analytical baseline.
5. Close a small parameter-search loop with reference checks.

The annulus provides a known solution for testing these connections. The computational benefit of the broader SGK approach will need evaluation on a problem with expensive reference analysis.

## License

Apache 2.0. See [LICENSE](LICENSE).
