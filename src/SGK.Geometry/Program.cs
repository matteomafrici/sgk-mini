// See https://aka.ms/new-console-template for more information

using PicoGK;
using System.Numerics;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

int nExitCode = 0;

try
{
    HollowCylinderConfig oConfig = HollowCylinderConfig.FromArgs(args);
    bool bAutoExit = args.Contains("--auto-exit", StringComparer.Ordinal);

    Library.Go(
        (float)oConfig.VoxelSizeMm,
        () =>
        {
            // The task runs on a PicoGK thread. An exception escaping it is not
            // guaranteed to reach the catch block below, so it is captured here
            // and turned into a non-zero exit code explicitly.
            try
            {
                HollowCylinderTask.Run(oConfig);
            }
            catch (Exception e)
            {
                Console.WriteLine(e.ToString());
                nExitCode = 1;
            }
        },
        bEndAppWithTask: bAutoExit);
}
catch (Exception e)
{
    Console.WriteLine(e.ToString());
    nExitCode = 1;
}

return nExitCode;

class HollowCylinderConfig
{
    // Identity of the case. It is written into the records and used for the
    // output file names, so a dataset can hold many cases without collisions.
    // The default keeps every existing caller working unchanged.
    public string CaseId { get; set; } = "hollow-cylinder";

    public double OuterRadiusMm { get; set; } = 10.0;
    public double InnerRadiusMm { get; set; } = 8.0;
    public double LengthMm { get; set; } = 50.0;

    // Voxel size is a declared case parameter: it bounds which features the
    // geometry can represent, so it belongs in the case record, not in the code.
    // 0.2 mm is the measured choice: the last resolution where refining still
    // improves the geometry (see validation/voxel-resolution-curve.md).
    public double VoxelSizeMm { get; set; } = 0.2;

    // Fluid and flow are inputs of the physical case, not constants of the
    // program: the dataset varies them per case. The defaults are the
    // water-like reference used by the original validation.
    public double DensityKgPerM3 { get; set; } = 1000.0;
    public double DynamicViscosityPaS { get; set; } = 1.0e-3;
    public double VolumetricFlowRateM3PerS { get; set; } = 1.0e-6;

    // Where the generated artifacts go. Empty means <repository>/output, which
    // is the historical behaviour. A dataset passes an absolute per-case path.
    public string OutputDirectory { get; set; } = "";

    public static HollowCylinderConfig FromArgs(string[] args)
    {
        int nIndex = Array.IndexOf(args, "--config");

        if (nIndex < 0)
        {
            return new HollowCylinderConfig();
        }

        if (nIndex + 1 >= args.Length)
        {
            throw new Exception("--config requires a JSON file path");
        }

        string strPath = args[nIndex + 1];
        string strJson = File.ReadAllText(strPath);

        // Unknown properties are rejected instead of silently ignored. A
        // misspelled "InnerRadiusMm" must fail loudly; otherwise the case runs
        // with the default geometry and every downstream number is wrong while
        // looking perfectly valid.
        HollowCylinderConfig? oConfig = JsonSerializer.Deserialize<HollowCylinderConfig>(
            strJson,
            new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow
            });

        if (oConfig is null)
        {
            throw new Exception($"Config deserialization returned null: {strPath}");
        }

        oConfig.Validate();

