# Blender MOF Wrapper for UV Unwrapper - Copyright (C) 2025 Ultikynnys
#
# This file is part of Blender MOF Wrapper for UV Unwrapper .
#
# Blender MOF Wrapper for UV Unwrapper  is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3
#
# Blender MOF Wrapper for UV Unwrapper  is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Blender MOF Wrapper for UV Unwrapper.  If not, see <https://www.gnu.org/licenses/>.


import bpy, os, subprocess, zipfile, tempfile, shutil,re
import mathutils
from bpy.props import (
    StringProperty, IntProperty, FloatProperty, BoolProperty, PointerProperty
)
from bpy.types import Operator, Panel, AddonPreferences, PropertyGroup

bl_info = {
    "name": "Blender Wrapper for MOF UV Unwrapper",
    "blender": (4, 3, 0),
    "category": "UV",
    "version": (1, 0, 1),
    "author": "Ultikynnys",
    "description": "Wrapper that makes the MOF Unwrapper work in Blender",
    "tracker_url": "https://github.com/Ultikynnys/MinistryOfBlender",
}

# -------------------------------------------------------------------
# Property Group for operator parameters
# -------------------------------------------------------------------
class MOFProperties(PropertyGroup):
    resolution: IntProperty(name="Texture Resolution", default=1024)
    separate_hard_edges: BoolProperty(name="Separate Hard Edges", default=False)
    aspect: FloatProperty(name="Aspect", default=1.0)
    use_normals: BoolProperty(name="Use Normals", default=False)
    udims: IntProperty(name="UDIMs", default=1)
    overlap_identical: BoolProperty(name="Overlap Identical Parts", default=False)
    overlap_mirrored: BoolProperty(name="Overlap Mirrored Parts", default=False)
    world_scale: BoolProperty(name="World Scale UV", default=False)
    texture_density: IntProperty(name="Texture Density", default=1024)
    seam_x: FloatProperty(name="Seam X", default=0.0)
    seam_y: FloatProperty(name="Seam Y", default=0.0)
    seam_z: FloatProperty(name="Seam Z", default=0.0)
    suppress_validation: BoolProperty(name="Suppress Validation", default=False)
    quads: BoolProperty(name="Quads", default=True)
    vertex_weld: BoolProperty(name="Vertex Weld", default=True)
    flat_soft_surface: BoolProperty(name="Flat Soft Surface", default=True)
    use_flat_shading: BoolProperty(name="Flat Shading", default=True)
    cones: BoolProperty(name="Cones", default=True)
    cone_ratio: FloatProperty(name="Cone Ratio", default=0.5)
    grids: BoolProperty(name="Grids", default=True)
    strips: BoolProperty(name="Strips", default=True)
    patches: BoolProperty(name="Patches", default=True)
    planes: BoolProperty(name="Planes", default=True)
    flatness: FloatProperty(name="Flatness", default=0.9)
    merge: BoolProperty(name="Merge", default=True)
    merge_limit: FloatProperty(name="Merge Limit", default=0.0)
    pre_smooth: BoolProperty(name="Pre-Smooth", default=True)
    soft_unfold: BoolProperty(name="Soft Unfold", default=True)
    tubes: BoolProperty(name="Tubes", default=True)
    junctions: BoolProperty(name="Junctions", default=True)
    extra_debug: BoolProperty(name="Extra Debug Point", default=False)
    angle_based_flattening: BoolProperty(name="Angle-based Flattening", default=True)
    smooth: BoolProperty(name="Smooth", default=True)
    repair_smooth: BoolProperty(name="Repair Smooth", default=True)
    repair: BoolProperty(name="Repair", default=True)
    squares: BoolProperty(name="Squares", default=True)
    relax: BoolProperty(name="Relax", default=True)
    relax_iterations: IntProperty(name="Relax Iterations", default=50)
    expand: FloatProperty(name="Expand", default=0.25)
    cut: BoolProperty(name="Cut", default=True)
    stretch: BoolProperty(name="Stretch", default=True)
    match: BoolProperty(name="Match", default=True)
    packing: BoolProperty(name="Packing", default=True)
    rasterization: IntProperty(name="Rasterization Resolution", default=64)
    packing_iterations: IntProperty(name="Packing Iterations", default=4)
    scale_to_fit: FloatProperty(name="Scale To Fit", default=0.5)
    validate: BoolProperty(name="Validate", default=False)
    uv_margin: FloatProperty(name="UV Margin", default=0.1, min=0.0)

