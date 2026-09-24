bl_info = {
    "name": "Import Blend Everything",
    "author": "s1ns7k",
    "version": (1, 2, 0),
    "blender": (5, 0, 0),
    "location": "File > Import > Blend (Everything into Current Scene)",
    "description": "Adds everything from another .blend (objects, constraints, modifiers, data) "
                   "to the current scene without touching scene settings",
    "category": "Import-Export",
}

import os

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

# Datablock types that are never imported
SKIP_TYPES = {"screens", "window_managers", "workspaces", "libraries", "brushes"}

# Datablock types that reference files on disk (relative paths get fixed)
PATH_TYPES = {"images", "sounds", "movieclips", "fonts", "cache_files", "volumes"}

# Leftovers of the source scene: removed if nothing uses them
JUNK_TYPES = {"worlds", "linestyles"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def id_collections():
    """Yield (name, collection) for every ID collection in bpy.data we care about."""
    for attr in dir(bpy.data):
        if attr.startswith("_") or attr in SKIP_TYPES:
            continue
        try:
            coll = getattr(bpy.data, attr)
        except Exception:
            continue
        if isinstance(coll, bpy.types.bpy_prop_collection):
            yield attr, coll


def snapshot():
    """Remember which datablocks exist right now (by pointer)."""
    snap = {}
    for attr, coll in id_collections():
        try:
            snap[attr] = {i.as_pointer() for i in coll}
        except Exception:
            pass
    return snap


def new_ids_since(snap):
    """Return [(type, id)] for every datablock that appeared after the snapshot."""
    out = []
    for attr, coll in id_collections():
        seen = snap.get(attr)
        if seen is None:
            continue
        try:
            out.extend((attr, i) for i in coll if i.as_pointer() not in seen)
        except Exception:
            pass
    return out


def find_layer_collection(root, name):
    if root.name == name:
        return root
    for ch in root.children:
        found = find_layer_collection(ch, name)
        if found:
            return found
    return None


def _constraint_objects(con):
    for name in ("target", "pole_target"):
        yield getattr(con, name, None)
    for t in getattr(con, "targets", ()):
        yield getattr(t, "target", None)


def referenced_objects(ob):
    """Objects that `ob` depends on: parent, constraint targets, modifier objects, driver targets."""
    found = []

    def add(x):
        if isinstance(x, bpy.types.Object) and x != ob:
            found.append(x)

    add(ob.parent)
    for con in ob.constraints:
        for x in _constraint_objects(con):
            add(x)
    if ob.pose:
        for pb in ob.pose.bones:
            for con in pb.constraints:
                for x in _constraint_objects(con):
                    add(x)
    for mod in ob.modifiers:
        for prop in mod.bl_rna.properties:
            if prop.type == 'POINTER':
                try:
                    add(getattr(mod, prop.identifier))
                except Exception:
                    pass
    ad = ob.animation_data
    if ad:
        for fc in ad.drivers:
            for var in fc.driver.variables:
                for t in var.targets:
                    add(t.id)
    return found


def link_dependencies(scene, parent_collection, imported_objects, name):
    """Link imported objects that other objects depend on (IK targets, controllers, armatures,
    modifier objects...) but which were not on the source scene, into a 'Helpers' collection.
    Without this they would have no users and could be lost on save."""
    imported = set(imported_objects)
    in_scene = set(scene.objects)
    queue = [ob for ob in imported if ob in in_scene]
    seen = set(queue)
    missing = []
    while queue:
        ob = queue.pop()
        for ref in referenced_objects(ob):
            if ref in seen:
                continue
            seen.add(ref)
            if ref in imported and ref not in in_scene:
                missing.append(ref)
                queue.append(ref)
    if not missing:
        return None
    helpers = bpy.data.collections.new(f"{name} Helpers")
    parent_collection.children.link(helpers)
    for ob in missing:
        try:
            helpers.objects.link(ob)
        except RuntimeError:
            pass
    return helpers


def count_constraints(objects):
    total = 0
    for ob in objects:
        try:
            total += len(ob.constraints)
            if ob.pose:
                for pb in ob.pose.bones:
                    total += len(pb.constraints)
        except Exception:
            pass
    return total


def fix_paths(new_ids, src_dir):
    """If a relative path is broken, rewrite it as an absolute path based on the source .blend."""
    for attr, idb in new_ids:
        if attr not in PATH_TYPES:
            continue
        try:
            fp = idb.filepath
            if not fp or not fp.startswith("//") or getattr(idb, "packed_file", None):
                continue
            if os.path.exists(bpy.path.abspath(fp)):
                continue
            cand = os.path.normpath(os.path.join(src_dir, fp[2:]))
            if os.path.exists(cand):
                idb.filepath = cand
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------

class IMPORT_OT_blend_everything(Operator, ImportHelper):
    """Add everything from another .blend file to the current scene"""
    bl_idname = "import_scene.blend_everything"
    bl_label = "Import .blend (Everything)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".blend"
    filter_glob: StringProperty(default="*.blend", options={'HIDDEN'})

    wrap_in_collection: BoolProperty(
        name="Wrap in Collection",
        description="Put everything imported into a separate collection named after the file",
        default=False,
    )
    link_dependencies: BoolProperty(
        name="Link Referenced Objects",
        description="Objects that constraints, modifiers, parents or drivers point to, but that "
                    "were not on the source scene (IK targets, controllers...), are added to a "
                    "hidden 'Helpers' collection so they are kept and saved",
        default=True,
    )
    import_unused: BoolProperty(
        name="Import Unused Data",
        description="Also import data that nothing on the source scene uses. Slower and heavier. "
                    "Off = only what the scene actually uses (fast)",
        default=False,
    )
    fake_user_unused: BoolProperty(
        name="Fake User for Unused Data",
        description="Imported data that ended up unused gets a Fake User so it is not lost "
                    "when saving (mostly relevant with Import Unused Data)",
        default=True,
    )

    def execute(self, context):
        path = bpy.path.abspath(self.filepath)
        if not os.path.isfile(path):
            self.report({'ERROR'}, "File not found")
            return {'CANCELLED'}
        if bpy.data.filepath and os.path.samefile(path, bpy.data.filepath):
            self.report({'ERROR'}, "Cannot import the currently open file into itself")
            return {'CANCELLED'}

        scene = context.scene
        src_dir = os.path.dirname(path)
        name = os.path.splitext(os.path.basename(path))[0]
        snap = snapshot()

        # 1. Load datablocks.
        #    Fast mode: load only the scene(s). Blender pulls in everything they use
        #    (collections, objects, meshes, armatures, materials, actions, constraint targets...).
        #    Constraints, modifiers, shape keys, vertex groups, drivers and custom properties
        #    live inside objects/object data, so they come along automatically.
        try:
            with bpy.data.libraries.load(path, link=False) as (data_from, data_to):
                if self.import_unused:
                    for attr in dir(data_from):
                        if attr.startswith("_") or attr in SKIP_TYPES:
                            continue
                        try:
                            names = list(getattr(data_from, attr))
                            if names and isinstance(names[0], str):
                                setattr(data_to, attr, names)
                        except Exception:
                            pass
                else:
                    data_to.scenes = list(data_from.scenes)
        except Exception as e:
            self.report({'ERROR'}, f"Could not open .blend: {e}")
            return {'CANCELLED'}

        src_scenes = [s for s in data_to.scenes if s is not None]
        new_ids = new_ids_since(snap)
        new_objects = [i for a, i in new_ids if a == "objects"]

        # 2. Decide where to put things
        target = scene.collection
        if self.wrap_in_collection:
            wrapper = bpy.data.collections.new(name)
            scene.collection.children.link(wrapper)
            target = wrapper

        # 3. Link everything that was on the source scene(s) into the current scene
        for s in src_scenes:
            for col in list(s.collection.children):
                try:
                    target.children.link(col)
                except RuntimeError:
                    pass
            for ob in list(s.collection.objects):
                try:
                    target.objects.link(ob)
                except RuntimeError:
                    pass

        # 4. Keep objects that others depend on (constraint targets etc.), hidden
        helpers = None
        if self.link_dependencies:
            try:
                helpers = link_dependencies(scene, target, new_objects, name)
                if helpers:
                    lc = find_layer_collection(context.view_layer.layer_collection, helpers.name)
                    if lc:
                        lc.hide_viewport = True
            except Exception as e:
                print(f"[Import Blend Everything] dependency linking failed: {e}")

        # 5. Temporary source scenes are not needed; current scene settings stay untouched
        for s in src_scenes:
            try:
                bpy.data.scenes.remove(s, do_unlink=True)
            except Exception:
                pass

        # 6. Fix texture paths, clean up scene leftovers, apply Fake User
        fix_paths(new_ids, src_dir)
        for attr, idb in new_ids:
            if attr == "scenes":
                continue
            try:
                if idb.users != 0:
                    continue
                is_junk = attr in JUNK_TYPES or getattr(idb, "bl_idname", "") == "CompositorNodeTree"
                if is_junk:
                    getattr(bpy.data, attr).remove(idb)
                elif self.fake_user_unused:
                    idb.use_fake_user = True
            except Exception:
                pass

        counts = {}
        for attr, _ in new_ids:
            counts[attr] = counts.get(attr, 0) + 1
        n_con = count_constraints(new_objects)
        msg = (
            f"Imported: {counts.get('objects', 0)} objects, "
            f"{counts.get('collections', 0)} collections, "
            f"{counts.get('materials', 0)} materials, "
            f"{n_con} constraints"
        )
        if helpers:
            msg += f" (helper objects in hidden '{helpers.name}')"
        print(f"[Import Blend Everything] {msg}")
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(
        IMPORT_OT_blend_everything.bl_idname,
        text="Blend (Everything into Current Scene)",
        icon='APPEND_BLEND',
    )


classes = (IMPORT_OT_blend_everything,)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(menu_func)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