        return oConfig;
    }

    public void Validate()
    {
        if (string.IsNullOrWhiteSpace(CaseId))
        {
            throw new Exception("Case id is empty");
        }

        foreach (char c in CaseId)
        {
            bool bAllowed =
                char.IsAsciiLetterOrDigit(c) || c == '-' || c == '_' || c == '.';

            if (!bAllowed)
            {
                throw new Exception(
                    $"Case id contains a character that is not safe in a file name: '{c}'");
            }
        }

        RequireFinite(OuterRadiusMm, "outer radius");
        RequireFinite(InnerRadiusMm, "inner radius");
        RequireFinite(LengthMm, "length");
        RequireFinite(VoxelSizeMm, "voxel size");
        RequireFinite(DensityKgPerM3, "density");
        RequireFinite(DynamicViscosityPaS, "dynamic viscosity");
        RequireFinite(VolumetricFlowRateM3PerS, "volumetric flow rate");

        if (OuterRadiusMm <= 0.0)
        {
            throw new Exception($"Invalid outer radius: {OuterRadiusMm}");
        }

        if (InnerRadiusMm <= 0.0)
        {
            throw new Exception($"Invalid inner radius: {InnerRadiusMm}");
        }

        if (InnerRadiusMm >= OuterRadiusMm)
        {
            throw new Exception(
                $"Inner radius must be smaller than outer radius: inner={InnerRadiusMm}, outer={OuterRadiusMm}");
        }

        if (LengthMm <= 0.0)
        {
            throw new Exception($"Invalid length: {LengthMm}");
        }

        if (VoxelSizeMm <= 0.0 || VoxelSizeMm > 1.0)
        {
            throw new Exception(
                $"Invalid voxel size: {VoxelSizeMm} mm (expected 0 < voxel <= 1 mm)");
        }

        if (DensityKgPerM3 <= 0.0)
        {
            throw new Exception($"Invalid density: {DensityKgPerM3}");
        }

        if (DynamicViscosityPaS <= 0.0)
        {
            throw new Exception($"Invalid dynamic viscosity: {DynamicViscosityPaS}");
        }

        if (VolumetricFlowRateM3PerS <= 0.0)
        {
            throw new Exception($"Invalid volumetric flow rate: {VolumetricFlowRateM3PerS}");
        }

        // PicoGK works in float millimetres. Refuse dimensions that cannot be
        // represented with a meaningful number of voxels instead of producing a
        // truncated or empty body.
        const double maxVoxelsPerAxis = 100_000.0;

        if (2.0 * OuterRadiusMm / VoxelSizeMm > maxVoxelsPerAxis ||
            LengthMm / VoxelSizeMm > maxVoxelsPerAxis)
        {
            throw new Exception(
                $"Geometry is not representable at {VoxelSizeMm} mm voxel: " +
                $"diameter {2.0 * OuterRadiusMm} mm, length {LengthMm} mm");
        }

        if (2.0 * OuterRadiusMm > float.MaxValue || LengthMm > float.MaxValue)
        {
            throw new Exception("Geometry dimensions exceed the float range");
        }
    }

    private static void RequireFinite(double value, string name)
    {
        if (!double.IsFinite(value))
        {
            throw new Exception($"Non-finite {name}: {value}");
        }
    }
}

