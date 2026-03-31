# Blender MOF Wrapper for UV Unwrapper - Copyright (C) 2025 Ultikynnys
#
# This file is part of Blender MOF Wrapper for UV Unwrapper.
#
# Blender MOF Wrapper for UV Unwrapper is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3
#
# Blender MOF Wrapper for UV Unwrapper is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Blender MOF Wrapper for UV Unwrapper.  If not, see <https://www.gnu.org/licenses/>.

import bpy, os, subprocess, zipfile, tempfile, shutil, re
import mathutils
import bmesh
import tomllib
from bpy.props import (
    StringProperty, IntProperty, FloatProperty, BoolProperty, PointerProperty, EnumProperty
)
from bpy.types import Operator, Panel, AddonPreferences, PropertyGroup


# Global variable to store the last target UV‐map name
last_target_uv_map = ""

# Read version from blender_manifest.toml
def get_addon_version():
    try:
        manifest_path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
        with open(manifest_path, "rb") as f:
            manifest = tomllib.load(f)
            return manifest.get("version", "1.0.0")
    except:
        return "1.0.0"

bl_info = {
    "name": "Blender Wrapper for MOF UV Unwrapper",
    "blender": (4, 4, 0),
    "category": "UV",
    "version": tuple(map(int, get_addon_version().split("."))),
    "author": "Ultikynnys",
    "description": "Wrapper that makes the MOF Unwrapper work in Blender",
    "tracker_url": "https://github.com/Ultikynnys/MinistryOfBlender",
}


# -------------------------------------------------------------------
# EnumProperty for UV map selection
# -------------------------------------------------------------------

def uv_map_items(self, context):
    # 1) a “none” entry with a valid ID
    items = [
        ('NONE', 'Select UV Map…', 'No UV map selected yet'),
    ]
    
    # Gather only mesh objects from selection
    selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
    
    if not selected_meshes:
        return items

    # 2) intersect UV map names from all mesh objects
    # Initialize with the UV map names from the first mesh object
    common_uv_names = {uv.name for uv in selected_meshes[0].data.uv_layers}
    
    # Intersect with the names from all other selected meshes
    for obj in selected_meshes[1:]:
        obj_uv_names = {uv.name for uv in obj.data.uv_layers}
        common_uv_names.intersection_update(obj_uv_names)
    
    # Convert back to sorted list
    uv_names = sorted(list(common_uv_names))

    # 3) if the stored value is something other than "NONE" but it no longer exists on all objects,
    #    show it as “Missing” — but never for "NONE" itself.
    current = getattr(self, 'target_uv_map', 'NONE')
    if current != 'NONE' and current not in uv_names:
        items.append(
            (current,
             f"{current} (Missing)",
             "Previously selected UV map is no longer on all selected meshes")
        )

    # 4) append all the real ones
    items.extend((name, name, "") for name in uv_names)
    return items



