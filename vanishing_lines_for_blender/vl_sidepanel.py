import os
import bpy


################
# VL SIDEPANEL #
################
def get_scene_camera(context)-> bpy.types.Object|None:
    camera = context.scene.camera
    return camera


def execute(self, context):
        cam_data = context.camera
        
        if 0 <= self.index < len(cam_data.background_images):
            cam_data.background_images.remove(cam_data.background_images[self.index])
            
            
            
            self.report({'INFO'}, f"Removed background image {self.index}")
        
        return {'FINISHED'}

class CAMERA_OT_add_bg_image(bpy.types.Operator):
    bl_idname = "camera.add_bg_image"
    bl_label = "Add Background Image"

    def execute(self, context):
        cam = get_scene_camera(context)
        cam.data.background_images.new()

        # This forces the current area (the panel) to refresh immediately
        for area in context.screen.areas:
            if area.type == 'PROPERTIES':
                area.tag_redraw()

        return {'FINISHED'}

class CAMERA_OT_remove_bg_image(bpy.types.Operator):
    """Remove a specific background image from the camera"""
    bl_idname = "camera.remove_bg_image"
    bl_label = "Remove Background Image"
    bl_options = {'REGISTER', 'UNDO'}

    # This property will hold the index of the image to remove
    index: bpy.props.IntProperty()

    def execute(self, context):
        cam_data = get_scene_camera(context).data
        
        # Check if the index is valid before trying to remove
        if 0 <= self.index < len(cam_data.background_images):
            cam_data.background_images.remove(cam_data.background_images[self.index])

            # This forces the current area (the panel) to refresh immediately
            for area in context.screen.areas:
                if area.type == 'PROPERTIES':
                    area.tag_redraw()
        else:
            self.report({'WARNING'}, "Invalid background image index")
            
        return {'FINISHED'}
from pathlib import Path

def is_operator_running(op_idname):
    for op in bpy.context.window.modal_operators:
        if op.bl_idname == 'VIEW_OT_vanishing_lines_operator':
            return True
    return False