class HollowCylinderTask
{
    public static void Run(HollowCylinderConfig config)
    {
        float fLengthMm = (float)config.LengthMm;
        float fOuterRadiusMm = (float)config.OuterRadiusMm;
        float fInnerRadiusMm = (float)config.InnerRadiusMm;

        Lattice latOutside = new();
        latOutside.AddBeam(
            new Vector3(0, 0, 0),
            new Vector3(0, 0, fLengthMm),
            fOuterRadiusMm, fOuterRadiusMm,
            false);

        Voxels voxOutside = new(latOutside);

        Lattice latInside = new();
        latInside.AddBeam(
            new Vector3(0, 0, 0),
            new Vector3(0, 0, fLengthMm),
            fInnerRadiusMm, fInnerRadiusMm,
            false);

        Voxels voxInside = new(latInside);

        voxOutside.BoolSubtract(voxInside);

        string outputDir = ResolveOutputDirectory(config);
        Directory.CreateDirectory(outputDir);

        string vdbFileName = $"{config.CaseId}.vdb";
        string vdbPath = Path.Combine(outputDir, vdbFileName);

        using (OpenVdbFile vdb = new(Library.oLibrary()))
        {
            vdb.nAdd(voxOutside, "HollowCylinder");
            vdb.SaveToFile(vdbPath);
            Console.WriteLine($"Saved VDB: {vdbPath}");
        }

        Voxels loadedVoxels = Voxels.voxFromVdbFile(vdbPath);
        Console.WriteLine("Reloaded VDB into voxel field successfully");

        bool isEqual = voxOutside.bIsEqual(loadedVoxels);

        voxOutside.CalculateProperties(out float originalVolume, out BBox3 originalBox);
        loadedVoxels.CalculateProperties(out float loadedVolume, out BBox3 loadedBox);

        Console.WriteLine($"Original volume [mm^3]: {originalVolume}");
        Console.WriteLine($"Loaded volume   [mm^3]: {loadedVolume}");
        Console.WriteLine($"Original bbox: {originalBox}");
        Console.WriteLine($"Loaded bbox:   {loadedBox}");
        Console.WriteLine($"Voxel equality: {isEqual}");

        if (!isEqual)
        {
            throw new Exception("Reloaded voxel field does not match original voxel field");
        }

        var featureRecord = new HollowCylinderFeatureRecord
        {
            SchemaVersion = "sgk-mini.feature-record.v2",
            CaseId = config.CaseId,
            SourceVdbPath = vdbFileName,
            VoxelSizeMm = config.VoxelSizeMm,
            VolumeMm3 = loadedVolume,
            BBoxMinXMm = loadedBox.vecMin.X,
            BBoxMinYMm = loadedBox.vecMin.Y,
            BBoxMinZMm = loadedBox.vecMin.Z,
            BBoxMaxXMm = loadedBox.vecMax.X,
            BBoxMaxYMm = loadedBox.vecMax.Y,
            BBoxMaxZMm = loadedBox.vecMax.Z
        };

        string featurePath = Path.Combine(outputDir, $"{config.CaseId}.features.json");

        string featureJson = JsonSerializer.Serialize(
            featureRecord,
            new JsonSerializerOptions { WriteIndented = true });

        File.WriteAllText(featurePath, featureJson);
        Console.WriteLine($"Saved feature record: {featurePath}");

        HollowCylinderFeatureRecord reloadedFeatureRecord = ReadAndValidateFeatureRecord(featurePath);

        Console.WriteLine($"Reloaded feature record schema: {reloadedFeatureRecord.SchemaVersion}");
        Console.WriteLine($"Reloaded feature record case:   {reloadedFeatureRecord.CaseId}");
        Console.WriteLine($"Reloaded feature record volume: {reloadedFeatureRecord.VolumeMm3}");
        Console.WriteLine("Feature record validation passed");

        HollowCylinderPhysicalRecord physicalRecord =
            ComputeConcentricAnnulusLaminarFlowPhysicalRecord(reloadedFeatureRecord, config);

        string physicalPath = Path.Combine(outputDir, $"{config.CaseId}.physical-case.json");

        string physicalJson = JsonSerializer.Serialize(
            physicalRecord,
            new JsonSerializerOptions { WriteIndented = true });

        File.WriteAllText(physicalPath, physicalJson);
        Console.WriteLine($"Saved physical record: {physicalPath}");

        HollowCylinderPhysicalRecord reloadedPhysicalRecord =
            ReadAndValidatePhysicalRecord(physicalPath);

        Console.WriteLine($"Reloaded physical schema: {reloadedPhysicalRecord.SchemaVersion}");
        Console.WriteLine($"Reloaded physical case:   {reloadedPhysicalRecord.CaseId}");
        Console.WriteLine($"Reloaded pressure drop:   {reloadedPhysicalRecord.PressureDropPa}");
        Console.WriteLine($"Reloaded max velocity:    {reloadedPhysicalRecord.MaxVelocityMPerS}");
        Console.WriteLine("Physical record validation passed");

        Library.oViewer().Add(loadedVoxels);

        Console.WriteLine("Hollow cylinder generated: "
            + $"OD {2.0 * reloadedPhysicalRecord.OuterRadiusMm:F3} mm, "
            + $"ID {2.0 * reloadedPhysicalRecord.InnerRadiusMm:F3} mm, "
            + $"length {reloadedPhysicalRecord.LengthMm:F3} mm (reconstructed from the voxel field)");
        Console.WriteLine("Serialization round-trip validated successfully");
        Console.WriteLine("Feature extraction record written successfully");
        Console.WriteLine("Feature extraction record read successfully");
        Console.WriteLine("Analytic annulus-flow benchmark written successfully");
        Console.WriteLine("Analytic annulus-flow benchmark read successfully");
    }

    private static string ResolveOutputDirectory(HollowCylinderConfig config)
    {
        if (string.IsNullOrWhiteSpace(config.OutputDirectory))
        {
            return Path.Combine(FindRepositoryRoot(), "output");
        }

        return Path.GetFullPath(config.OutputDirectory);
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? oDir = new DirectoryInfo(AppContext.BaseDirectory);

        while (oDir is not null)
        {
            if (File.Exists(Path.Combine(oDir.FullName, "SGK-Mini.sln")))
            {
                return oDir.FullName;
            }

            oDir = oDir.Parent;
        }

        throw new Exception(
            "Could not locate the repository root (SGK-Mini.sln not found above the assembly).");
    }