# -------------------------------------------------------------------
# Property Group for operator parameters
# -------------------------------------------------------------------
class MOFProperties(PropertyGroup):
    """
    PropertyGroup that holds all the parameters for the MOF UV Unwrapper.

    Each property corresponds to a parameter used by the external UV unwrapping tool.
    All integer and float properties are clamped with a minimum value of 0.
    """
    resolution: IntProperty(
        name="Texture Resolution", 
        default=1024, 
        min=0,
        description="Set the texture resolution (in pixels) for the UV unwrap"
    )

    separate_hard_edges: BoolProperty(
        name="Separate Hard Edges",
        default=False,
        description="Split edges that are both marked as seam and set as hard (non-smooth)"
    )
    separate_marked_edges: BoolProperty(
        name="Separate Marked Edges",
        default=False,
        description="Split the mesh along all marked (seam) edges regardless of sharpness"
    )
    aspect: FloatProperty(
        name="Aspect", 
        default=1.0, 
        min=0.0,
        description="Set the aspect ratio used in the UV unwrapping process"
    )
    use_normals: BoolProperty(
        name="Use Normals", 
        default=False,
        description="Enable the use of vertex normals during UV calculation"
    )
    udims: IntProperty(
        name="UDIMs", 
        default=1, 
        min=0,
        description="Number of UDIM tiles to generate for the UV layout"
    )
    overlap_identical: BoolProperty(
        name="Overlap Identical Parts", 
        default=False,
        description="Allow identical mesh parts to overlap in the UV space"
    )
    overlap_mirrored: BoolProperty(
        name="Overlap Mirrored Parts", 
        default=False,
        description="Allow mirrored mesh parts to overlap in the UV space"
    )
    world_scale: BoolProperty(
        name="World Scale UV", 
        default=False,
        description="Apply the world scale to the UV coordinates"
    )
    texture_density: IntProperty(
        name="Texture Density", 
        default=1024, 
        min=0,
        description="Define the density (pixels per unit) for texturing"
    )
    seam_x: FloatProperty(
        name="Seam X", 
        default=0.0, 
        min=0.0,
        description="Offset the seam in the X direction"
    )
    seam_y: FloatProperty(
        name="Seam Y", 
        default=0.0, 
        min=0.0,
        description="Offset the seam in the Y direction"
    )
    seam_z: FloatProperty(
        name="Seam Z", 
        default=0.0, 
        min=0.0,
        description="Offset the seam in the Z direction"
    )
    suppress_validation: BoolProperty(
        name="Suppress Validation", 
        default=False,
        description="Disable validation checks in the external tool"
    )
    quads: BoolProperty(
        name="Quads", 
        default=True,
        description="Prefer quad faces in the UV unwrap for better topology"
    )
    flat_soft_surface: BoolProperty(
        name="Flat Soft Surface", 
        default=True,
        description="Flatten soft surfaces for improved UV layout"
    )
    cones: BoolProperty(
        name="Cones", 
        default=True,
        description="Enable cone calculations for shading correction"
    )
    cone_ratio: FloatProperty(
        name="Cone Ratio", 
        default=0.5, 
        min=0.0,
        description="Set the ratio used for cone calculations"
    )
    grids: BoolProperty(
        name="Grids", 
        default=True,
        description="Enable grid processing for the UV layout"
    )
    strips: BoolProperty(
        name="Strips", 
        default=True,
        description="Enable strip processing for more efficient UV packing"
    )
    patches: BoolProperty(
        name="Patches", 
        default=True,
        description="Use patch-based processing in the UV layout"
    )
    planes: BoolProperty(
        name="Planes", 
        default=True,
        description="Enable detection of planar regions for the UV unwrap"
    )
    flatness: FloatProperty(
        name="Flatness", 
        default=0.9, 
        min=0.0,
        description="Threshold for determining flatness during UV flattening"
    )
    merge: BoolProperty(
        name="Merge", 
        default=True,
        description="Merge similar UV islands after unwrapping"
    )
    merge_limit: FloatProperty(
        name="Merge Limit", 
        default=0.0, 
        min=0.0,
        description="Set the distance threshold for merging UV islands"
    )
    pre_smooth: BoolProperty(
        name="Pre-Smooth", 
        default=True,
        description="Smooth the mesh before unwrapping to improve UV results"
    )
    soft_unfold: BoolProperty(
        name="Soft Unfold", 
        default=True,
        description="Apply a soft unfolding algorithm to reduce distortions"
    )
    tubes: BoolProperty(
        name="Tubes", 
        default=True,
        description="Enable tube-like processing for cylindrical mesh parts"
    )
    junctions: BoolProperty(
        name="Junctions", 
        default=True,
        description="Detect and process junctions in the mesh during unwrapping"
    )
    extra_debug: BoolProperty(
        name="Extra Debug Point", 
        default=False,
        description="Enable extra debugging information for troubleshooting"
    )
    angle_based_flattening: BoolProperty(
        name="Angle-based Flattening", 
        default=True,
        description="Use angle-based flattening for a more natural UV layout"
    )
    smooth: BoolProperty(
        name="Smooth", 
        default=True,
        description="Apply smoothing to the final UV layout"
    )
    repair_smooth: BoolProperty(
        name="Repair Smooth", 
        default=True,
        description="Smooth out repair areas in the UV layout for better transitions"
    )
    repair: BoolProperty(
        name="Repair", 
        default=True,
        description="Perform repair operations on the UV layout to fix errors"
    )
    squares: BoolProperty(
        name="Squares", 
        default=True,
        description="Enforce square UV islands where possible"
    )
    relax: BoolProperty(
        name="Relax", 
        default=True,
        description="Relax the UV islands to reduce texture stretching"
    )
    relax_iterations: IntProperty(
        name="Relax Iterations", 
        default=50, 
        min=0,
        description="Number of iterations to run during the UV relaxation process"
    )
    expand: FloatProperty(
        name="Expand", 
        default=0.25, 
        min=0.0,
        description="Factor by which to expand the UV islands before packing"
    )
    cut: BoolProperty(
        name="Cut", 
        default=True,
        description="Enable cutting in the UV layout to separate islands"
    )
    stretch: BoolProperty(
        name="Stretch", 
        default=True,
        description="Allow UV islands to stretch to better fill the UV space"
    )
    match: BoolProperty(
        name="Match", 
        default=True,
        description="Match adjacent UV islands to minimize seams"
    )
    packing: BoolProperty(
        name="Packing", 
        default=True,
        description="Enable packing of UV islands into the texture space"
    )
    rasterization: IntProperty(
        name="Rasterization Resolution", 
        default=64, 
        min=0,
        description="Resolution for rasterizing UV islands during packing"
    )
    packing_iterations: IntProperty(
        name="Packing Iterations", 
        default=4, 
        min=0,
        description="Number of iterations to optimize the packing of UV islands"
    )
    scale_to_fit: FloatProperty(
        name="Scale To Fit", 
        default=0.5, 
        min=0.0,
        description="Scale factor to fit the UV islands within the texture space"
    )
    validate: BoolProperty(
        name="Validate", 
        default=False,
        description="Run validation on the final UV layout for errors"
    )
    uv_margin: FloatProperty(
        name="UV Margin", 
        default=0.1, 
        min=0.0,
        description="Margin between UV islands in the texture space"
    )
    pixel_padding: IntProperty(
        name="Pixel Padding", 
        default=2, 
        min=0,
        description="Padding in pixels applied during UV tile scaling"
    )

    target_uv_map: StringProperty(
        name="Target UV Map",
        description="Name of the UV map to write the unwrapped UVs into",
        default=""
    )



