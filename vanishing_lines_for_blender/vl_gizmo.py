import bpy
import math
from mathutils import Vector, Matrix
from bpy.types import Operator, Gizmo, GizmoGroup
from bpy.props import FloatVectorProperty, BoolProperty

# ------------------------------------------------------------
# Scene / WM properties
# ------------------------------------------------------------
bpy.types.Scene.line_a = FloatVectorProperty(
    name="Line A", size=2, default=(200.0, 200.0)
)
bpy.types.Scene.line_b = FloatVectorProperty(
    name="Line B", size=2, default=(400.0, 300.0)
)
bpy.types.WindowManager.my_modal_running = BoolProperty(default=False)

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def midpoint(a, b):
    return ((a[0]+b[0])*0.5, (a[1]+b[1])*0.5)

# ------------------------------------------------------------
# Custom Dot Gizmo
# ------------------------------------------------------------
class MY_GT_dot(Gizmo):
    bl_idname = "MY_GT_dot"

    def setup(self):
        # tiny sphere for handle
        self.shape = self.new_custom_shape('SPHERE', [(0,0,0)])
        self.scale_basis = 0.03

    def draw(self, context):
        # position handled by matrix_basis
        self.draw_custom_shape(self.shape)

    def test_select(self, context, location):
        return -1

# ------------------------------------------------------------
# Line Gizmo
# ------------------------------------------------------------
class MY_GT_line_2d(Gizmo):
    bl_idname = "MY_GT_line_2d"

    def setup(self):
        # line from (0,0,0) to (1,0,0)
        self.shape = self.new_custom_shape('LINES', [(0,0,0),(1,0,0)])

    def draw(self, context):
        a = context.scene.line_a
        b = context.scene.line_b
        a_vec = Vector((a[0], a[1], 0))
        b_vec = Vector((b[0], b[1], 0))
        delta = b_vec - a_vec
        length = delta.length
        angle = math.atan2(delta.y, delta.x)

        rot = Matrix.Rotation(angle, 4, 'Z')
        scale = Matrix.Scale(length, 4, Vector((1,0,0)))
        self.matrix_basis = Matrix.Translation(a_vec) @ rot @ scale

        self.draw_custom_shape(self.shape)

    def test_select(self, context, location):
        return -1

# ------------------------------------------------------------
# Gizmo Group
# ------------------------------------------------------------
class MY_GGT_line_segment_2d(GizmoGroup):
    bl_idname = "MY_GGT_line_segment_2d"
    bl_label = "2D Line Segment Gizmo"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D'}

    @classmethod
    def poll(cls, context):
        return context.window_manager.my_modal_running

    def setup(self, context):
        scene = context.scene

        # --- Line ---
        self.line = self.gizmos.new("MY_GT_line_2d")
        self.line.color = (1,1,1)
        self.line.alpha = 0.8

        # --- Endpoint A ---
        a = self.gizmos.new("MY_GT_dot")
        a.color = (0.2,0.8,1.0)
        a.scale_basis = 8

        def get_a_matrix():
            return Matrix.Translation(Vector((scene.line_a[0], scene.line_a[1], 0)))
        def set_a_matrix(mtx):
            t = mtx.to_translation()
            scene.line_a = (t.x, t.y)
        a.target_set_handler("matrix_basis", get=get_a_matrix, set=set_a_matrix)

        # --- Endpoint B ---
        b = self.gizmos.new("MY_GT_dot")
        b.color = (1.0,0.4,0.4)
        b.scale_basis = 8

        def get_b_matrix():
            return Matrix.Translation(Vector((scene.line_b[0], scene.line_b[1], 0)))
        def set_b_matrix(mtx):
            t = mtx.to_translation()
            scene.line_b = (t.x, t.y)
        b.target_set_handler("matrix_basis", get=get_b_matrix, set=set_b_matrix)

        # --- Midpoint ---
        m = self.gizmos.new("MY_GT_dot")
        m.color = (1.0,1.0,0.2)
        m.scale_basis = 10
        self._mid_cache = (0.0,0.0)

        def get_mid_matrix():
            mid = midpoint(scene.line_a, scene.line_b)
            return Matrix.Translation(Vector((mid[0], mid[1], 0)))

        def set_mid_matrix(mtx):
            t = mtx.to_translation()
            dx = t.x - self._mid_cache[0]
            dy = t.y - self._mid_cache[1]
            scene.line_a = (scene.line_a[0]+dx, scene.line_a[1]+dy)
            scene.line_b = (scene.line_b[0]+dx, scene.line_b[1]+dy)

        m.target_set_handler("matrix_basis", get=get_mid_matrix, set=set_mid_matrix)

        self.a = a
        self.b = b
        self.m = m

    def refresh(self, context):
        if not hasattr(self, "a"):
            return

        scene = context.scene
        a = scene.line_a
        b = scene.line_b
        mid = midpoint(a,b)

        self.a.matrix_basis.translation = Vector((a[0],a[1],0))
        self.b.matrix_basis.translation = Vector((b[0],b[1],0))
        self.m.matrix_basis.translation = Vector((mid[0],mid[1],0))

        self._mid_cache = mid

# ------------------------------------------------------------
# Modal Operator
# ------------------------------------------------------------
class MY_OT_modal_line_tool(Operator):
    bl_idname = "my.modal_line_tool"
    bl_label = "Modal Line Tool"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.my_modal_running = True
        wm.gizmo_group_type_ensure("MY_GGT_line_segment_2d")
        wm.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'ESC','RIGHTMOUSE'}:
            return self.cancel(context)
        if event.type in {'RET','LEFTMOUSE'}:
            return self.finish(context)
        return {'RUNNING_MODAL'}

    def finish(self, context):
        self._disable(context)
        return {'FINISHED'}

    def cancel(self, context):
        self._disable(context)
        return {'CANCELLED'}

    def _disable(self, context):
        wm = context.window_manager
        wm.my_modal_running = False
        wm.gizmo_group_type_unlink_delayed("MY_GGT_line_segment_2d")
        context.area.tag_redraw()

# ------------------------------------------------------------
# Register
# ------------------------------------------------------------
classes = (
    MY_GT_dot,
    MY_GT_line_2d,
    MY_GGT_line_segment_2d,
    MY_OT_modal_line_tool,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)

def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