    private static HollowCylinderFeatureRecord ReadAndValidateFeatureRecord(string featurePath)
    {
        string json = File.ReadAllText(featurePath);

        HollowCylinderFeatureRecord? record =
            JsonSerializer.Deserialize<HollowCylinderFeatureRecord>(json);

        if (record is null)
        {
            throw new Exception("Feature record deserialization returned null");
        }

        if (record.SchemaVersion != "sgk-mini.feature-record.v2")
        {
            throw new Exception($"Unexpected schema version: {record.SchemaVersion}");
        }

        if (string.IsNullOrWhiteSpace(record.CaseId))
        {
            throw new Exception("Feature record case id is empty");
        }

        RequireFinite(record.VoxelSizeMm, "feature voxel size");
        RequireFinite(record.VolumeMm3, "feature volume");
        RequireFinite(record.BBoxMinXMm, "feature bbox min X");
        RequireFinite(record.BBoxMinYMm, "feature bbox min Y");
        RequireFinite(record.BBoxMinZMm, "feature bbox min Z");
        RequireFinite(record.BBoxMaxXMm, "feature bbox max X");
        RequireFinite(record.BBoxMaxYMm, "feature bbox max Y");
        RequireFinite(record.BBoxMaxZMm, "feature bbox max Z");

        if (record.VoxelSizeMm <= 0.0)
        {
            throw new Exception($"Invalid feature voxel size: {record.VoxelSizeMm}");
        }

        if (record.VolumeMm3 <= 0)
        {
            throw new Exception($"Invalid volume: {record.VolumeMm3}");
        }

        double spanXMm = record.BBoxMaxXMm - record.BBoxMinXMm;
        double spanYMm = record.BBoxMaxYMm - record.BBoxMinYMm;
        double spanZMm = record.BBoxMaxZMm - record.BBoxMinZMm;

        if (spanXMm <= 0 || spanYMm <= 0 || spanZMm <= 0)
        {
            throw new Exception(
                $"Invalid bbox spans: X={spanXMm}, Y={spanYMm}, Z={spanZMm}");
        }

        // The body is a concentric cylinder, so its transverse extents must
        // describe a circle. Two voxels of slack cover the discretisation of the
        // bounding box. A truncated or clipped body fails here instead of
        // producing a plausible-looking but wrong radius.
        double transverseTolerance = 2.0 * record.VoxelSizeMm;

        if (Math.Abs(spanXMm - spanYMm) > transverseTolerance)
        {
            throw new Exception(
                $"Transverse extents differ: X={spanXMm}, Y={spanYMm} mm " +
                $"(tolerance {transverseTolerance} mm)");
        }

        double halfSpanXMm = 0.5 * spanXMm;
        double halfSpanYMm = 0.5 * spanYMm;

        if (Math.Abs(Math.Abs(record.BBoxMinXMm) - halfSpanXMm) > transverseTolerance ||
            Math.Abs(Math.Abs(record.BBoxMaxXMm) - halfSpanXMm) > transverseTolerance ||
            Math.Abs(Math.Abs(record.BBoxMinYMm) - halfSpanYMm) > transverseTolerance ||
            Math.Abs(Math.Abs(record.BBoxMaxYMm) - halfSpanYMm) > transverseTolerance)
        {
            throw new Exception(
                "Bounding box is not centred on the axis: " +
                $"X=[{record.BBoxMinXMm}, {record.BBoxMaxXMm}], " +
                $"Y=[{record.BBoxMinYMm}, {record.BBoxMaxYMm}]");
        }

        return record;
    }

