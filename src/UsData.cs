using System;
using System.IO;
using System.IO.Compression;
using System.Collections.Generic;
using System.Reflection;

namespace USMap
{
    // Baked real-world data (see tools\): chunk grid, water/ocean fields and elevation.
    // Raster pixel = 4 game tiles. Chunk = 96 tiles = 24 pixels. Row 0 is the north edge.
    internal static class UsData
    {
        internal const int Chunk = 96, PxPerTile = 4;
        internal static int CW, CH, W, H, EW, EH, BornX, BornY;
        internal static byte[] Types, Veg, Water, Ocean;
        internal static short[] Elev;
        internal static List<(int ax, int ay, int bx, int by)> Edges = new();

        internal static bool Load()
        {
            try
            {
                string dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                string path = Path.Combine(dir, "usmap.bin");
                if (!File.Exists(path)) { BLog.Error("Missing " + path); return false; }
                using var fs = File.OpenRead(path);
                using var gz = new GZipStream(fs, CompressionMode.Decompress);
                using var ms = new MemoryStream(); gz.CopyTo(ms); ms.Position = 0;
                using var br = new BinaryReader(ms);
                if (new string(br.ReadChars(4)) != "USMP") throw new Exception("bad header");
                int ver = br.ReadInt32(); CW = br.ReadInt32(); CH = br.ReadInt32(); W = br.ReadInt32(); H = br.ReadInt32();
                int ne = br.ReadInt32(); BornX = br.ReadInt32(); BornY = br.ReadInt32();
                Types = br.ReadBytes(CW * CH); Veg = br.ReadBytes(CW * CH);
                for (int i = 0; i < ne; i++) Edges.Add((br.ReadInt16(), br.ReadInt16(), br.ReadInt16(), br.ReadInt16()));
                Water = br.ReadBytes(W * H); Ocean = br.ReadBytes(W * H);
                EW = br.ReadInt32(); EH = br.ReadInt32();
                Elev = new short[EW * EH];
                for (int i = 0; i < Elev.Length; i++) Elev[i] = br.ReadInt16();
                BLog.Info($"usmap.bin v{ver}: {CW}x{CH} chunks, raster {W}x{H}, {ne} interstate links, spawn chunk ({BornX},{BornY}).");
                return true;
            }
            catch (Exception e) { BLog.Error("Reading usmap.bin failed", e); return false; }
        }

        // grid column/row -> game chunk coordinate (game y points north)
        internal static int ChunkX(int col) => col - CW / 2;
        internal static int ChunkY(int row) => CH / 2 - 1 - row;
        internal static int Col(int chunkX) => chunkX + CW / 2;
        internal static int Row(int chunkY) => CH / 2 - 1 - chunkY;

        // world position -> raster pixel (float). Tile 0 is the west edge of the west-most chunk.
        static void ToPx(float wx, float wy, out float px, out float py)
        {
            float gx = wx + CW / 2 * Chunk + Chunk / 2;
            float gy = wy + CH / 2 * Chunk + Chunk / 2;
            px = gx / PxPerTile - 0.5f;
            py = (H * PxPerTile - gy) / PxPerTile - 0.5f;
        }

        static float Bilinear(byte[] a, int w, int h, float px, float py, float outside)
        {
            if (px < -1 || py < -1 || px > w || py > h) return outside;
            int x0 = (int)MathF.Floor(px), y0 = (int)MathF.Floor(py);
            float fx = px - x0, fy = py - y0;
            float S(int x, int y) => (x < 0 || y < 0 || x >= w || y >= h) ? outside : a[y * w + x];
            return (S(x0, y0) * (1 - fx) + S(x0 + 1, y0) * fx) * (1 - fy) + (S(x0, y0 + 1) * (1 - fx) + S(x0 + 1, y0 + 1) * fx) * fy;
        }

        // 0..255, 255 = water
        internal static float WaterAt(float wx, float wy) { ToPx(wx, wy, out var px, out var py); return Bilinear(Water, W, H, px, py, 255); }
        internal static float OceanAt(float wx, float wy) { ToPx(wx, wy, out var px, out var py); return Bilinear(Ocean, W, H, px, py, 255); }

        // metres above sea level
        internal static float ElevAt(float wx, float wy)
        {
            ToPx(wx, wy, out var px, out var py);
            px = (px + 0.5f) * EW / W - 0.5f; py = (py + 0.5f) * EH / H - 0.5f;
            int x0 = (int)MathF.Floor(px), y0 = (int)MathF.Floor(py);
            float fx = px - x0, fy = py - y0;
            float S(int x, int y) { x = Math.Clamp(x, 0, EW - 1); y = Math.Clamp(y, 0, EH - 1); return Elev[y * EW + x]; }
            return (S(x0, y0) * (1 - fx) + S(x0 + 1, y0) * fx) * (1 - fy) + (S(x0, y0 + 1) * (1 - fx) + S(x0 + 1, y0 + 1) * fx) * fy;
        }
    }
}