# -------------------------------------------------------------------
# Addon Preferences with version check operator
# -------------------------------------------------------------------
class MOFAddonPreferences(AddonPreferences):
    bl_idname = __package__

    executable_path: StringProperty(
        name="Executable Zip Path",
        subtype='FILE_PATH',
        default="",
        description="Path to the MinistryOfFlat zip file"
    )

    version: StringProperty(
        name="Version",
        default="unknown",
        description="Version of the MinistryOfFlat zip file"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "executable_path")
        # Provide a button to check/update the version from the zip file.
        row = layout.row(align=True)
        row.label(text=f"Zip Version: {self.version}")
        row.operator("wm.checkmofzipversion", text="Check Version")
        if not self.executable_path or not os.path.exists(bpy.path.abspath(self.executable_path)):
            layout.label(text="Please download the MinistryOfFlat zip file from the official site.", icon='INFO')

# -------------------------------------------------------------------
# Operator to check/extract version from the zip file
# -------------------------------------------------------------------
class CheckMOFZipVersionOperator(Operator):
    bl_idname = "wm.checkmofzipversion"
    bl_label = "Check MinistryOfFlat Zip Version"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        zip_path = bpy.path.abspath(prefs.executable_path)
        if not prefs.executable_path or not os.path.exists(zip_path):
            self.report({'ERROR'}, "Zip file not set or not found")
            prefs.version = "unknown"
            return {'CANCELLED'}
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                doc_filename = None
                # Search for documentation.txt in any folder, case-insensitive.
                for name in zf.namelist():
                    if os.path.basename(name).lower() == "documentation.txt":
                        doc_filename = name
                        break
                if doc_filename:
                    with zf.open(doc_filename) as doc_file:
                        content = doc_file.read().decode("utf-8")
                        # Look for a version string like "version: 3.7.2" or "version 3.7.2"
                        match = re.search(r"[Vv]ersion[:\s]+([\d]+\.[\d]+(?:\.[\d]+)?)", content)
                        if match:
                            prefs.version = match.group(1)
                        else:
                            prefs.version = "unknown"
                            self.report({'WARNING'}, "Version string not found in Documentation.txt")
                else:
                    prefs.version = "unknown"
                    self.report({'WARNING'}, "Documentation.txt not found in zip")
        except Exception as e:
            prefs.version = "unknown"
            self.report({'ERROR'}, f"Error checking zip version: {e}")
            return {'CANCELLED'}
        self.report({'INFO'}, f"Zip Version: {prefs.version}")
        return {'FINISHED'}