    private static HollowCylinderPhysicalRecord ComputeConcentricAnnulusLaminarFlowPhysicalRecord(
        HollowCylinderFeatureRecord featureRecord,
        HollowCylinderConfig config)
    {
        double rhoKgPerM3 = config.DensityKgPerM3;
        double muPaS = config.DynamicViscosityPaS;
        double volumetricFlowRateM3PerS = config.VolumetricFlowRateM3PerS;
        const int velocityProfileSampleCount = 17;

        double lengthMm = featureRecord.BBoxMaxZMm - featureRecord.BBoxMinZMm;
        double outerRadiusMm = Math.Max(
            Math.Max(Math.Abs(featureRecord.BBoxMaxXMm), Math.Abs(featureRecord.BBoxMaxYMm)),
            Math.Max(Math.Abs(featureRecord.BBoxMinXMm), Math.Abs(featureRecord.BBoxMinYMm)));

        double areaMm2 = featureRecord.VolumeMm3 / lengthMm;
        double innerRadiusMm = Math.Sqrt(
            outerRadiusMm * outerRadiusMm - areaMm2 / Math.PI);

        if (!(innerRadiusMm > 0.0) || innerRadiusMm >= outerRadiusMm)
        {
            throw new Exception(
                $"Reconstructed radii are not a valid annulus: inner={innerRadiusMm} mm, " +
                $"outer={outerRadiusMm} mm");
        }

        double kappa = innerRadiusMm / outerRadiusMm;
        double areaM2 = areaMm2 * 1.0e-6;
        double lengthM = lengthMm * 1.0e-3;
        double outerRadiusM = outerRadiusMm * 1.0e-3;
        double innerRadiusM = innerRadiusMm * 1.0e-3;
        double hydraulicDiameterM = 2.0 * (outerRadiusMm - innerRadiusMm) * 1.0e-3;

        double meanVelocityMPerS = volumetricFlowRateM3PerS / areaM2;
        double reynolds = rhoKgPerM3 * meanVelocityMPerS * hydraulicDiameterM / muPaS;

        if (reynolds >= 2000.0)
        {
            throw new Exception(
                $"Requested flow is not laminar: Re={reynolds:F1} (must stay below 2000)");
        }

        double annulusFactor =
            1.0 + kappa * kappa + (1.0 - kappa * kappa) / Math.Log(kappa);

        double pressureGradientPaPerM =
            (muPaS / (outerRadiusM * outerRadiusM)) *
            (8.0 / annulusFactor) *
            meanVelocityMPerS;

        double pressureDropPa = pressureGradientPaPerM * lengthM;

        double dpDz = -pressureGradientPaPerM;

        VelocityProfileSample[] velocityProfileSamples =
            BuildVelocityProfileSamples(
                innerRadiusM,
                outerRadiusM,
                dpDz,
                muPaS,
                velocityProfileSampleCount);

        // The peak of the analytical profile is continuous, so it is evaluated
        // where du/dr = 0 rather than read off the sampled profile. Sampling the
        // 17 points can only understate the true peak.
        double maxVelocityRadiusM = Math.Sqrt(
            (outerRadiusM * outerRadiusM - innerRadiusM * innerRadiusM) /
            (2.0 * Math.Log(outerRadiusM / innerRadiusM)));

        double maxVelocityMPerS = ComputeAxialVelocityMPerS(
            maxVelocityRadiusM,
            innerRadiusM,
            outerRadiusM,
            dpDz,
            muPaS);

        double maxVelocityRadiusMm = maxVelocityRadiusM * 1.0e3;

        // Kept separately for traceability: this is what the sampled profile shows,
        // and what a mesh-node comparison would see.
        double sampledMaxVelocityMPerS = double.MinValue;
        double sampledMaxVelocityRadiusMm = 0.0;

        foreach (VelocityProfileSample sample in velocityProfileSamples)
        {
            if (sample.AxialVelocityMPerS > sampledMaxVelocityMPerS)
            {
                sampledMaxVelocityMPerS = sample.AxialVelocityMPerS;
                sampledMaxVelocityRadiusMm = sample.RadiusMm;
            }
        }

        // Signed in the increasing-radial direction: the wall drags the fluid
        // forward at the inner wall (positive) and holds it back at the outer
        // wall (negative). Keeping one coordinate system for both avoids the
        // sign confusion that a "magnitude" would hide.
        double innerWallShearStressPa =
            ComputeShearStressPa(innerRadiusM, dpDz, muPaS, innerRadiusM, outerRadiusM);

        double outerWallShearStressPa =
            ComputeShearStressPa(outerRadiusM, dpDz, muPaS, innerRadiusM, outerRadiusM);

        return new HollowCylinderPhysicalRecord
        {
            SchemaVersion = "sgk-mini.physical-record.v3",
            CaseId = featureRecord.CaseId,
            SourceFeaturePath = featureRecord.SourceVdbPath
                .Replace(".vdb", ".features.json", StringComparison.Ordinal),
            PhysicalCase = "steady-fully-developed-laminar-axial-flow-in-concentric-annulus",
            GeometryInterpretation =
                "The hollow-cylinder voxel body is the solid wall material between the inner " +
                "and outer radius; its volume and bounding box are used only to recover those " +
                "radii. The fluid domain is the concentric annular space bounded by them, not " +
                "the voxel solid, and no separate fluid region is extracted from the geometry.",
            FluidName = "water-like-reference",
            DensityKgPerM3 = rhoKgPerM3,
            DynamicViscosityPaS = muPaS,
            VolumetricFlowRateM3PerS = volumetricFlowRateM3PerS,
            Assumptions = new[]
            {
                "incompressible-fluid",
                "newtonian-fluid",
                "steady-flow",
                "fully-developed-axial-flow",
                "concentric-annulus",
                "constant-cross-section",
                "no-slip-walls",
                "laminar-regime",
                "entry-and-exit-effects-neglected"
            },
            LengthMm = lengthMm,
            OuterRadiusMm = outerRadiusMm,
            InnerRadiusMm = innerRadiusMm,
            CrossSectionAreaMm2 = areaMm2,
            RadiusRatio = kappa,
            MeanVelocityMPerS = meanVelocityMPerS,
            ReynoldsNumber = reynolds,
            PressureGradientPaPerM = pressureGradientPaPerM,
            PressureDropPa = pressureDropPa,
            MaxVelocityMPerS = maxVelocityMPerS,
            MaxVelocityRadiusMm = maxVelocityRadiusMm,
            SampledMaxVelocityMPerS = sampledMaxVelocityMPerS,
            SampledMaxVelocityRadiusMm = sampledMaxVelocityRadiusMm,
            InnerWallShearStressPa = innerWallShearStressPa,
            OuterWallShearStressPa = outerWallShearStressPa,
            ShearStressSignConvention =
                "signed mu*du/dr in the increasing-r direction; positive at the inner wall, " +
                "negative at the outer wall",
            VoxelSizeMm = featureRecord.VoxelSizeMm,
            VelocityProfileSamples = velocityProfileSamples
        };
    }

