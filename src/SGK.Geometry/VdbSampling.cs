using System.Globalization;
using System.Numerics;
using PicoGK;

static class VdbSampling
{
    public static int Run(string[] args)
    {
        if (args.Length != 6)
            throw new ArgumentException(
                "Usage: --sample-vdb <vdb> <voxel-mm> <queries-mm.tsv> <sdf-mm.tsv> <surface-mm.tsv>");

        float voxelSize = float.Parse(args[2], CultureInfo.InvariantCulture);
        if (!float.IsFinite(voxelSize) || voxelSize <= 0)
            throw new ArgumentException("Voxel size must be positive and finite");

        Exception? failure = null;
        Library.Go(voxelSize, () =>
        {
            try
            {
                Export(args[1], args[3], args[4], args[5], voxelSize);
            }
            catch (Exception error)
            {
                failure = error;
            }
        }, bEndAppWithTask: true);
        if (failure is not null)
            throw new InvalidOperationException("VDB sampling failed", failure);
        return 0;
    }

    private static void Export(string vdbPath, string queriesPath, string sdfPath,
        string surfacePath, float voxelSize)
    {
        Voxels solid = Voxels.voxFromVdbFile(vdbPath);
        ScalarField distance = new(solid);
        using (StreamWriter output = File.CreateText(sdfPath))
        {
            foreach (string line in File.ReadLines(queriesPath))
            {
                string[] parts = line.Split('\t');
                if (parts.Length != 3)
                    throw new FormatException("Each query must contain three tab-separated coordinates");
                Vector3 point = new(
                    float.Parse(parts[0], CultureInfo.InvariantCulture),
                    float.Parse(parts[1], CultureInfo.InvariantCulture),
                    float.Parse(parts[2], CultureInfo.InvariantCulture));
                if (!float.IsFinite(point.X) || !float.IsFinite(point.Y) || !float.IsFinite(point.Z))
                    throw new FormatException("Query coordinates must be finite");

                // The native field returns millimetres, including the signed
                // background value when the voxel is outside the active band.
                // The converter checks the units on neighbouring grid nodes.
                distance.bGetValue(point, out float value);
                float signedDistance = Math.Clamp(value, -voxelSize, voxelSize);
                output.WriteLine(signedDistance.ToString("R", CultureInfo.InvariantCulture));
            }
        }

        Mesh surface = new(solid);
        using StreamWriter vertices = File.CreateText(surfacePath);
        int count = surface.nVertexCount();
        for (int i = 0; i < count; i++)
        {
            Vector3 point = surface.vecVertexAt(i);
            vertices.WriteLine(FormattableString.Invariant($"{point.X:R}\t{point.Y:R}\t{point.Z:R}"));
        }
    }
}
