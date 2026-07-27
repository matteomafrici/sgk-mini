// See https://aka.ms/new-console-template for more information
// Console.WriteLine("Hello, World!");

using PicoGK;
using System.Numerics;
using System.IO;

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

        string vdbPath = Path.Combine("/home/matteo-mafrici/work/sgk-mini/output", "hollow-cylinder.vdb");
        Directory.CreateDirectory("/home/matteo-mafrici/work/sgk-mini/output");

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

        Library.oViewer().Add(loadedVoxels);

        Console.WriteLine("Hollow cylinder generated: OD 20mm, ID 16mm, length 50mm");
        Console.WriteLine("Serialization round-trip validated successfully");
    }
}
