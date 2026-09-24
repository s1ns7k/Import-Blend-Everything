# Import Blend Everything

A Blender add-on that imports **everything** from another `.blend` file into your **current scene** in one click.

Pick a `.blend`, and the add-on brings in all its objects, collections and data (meshes, armatures, materials, constraints, modifiers, animations, and more) exactly as they were, without touching your scene settings (render engine, world, camera, frame range, etc.).

It is handy for moving a character, prop or whole set from one project to another without opening the *Append* dialog and hunting for datablocks one by one.

---

## Features

- One-step import: **File → Import → Blend (Everything into Current Scene)**
- Keeps the collection hierarchy from the source file
- Keeps everything stored on the objects: **constraints** (object and bone), **modifiers**, **drivers**, **shape keys**, **vertex groups**, **custom properties**, parenting
- Keeps all object data: meshes, curves, armatures, lights, cameras, materials, node groups, textures, actions, and so on
- **Fast by default:** only data that the source scene actually uses is loaded, not the whole file
- **Constraint targets are kept:** objects that constraints, modifiers, parents or drivers point to (IK targets, controllers, etc.) are preserved even if they were not on the source scene
- **Does not touch your scene settings:** your render engine, world, camera, units, frame range and view layers stay as they are
- Fixes broken relative texture paths automatically
- Status bar summary with the number of imported objects, materials and **constraints**
- Undo-friendly (`Ctrl+Z` reverts the whole import)

## Requirements

- Blender **5.0** or newer

## Installation

1. Download [`import_blend_everything.py`](import_blend_everything.py) from this repository.
2. In Blender, open **Edit → Preferences → Add-ons**.
3. Click the dropdown arrow in the top-right corner and choose **Install from Disk...**
4. Select `import_blend_everything.py`.
5. Make sure the checkbox next to **Import Blend Everything** is enabled.

> **Updating:** install the new file the same way, then disable and re-enable the add-on (or restart Blender).
>
> **Quick test without installing:** open the file in Blender's **Text Editor** and click **Run Script**. The add-on stays active until you restart Blender.

## Usage

1. Open the scene you want to import **into**.
2. Go to **File → Import → Blend (Everything into Current Scene)**.
3. Browse to the `.blend` file you want to bring in.
4. (Optional) Adjust the options in the panel on the right side of the file browser.
5. Click **Import .blend (Everything)**.

Everything that was on the source file's scene now appears in your current scene. A message in the status bar tells you how many objects, collections, materials and constraints were added.

## Options

| Option | Default | Description |
|---|---|---|
| **Wrap in Collection** | Off | Puts everything imported into a new collection named after the file, so it is easy to select, move or delete as a group. |
| **Link Referenced Objects** | On | Objects that constraints, modifiers, parents or drivers point to, but that were not on the source scene (IK targets, controllers, helper empties...), are added to a hidden `<file name> Helpers` collection. This keeps constraints working and stops those objects from being lost when you save. Unhide the collection in the Outliner if you need to use them. |
| **Import Unused Data** | Off | Also imports data that nothing on the source scene uses (spare materials, meshes, node groups, etc.). Slower and heavier, so leave it off unless you need it. |
| **Fake User for Unused Data** | On | Imported data that ended up unused gets a Fake User so it is not purged when you save. Mostly relevant together with **Import Unused Data**. |

## What gets imported

By default, everything the source scene uses:

- Objects and collections on the scene, with their meshes, curves, surfaces, metaballs, volumes, point clouds, hair curves and lattices
- Armatures and poses (bone constraints included)
- Modifiers, object constraints, drivers, shape keys, vertex groups, custom properties
- Materials, node groups, textures, images, fonts, sounds, movie clips
- Actions (animation data), lights, light probes, cameras, speakers
- Objects that the above depend on (constraint targets, parents, modifier objects, driver targets)

With **Import Unused Data** enabled, the rest of the file is imported as well and shows up in **Outliner → Blender File**.

## What is NOT imported

- **Scene settings:** render engine and render settings, world, scene camera, frame range, units, color management, view layers, compositing, scene physics
- Workspaces, screens, window managers and brushes (UI and tool data)
- Linked library references

The world, line styles and compositor node trees that belonged to the source scene are discarded if nothing else uses them.

## Performance

Importing is a single operation that does not evaluate or redraw anything in between, and by default it loads only what the source scene needs. If the viewport still feels slow right after importing a heavy character, the cause is usually Blender evaluating the imported objects' modifiers (for example Subdivision Surface) rather than the import itself. Turning off those modifiers in the viewport, or importing into a wrapper collection you can hide, helps.

## Notes and limitations

- **Name conflicts:** if your file already has a datablock with the same name, Blender adds a numeric suffix (for example `Material.001`). Nothing in your existing scene is overwritten or merged.
- **Texture paths:** if an image, sound or font uses a relative path that no longer resolves, the add-on rewrites it as an absolute path pointing to the source file's folder (when the file exists there).
- **Multiple scenes in the source file:** everything from all of them is merged into your current scene.
- **Same file:** you cannot import the currently open file into itself.

## Troubleshooting

**The menu entry is missing**
Check that the add-on is enabled in **Edit → Preferences → Add-ons**.

**A constraint is red or has no target**
Check the status bar message after import: it shows how many constraints came over. Then look in the hidden `<file name> Helpers` collection for the missing target object. If the target object does not exist in the source file at all, there is nothing to import.

**Nothing appears in the scene**
Check the **Outliner → Blender File** view. If the source file's scene was empty, nothing is linked to your scene.

**Something did not import correctly**
Open Blender's system console and run the import again, then look for error messages:

- Windows: **Window → Toggle System Console**
- Linux / macOS: start Blender from a terminal

Please include the console output when reporting an issue.

## Uninstall

Go to **Edit → Preferences → Add-ons**, find **Import Blend Everything**, expand it and click **Remove**.

## License

Add your license of choice here (for example MIT).
