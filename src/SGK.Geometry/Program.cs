// See https://aka.ms/new-console-template for more information

using PicoGK;
using System.Numerics;
using System.IO;
using System.Text.Json;

try
{
    Library.Go(0.3f, HollowCylinderTask.Run);
}
catch (Exception e)
{
    Console.WriteLine(e.ToString());
}

class HollowCylinderTask
{
    public static void Run()
    {
        Lattice latOutside = new();
        latOutside.AddBeam(
            new Vector3(0, 0, 0),
            new Vector3(0, 0, 50),
            10, 10,
            false);

        Voxels voxOutside = new(latOutside);

        Lattice latInside = new();
        latInside.AddBeam(
            new Vector3(0, 0, 0),
            new Vector3(0, 0, 50),
            8, 8,
            false);

        Voxels voxInside = new(latInside);

        voxOutside.BoolSubtract(voxInside);

        string outputDir = Path.Combine(Directory.GetCurrentDirectory(), "..", "..", "output");
        outputDir = Path.GetFullPath(outputDir);
        Directory.CreateDirectory(outputDir);

        string vdbFileName = "hollow-cylinder.vdb";
        string vdbRepoRelativePath = Path.Combine("output", vdbFileName);
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
            SchemaVersion = "sgk-mini.feature-record.v1",
            CaseId = "hollow-cylinder",
            SourceVdbPath = vdbRepoRelativePath,
            VolumeMm3 = loadedVolume,
            BBoxMinXMm = loadedBox.vecMin.X,
            BBoxMinYMm = loadedBox.vecMin.Y,
            BBoxMinZMm = loadedBox.vecMin.Z,
            BBoxMaxXMm = loadedBox.vecMax.X,
            BBoxMaxYMm = loadedBox.vecMax.Y,
            BBoxMaxZMm = loadedBox.vecMax.Z
        };

        string featurePath = Path.Combine(outputDir, "hollow-cylinder.features.json");

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
            ComputeConcentricAnnulusLaminarFlowPhysicalRecord(reloadedFeatureRecord);

        string physicalPath = Path.Combine(outputDir, "hollow-cylinder.physical-case.json");

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

        Console.WriteLine("Hollow cylinder generated: OD 20mm, ID 16mm, length 50mm");
        Console.WriteLine("Serialization round-trip validated successfully");
        Console.WriteLine("Feature extraction record written successfully");
        Console.WriteLine("Feature extraction record read successfully");
        Console.WriteLine("Analytic annulus-flow benchmark written successfully");
        Console.WriteLine("Analytic annulus-flow benchmark read successfully");
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

        if (record.SchemaVersion != "sgk-mini.feature-record.v1")
        {
            throw new Exception($"Unexpected schema version: {record.SchemaVersion}");
        }

        if (record.CaseId != "hollow-cylinder")
        {
            throw new Exception($"Unexpected case id: {record.CaseId}");
        }

        if (record.VolumeMm3 <= 0)
        {
            throw new Exception($"Invalid volume: {record.VolumeMm3}");
        }

        if (record.BBoxMaxZMm <= record.BBoxMinZMm)
        {
            throw new Exception(
                $"Invalid bbox Z range: min={record.BBoxMinZMm}, max={record.BBoxMaxZMm}");
        }

