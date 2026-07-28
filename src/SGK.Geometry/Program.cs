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

        Library.oViewer().Add(loadedVoxels);

        Console.WriteLine("Hollow cylinder generated: OD 20mm, ID 16mm, length 50mm");
        Console.WriteLine("Serialization round-trip validated successfully");
        Console.WriteLine("Feature extraction record written successfully");
        Console.WriteLine("Feature extraction record read successfully");
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