# -------------------------------------------------------------------
# Addon Preferences with version check operator
# -------------------------------------------------------------------

class MOFAddonPreferences(AddonPreferences):
    """
    Addon preferences for the Blender Wrapper for MOF UV Unwrapper.

    This class allows the user to set the executable path for the MinistryOfFlat zip file
    and displays the current version extracted from the zip.
    """
    bl_idname = __package__

    def update_executable_path(self, context):
        """Automatically check version when path changes"""
        zip_path = bpy.path.abspath(self.executable_path)
        if self.executable_path and os.path.exists(zip_path):
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    doc_filename = None
                    for name in zf.namelist():
                        if os.path.basename(name).lower() == "documentation.txt":
                            doc_filename = name
                            break
                    if doc_filename:
                        with zf.open(doc_filename) as doc_file:
                            content = doc_file.read().decode("utf-8")
                            match = re.search(r"[Vv]ersion[:\s]+([\d]+\.[\d]+(?:\.[\d]+)?)", content)
                            if match:
                                self.version = match.group(1)
                            else:
                                self.version = "unknown"
                    else:
                        self.version = "unknown"
            except Exception:
                self.version = "unknown"
        else:
            self.version = "unknown"

    executable_path: StringProperty(
        name="Executable Zip Path",
        subtype='FILE_PATH',
        default="",
        description="Path to the MinistryOfFlat zip file",
        update=update_executable_path
    )

    version: StringProperty(
        name="Version",
        default="unknown",
        description="Version of the MinistryOfFlat zip file"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "executable_path")
        layout.label(text=f"Zip Version: {self.version}")
        if not self.executable_path or not os.path.exists(bpy.path.abspath(self.executable_path)):
            layout.label(text="Please download MinistryOfFlat from:", icon='INFO')
            layout.operator("wm.url_open", text="https://www.quelsolaar.com/ministry_of_flat/", icon='URL').url = "https://www.quelsolaar.com/ministry_of_flat/"