    private static VelocityProfileSample[] BuildVelocityProfileSamples(
        double innerRadiusM,
        double outerRadiusM,
        double dpDz,
        double muPaS,
        int sampleCount)
    {
        VelocityProfileSample[] samples = new VelocityProfileSample[sampleCount];

        double spanM = outerRadiusM - innerRadiusM;

        for (int i = 0; i < sampleCount; i++)
        {
            double t = sampleCount == 1 ? 0.0 : (double)i / (sampleCount - 1);
            double radiusM = innerRadiusM + t * spanM;
            double velocityMPerS = ComputeAxialVelocityMPerS(radiusM, innerRadiusM, outerRadiusM, dpDz, muPaS);

            samples[i] = new VelocityProfileSample
            {
                SampleIndex = i,
                RadiusMm = radiusM * 1.0e3,
                RadiusNormalized = t,
                AxialVelocityMPerS = velocityMPerS
            };
        }

        return samples;
    }

    private static double ComputeAxialVelocityMPerS(
        double radiusM,
        double innerRadiusM,
        double outerRadiusM,
        double dpDz,
        double muPaS)
    {
        double logTerm = Math.Log(radiusM / innerRadiusM) / Math.Log(outerRadiusM / innerRadiusM);

        return (dpDz / (4.0 * muPaS)) *
               ((radiusM * radiusM - innerRadiusM * innerRadiusM) -
                (outerRadiusM * outerRadiusM - innerRadiusM * innerRadiusM) * logTerm);
    }

    private static double ComputeVelocityDerivativeMPerSPerM(
        double radiusM,
        double innerRadiusM,
        double outerRadiusM,
        double dpDz,
        double muPaS)
    {
        return (dpDz / (4.0 * muPaS)) *
               (2.0 * radiusM -
                (outerRadiusM * outerRadiusM - innerRadiusM * innerRadiusM) /
                (radiusM * Math.Log(outerRadiusM / innerRadiusM)));
    }

    private static double ComputeShearStressPa(
        double radiusM,
        double dpDz,
        double muPaS,
        double innerRadiusM,
        double outerRadiusM)
    {
        double duDr = ComputeVelocityDerivativeMPerSPerM(
            radiusM,
            innerRadiusM,
            outerRadiusM,
            dpDz,
            muPaS);

        return muPaS * duDr;
    }

