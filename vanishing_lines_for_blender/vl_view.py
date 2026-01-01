
def draw_background_images_panel(layout, camera):
    #####################
    # BACKGROUND IMAGES #
    #####################
    header, background_images_panel = layout.panel("Background_Images", default_closed=True)

    header.prop(camera.data, "show_background_images", text="Background Images")
    
    if background_images_panel:
        background_images_panel.operator("camera.add_bg_image", text="Add Background Image", icon='ADD')

        for i, bg_image in enumerate(camera.data.background_images):
            box = background_images_panel.box()
            header, bg_panel = box.panel(f"No{i}_vl_bg_image", default_closed=True)
            
            header.label(text=f"{bpy.path.basename(bg_image.image.filepath)}" if bg_image.image else "Not Set")
            icon = 'RESTRICT_VIEW_OFF' if bg_image.show_background_image else 'RESTRICT_VIEW_ON'
            header.prop(bg_image, "show_background_image", text="", icon=icon, emboss=False)
            
            # ASSIGN THE INDEX HERE
            op = header.operator("camera.remove_bg_image", text="", icon="X", emboss=False)
            op.index = i
            
            if bg_panel:
                col = bg_panel.column()
                col.use_property_split = True
                col.use_property_decorate = False
                col.row().prop(bg_image, "source", expand=True, text="Background Source")
                
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
                
def draw_solver_panel(layout, camera):
    ##########
    # SOLVER #
    ##########
    header, background_images_panel = layout.panel("solver", default_closed=False)
    header_row = header.row()
    header_row.alert = camera.data.vl_settings.error_message != ""
    header_row.label(text="Solver")
    
    if background_images_panel:


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

def draw_reference_distance_panel(layout, camera):
    ######################
    # REFERENCE DISTANCE #
    ######################
    header, background_images_panel = layout.panel("reference_distance", default_closed=False)
    header.label(text="Reference Distance")
    if background_images_panel:
        background_images_panel.prop(camera.data.vl_settings, "scene_scale_mode", text="Scale Mode")
        background_images_panel.prop(camera.data.vl_settings, "scene_scale", text="Scene Scale")

        row = background_images_panel.row()
        row.enabled = camera.data.vl_settings.scene_scale_mode != 'ORIGIN'
        # row.prop(camera.data.vl_settings, "reference_distance", text="Reference Distance")
        row.prop(camera.data.vl_settings, "reference_distance_segment", text="Reference Distance Segment")
        background_images_panel.separator()

def draw_axis_assignment_panel(layout, camera):
    ###################
    # AXIS ASSIGNMENT #
    ###################
    header, background_images_panel = layout.panel("axis_assignement", default_closed=True)
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

def draw_coordinates_panel(layout, camera):
    ##################
    # CONTROL POINTS #
    ##################
    header, coordinates_panel = layout.panel("control_points", default_closed=True)
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

