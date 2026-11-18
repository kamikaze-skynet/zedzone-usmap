# US Map (ZED ZONE mod)

Play ZED ZONE on the United States. The lower 48 states are built from real elevation, coastlines, land cover, cities and interstates, scaled to a 128 x 80 chunk map.

## Requires

- ZED ZONE (Windows, Steam)
- [ZED ZONE Code Mod Loader](https://steamcommunity.com/sharedfiles/filedetails/?id=3834614258) - run its install.cmd once, then start the game through Steam.

## Use
Create a new sandbox map with **USA** in its name. The mod remembers US maps by id in `BepInEx\config\USMap.maps.txt`, so renaming one later is fine. Other maps are not touched.

## What it changes
- **Chunk grid:** every chunk gets a type from the real map (towns for cities, farms for cropland, the spawn in central Kansas, bases, plants, airports, ports, labs). Difficulty grows with distance from the spawn.
- **Water:** `MapController.CalculateWaterFloatByWorldPosition` returns real water (sea, lakes, rivers).
- **Ocean:** `MapController.IsInOcean` returns the real open sea.
- **Hills:** the terrain noise (`ShapeGenerator.CalculateTerrainPoint` on the terrain generator) follows real elevation.
- **Roads:** the game's own links between towns, plus highways along the interstates.
- **Size:** `MapController.mapSizeX/Y` are 128 x 80 while a US map is loaded.

## Settings
`BepInEx\config\girthy_mods.zedzone.usmap.cfg`: map name trigger, interstates on/off, terrain height mapping, noise blend.

## Build
```
dotnet build src\USMap.csproj -c Release -p:GameDir="D:\SteamLibrary\steamapps\common\ZED ZONE"
```
The mod folder needs `USMap.dll`, `usmap.bin` (from `data\`) and `mod.json`.

## Rebaking the map data
`tools\` has the Python scripts that make `data\usmap.bin` (bake.py, chunks.py, export.py; preview.py draws a preview image). They need numpy, pillow, pyproj, pyshp and netCDF4.