class VIEW_PT_vanishing_lines(bpy.types.Panel):
    """Creates a Panel in the 3D Viewport sidebar"""
    bl_label = "Vanishing Lines"
    bl_idname = "VIEW_PT_vanishing_lines"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VL'

    def draw_background_images_panel(self, context, camera):
        #####################
        # BACKGROUND IMAGES #
        #####################
        header, background_images_panel = self.layout.panel("Background_Images", default_closed=True)

        header.prop(camera.data, "show_background_images", text="Background Images")
        
        if background_images_panel:
            all_icons = [
                "CHAR_NOTDEF",
                "CHAR_REPLACEMENT",
                "NOT_FOUND",
                "BLANK1",
                "AUTOMERGE_OFF",
                "AUTOMERGE_ON",
                "CHECKBOX_DEHLT",
                "CHECKBOX_HLT",
                "CLIPUV_DEHLT",
                "CLIPUV_HLT",
                "DECORATE_UNLOCKED",
                "DECORATE_LOCKED",
                "FAKE_USER_OFF",
                "FAKE_USER_ON",
                "HIDE_ON",
                "HIDE_OFF",
                "INDIRECT_ONLY_OFF",
                "INDIRECT_ONLY_ON",
                "ONIONSKIN_OFF",
                "ONIONSKIN_ON",
                "UNPINNED",
                "PINNED",
                "RADIOBUT_OFF",
                "RADIOBUT_ON",
                "RECORD_OFF",
                "RECORD_ON",
                "RESTRICT_RENDER_ON",
                "RESTRICT_RENDER_OFF",
                "RESTRICT_SELECT_ON",
                "RESTRICT_SELECT_OFF",
                "RESTRICT_VIEW_ON",
                "RESTRICT_VIEW_OFF",
                "RIGHTARROW",
                "DOWNARROW_HLT",
                "SELECT_INTERSECT",
                "SELECT_DIFFERENCE",
                "SNAP_OFF",
                "SNAP_ON",
                "PLAYHEAD_SNAP_OFF",
                "PLAYHEAD_SNAP_ON",
                "UNLOCKED",
                "LOCKED",
                "VIS_SEL_11",
                "VIS_SEL_10",
                "VIS_SEL_01",
                "VIS_SEL_00",
                "CANCEL",
                "ERROR",
                "QUESTION",
                "ADD",
                "ARROW_LEFTRIGHT",
                "AUTO",
                "BLENDER",
                "BORDERMOVE",
                "BRUSHES_ALL",
                "CHECKMARK",
                "COLLAPSEMENU",
                "COLLECTION_NEW",
                "COLOR",
                "COPY_ID",
                "DISCLOSURE_TRI_DOWN",
                "DISCLOSURE_TRI_RIGHT",
                "DOT",
                "DRIVER_DISTANCE",
                "DRIVER_ROTATIONAL_DIFFERENCE",
                "DRIVER_TRANSFORM",
                "DUPLICATE",
                "EYEDROPPER",
                "FCURVE_SNAPSHOT",
                "FILE_NEW",
                "FILE_TICK",
                "FREEZE",
                "FULLSCREEN_ENTER",
                "FULLSCREEN_EXIT",
                "GHOST_DISABLED",
                "GHOST_ENABLED",
                "GRIP",
                "GRIP_V",
                "HAND",
                "HELP",
                "LINKED",
                "MENU_PANEL",
                "NODE_SEL",
                "NODE",
                "OBJECT_HIDDEN",
                "OPTIONS",
                "PANEL_CLOSE",
                "PLUGIN",
                "PLUS",
                "PRESET_NEW",
                "QUIT",
                "RECOVER_LAST",
                "REMOVE",
                "RIGHTARROW_THIN",
                "SCREEN_BACK",
                "STATUSBAR",
                "STYLUS_PRESSURE",
                "THREE_DOTS",
                "TOPBAR",
                "TRASH",
                "TRIA_DOWN",
                "TRIA_LEFT",
                "TRIA_RIGHT",
                "TRIA_UP",
                "UNLINKED",
                "URL",
                "VIEWZOOM",
                "WINDOW",
                "WORKSPACE",
                "X",
                "ZOOM_ALL",
                "ZOOM_IN",
                "ZOOM_OUT",
                "ZOOM_PREVIOUS",
                "ZOOM_SELECTED",
                "MODIFIER",
                "PARTICLES",
                "PHYSICS",
                "SHADERFX",
                "SPEAKER",
                "OUTPUT",
                "SCENE",
                "TOOL_SETTINGS",
                "LIGHT",
                "MATERIAL",
                "TEXTURE",
                "WORLD",
                "ANIM",
                "SCRIPT",
                "GEOMETRY_NODES",
                "TEXT",
                "ACTION",
                "ASSET_MANAGER",
                "CONSOLE",
                "FILEBROWSER",
                "GEOMETRY_SET",
                "GRAPH",
                "IMAGE",
                "INFO",
                "NLA",
                "NODE_COMPOSITING",
                "NODE_MATERIAL",
                "NODE_TEXTURE",
                "NODETREE",
                "OUTLINER",
                "PREFERENCES",
                "PROPERTIES",
                "SEQUENCE",
                "SOUND",
                "SPREADSHEET",
                "TIME",
                "TRACKER",
                "UV",
                "VIEW3D",
                "EDITMODE_HLT",
                "OBJECT_DATAMODE",
                "PARTICLEMODE",
                "POSE_HLT",
                "SCULPTMODE_HLT",
                "TPAINT_HLT",
                "UV_DATA",
                "VPAINT_HLT",
                "WPAINT_HLT",
                "TRACKER_DATA",
                "TRACKING_BACKWARDS_SINGLE",
                "TRACKING_BACKWARDS",
                "TRACKING_CLEAR_BACKWARDS",
                "TRACKING_CLEAR_FORWARDS",
                "TRACKING_FORWARDS_SINGLE",
                "TRACKING_FORWARDS",
                "TRACKING_REFINE_BACKWARDS",
                "TRACKING_REFINE_FORWARDS",
                "TRACKING",
                "GROUP",
                "CONSTRAINT_BONE",
                "CONSTRAINT",
                "ARMATURE_DATA",
                "BONE_DATA",
                "CAMERA_DATA",
                "CURVE_DATA",
                "EMPTY_DATA",
                "FONT_DATA",
                "LATTICE_DATA",
                "LIGHT_DATA",
                "MESH_DATA",
                "META_DATA",
                "PARTICLE_DATA",
                "SHAPEKEY_DATA",
                "SURFACE_DATA",
                "OBJECT_DATA",
                "RENDER_RESULT",
                "RENDERLAYERS",
                "SCENE_DATA",
                "BRUSH_DATA",
                "IMAGE_DATA",
                "LINE_DATA",
                "MATERIAL_DATA",
                "TEXTURE_DATA",
                "WORLD_DATA",
                "ANIM_DATA",
                "BOIDS",
                "CAMERA_STEREO",
                "COMMUNITY",
                "FACE_MAPS",
                "FCURVE",
                "FILE",
                "GREASEPENCIL",
                "GREASEPENCIL_LAYER_GROUP",
                "GROUP_BONE",
                "GROUP_UVS",
                "GROUP_VCOL",
                "GROUP_VERTEX",
                "LIBRARY_DATA_BROKEN",
                "LIBRARY_DATA_DIRECT",
                "LIBRARY_DATA_OVERRIDE",
                "ORPHAN_DATA",
                "PACKAGE",
                "PRESET",
                "RENDER_ANIMATION",
                "RENDER_STILL",
                "RNA",
                "STRANDS",
                "UGLYPACKAGE",
                "MOUSE_LMB",
                "MOUSE_MMB",
                "MOUSE_RMB",
                "MOUSE_MMB_SCROLL",
                "MOUSE_LMB_2X",
                "MOUSE_MOVE",
                "MOUSE_LMB_DRAG",
                "MOUSE_MMB_DRAG",
                "MOUSE_RMB_DRAG",
                "DECORATE_ANIMATE",
                "DECORATE_DRIVER",
                "DECORATE_KEYFRAME",
                "DECORATE_LIBRARY_OVERRIDE",
                "DECORATE_LINKED",
                "DECORATE_OVERRIDE",
                "DECORATE"
            ]
            # panel.label(text="See camera properties for more options.")
            background_images_panel.operator("camera.add_bg_image", text="Add Background Image", icon='ADD')

            for i, bg_image in enumerate(camera.data.background_images):
                box = self.layout.box()
                header, bg_panel = box.panel(f"No{i}_vl_bg_image", default_closed=True)
                
                header.label(text=f"{bpy.path.basename(bg_image.image.filepath)}" if bg_image.image else "Not Set")
                icon = 'RESTRICT_VIEW_OFF' if bg_image.show_background_image else 'RESTRICT_VIEW_ON'
                header.prop(bg_image, "show_background_image", text="", icon=icon, emboss=False)
                
                # ASSIGN THE INDEX HERE
                op = header.operator("camera.remove_bg_image", text="", icon="X", emboss=False)
                op.index = i
                
                # if panel:
                #     # 1. The Source Enum (Expanded or Dropdown)
                #     panel.prop(bg_image, "source", text="Source")

                #     # 2. The File Path / Image Selector (The Browse & Open buttons)
                #     # This template is what creates the 'Browse' and 'Open' UI seen in Blender
                #     row = panel.row()
                #     row.template_ID(bg_image, "image", open="image.open")
                    
                #     # 3. Opacity Slider
                #     row = panel.row()
                #     row.prop(bg_image, "alpha", text="Opacity", slider=True)


                def draw_enum_row(layout, data, prop_name, label_text):
                    """Replicates the native horizontal enum layout with aligned labels"""
                    col = layout.column()
                    col.use_property_split = True
                    col.use_property_decorate = False
                    
                    # We use a row inside the split column to ensure 'expand' works correctly
                    row = col.row()
                    row.prop(data, prop_name, expand=True, text=label_text)

                if bg_panel:
                    draw_enum_row(bg_panel, bg_image, "source", "Background Source")

                    # # 2. Data Selection (Browse/Open)
                    # if bg_image.source == 'IMAGE':
                    #     
                    #     pass
                        
                    # else:
                    #     bg_panel.template_ID(bg_image, "movie_clip", open="clip.open")

                    # Only show the rest if we actually have data assigned
                    
                    col = bg_panel.column()
                    col.use_property_split = True
                    col.use_property_decorate = False
                    match bg_image.source:
                        case 'IMAGE':
                            col.template_ID(bg_image, "image", open="image.open")

                            has_data = True if bg_image.image else False
                            if has_data:
                                # 3. Main Settings (Opacity, Depth, Frame Method)
                                col.template_image(bg_image, "image", bg_image.image_user, compact=True)

                        case 'MOVIE_CLIP':
                            has_data = True if bg_image.clip else False
                            
                            col.prop(bg_image, "use_camera_clip", text="Active Clip")
                            col.template_movieclip(bg_image, "clip")
                            clip_user_col = col.column()
                            clip_user_col.enabled = has_data
                            clip_user_col.prop(bg_image.clip_user, "use_render_undistorted", text="Render Undistorted")
                            clip_user_col.prop(bg_image.clip_user, "proxy_render_size", text="Proxy Render Size")
                        
                    if has_data:
                        ## BG SETTINGS
                        col.prop(bg_image.image, "use_view_as_render", text="View as Render")
                        col.prop(bg_image, "alpha", text="Opacity", slider=True)
                        # row = panel.row(align=True)
                        row = col.row(align=True)
                        row.prop(bg_image, "display_depth", text="Depth", expand=True)
                        row = col.row(align=True)
                        row.prop(bg_image, "frame_method", text="Frame Method", expand=True)

                        # row = col.row(align=True)
                        col.prop(bg_image, "offset", text="Offset")
                        col.prop(bg_image, "rotation", text="Rotation")
                        col.prop(bg_image, "scale", text="Scale")

                        flip_column = col.column(align=True, heading="Flip")
                        flip_column.prop(bg_image, "use_flip_x", text="X", toggle=False)
                        flip_column.prop(bg_image, "use_flip_y", text="Y", toggle=False)

                        # # 4. Background vs Foreground Toggle
                        # panel.prop(bg_image, "show_on_foreground", text="Front")

                        # # 5. Transformation Layout
                        # # Blender uses a column with a label and then a grid-like layout
                        # col = panel.column(align=True)
                        
                        # # Offset (X and Y)
                        # row = col.row(align=True)
                        # row.prop(bg_image, "offset", text="Offset")
                        
                        # # Rotation and Scale
                        # row = col.row(align=True)
                        # row.prop(bg_image, "rotation", text="Rotation")
                        # row.prop(bg_image, "scale", text="Scale")

                        # # 6. Flip Options (Horizontal / Vertical)
                        # row = panel.row(align=True)
                        # row.prop(bg_image, "show_expanded", text="Flip", icon='TRIA_DOWN' if bg_image.show_expanded else 'TRIA_RIGHT', emboss=False)
                        
                        # if bg_image.show_expanded:
                        #     sub = panel.column(align=True)
                        #     row = sub.row(align=True)
                        #     row.prop(bg_image, "use_flip_x", text="Flip Horizontal", toggle=True)
                        #     row.prop(bg_image, "use_flip_y", text="Flip Vertical", toggle=True)

                    background_images_panel.separator()

    def draw_solver_panel(self, context, camera):
        ##########
        # SOLVER #
        ##########
        header, background_images_panel = self.layout.panel("solver", default_closed=False)
        header_row = header.row()
        header_row.alert = camera.data.vl_settings.error_message != ""
        header_row.label(text="Solver")
       
        if background_images_panel:
            background_images_panel.prop(camera.data.vl_settings, "solver_is_paused", text="Pause Solver")
            background_images_panel.separator()

            # panel.prop(camera.data.vl_settings, "compute_space", text="Compute Space")
            # panel.separator()
            background_images_panel.prop(camera.data.vl_settings, "mode", text="Mode")

            mode = camera.data.vl_settings.mode

            # match mode:
            #     case 'ONE_POINT':
            row = background_images_panel.row()
            row.enabled = mode == 'ONE_POINT'
            row.prop(camera.data, "lens", text="Focal Length")

            row = background_images_panel.row()
            row.enabled = mode in {'ONE_POINT', 'TWO_POINT'}
            row.prop(camera.data.vl_settings, "enable_manual_principal", text="Manual Principal Point")

            row = background_images_panel.row()
            row.enabled = mode in {'TWO_POINT', 'THREE_POINT'}

            background_images_panel.separator()

            if error_msg:=camera.data.vl_settings.error_message:
                error_row = background_images_panel.column()
                error_row.alert = camera.data.vl_settings.error_message != ""
                lines = str(error_msg).splitlines()
                for i, line in enumerate(lines):
                    line_row = error_row.row()
                    if i == 0:
                        line_row.label(text=line, icon='ERROR')
                    else:
                        line_row.label(text=line)

    def draw_reference_distance_panel(self, context, camera):
        ######################
        # REFERENCE DISTANCE #
        ######################
        header, background_images_panel = self.layout.panel("reference_distance", default_closed=False)
        header.label(text="Reference Distance")
        if background_images_panel:
            background_images_panel.prop(camera.data.vl_settings, "scene_scale_mode", text="Scale Mode")
            background_images_panel.prop(camera.data.vl_settings, "scene_scale", text="Scene Scale")

            row = background_images_panel.row()
            row.enabled = camera.data.vl_settings.scene_scale_mode != 'ORIGIN'
            # row.prop(camera.data.vl_settings, "reference_distance", text="Reference Distance")
            row.prop(camera.data.vl_settings, "reference_distance_segment", text="Reference Distance Segment")
            background_images_panel.separator()

    def draw_axis_assignment_panel(self, context, camera):
        ###################
        # AXIS ASSIGNMENT #
        ###################
        header, background_images_panel = self.layout.panel("axis_assignement", default_closed=True)
        header.label(text="Axis Assignement")

        if background_images_panel:
            # panel.prop(camera.data.vl_settings, "floor", text="Floor", expand=False)
            row = background_images_panel.row()
            row.prop(camera.data.vl_settings, "first_axis", text="First Axis", expand=False)
            row = background_images_panel.row()
            incompatible_second_axis = camera.data.vl_settings.first_axis[0] == camera.data.vl_settings.second_axis[0]
            row.alert = incompatible_second_axis
            row.prop(camera.data.vl_settings, "second_axis", text="Second Axis", expand=False)
            background_images_panel.separator()

            box = background_images_panel.row()
            box.label(text="First Axis")
            col = box.column(align=True)
            
            row = col.row(align=True)
            row.prop_enum(camera.data.vl_settings, "first_axis", "X-")
            row.prop_enum(camera.data.vl_settings, "first_axis", "X+")

            row = col.row(align=True)
            row.prop_enum(camera.data.vl_settings, "first_axis", "Y-")
            row.prop_enum(camera.data.vl_settings, "first_axis", "Y+")

            row = col.row(align=True)
            row.prop_enum(camera.data.vl_settings, "first_axis", "Z-")
            row.prop_enum(camera.data.vl_settings, "first_axis", "Z+")

            box = background_images_panel.row()
            box.label(text="Second Axis")
            col = box.column(align=True)
            
            row = col.row(align=True)
            row.enabled = not camera.data.vl_settings.first_axis.startswith("X")
            row.prop_enum(camera.data.vl_settings, "second_axis", "X-")
            row.prop_enum(camera.data.vl_settings, "second_axis", "X+")

            row = col.row(align=True)
            row.enabled = not camera.data.vl_settings.first_axis.startswith("Y")
            row.prop_enum(camera.data.vl_settings, "second_axis", "Y-")
            row.prop_enum(camera.data.vl_settings, "second_axis", "Y+")


            row = col.row(align=True)
            row.enabled = not camera.data.vl_settings.first_axis.startswith("Z")
            row.prop_enum(camera.data.vl_settings, "second_axis", "Z-")
            row.prop_enum(camera.data.vl_settings, "second_axis", "Z+")

            # col.prop_enum(camera.data.vl_settings, "second_axis", text="Second Axis", expand=False)
            # col.prop_enum(camera.data.vl_settings, "third_axis", text="Third Axis", expand=False)
            # row = panel.row(align=False)
            # row.prop(camera.data.vl_settings, "first_axis_assignment", text="1st Axis", expand=True)
            # row.prop(camera.data.vl_settings, "first_axis_sign", text="1st Sign", expand=True)
            # row = panel.row(align=True)
            # row.prop(camera.data.vl_settings, "second_axis_assignment", text="2nd Axis", expand=True)
            # panel.separator()

    def draw_coordinates_panel(self, context, camera):
        ##################
        # CONTROL POINTS #
        ##################
        header, coordinates_panel = self.layout.panel("control_points", default_closed=True)
        header.label(text="Coordinates")

        def prop_point(layout, data, prop, text):
            layout = col.column(align=True, heading="Origin")
            layout.prop(data, prop, index=0, text=f"{text} X")
            layout.prop(data, prop, index=1, text="Y")

        if coordinates_panel:
            col = coordinates_panel.column()
            col.use_property_split = True
            col.use_property_decorate = False

            # origin
            prop_point(col, camera.data.vl_settings, 'origin', "Origin")
            prop_point(col, camera.data.vl_settings, 'principal', "Principal")

            for axis_idx, (axis_label, lines) in enumerate([
                ("1st Axis", camera.data.vl_settings.first_vanishing_lines), 
                ("2nd Axis", camera.data.vl_settings.second_vanishing_lines),
                ("3rd Axis", camera.data.vl_settings.third_vanishing_lines),
            ]):
                col.separator()
                # row = panel.row(align=True)
                # panel.label(text=label)
                for line_idx, line in enumerate(lines):
                    row = col.row()
                    row.prop(line, 'start', text=f"{ f'{axis_label} ' if line_idx == 0 else ' '}" + f"#{line_idx}")
                    row.prop(line, "end",   text="")

            coordinates_panel.separator()

    def draw(self, context):
        #################
        # ACTIVE CAMERA #
        #################

        # validate context
        camera = get_scene_camera(context)
        if camera is None:
            self.layout.label(text="No active camera in the scene.")
            return
        
        self.layout.label(text=f"Active Camera: '{camera.name}'")

        if not is_operator_running("VIEW_OT_vanishing_lines_operator"):
            self.layout.operator("view.vanishing_lines_operator", text="Start Vanishing Lines")
            return
        
        self.draw_background_images_panel(context, camera)
        
        self.draw_solver_panel(context, camera)
        
        self.draw_reference_distance_panel(context, camera)

        self.draw_axis_assignment_panel(context, camera)

        self.draw_coordinates_panel(context, camera)






######################
# REGISTER FUNCTIONS #
######################
def register():
    bpy.utils.register_class(CAMERA_OT_add_bg_image)
    bpy.utils.register_class(CAMERA_OT_remove_bg_image)
    bpy.utils.register_class(VIEW_PT_vanishing_lines)
    
def unregister():
    bpy.utils.unregister_class(VIEW_PT_vanishing_lines)
    bpy.utils.unregister_class(CAMERA_OT_remove_bg_image)
    bpy.utils.unregister_class(CAMERA_OT_add_bg_image)