    private static HollowCylinderPhysicalRecord ReadAndValidatePhysicalRecord(string physicalPath)
    {
        string json = File.ReadAllText(physicalPath);

        HollowCylinderPhysicalRecord? record =
            JsonSerializer.Deserialize<HollowCylinderPhysicalRecord>(json);

        if (record is null)
        {
            throw new Exception("Physical record deserialization returned null");
        }

        if (record.SchemaVersion != "sgk-mini.physical-record.v3")
        {
            throw new Exception($"Unexpected physical schema version: {record.SchemaVersion}");
        }

        if (string.IsNullOrWhiteSpace(record.CaseId))
        {
            throw new Exception("Physical record case id is empty");
        }

        RequireFinite(record.DensityKgPerM3, "density");
        RequireFinite(record.DynamicViscosityPaS, "dynamic viscosity");
        RequireFinite(record.VolumetricFlowRateM3PerS, "volumetric flow rate");
        RequireFinite(record.LengthMm, "physical length");
        RequireFinite(record.OuterRadiusMm, "outer radius");
        RequireFinite(record.InnerRadiusMm, "inner radius");
        RequireFinite(record.CrossSectionAreaMm2, "cross-section area");
        RequireFinite(record.RadiusRatio, "radius ratio");
        RequireFinite(record.MeanVelocityMPerS, "mean velocity");
        RequireFinite(record.ReynoldsNumber, "Reynolds number");
        RequireFinite(record.PressureGradientPaPerM, "pressure gradient");
        RequireFinite(record.PressureDropPa, "pressure drop");
        RequireFinite(record.MaxVelocityMPerS, "max velocity");
        RequireFinite(record.MaxVelocityRadiusMm, "max velocity radius");
        RequireFinite(record.SampledMaxVelocityMPerS, "sampled max velocity");
        RequireFinite(record.SampledMaxVelocityRadiusMm, "sampled max velocity radius");
        RequireFinite(record.InnerWallShearStressPa, "inner wall shear stress");
        RequireFinite(record.OuterWallShearStressPa, "outer wall shear stress");
        RequireFinite(record.VoxelSizeMm, "voxel size");

        if (record.DensityKgPerM3 <= 0 || record.DynamicViscosityPaS <= 0 ||
            record.VolumetricFlowRateM3PerS <= 0)
        {
            throw new Exception("Density, viscosity and flow rate must be positive");
        }

        if (record.LengthMm <= 0)
        {
            throw new Exception($"Invalid physical length: {record.LengthMm}");
        }

        if (record.OuterRadiusMm <= record.InnerRadiusMm)
        {
            throw new Exception(
                $"Invalid radii: outer={record.OuterRadiusMm}, inner={record.InnerRadiusMm}");
        }

        if (record.CrossSectionAreaMm2 <= 0)
        {
            throw new Exception($"Invalid cross-section area: {record.CrossSectionAreaMm2}");
        }

        if (record.RadiusRatio <= 0 || record.RadiusRatio >= 1)
        {
            throw new Exception($"Invalid radius ratio: {record.RadiusRatio}");
        }

        if (record.ReynoldsNumber >= 2000)
        {
            throw new Exception($"Flow is not laminar enough for this benchmark: Re={record.ReynoldsNumber}");
        }

        if (record.PressureGradientPaPerM <= 0)
        {
            throw new Exception($"Invalid pressure gradient: {record.PressureGradientPaPerM}");
        }

        if (record.PressureDropPa <= 0)
        {
            throw new Exception($"Invalid pressure drop: {record.PressureDropPa}");
        }

        if (record.MaxVelocityMPerS <= 0)
        {
            throw new Exception($"Invalid max velocity: {record.MaxVelocityMPerS}");
        }

        if (record.MaxVelocityRadiusMm <= record.InnerRadiusMm ||
            record.MaxVelocityRadiusMm >= record.OuterRadiusMm)
        {
            throw new Exception(
                $"Peak velocity radius outside the annulus: radius={record.MaxVelocityRadiusMm}, " +
                $"inner={record.InnerRadiusMm}, outer={record.OuterRadiusMm}");
        }

        if (record.SampledMaxVelocityMPerS <= 0)
        {
            throw new Exception(
                $"Invalid sampled max velocity: {record.SampledMaxVelocityMPerS}");
        }

        if (record.SampledMaxVelocityMPerS > record.MaxVelocityMPerS)
        {
            throw new Exception(
                "Sampled peak velocity exceeds the continuous analytical peak: " +
                $"{record.SampledMaxVelocityMPerS} > {record.MaxVelocityMPerS}");
        }

        // The record is a closed set of numbers: every derived quantity must be
        // reproducible from the ones it claims to derive from. A mismatch means
        // the file was edited or produced by a different formula.
        double areaM2 = record.CrossSectionAreaMm2 * 1.0e-6;
        double expectedMeanVelocity = record.VolumetricFlowRateM3PerS / areaM2;

        if (!IsCloseRelative(record.MeanVelocityMPerS, expectedMeanVelocity, 1.0e-9))
        {
            throw new Exception(
                $"Mean velocity {record.MeanVelocityMPerS} does not equal Q/area " +
                $"{expectedMeanVelocity}");
        }

        double hydraulicDiameterM = 2.0 * (record.OuterRadiusMm - record.InnerRadiusMm) * 1.0e-3;
        double expectedReynolds =
            record.DensityKgPerM3 * record.MeanVelocityMPerS * hydraulicDiameterM /
            record.DynamicViscosityPaS;

        if (!IsCloseRelative(record.ReynoldsNumber, expectedReynolds, 1.0e-9))
        {
            throw new Exception(
                $"Reynolds number {record.ReynoldsNumber} does not match its definition " +
                $"{expectedReynolds}");
        }

        if (record.VelocityProfileSamples is null || record.VelocityProfileSamples.Length != 17)
        {
            throw new Exception("Velocity profile sample array is missing or has unexpected length");
        }

        for (int i = 0; i < record.VelocityProfileSamples.Length; i++)
        {
            VelocityProfileSample sample = record.VelocityProfileSamples[i];

            RequireFinite(sample.RadiusMm, $"profile radius {i}");
            RequireFinite(sample.RadiusNormalized, $"profile normalized radius {i}");
            RequireFinite(sample.AxialVelocityMPerS, $"profile velocity {i}");

            if (sample.RadiusMm < record.InnerRadiusMm - 1.0e-9 ||
                sample.RadiusMm > record.OuterRadiusMm + 1.0e-9)
            {
                throw new Exception(
                    $"Profile sample {i} lies outside the annulus: r={sample.RadiusMm}");
            }
        }

        if (Math.Abs(record.VelocityProfileSamples[0].AxialVelocityMPerS) > 1.0e-9)
        {
            throw new Exception("Inner wall velocity sample is not approximately zero");
        }

        if (Math.Abs(record.VelocityProfileSamples[^1].AxialVelocityMPerS) > 1.0e-9)
        {
            throw new Exception("Outer wall velocity sample is not approximately zero");
        }

        // The analytical profile is unimodal: it rises from the inner wall,
        // reaches one maximum, and falls to the outer wall. A second turning
        // point means the samples do not describe this solution.
        int peakIndex = 0;
        for (int i = 1; i < record.VelocityProfileSamples.Length; i++)
        {
            if (record.VelocityProfileSamples[i].AxialVelocityMPerS >
                record.VelocityProfileSamples[peakIndex].AxialVelocityMPerS)
            {
                peakIndex = i;
            }
        }

        for (int i = 1; i <= peakIndex; i++)
        {
            if (record.VelocityProfileSamples[i].AxialVelocityMPerS <
                record.VelocityProfileSamples[i - 1].AxialVelocityMPerS - 1.0e-12)
            {
                throw new Exception($"Profile is not monotone before its peak at sample {i}");
            }
        }

        for (int i = peakIndex + 1; i < record.VelocityProfileSamples.Length; i++)
        {
            if (record.VelocityProfileSamples[i].AxialVelocityMPerS >
                record.VelocityProfileSamples[i - 1].AxialVelocityMPerS + 1.0e-12)
            {
                throw new Exception($"Profile is not monotone after its peak at sample {i}");
            }
        }

        if (record.InnerWallShearStressPa <= 0 || record.OuterWallShearStressPa >= 0)
        {
            throw new Exception(
                "Wall shear stresses do not follow the recorded sign convention " +
                $"(inner={record.InnerWallShearStressPa}, outer={record.OuterWallShearStressPa})");
        }

        if (string.IsNullOrWhiteSpace(record.ShearStressSignConvention))
        {
            throw new Exception("Shear stress sign convention is not recorded");
        }

        return record;
    }