# -------------------------------------------------------------------
# Operator to perform auto UV unwrapping via external tool
# -------------------------------------------------------------------
class AutoUVOperator(Operator):
    bl_idname = "object.auto_uv_operator"
    bl_label = "Auto UV Unwrap"
    bl_description = "Unwraps the selected mesh using the Ministry of Flat algorithm"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # 0) check for a valid executable path
        prefs = context.preferences.addons[__package__].preferences
        if not prefs.executable_path:
            cls.poll_message_set("MinistryOfFlat zip path not set in addon preferences")
            return False
            
        # 1) must have at least one mesh selected...
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            cls.poll_message_set("At least one mesh object must be selected")
            return False
        
        # 2) all selected meshes must have at least one UV layer
        for o in objs:
            if not o.data.uv_layers:
                cls.poll_message_set(f"Object '{o.name}' has no UV layers")
                return False
        
        # 3) intersect UV map names from all mesh objects
        common_uv_names = {uv.name for uv in objs[0].data.uv_layers}
        for o in objs[1:]:
            common_uv_names.intersection_update({uv.name for uv in o.data.uv_layers})
        
        if not common_uv_names:
            cls.poll_message_set("No common UV maps found among selected objects")
            return False

        # 4) and a valid UV name must be chosen (i.e. not our 'NONE' placeholder)
        if not hasattr(context.scene, 'mof_properties'):
            cls.poll_message_set("MOF properties not found in scene")
            return False
            
        sel = context.scene.mof_properties.target_uv_map
        if sel == 'NONE':
            cls.poll_message_set("Please select a target UV map")
            return False

        if sel not in common_uv_names:
            cls.poll_message_set(f"Target UV map '{sel}' not found on all selected meshes")
            return False

        # 5) finally make sure the zip contains the console executable
        zip_path = bpy.path.abspath(prefs.executable_path)
        if not os.path.exists(zip_path):
            cls.poll_message_set(f"MinistryOfFlat zip file not found at: {zip_path}")
            return False
            
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                if not any(f.lower().endswith("unwrapconsole3.exe") for f in zf.namelist() if not f.endswith("/")):
                    cls.poll_message_set("MinistryOfFlat zip doesn't contain unwrapconsole3.exe")
                    return False
                return True
        except Exception as e:
            cls.poll_message_set(f"Error reading MinistryOfFlat zip: {str(e)}")
            return False

    def execute(self, context):
        global last_target_uv_map
        last_target_uv_map = context.scene.mof_properties.target_uv_map

        # Store the previous mode (default to 'OBJECT' if no active object)
        previous_mode = context.active_object.mode if context.active_object else 'OBJECT'
        bpy.ops.object.mode_set(mode='OBJECT')

        # Process all selected mesh objects.
        selected_objs = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_objs:
            self.report({'ERROR'}, "No mesh objects selected")
            return {"CANCELLED"}

        # Extract the external tool once from the MinistryOfFlat zip file.
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

        # Group objects by their mesh data to avoid redundant processing
        mesh_to_objs = {}
        for obj in selected_objs:
            if obj.data not in mesh_to_objs:
                mesh_to_objs[obj.data] = []
            mesh_to_objs[obj.data].append(obj)

        props = context.scene.mof_properties
        temp_dir = bpy.app.tempdir

        for mesh, mesh_users in mesh_to_objs.items():
            # Use the first object as a representative for this mesh
            original_obj = mesh_users[0]
            
            # Create a temporary copy of the object for processing.
            import time
            temp_name = f"{original_obj.name}_mof_temp_{int(time.time() * 1000)}"
            
            temp_obj = original_obj.copy()
            temp_obj.data = original_obj.data.copy() # Create a unique copy for processing
            temp_obj.name = temp_name
            context.collection.objects.link(temp_obj)
            temp_obj.matrix_world = mathutils.Matrix.Identity(4)

            # Deselect all and select only the temporary object.
            # CRITICAL: We MUST set the active object BEFORE entering Edit Mode or running operators.
            for obj in context.selected_objects:
                obj.select_set(False)
            temp_obj.select_set(True)
            context.view_layer.objects.active = temp_obj

            # Split edges according to the chosen method.
            # Note: separate_marked_edges requires seam marks; separate_hard_edges
            # acts on sharp/non-smooth edges which are independent of seam marks,
            # so its guard must not depend on any(edge.use_seam ...).
            if props.separate_marked_edges and any(edge.use_seam for edge in temp_obj.data.edges):
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.context.view_layer.update()
                bm = bmesh.from_edit_mesh(temp_obj.data)
                marked_edges = [edge for edge in bm.edges if edge.seam]
                if marked_edges:
                    bmesh.ops.split_edges(bm, edges=marked_edges)
                    bmesh.update_edit_mesh(temp_obj.data)
                bpy.ops.object.mode_set(mode='OBJECT')
            elif props.separate_hard_edges:
                # Backwards compatible check for hard edges
                def is_hard(e):
                    if hasattr(e, "smooth"):
                        return not e.smooth
                    return getattr(e, "use_edge_sharp", False)
                
                if any(is_hard(edge) for edge in temp_obj.data.edges):
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.context.view_layer.update()
                    bm = bmesh.from_edit_mesh(temp_obj.data)
                    
                    # For BMesh edges (BMEdge), 'smooth' was removed in 4.1
                    sharp_layer = bm.edges.layers.bool.get("sharp_edge")
                    if sharp_layer:
                        hard_edges = [e for e in bm.edges if e[sharp_layer]]
                    else:
                        # Fallback for older versions
                        hard_edges = [e for e in bm.edges if not getattr(e, "smooth", True)]

                    if hard_edges:
                        bmesh.ops.split_edges(bm, edges=hard_edges)
                        bmesh.update_edit_mesh(temp_obj.data)
                    bpy.ops.object.mode_set(mode='OBJECT')

            # Export the temporary object as OBJ.
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
                self.report({'ERROR'}, f"Export failed for {original_obj.name}: {e}")
                bpy.data.objects.remove(temp_obj, do_unlink=True)
                continue

            # Clean up temp object
            bpy.data.objects.remove(temp_obj, do_unlink=True)

            # Build command
            cmd = [exe, in_path, out_path]
            params = [
                ("-RESOLUTION", str(props.resolution)),
                ("-SEPARATE", "TRUE" if props.separate_hard_edges else "FALSE"),
                ("-ASPECT", str(props.aspect)),
                ("-NORMALS", "TRUE" if props.use_normals else "FALSE"),
                ("-UDIMS", str(props.udims)),
                ("-OVERLAP", "TRUE" if props.overlap_identical else "FALSE"),
                ("-MIRROR", "TRUE" if props.overlap_mirrored else "FALSE"),
                ("-WORLDSCALE", "TRUE" if props.world_scale else "FALSE"),
                ("-DENSITY", str(props.texture_density)),
                ("-CENTER", str(props.seam_x), str(props.seam_y), str(props.seam_z)),
                ("-SUPRESS", "TRUE" if props.suppress_validation else "FALSE"),
                ("-QUAD", "TRUE" if props.quads else "FALSE"),
                ("-WELD", "FALSE"),
                ("-FLAT", "TRUE" if props.flat_soft_surface else "FALSE"),
                ("-CONE", "TRUE" if props.cones else "FALSE"),
                ("-CONERATIO", str(props.cone_ratio)),
                ("-GRIDS", "TRUE" if props.grids else "FALSE"),
                ("-STRIP", "TRUE" if props.strips else "FALSE"),
                ("-PATCH", "TRUE" if props.patches else "FALSE"),
                ("-PLANES", "TRUE" if props.planes else "FALSE"),
                ("-FLATT", str(props.flatness)),
                ("-MERGE", "TRUE" if props.merge else "FALSE"),
                ("-MERGELIMIT", str(props.merge_limit)),
                ("-PRESMOOTH", "TRUE" if props.pre_smooth else "FALSE"),
                ("-SOFTUNFOLD", "TRUE" if props.soft_unfold else "FALSE"),
                ("-TUBES", "TRUE" if props.tubes else "FALSE"),
                ("-JUNCTIONSDEBUG", "TRUE" if props.junctions else "FALSE"),
                ("-EXTRADEBUG", "TRUE" if props.extra_debug else "FALSE"),
                ("-ABF", "TRUE" if props.angle_based_flattening else "FALSE"),
                ("-SMOOTH", "TRUE" if props.smooth else "FALSE"),
                ("-REPAIRSMOOTH", "TRUE" if props.repair_smooth else "FALSE"),
                ("-REPAIR", "TRUE" if props.repair else "FALSE"),
                ("-SQUARE", "TRUE" if props.squares else "FALSE"),
                ("-RELAX", "TRUE" if props.relax else "FALSE"),
                ("-RELAX_ITERATIONS", str(props.relax_iterations)),
                ("-EXPAND", str(props.expand)),
                ("-CUTDEBUG", "TRUE" if props.cut else "FALSE"),
                ("-STRETCH", "TRUE" if props.stretch else "FALSE"),
                ("-MATCH", "TRUE" if props.match else "FALSE"),
                ("-PACKING", "TRUE" if props.packing else "FALSE"),
                ("-RASTERIZATION", str(props.rasterization)),
                ("-PACKING_ITERATIONS", str(props.packing_iterations)),
                ("-SCALETOFIT", str(props.scale_to_fit)),
                ("-VALIDATE", "TRUE" if props.validate else "FALSE"),
            ]
            for tup in params:
                cmd.extend(tup)

            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    if not (os.path.exists(out_path) and os.path.getsize(out_path) > 0):
                        self.report({'ERROR'}, f"External tool failed on {original_obj.name}")
                        continue
            except Exception as e:
                self.report({'ERROR'}, f"Error running tool on {original_obj.name}: {e}")
                continue

            try:
                bpy.ops.wm.obj_import(filepath=out_path, forward_axis='Y', up_axis='Z')
            except Exception as e:
                self.report({'ERROR'}, f"Import failed for {original_obj.name}: {e}")
                continue

            imported_obj = context.active_object
            if imported_obj and imported_obj.type == 'MESH':
                imported_obj.name = f"{original_obj.name}_mof_imported_{int(time.time() * 1000)}"
                
                # Target for UV transfer
                target_obj = original_obj.copy()
                target_obj.data = original_obj.data.copy()
                target_obj.name = f"{original_obj.name}_MOF_Target"
                context.collection.objects.link(target_obj)
                target_obj.matrix_world = mathutils.Matrix.Identity(4)

                bpy.ops.object.select_all(action='DESELECT')
                target_obj.select_set(True)
                context.view_layer.objects.active = target_obj

                if props.target_uv_map not in target_obj.data.uv_layers:
                    self.report({'WARNING'}, f"UV map '{props.target_uv_map}' not found on {original_obj.name}, skipping")
                    bpy.data.objects.remove(imported_obj, do_unlink=True)
                    bpy.data.objects.remove(target_obj, do_unlink=True)
                    continue

                target_obj.data.uv_layers.active = target_obj.data.uv_layers[props.target_uv_map]
                if imported_obj.data.uv_layers:
                    imported_obj.data.uv_layers[0].name = props.target_uv_map
                
                dt_mod = target_obj.modifiers.new(name="DataTransfer", type='DATA_TRANSFER')
                dt_mod.object = imported_obj
                dt_mod.use_loop_data = True
                dt_mod.data_types_loops = {'UV'}
                dt_mod.loop_mapping = 'TOPOLOGY'
                dt_mod.layers_uv_select_src = 'ALL'
                dt_mod.layers_uv_select_dst = 'NAME'

                bpy.ops.object.modifier_apply(modifier=dt_mod.name)
                bpy.data.objects.remove(imported_obj, do_unlink=True)

                # Scaling/Padding
                uv_layer = target_obj.data.uv_layers.active.data
                coords = [loop.uv for loop in uv_layer]
                if coords:
                    min_u = min(c.x for c in coords)
                    max_u = max(c.x for c in coords)
                    min_v = min(c.y for c in coords)
                    max_v = max(c.y for c in coords)
                    range_u = max_u - min_u
                    range_v = max_v - min_v
                    if range_u > 0 and range_v > 0:
                        padding = props.pixel_padding / props.resolution
                        for uv in coords:
                            uv.x = padding + ((uv.x - min_u) / range_u) * (1 - 2 * padding)
                            uv.y = padding + ((uv.y - min_v) / range_v) * (1 - 2 * padding)

                # Update all users of this mesh
                new_mesh_data = target_obj.data
                for user in mesh_users:
                    user.data = new_mesh_data
                
                bpy.data.objects.remove(target_obj, do_unlink=True)

            # Cleanup files
            for fp in (in_path, out_path):
                if os.path.exists(fp):
                    try: os.remove(fp)
                    except: pass

        # End of loop cleanup
        try:
            if os.path.exists(extract_path):
                shutil.rmtree(extract_path)
        except:
            pass

        # Restore original selection
        bpy.ops.object.select_all(action='DESELECT')
        for obj in selected_objs:
            obj.select_set(True)
        if selected_objs:
            context.view_layer.objects.active = selected_objs[0]

        self.report({'INFO'}, f"MOF Unwrap complete for {len(selected_objs)} objects")
        bpy.ops.object.mode_set(mode=previous_mode)
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
    """
    Main UI Panel for the MOF UV Unwrapper addon.

    Displays general settings and buttons for executing the auto UV unwrap.
    """
    bl_label = f"MOF UV unwrapper v{get_addon_version()}"
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
        
        prefs = context.preferences.addons[__package__].preferences
        zip_path = bpy.path.abspath(prefs.executable_path) if prefs.executable_path else ""
        if not prefs.executable_path or not os.path.exists(zip_path):
            layout.label(text="MinistryOfFlat zip file not set", icon='ERROR')
            layout.label(text="Please download MinistryOfFlat from:", icon='INFO')
            layout.operator("wm.url_open", text="https://www.quelsolaar.com/ministry_of_flat/", icon='URL').url = "https://www.quelsolaar.com/ministry_of_flat/"
            layout.prop(prefs, "executable_path")
        else:
            layout.label(text=f"Zip Version: {prefs.version}")
        
        if os.name != "nt":
            layout.label(text="UV Unwrapping is only available on Windows", icon='ERROR')
        else:
            box = layout.box()
            box.label(text="General Settings", icon='WORLD')
            for attr in ("resolution", "separate_hard_edges", "separate_marked_edges", "aspect",
                         "overlap_identical", "overlap_mirrored", "world_scale", "texture_density"):
                row = box.row()
                row.prop(props, attr)
            box.prop(props, "pixel_padding")
            
            if context.object and context.object.type == 'MESH':
                box.prop_search(
                    context.scene.mof_properties,
                    "target_uv_map",
                    context.object.data,
                    "uv_layers",
                    text="Target UV Map"
                )
            else:
                box.prop(context.scene.mof_properties, "target_uv_map", text="Target UV Map")


            layout.operator(AutoUVOperator.bl_idname, icon='MOD_UVPROJECT')
        

class MOFDebugPanel(Panel):
    """
    Debug UI Panel for advanced settings.

    This panel exposes debug and additional settings that control various
    aspects of the UV unwrapping algorithm. For further details, refer to the documentation
    contained in the MinistryOfFlat zip file.
    """
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
        for attr in ("suppress_validation", "quads", "flat_soft_surface", "cones", "cone_ratio", "grids",
                     "strips", "patches", "planes", "flatness", "merge", "merge_limit", "pre_smooth", "soft_unfold", "tubes",
                     "junctions", "extra_debug", "angle_based_flattening", "smooth", "repair_smooth", "repair", "squares",
                     "relax", "relax_iterations", "expand", "cut", "stretch", "match", "packing", "rasterization",
                     "packing_iterations", "scale_to_fit", "validate", "uv_margin"):
            box.prop(props, attr)

classes = (
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
