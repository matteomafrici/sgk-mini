// See https://aka.ms/new-console-template for more information
// Console.WriteLine("Hello, World!");

using PicoGK;
using System.Numerics;

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

        Library.oViewer().Add(voxOutside);

        Console.WriteLine("Hollow cylinder generated: OD 20mm, ID 16mm, length 50mm");
    }
}