def draw_all_icons(layout):
    all_icons = [
        'NONE', 'CHAR_NOTDEF', 'CHAR_REPLACEMENT', 'NOT_FOUND', 'BLANK1', 'AUTOMERGE_OFF', 'AUTOMERGE_ON', 'CHECKBOX_DEHLT', 'CHECKBOX_HLT', 'CLIPUV_DEHLT', 'CLIPUV_HLT', 'DECORATE_UNLOCKED', 'DECORATE_LOCKED', 'FAKE_USER_OFF', 'FAKE_USER_ON', 'HIDE_ON', 'HIDE_OFF', 'INDIRECT_ONLY_OFF', 'INDIRECT_ONLY_ON', 'ONIONSKIN_OFF', 'ONIONSKIN_ON', 'UNPINNED', 'PINNED', 'RADIOBUT_OFF', 'RADIOBUT_ON', 'RECORD_OFF', 'RECORD_ON', 'RESTRICT_RENDER_ON', 'RESTRICT_RENDER_OFF', 'RESTRICT_SELECT_ON', 'RESTRICT_SELECT_OFF', 'RESTRICT_VIEW_ON', 'RESTRICT_VIEW_OFF', 'RIGHTARROW', 'DOWNARROW_HLT', 'SELECT_INTERSECT', 'SELECT_DIFFERENCE', 'SNAP_OFF', 'SNAP_ON', 'UNLOCKED', 'LOCKED', 'VIS_SEL_11', 'VIS_SEL_10', 'VIS_SEL_01', 'VIS_SEL_00', 'CANCEL', 'ERROR', 'QUESTION', 'ADD', 'ARROW_LEFTRIGHT', 'AUTO', 'BLENDER', 'BORDERMOVE', 'BRUSHES_ALL', 'CHECKMARK', 'COLLAPSEMENU', 'COLLECTION_NEW', 'COLOR', 'COPY_ID', 'DISCLOSURE_TRI_DOWN', 'DISCLOSURE_TRI_RIGHT', 'DOT', 'DRIVER_DISTANCE', 'DRIVER_ROTATIONAL_DIFFERENCE', 'DRIVER_TRANSFORM', 'DUPLICATE', 'EYEDROPPER', 'FCURVE_SNAPSHOT', 'FILE_NEW', 'FILE_TICK', 'FREEZE', 'FULLSCREEN_ENTER', 'FULLSCREEN_EXIT', 'GHOST_DISABLED', 'GHOST_ENABLED', 'GRIP', 'GRIP_V', 'HAND', 'HELP', 'LINKED', 'MENU_PANEL', 'NODE_SEL', 'NODE', 'OBJECT_HIDDEN', 'OPTIONS', 'PANEL_CLOSE', 'PLUGIN', 'PLUS', 'PRESET_NEW', 'QUIT', 'RECOVER_LAST', 'REMOVE', 'RIGHTARROW_THIN', 'SCREEN_BACK', 'STATUSBAR', 'STYLUS_PRESSURE', 'THREE_DOTS', 'TOPBAR', 'TRASH', 'TRIA_DOWN', 'TRIA_LEFT', 'TRIA_RIGHT', 'TRIA_UP', 'UNLINKED', 'URL', 'VIEWZOOM', 'WINDOW', 'WORKSPACE', 'X', 'ZOOM_ALL', 'ZOOM_IN', 'ZOOM_OUT', 'ZOOM_PREVIOUS', 'ZOOM_SELECTED', 'MODIFIER', 'PARTICLES', 'PHYSICS', 'SHADERFX', 'SPEAKER', 'OUTPUT', 'SCENE', 'TOOL_SETTINGS', 'LIGHT', 'MATERIAL', 'TEXTURE', 'WORLD', 'ANIM', 'SCRIPT', 'GEOMETRY_NODES', 'TEXT', 'ACTION', 'ASSET_MANAGER', 'CONSOLE', 'FILEBROWSER', 'GEOMETRY_SET', 'GRAPH', 'IMAGE', 'INFO', 'NLA', 'NODE_COMPOSITING', 'NODE_MATERIAL', 'NODE_TEXTURE', 'NODETREE', 'OUTLINER', 'PREFERENCES', 'PROPERTIES', 'SEQUENCE', 'SOUND', 'SPREADSHEET', 'TIME', 'TRACKER', 'UV', 'VIEW3D', 'EDITMODE_HLT', 'OBJECT_DATAMODE', 'PARTICLEMODE', 'POSE_HLT', 'SCULPTMODE_HLT', 'TPAINT_HLT', 'UV_DATA', 'VPAINT_HLT', 'WPAINT_HLT', 'TRACKER_DATA', 'TRACKING_BACKWARDS_SINGLE', 'TRACKING_BACKWARDS', 'TRACKING_CLEAR_BACKWARDS', 'TRACKING_CLEAR_FORWARDS', 'TRACKING_FORWARDS_SINGLE', 'TRACKING_FORWARDS', 'TRACKING_REFINE_BACKWARDS', 'TRACKING_REFINE_FORWARDS', 'TRACKING', 'GROUP', 'CONSTRAINT_BONE', 'CONSTRAINT', 'ARMATURE_DATA', 'BONE_DATA', 'CAMERA_DATA', 'CURVE_DATA', 'EMPTY_DATA', 'FONT_DATA', 'LATTICE_DATA', 'LIGHT_DATA', 'MESH_DATA', 'META_DATA', 'PARTICLE_DATA', 'SHAPEKEY_DATA', 'SURFACE_DATA', 'OBJECT_DATA', 'RENDER_RESULT', 'RENDERLAYERS', 'SCENE_DATA', 'BRUSH_DATA', 'IMAGE_DATA', 'LINE_DATA', 'MATERIAL_DATA', 'TEXTURE_DATA', 'WORLD_DATA', 'ANIM_DATA', 'BOIDS', 'CAMERA_STEREO', 'COMMUNITY', 'FACE_MAPS', 'FCURVE', 'FILE', 'GREASEPENCIL', 'GREASEPENCIL_LAYER_GROUP', 'GROUP_BONE', 'GROUP_UVS', 'GROUP_VCOL', 'GROUP_VERTEX', 'LIBRARY_DATA_BROKEN', 'LIBRARY_DATA_DIRECT', 'LIBRARY_DATA_OVERRIDE', 'ORPHAN_DATA', 'PACKAGE', 'PRESET', 'RENDER_ANIMATION', 'RENDER_STILL', 'RNA_ADD', 'RNA', 'STRANDS', 'UGLYPACKAGE', 'MOUSE_LMB', 'MOUSE_MMB', 'MOUSE_RMB', 'MOUSE_MMB_SCROLL', 'MOUSE_LMB_2X', 'MOUSE_MOVE', 'MOUSE_LMB_DRAG', 'MOUSE_MMB_DRAG', 'MOUSE_RMB_DRAG', 'DECORATE_ANIMATE', 'DECORATE_DRIVER', 'DECORATE_KEYFRAME', 'DECORATE_LIBRARY_OVERRIDE', 'DECORATE_LINKED', 'DECORATE_OVERRIDE', 'DECORATE', 'OUTLINER_COLLECTION', 'CURVES_DATA', 'OUTLINER_DATA_ARMATURE', 'OUTLINER_DATA_CAMERA', 'OUTLINER_DATA_CURVE', 'OUTLINER_DATA_CURVES', 'OUTLINER_DATA_EMPTY', 'OUTLINER_DATA_FONT', 'OUTLINER_DATA_GP_LAYER', 'OUTLINER_DATA_GREASEPENCIL', 'OUTLINER_DATA_LATTICE', 'OUTLINER_DATA_LIGHT', 'OUTLINER_DATA_LIGHTPROBE', 'OUTLINER_DATA_MESH', 'OUTLINER_DATA_META', 'OUTLINER_DATA_POINTCLOUD', 'OUTLINER_DATA_SPEAKER', 'OUTLINER_DATA_SURFACE', 'OUTLINER_DATA_VOLUME', 'POINTCLOUD_DATA', 'POINTCLOUD_POINT', 'VOLUME_DATA', 'OUTLINER_OB_ARMATURE', 'OUTLINER_OB_CAMERA', 'OUTLINER_OB_CURVE', 'OUTLINER_OB_CURVES', 'OUTLINER_OB_EMPTY', 'OUTLINER_OB_FONT', 'OUTLINER_OB_FORCE_FIELD', 'OUTLINER_OB_GREASEPENCIL', 'OUTLINER_OB_GROUP_INSTANCE', 'OUTLINER_OB_IMAGE', 'OUTLINER_OB_LATTICE', 'OUTLINER_OB_LIGHT', 'OUTLINER_OB_LIGHTPROBE', 'OUTLINER_OB_MESH', 'OUTLINER_OB_META', 'OUTLINER_OB_POINTCLOUD', 'OUTLINER_OB_SPEAKER', 'OUTLINER_OB_SURFACE', 'OUTLINER_OB_VOLUME', 'GP_MULTIFRAME_EDITING', 'GP_ONLY_SELECTED', 'GP_SELECT_BETWEEN_STROKES', 'GP_SELECT_POINTS', 'GP_SELECT_STROKES', 'HOLDOUT_OFF', 'HOLDOUT_ON', 'MODIFIER_OFF', 'MODIFIER_ON', 'RESTRICT_COLOR_OFF', 'RESTRICT_COLOR_ON', 'RESTRICT_INSTANCED_OFF', 'RESTRICT_INSTANCED_ON', 'LIGHT_AREA', 'LIGHT_HEMI', 'LIGHT_POINT', 'LIGHT_SPOT', 'LIGHT_SUN', 'LIGHTPROBE_PLANE', 'LIGHTPROBE_SPHERE', 'LIGHTPROBE_VOLUME', 'COLOR_BLUE', 'COLOR_GREEN', 'COLOR_RED', 'CONE', 'CUBE', 'CURVE_BEZCIRCLE', 'CURVE_BEZCURVE', 'CURVE_NCIRCLE', 'CURVE_NCURVE', 'CURVE_PATH', 'CURVES', 'EMPTY_ARROWS', 'EMPTY_AXIS', 'EMPTY_SINGLE_ARROW', 'MESH_CAPSULE', 'MESH_CIRCLE', 'MESH_CONE', 'MESH_CUBE', 'MESH_CYLINDER', 'MESH_GRID', 'MESH_ICOSPHERE', 'MESH_MONKEY', 'MESH_PLANE', 'MESH_TORUS', 'MESH_UVSPHERE', 'META_BALL', 'META_CAPSULE', 'META_CUBE', 'META_ELLIPSOID', 'META_PLANE', 'MONKEY', 'SPHERE', 'STROKE', 'SURFACE_NCIRCLE', 'SURFACE_NCURVE', 'SURFACE_NCYLINDER', 'SURFACE_NSPHERE', 'SURFACE_NSURFACE', 'SURFACE_NTORUS', 'TRIA_DOWN_BAR', 'TRIA_LEFT_BAR', 'TRIA_RIGHT_BAR', 'TRIA_UP_BAR', 'AREA_DOCK', 'AREA_JOIN_DOWN', 'AREA_JOIN_LEFT', 'AREA_JOIN_UP', 'AREA_JOIN', 'AREA_SWAP', 'FORCE_BOID', 'FORCE_CHARGE', 'FORCE_CURVE', 'FORCE_DRAG', 'FORCE_FLUIDFLOW', 'FORCE_FORCE', 'FORCE_HARMONIC', 'FORCE_LENNARDJONES', 'FORCE_MAGNETIC', 'FORCE_TEXTURE', 'FORCE_TURBULENCE', 'FORCE_VORTEX', 'FORCE_WIND', 'IMAGE_BACKGROUND', 'IMAGE_PLANE', 'IMAGE_REFERENCE', 'RIGID_BODY_CONSTRAINT', 'RIGID_BODY', 'SPLIT_HORIZONTAL', 'SPLIT_VERTICAL', 'ANCHOR_BOTTOM', 'ANCHOR_CENTER', 'ANCHOR_LEFT', 'ANCHOR_RIGHT', 'ANCHOR_TOP', 'NODE_CORNER', 'NODE_INSERT_OFF', 'NODE_INSERT_ON', 'NODE_SIDE', 'NODE_TOP', 'SELECT_EXTEND', 'SELECT_SET', 'SELECT_SUBTRACT', 'ALIGN_BOTTOM', 'ALIGN_CENTER', 'ALIGN_FLUSH', 'ALIGN_JUSTIFY', 'ALIGN_LEFT', 'ALIGN_MIDDLE', 'ALIGN_RIGHT', 'ALIGN_TOP', 'BOLD', 'ITALIC', 'LINENUMBERS_OFF', 'LINENUMBERS_ON', 'SCRIPTPLUGINS', 'SMALL_CAPS', 'SYNTAX_OFF', 'SYNTAX_ON', 'UNDERLINE', 'WORDWRAP_OFF', 'WORDWRAP_ON', 'CON_ACTION', 'CON_ARMATURE', 'CON_CAMERASOLVER', 'CON_CHILDOF', 'CON_CLAMPTO', 'CON_DISTLIMIT', 'CON_FLOOR', 'CON_FOLLOWPATH', 'CON_FOLLOWTRACK', 'CON_KINEMATIC', 'CON_LOCKTRACK', 'CON_LOCLIKE', 'CON_LOCLIMIT', 'CON_OBJECTSOLVER', 'CON_PIVOT', 'CON_ROTLIKE', 'CON_ROTLIMIT', 'CON_SAMEVOL', 'CON_SHRINKWRAP', 'CON_SIZELIKE', 'CON_SIZELIMIT', 'CON_SPLINEIK', 'CON_STRETCHTO', 'CON_TRACKTO', 'CON_TRANSFORM_CACHE', 'CON_TRANSFORM', 'CON_TRANSLIKE', 'HOOK', 'MOD_ARMATURE', 'MOD_ARRAY', 'MOD_BEVEL', 'MOD_BOOLEAN', 'MOD_BUILD', 'MOD_CAST', 'MOD_CLOTH', 'MOD_CURVE', 'MOD_DASH', 'MOD_DATA_TRANSFER', 'MOD_DECIM', 'MOD_DISPLACE', 'MOD_DYNAMICPAINT', 'MOD_EDGESPLIT', 'MOD_ENVELOPE', 'MOD_EXPLODE', 'MOD_FLUID', 'MOD_FLUIDSIM', 'MOD_HUE_SATURATION', 'MOD_INSTANCE', 'MOD_LATTICE', 'MOD_LENGTH', 'MOD_LINEART', 'MOD_MASK', 'MOD_MESHDEFORM', 'MOD_MIRROR', 'MOD_MULTIRES', 'MOD_NOISE', 'MOD_NORMALEDIT', 'MOD_OCEAN', 'MOD_OFFSET', 'MOD_OPACITY', 'MOD_OUTLINE', 'MOD_PARTICLE_INSTANCE', 'MOD_PARTICLES', 'MOD_PHYSICS', 'MOD_REMESH', 'MOD_SCREW', 'MOD_SHRINKWRAP', 'MOD_SIMPLEDEFORM', 'MOD_SIMPLIFY', 'MOD_SKIN', 'MOD_SMOOTH', 'MOD_SOFT', 'MOD_SOLIDIFY', 'MOD_SUBSURF', 'MOD_THICKNESS', 'MOD_TIME', 'MOD_TINT', 'MOD_TRIANGULATE', 'MOD_UVPROJECT', 'MOD_VERTEX_WEIGHT', 'MOD_WARP', 'MOD_WAVE', 'MOD_WIREFRAME', 'MODIFIER_DATA', 'ACTION_SLOT', 'ACTION_TWEAK', 'DRIVER', 'FF', 'FRAME_NEXT', 'FRAME_PREV', 'HANDLE_ALIGNED', 'HANDLE_AUTO', 'HANDLE_AUTOCLAMPED', 'HANDLE_FREE', 'HANDLE_VECTOR', 'IPO_BACK', 'IPO_BEZIER', 'IPO_BOUNCE', 'IPO_CIRC', 'IPO_CONSTANT', 'IPO_CUBIC', 'IPO_EASE_IN_OUT', 'IPO_EASE_IN', 'IPO_EASE_OUT', 'IPO_ELASTIC', 'IPO_EXPO', 'IPO_LINEAR', 'IPO_QUAD', 'IPO_QUART', 'IPO_QUINT', 'IPO_SINE', 'KEY_DEHLT', 'KEY_HLT', 'KEYFRAME_HLT', 'KEYFRAME', 'KEYINGSET', 'MARKER_HLT', 'MARKER', 'MUTE_IPO_OFF', 'MUTE_IPO_ON', 'NEXT_KEYFRAME', 'NLA_PUSHDOWN', 'NORMALIZE_FCURVES', 'ORIENTATION_PARENT', 'PAUSE', 'PLAY_REVERSE', 'PLAY_SOUND', 'PLAY', 'PMARKER_ACT', 'PMARKER_SEL', 'PMARKER', 'PREV_KEYFRAME', 'PREVIEW_RANGE', 'REC', 'REW', 'SOLO_OFF', 'SOLO_ON', 'CENTER_ONLY', 'CURSOR', 'EDGESEL', 'FACE_CORNER', 'FACESEL', 'INVERSESQUARECURVE', 'LINCURVE', 'NOCURVE', 'PARTICLE_PATH', 'PARTICLE_POINT', 'PARTICLE_TIP', 'PIVOT_ACTIVE', 'PIVOT_BOUNDBOX', 'PIVOT_CURSOR', 'PIVOT_INDIVIDUAL', 'PIVOT_MEDIAN', 'PROP_CON', 'PROP_OFF', 'PROP_ON', 'PROP_PROJECTED', 'RNDCURVE', 'ROOTCURVE', 'SHARPCURVE', 'SMOOTHCURVE', 'SPHERECURVE', 'VERTEXSEL', 'SNAP_EDGE', 'SNAP_FACE_CENTER', 'SNAP_FACE_NEAREST', 'SNAP_FACE', 'SNAP_GRID', 'SNAP_INCREMENT', 'SNAP_MIDPOINT', 'SNAP_NORMAL', 'SNAP_PEEL_OBJECT', 'SNAP_PERPENDICULAR', 'SNAP_VERTEX', 'SNAP_VOLUME', 'STICKY_UVS_DISABLE', 'STICKY_UVS_LOC', 'STICKY_UVS_VERT', 'ORIENTATION_GIMBAL', 'ORIENTATION_GLOBAL', 'ORIENTATION_LOCAL', 'ORIENTATION_NORMAL', 'ORIENTATION_VIEW', 'COPYDOWN', 'FIXED_SIZE', 'GIZMO', 'GP_CAPS_FLAT', 'GP_CAPS_ROUND', 'NORMALS_FACE', 'NORMALS_VERTEX_FACE', 'NORMALS_VERTEX', 'OBJECT_ORIGIN', 'ORIENTATION_CURSOR', 'PASTEDOWN', 'PASTEFLIPDOWN', 'PASTEFLIPUP', 'TRANSFORM_ORIGINS', 'UV_EDGESEL', 'UV_FACESEL', 'UV_ISLANDSEL', 'UV_SYNC_SELECT', 'UV_VERTEXSEL', 'AXIS_FRONT', 'AXIS_SIDE', 'AXIS_TOP', 'GRID', 'LAYER_ACTIVE', 'LAYER_USED', 'LOCKVIEW_OFF', 'LOCKVIEW_ON', 'OVERLAY', 'SHADING_BBOX', 'SHADING_RENDERED', 'SHADING_SOLID', 'SHADING_TEXTURE', 'SHADING_WIRE', 'XRAY', 'VIEW_CAMERA_UNSELECTED', 'VIEW_CAMERA', 'VIEW_LOCKED', 'VIEW_ORTHO', 'VIEW_PAN', 'VIEW_PERSPECTIVE', 'VIEW_UNLOCKED', 'VIEW_ZOOM', 'FILE_ALIAS', 'FILE_FOLDER', 'FOLDER_REDIRECT', 'APPEND_BLEND', 'BACK', 'BOOKMARKS', 'CURRENT_FILE', 'DESKTOP', 'DISC', 'DISK_DRIVE', 'DOCUMENTS', 'EXPORT', 'EXTERNAL_DRIVE', 'FILE_3D', 'FILE_ARCHIVE', 'FILE_BACKUP', 'FILE_BLANK', 'FILE_BLEND', 'FILE_CACHE', 'FILE_FONT', 'FILE_HIDDEN', 'FILE_IMAGE', 'FILE_MOVIE', 'FILE_PARENT', 'FILE_REFRESH', 'FILE_SCRIPT', 'FILE_SOUND', 'FILE_TEXT', 'FILE_VOLUME', 'FILTER', 'FONTPREVIEW', 'FORWARD', 'HOME', 'IMGDISPLAY', 'IMPORT', 'LINK_BLEND', 'LONGDISPLAY', 'LOOP_BACK', 'LOOP_FORWARDS', 'NETWORK_DRIVE', 'NEWFOLDER', 'PREVIEW_LOADING', 'SETTINGS', 'SHORTDISPLAY', 'SORT_ASC', 'SORT_DESC', 'SORTALPHA', 'SORTBYEXT', 'SORTSIZE', 'SORTTIME', 'SYSTEM', 'TAG', 'TEMP', 'ALIASED', 'ANTIALIASED', 'MAT_SPHERE_SKY', 'MATCLOTH', 'MATCUBE', 'MATFLUID', 'MATPLANE', 'MATSHADERBALL', 'MATSPHERE', 'SEQ_CHROMA_SCOPE', 'SEQ_HISTOGRAM', 'SEQ_LUMA_WAVEFORM', 'SEQ_PREVIEW', 'SEQ_SEQUENCER', 'SEQ_SPLITVIEW', 'SEQ_STRIP_DUPLICATE', 'SEQ_STRIP_META', 'IMAGE_ALPHA', 'IMAGE_RGB_ALPHA', 'IMAGE_RGB', 'IMAGE_ZDEPTH', 'BLENDER_LOGO_LARGE', 'CANCEL_LARGE', 'DISC_LARGE', 'DISK_DRIVE_LARGE', 'EXTERNAL_DRIVE_LARGE', 'FILE_FOLDER_LARGE', 'FILE_LARGE', 'FILE_PARENT_LARGE', 'INFO_LARGE', 'NETWORK_DRIVE_LARGE', 'QUESTION_LARGE', 'WARNING_LARGE', 'KEY_BACKSPACE_FILLED', 'KEY_BACKSPACE', 'KEY_COMMAND_FILLED', 'KEY_COMMAND', 'KEY_CONTROL_FILLED', 'KEY_CONTROL', 'KEY_EMPTY1_FILLED', 'KEY_EMPTY1', 'KEY_EMPTY2_FILLED', 'KEY_EMPTY2', 'KEY_EMPTY3_FILLED', 'KEY_EMPTY3', 'KEY_MENU_FILLED', 'KEY_MENU', 'KEY_OPTION_FILLED', 'KEY_OPTION', 'KEY_RETURN_FILLED', 'KEY_RETURN', 'KEY_RING_FILLED', 'KEY_RING', 'KEY_SHIFT_FILLED', 'KEY_SHIFT', 'KEY_TAB_FILLED', 'KEY_TAB', 'KEY_WINDOWS_FILLED', 'KEY_WINDOWS', 'GESTURE_PAN', 'GESTURE_ROTATE', 'GESTURE_ZOOM', 'FUND', 'HEART', 'INTERNET_OFFLINE', 'INTERNET', 'USER', 'EXPERIMENTAL', 'MEMORY', 'RGB_RED', 'RGB_GREEN', 'RGB_BLUE', 'KEYTYPE_KEYFRAME_VEC', 'KEYTYPE_BREAKDOWN_VEC', 'KEYTYPE_EXTREME_VEC', 'KEYTYPE_JITTER_VEC', 'KEYTYPE_MOVING_HOLD_VEC', 'KEYTYPE_GENERATED_VEC', 'HANDLETYPE_FREE_VEC', 'HANDLETYPE_ALIGNED_VEC', 'HANDLETYPE_VECTOR_VEC', 'HANDLETYPE_AUTO_VEC', 'HANDLETYPE_AUTO_CLAMP_VEC', 'COLORSET_01_VEC', 'COLORSET_02_VEC', 'COLORSET_03_VEC', 'COLORSET_04_VEC', 'COLORSET_05_VEC', 'COLORSET_06_VEC', 'COLORSET_07_VEC', 'COLORSET_08_VEC', 'COLORSET_09_VEC', 'COLORSET_10_VEC', 'COLORSET_11_VEC', 'COLORSET_12_VEC', 'COLORSET_13_VEC', 'COLORSET_14_VEC', 'COLORSET_15_VEC', 'COLORSET_16_VEC', 'COLORSET_17_VEC', 'COLORSET_18_VEC', 'COLORSET_19_VEC', 'COLORSET_20_VEC', 'COLLECTION_COLOR_01', 'COLLECTION_COLOR_02', 'COLLECTION_COLOR_03', 'COLLECTION_COLOR_04', 'COLLECTION_COLOR_05', 'COLLECTION_COLOR_06', 'COLLECTION_COLOR_07', 'COLLECTION_COLOR_08', 'STRIP_COLOR_01', 'STRIP_COLOR_02', 'STRIP_COLOR_03', 'STRIP_COLOR_04', 'STRIP_COLOR_05', 'STRIP_COLOR_06', 'STRIP_COLOR_07', 'STRIP_COLOR_08', 'STRIP_COLOR_09', 'LIBRARY_DATA_INDIRECT', 'LIBRARY_DATA_OVERRIDE_NONEDITABLE', 'LAYERGROUP_COLOR_01', 'LAYERGROUP_COLOR_02', 'LAYERGROUP_COLOR_03', 'LAYERGROUP_COLOR_04', 'LAYERGROUP_COLOR_05', 'LAYERGROUP_COLOR_06', 'LAYERGROUP_COLOR_07', 'LAYERGROUP_COLOR_08', 'EVENT_A', 'EVENT_B', 'EVENT_C', 'EVENT_D', 'EVENT_E', 'EVENT_F', 'EVENT_G', 'EVENT_H', 'EVENT_I', 'EVENT_J', 'EVENT_K', 'EVENT_L', 'EVENT_M', 'EVENT_N', 'EVENT_O', 'EVENT_P', 'EVENT_Q', 'EVENT_R', 'EVENT_S', 'EVENT_T', 'EVENT_U', 'EVENT_V', 'EVENT_W', 'EVENT_X', 'EVENT_Y', 'EVENT_Z', 'EVENT_SHIFT', 'EVENT_CTRL', 'EVENT_ALT', 'EVENT_OS', 'EVENT_HYPER', 'EVENT_F1', 'EVENT_F2', 'EVENT_F3', 'EVENT_F4', 'EVENT_F5', 'EVENT_F6', 'EVENT_F7', 'EVENT_F8', 'EVENT_F9', 'EVENT_F10', 'EVENT_F11', 'EVENT_F12', 'EVENT_F13', 'EVENT_F14', 'EVENT_F15', 'EVENT_F16', 'EVENT_F17', 'EVENT_F18', 'EVENT_F19', 'EVENT_F20', 'EVENT_F21', 'EVENT_F22', 'EVENT_F23', 'EVENT_F24', 'EVENT_ESC', 'EVENT_TAB', 'EVENT_PAGEUP', 'EVENT_PAGEDOWN', 'EVENT_RETURN', 'EVENT_SPACEKEY', 'EVENT_ZEROKEY', 'EVENT_ONEKEY', 'EVENT_TWOKEY', 'EVENT_THREEKEY', 'EVENT_FOURKEY', 'EVENT_FIVEKEY', 'EVENT_SIXKEY', 'EVENT_SEVENKEY', 'EVENT_EIGHTKEY', 'EVENT_NINEKEY', 'EVENT_PAD0', 'EVENT_PAD1', 'EVENT_PAD2', 'EVENT_PAD3', 'EVENT_PAD4', 'EVENT_PAD5', 'EVENT_PAD6', 'EVENT_PAD7', 'EVENT_PAD8', 'EVENT_PAD9', 'EVENT_PADASTER', 'EVENT_PADSLASH', 'EVENT_PADMINUS', 'EVENT_PADENTER', 'EVENT_PADPLUS', 'EVENT_PADPERIOD', 'EVENT_MOUSE_4', 'EVENT_MOUSE_5', 'EVENT_MOUSE_6', 'EVENT_MOUSE_7', 'EVENT_TABLET_STYLUS', 'EVENT_TABLET_ERASER', 'EVENT_LEFT_ARROW', 'EVENT_DOWN_ARROW', 'EVENT_RIGHT_ARROW', 'EVENT_UP_ARROW', 'EVENT_PAUSE', 'EVENT_INSERT', 'EVENT_HOME', 'EVENT_END', 'EVENT_UNKNOWN', 'EVENT_GRLESS', 'EVENT_MEDIAPLAY', 'EVENT_MEDIASTOP', 'EVENT_MEDIAFIRST', 'EVENT_MEDIALAST', 'EVENT_APP', 'EVENT_CAPSLOCK', 'EVENT_BACKSPACE', 'EVENT_DEL', 'EVENT_SEMICOLON', 'EVENT_PERIOD', 'EVENT_COMMA', 'EVENT_QUOTE', 'EVENT_ACCENTGRAVE', 'EVENT_MINUS', 'EVENT_PLUS', 'EVENT_SLASH', 'EVENT_BACKSLASH', 'EVENT_EQUAL', 'EVENT_LEFTBRACKET', 'EVENT_RIGHTBRACKET', 'EVENT_PAD_PAN', 'EVENT_PAD_ROTATE', 'EVENT_PAD_ZOOM', 'EVENT_NDOF_BUTTON_V1', 'EVENT_NDOF_BUTTON_V2', 'EVENT_NDOF_BUTTON_V3', 'EVENT_NDOF_BUTTON_SAVE_V1', 'EVENT_NDOF_BUTTON_SAVE_V2', 'EVENT_NDOF_BUTTON_SAVE_V3', 'EVENT_NDOF_BUTTON_1', 'EVENT_NDOF_BUTTON_2', 'EVENT_NDOF_BUTTON_3', 'EVENT_NDOF_BUTTON_4', 'EVENT_NDOF_BUTTON_5', 'EVENT_NDOF_BUTTON_6', 'EVENT_NDOF_BUTTON_7', 'EVENT_NDOF_BUTTON_8', 'EVENT_NDOF_BUTTON_9', 'EVENT_NDOF_BUTTON_10', 'EVENT_NDOF_BUTTON_11', 'EVENT_NDOF_BUTTON_12', 'EVENT_NDOF_BUTTON_MENU', 'EVENT_NDOF_BUTTON_FIT', 'EVENT_NDOF_BUTTON_TOP', 'EVENT_NDOF_BUTTON_BOTTOM', 'EVENT_NDOF_BUTTON_LEFT', 'EVENT_NDOF_BUTTON_RIGHT', 'EVENT_NDOF_BUTTON_FRONT', 'EVENT_NDOF_BUTTON_BACK', 'EVENT_NDOF_BUTTON_ISO1', 'EVENT_NDOF_BUTTON_ISO2', 'EVENT_NDOF_BUTTON_ROLL_CW', 'EVENT_NDOF_BUTTON_ROLL_CCW', 'EVENT_NDOF_BUTTON_SPIN_CW', 'EVENT_NDOF_BUTTON_SPIN_CCW', 'EVENT_NDOF_BUTTON_TILT_CW', 'EVENT_NDOF_BUTTON_TILT_CCW', 'EVENT_NDOF_BUTTON_ROTATE', 'EVENT_NDOF_BUTTON_PANZOOM', 'EVENT_NDOF_BUTTON_DOMINANT', 'EVENT_NDOF_BUTTON_PLUS', 'EVENT_NDOF_BUTTON_MINUS', 'NODE_SOCKET_FLOAT', 'NODE_SOCKET_VECTOR', 'NODE_SOCKET_RGBA', 'NODE_SOCKET_SHADER', 'NODE_SOCKET_BOOLEAN', 'NODE_SOCKET_INT', 'NODE_SOCKET_STRING', 'NODE_SOCKET_OBJECT', 'NODE_SOCKET_IMAGE', 'NODE_SOCKET_GEOMETRY', 'NODE_SOCKET_COLLECTION', 'NODE_SOCKET_TEXTURE', 'NODE_SOCKET_MATERIAL', 'NODE_SOCKET_ROTATION', 'NODE_SOCKET_MENU', 'NODE_SOCKET_MATRIX', 'NODE_SOCKET_BUNDLE', 'NODE_SOCKET_CLOSURE'
    ]

    col = layout.column()
    for icon in all_icons:
        try:
            col.label(text=icon, icon=icon)
        except TypeError as e:
            print(f"Icon '{icon}' not found.")