# -------------------------------------------------------------------
# Operator to perform auto UV unwrapping via external tool
# -------------------------------------------------------------------
class AutoUVOperator(Operator):
    bl_idname = "object.auto_uv_operator"
    bl_label = "Auto UV Unwrap"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Fail polling immediately on non-Windows systems.
        if os.name != "nt":
            return False

        prefs = context.preferences.addons[__package__].preferences
        zip_path = bpy.path.abspath(prefs.executable_path)
        if not prefs.executable_path or not os.path.exists(zip_path):
            return False
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                found = False
                # Since we only support Windows, only check for .exe files.
                for file in zf.namelist():
                    if file.lower().endswith("unwrapconsole3.exe"):
                        found = True
                        break
                    elif file.lower().endswith(".exe") and not file.endswith("/"):
                        found = True
                return found
        except Exception:
            return False

    def execute(self, context):
        original_obj = context.active_object
        if not original_obj:
            self.report({'ERROR'}, "No active object selected")
            return {"CANCELLED"}
        
        # Save original transformation.
        orig_matrix = original_obj.matrix_world.copy()
        
        # Remove any leftover temporary object.
        temp_name = original_obj.name + "_temp"
        if temp_name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[temp_name], do_unlink=True)
        
        # Duplicate the object.
        temp_obj = original_obj.copy()
        temp_obj.data = original_obj.data.copy()
        temp_obj.name = temp_name
        context.collection.objects.link(temp_obj)
        
        # Clear transformation on both objects.
        original_obj.matrix_world = mathutils.Matrix.Identity(4)
        temp_obj.matrix_world = mathutils.Matrix.Identity(4)
        
        # Adjust selection so that temp_obj is the only one selected.
        original_obj.select_set(False)
        for obj in context.selected_objects:
            if obj != temp_obj:
                obj.select_set(False)
        temp_obj.select_set(True)
        context.view_layer.objects.active = temp_obj
        
        # Apply shading based on user preference.
        if context.scene.mof_properties.use_flat_shading:
            bpy.ops.object.shade_flat()
        else:
            bpy.ops.object.shade_smooth()

        # Export the temporary object with correct OBJ settings (Z up, Y forward).
        temp_dir = bpy.app.tempdir
        name_safe = temp_obj.name.replace(" ", "_")
        in_path = os.path.join(temp_dir, f"{name_safe}.obj")
        out_path = os.path.join(temp_dir, f"{name_safe}_unwrapped.obj")
        try:
            bpy.ops.wm.obj_export(
                filepath=in_path,
                export_selected_objects=True,
                export_materials=False,
                forward_axis='Y',
                up_axis='Z'
            )
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            bpy.app.timers.register(lambda: remove_temp(temp_obj), first_interval=1.0)
            return {"CANCELLED"}
        bpy.app.timers.register(lambda: remove_temp(temp_obj), first_interval=1.0)

        # Run external tool.
        prefs = context.preferences.addons[__package__].preferences
        zip_path = bpy.path.abspath(prefs.executable_path)
        if not os.path.exists(zip_path):
            self.report({'ERROR'}, f"Zip file not found: {zip_path}")
            return {"CANCELLED"}
        try:
            extract_path = tempfile.mkdtemp(prefix="brender_mof_")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to extract zip file: {e}")
            return {"CANCELLED"}
        exe = None
        for root, dirs, files in os.walk(extract_path):
            for file in files:
                candidate = os.path.join(root, file)
                if os.name == "nt":
                    lower = file.lower()
                    if lower == "unwrapconsole3.exe":
                        exe = candidate
                        break
                    elif lower.endswith(".exe") and exe is None:
                        exe = candidate
                else:
                    if os.access(candidate, os.X_OK) and not os.path.isdir(candidate):
                        exe = candidate
                        break
            if exe:
                break
        if not exe:
            self.report({'ERROR'}, "No executable found in the zip file")
            try:
                shutil.rmtree(extract_path)
            except Exception:
                pass
            return {"CANCELLED"}
        p = context.scene.mof_properties
        cmd = [exe, in_path, out_path]
        params = [
            ("-RESOLUTION", str(p.resolution)),
            ("-SEPARATE", "TRUE" if p.separate_hard_edges else "FALSE"),
            ("-ASPECT", str(p.aspect)),
            ("-NORMALS", "TRUE" if p.use_normals else "FALSE"),
            ("-UDIMS", str(p.udims)),
            ("-OVERLAP", "TRUE" if p.overlap_identical else "FALSE"),
            ("-MIRROR", "TRUE" if p.overlap_mirrored else "FALSE"),
            ("-WORLDSCALE", "TRUE" if p.world_scale else "FALSE"),
            ("-DENSITY", str(p.texture_density)),
            ("-CENTER", str(p.seam_x), str(p.seam_y), str(p.seam_z)),
            ("-SUPRESS", "TRUE" if p.suppress_validation else "FALSE"),
            ("-QUAD", "TRUE" if p.quads else "FALSE"),
            ("-WELD", "TRUE" if p.vertex_weld else "FALSE"),
            ("-FLAT", "TRUE" if p.flat_soft_surface else "FALSE"),
            ("-CONE", "TRUE" if p.cones else "FALSE"),
            ("-CONERATIO", str(p.cone_ratio)),
            ("-GRIDS", "TRUE" if p.grids else "FALSE"),
            ("-STRIP", "TRUE" if p.strips else "FALSE"),
            ("-PATCH", "TRUE" if p.patches else "FALSE"),
            ("-PLANES", "TRUE" if p.planes else "FALSE"),
            ("-FLATT", str(p.flatness)),
            ("-MERGE", "TRUE" if p.merge else "FALSE"),
            ("-MERGELIMIT", str(p.merge_limit)),
            ("-PRESMOOTH", "TRUE" if p.pre_smooth else "FALSE"),
            ("-SOFTUNFOLD", "TRUE" if p.soft_unfold else "FALSE"),
            ("-TUBES", "TRUE" if p.tubes else "FALSE"),
            ("-JUNCTIONSDEBUG", "TRUE" if p.junctions else "FALSE"),
            ("-EXTRADEBUG", "TRUE" if p.extra_debug else "FALSE"),
            ("-ABF", "TRUE" if p.angle_based_flattening else "FALSE"),
            ("-SMOOTH", "TRUE" if p.smooth else "FALSE"),
            ("-REPAIRSMOOTH", "TRUE" if p.repair_smooth else "FALSE"),
            ("-REPAIR", "TRUE" if p.repair else "FALSE"),
            ("-SQUARE", "TRUE" if p.squares else "FALSE"),
            ("-RELAX", "TRUE" if p.relax else "FALSE"),
            ("-RELAX_ITERATIONS", str(p.relax_iterations)),
            ("-EXPAND", str(p.expand)),
            ("-CUTDEBUG", "TRUE" if p.cut else "FALSE"),
            ("-STRETCH", "TRUE" if p.stretch else "FALSE"),
            ("-MATCH", "TRUE" if p.match else "FALSE"),
            ("-PACKING", "TRUE" if p.packing else "FALSE"),
            ("-RASTERIZATION", str(p.rasterization)),
            ("-PACKING_ITERATIONS", str(p.packing_iterations)),
            ("-SCALETOFIT", str(p.scale_to_fit)),
            ("-VALIDATE", "TRUE" if p.validate else "FALSE"),
        ]
        for tup in params:
            cmd.extend(tup)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
                    self.report({'ERROR'}, f"External tool failed with exit code {result.returncode}")
                    return {"CANCELLED"}
        except Exception as e:
            self.report({'ERROR'}, f"Error running tool: {e}")
            return {"CANCELLED"}
        try:
            bpy.ops.wm.obj_import(filepath=out_path, forward_axis='Y', up_axis='Z')
        except Exception as e:
            self.report({'ERROR'}, f"Import failed: {e}")
            return {"CANCELLED"}
        
        # Post-process: Transfer additional data from the original object.
        imported_obj = context.active_object
        if imported_obj and imported_obj.type == 'MESH':
            imported_obj.name = original_obj.name + "_mof_Unwrapped"
            context.view_layer.objects.active = imported_obj
            # Add a Data Transfer modifier to recover custom normals via topology.
            dt_mod = imported_obj.modifiers.new(name="DataTransfer", type='DATA_TRANSFER')
            dt_mod.object = original_obj
            dt_mod.use_loop_data = True
            dt_mod.data_types_loops = {'CUSTOM_NORMAL'}
            dt_mod.loop_mapping = 'TOPOLOGY'
            bpy.ops.object.modifier_apply(modifier=dt_mod.name)
            bpy.ops.object.mode_set(mode='OBJECT')
        else:
            self.report({'WARNING'}, "No valid imported mesh found for UV processing")
        
        # Restore original object's transformation.
        original_obj.matrix_world = orig_matrix
        if imported_obj and imported_obj.type == 'MESH':
            imported_obj.matrix_world = orig_matrix
        
        # Clean up temporary files and extraction folder.
        for fp in (in_path, out_path):
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
        try:
            if os.path.exists(extract_path):
                shutil.rmtree(extract_path)
        except Exception:
            pass
        
        self.report({'INFO'}, "UV Unwrapping complete")
        return {"FINISHED"}