        return record;
    }

    private static HollowCylinderPhysicalRecord ComputeConcentricAnnulusLaminarFlowPhysicalRecord(
        HollowCylinderFeatureRecord featureRecord)
    {
        const double rhoKgPerM3 = 1000.0;
        const double muPaS = 1.0e-3;
        const double volumetricFlowRateM3PerS = 1.0e-6;
        const int velocityProfileSampleCount = 17;

        double lengthMm = featureRecord.BBoxMaxZMm - featureRecord.BBoxMinZMm;
        double outerRadiusMm = Math.Max(
            Math.Abs(featureRecord.BBoxMaxXMm),
            Math.Abs(featureRecord.BBoxMaxYMm));

        double areaMm2 = featureRecord.VolumeMm3 / lengthMm;
        double innerRadiusMm = Math.Sqrt(
            outerRadiusMm * outerRadiusMm - areaMm2 / Math.PI);

        double kappa = innerRadiusMm / outerRadiusMm;
        double areaM2 = areaMm2 * 1.0e-6;
        double lengthM = lengthMm * 1.0e-3;
        double outerRadiusM = outerRadiusMm * 1.0e-3;
        double innerRadiusM = innerRadiusMm * 1.0e-3;
        double hydraulicDiameterM = 2.0 * (outerRadiusMm - innerRadiusMm) * 1.0e-3;

        double meanVelocityMPerS = volumetricFlowRateM3PerS / areaM2;
        double reynolds = rhoKgPerM3 * meanVelocityMPerS * hydraulicDiameterM / muPaS;

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

        double maxVelocityMPerS = double.MinValue;
        double maxVelocityRadiusMm = 0.0;

        foreach (VelocityProfileSample sample in velocityProfileSamples)
        {
            if (sample.AxialVelocityMPerS > maxVelocityMPerS)
            {
                maxVelocityMPerS = sample.AxialVelocityMPerS;
                maxVelocityRadiusMm = sample.RadiusMm;
            }
        }

        double innerWallShearStressPa =
            ComputeShearStressPa(innerRadiusM, dpDz, pressureGradientPaPerM, innerRadiusM, outerRadiusM);

        double outerWallShearStressPa =
            ComputeShearStressPa(outerRadiusM, dpDz, pressureGradientPaPerM, innerRadiusM, outerRadiusM);

        return new HollowCylinderPhysicalRecord
        {
            SchemaVersion = "sgk-mini.physical-record.v1",
            CaseId = featureRecord.CaseId,
            SourceFeaturePath = Path.Combine("output", "hollow-cylinder.features.json"),
            PhysicalCase = "steady-fully-developed-laminar-axial-flow-in-concentric-annulus",
            GeometryInterpretation =
                "The hollow-cylinder voxel geometry is treated as the solid wall of a concentric annular flow passage.",
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
            InnerWallShearStressPa = innerWallShearStressPa,
            OuterWallShearStressPa = outerWallShearStressPa,
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
        double pressureGradientPaPerM,
        double innerRadiusM,
        double outerRadiusM)
    {
        double duDr = ComputeVelocityDerivativeMPerSPerM(
            radiusM,
            innerRadiusM,
            outerRadiusM,
            dpDz,
            1.0e-3);

        return 1.0e-3 * duDr;
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

        if (record.SchemaVersion != "sgk-mini.physical-record.v1")
        {
            throw new Exception($"Unexpected physical schema version: {record.SchemaVersion}");
        }

        if (record.CaseId != "hollow-cylinder")
        {
            throw new Exception($"Unexpected physical case id: {record.CaseId}");
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

        if (record.VelocityProfileSamples is null || record.VelocityProfileSamples.Length != 17)
        {
            throw new Exception("Velocity profile sample array is missing or has unexpected length");
        }

        if (Math.Abs(record.VelocityProfileSamples[0].AxialVelocityMPerS) > 1.0e-9)
        {
            throw new Exception("Inner wall velocity sample is not approximately zero");
        }

        if (Math.Abs(record.VelocityProfileSamples[^1].AxialVelocityMPerS) > 1.0e-9)
        {
            throw new Exception("Outer wall velocity sample is not approximately zero");
        }

        return record;
    }
}

class HollowCylinderFeatureRecord
{
    public string SchemaVersion { get; set; } = "";
    public string CaseId { get; set; } = "";
    public string SourceVdbPath { get; set; } = "";
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
    public double InnerWallShearStressPa { get; set; }
    public double OuterWallShearStressPa { get; set; }
    public VelocityProfileSample[] VelocityProfileSamples { get; set; } = Array.Empty<VelocityProfileSample>();
}

class VelocityProfileSample
{
    public int SampleIndex { get; set; }
    public double RadiusMm { get; set; }
    public double RadiusNormalized { get; set; }
    public double AxialVelocityMPerS { get; set; }
}