    private static bool IsCloseRelative(double a, double b, double relativeTolerance)
    {
        double scale = Math.Max(Math.Abs(a), Math.Abs(b));
        return Math.Abs(a - b) <= relativeTolerance * Math.Max(scale, 1.0e-30);
    }

    private static void RequireFinite(double value, string name)
    {
        if (!double.IsFinite(value))
        {
            throw new Exception($"Non-finite {name}: {value}");
        }
    }
}

class HollowCylinderFeatureRecord
{
    public string SchemaVersion { get; set; } = "";
    public string CaseId { get; set; } = "";
    public string SourceVdbPath { get; set; } = "";
    public double VoxelSizeMm { get; set; }
    public float VolumeMm3 { get; set; }
    public float BBoxMinXMm { get; set; }
    public float BBoxMinYMm { get; set; }
    public float BBoxMinZMm { get; set; }
    public float BBoxMaxXMm { get; set; }
    public float BBoxMaxYMm { get; set; }
    public float BBoxMaxZMm { get; set; }
}

class HollowCylinderPhysicalRecord
{
    public string SchemaVersion { get; set; } = "";
    public string CaseId { get; set; } = "";
    public string SourceFeaturePath { get; set; } = "";
    public string PhysicalCase { get; set; } = "";
    public string GeometryInterpretation { get; set; } = "";
    public string FluidName { get; set; } = "";
    public double DensityKgPerM3 { get; set; }
    public double DynamicViscosityPaS { get; set; }
    public double VolumetricFlowRateM3PerS { get; set; }
    public string[] Assumptions { get; set; } = Array.Empty<string>();
    public double LengthMm { get; set; }
    public double OuterRadiusMm { get; set; }
    public double InnerRadiusMm { get; set; }
    public double CrossSectionAreaMm2 { get; set; }
    public double RadiusRatio { get; set; }
    public double MeanVelocityMPerS { get; set; }
    public double ReynoldsNumber { get; set; }
    public double PressureGradientPaPerM { get; set; }
    public double PressureDropPa { get; set; }
    public double MaxVelocityMPerS { get; set; }
    public double MaxVelocityRadiusMm { get; set; }
    public double SampledMaxVelocityMPerS { get; set; }
    public double SampledMaxVelocityRadiusMm { get; set; }
    public double InnerWallShearStressPa { get; set; }
    public double OuterWallShearStressPa { get; set; }
    public string ShearStressSignConvention { get; set; } = "";
    public double VoxelSizeMm { get; set; }
    public VelocityProfileSample[] VelocityProfileSamples { get; set; } = Array.Empty<VelocityProfileSample>();
}

class VelocityProfileSample
{
    public int SampleIndex { get; set; }
    public double RadiusMm { get; set; }
    public double RadiusNormalized { get; set; }
    public double AxialVelocityMPerS { get; set; }
}