# Helper function to remove temporary objects.
def remove_temp(temp_obj):
    if temp_obj and temp_obj.name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[temp_obj.name], do_unlink=True)
    return None

# -------------------------------------------------------------------
# Main UI Panels
# -------------------------------------------------------------------
class MOFMOFPanel(Panel):
    bl_label = "MOF UV unwrapper"
    bl_idname = "VIEW3D_PT_MOF_mof"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Blender MOF'
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator("wm.url_open", text="Addon Creator", icon='HEART').url = "https://blendermarket.com/creators/ultikynnys"
        row.operator("wm.url_open", text="MOF Creator", icon='HEART').url = "https://www.quelsolaar.com/"
        layout.separator()
        props = context.scene.mof_properties
        
        # Show zip file status and version prompt.
        prefs = context.preferences.addons[__package__].preferences
        zip_path = bpy.path.abspath(prefs.executable_path) if prefs.executable_path else ""
        if not prefs.executable_path or not os.path.exists(zip_path):
            layout.label(text="MinistryOfFlat zip file not set", icon='ERROR')
            layout.label(text="Please download the MinistryOfFlat zip file from the official site.", icon='INFO')
            layout.prop(prefs, "executable_path")
        else:
            layout.label(text=f"Zip Version: {prefs.version}")
        
        # Alert if not running on Windows.
        if os.name != "nt":
            layout.label(text="UV Unwrapping is only available on Windows", icon='ERROR')
        else:
            box = layout.box()
            box.label(text="General Settings", icon='WORLD')
            for attr in ("resolution", "separate_hard_edges", "aspect", "use_normals", "udims",
                         "overlap_identical", "overlap_mirrored", "world_scale", "texture_density", "use_flat_shading"):
                box.prop(props, attr)
            row = box.row(align=True)
            row.label(text="Seam Direction:")
            for attr in ("seam_x", "seam_y", "seam_z"):
                row.prop(props, attr, text="")
            layout.operator(AutoUVOperator.bl_idname, icon='MOD_UVPROJECT')
        

class MOFDebugPanel(Panel):
    bl_label = "MOF debug"
    bl_idname = "VIEW3D_PT_MOF_MOF_debug"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Blender MOF'
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.mof_properties
        box = layout.box()
        box.label(text="Open the zip to see the documentation.txt for what these are for")
        box.label(text="Debug Settings", icon='ERROR')
        for attr in ("suppress_validation", "quads", "vertex_weld", "flat_soft_surface", "cones", "cone_ratio", "grids",
                     "strips", "patches", "planes", "flatness", "merge", "merge_limit", "pre_smooth", "soft_unfold", "tubes",
                     "junctions", "extra_debug", "angle_based_flattening", "smooth", "repair_smooth", "repair", "squares",
                     "relax", "relax_iterations", "expand", "cut", "stretch", "match", "packing", "rasterization",
                     "packing_iterations", "scale_to_fit", "validate", "uv_margin"):
            box.prop(props, attr)

# -------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------
classes = (
    CheckMOFZipVersionOperator,
    MOFProperties,
    MOFAddonPreferences,
    AutoUVOperator,
    MOFMOFPanel,
    MOFDebugPanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mof_properties = PointerProperty(type=MOFProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.mof_properties

if __name__ == "__main__":
    register()
