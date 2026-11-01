bl_info = {
    "name": "Smear Generator",
    "author": "Claude",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "3D Viewport > N Panel > Smear",
    "description": "Generates a Smear plane driven by a simulation-zone geometry nodes setup",
    "category": "Object",
}

import bpy


def build_smear_group(target_obj):
    tree = bpy.data.node_groups.new("Smear", "GeometryNodeTree")
    nodes = tree.nodes
    links = tree.links

    # ---------------- Interface ----------------
    iface = tree.interface
    iface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    drag = iface.new_socket("Drag", in_out='INPUT', socket_type='NodeSocketFloat')
    drag.default_value = 1.0
    zfight = iface.new_socket("Zfighting", in_out='INPUT', socket_type='NodeSocketFloat')
    zfight.default_value = 0.12
    lifetime = iface.new_socket("Lifetime", in_out='INPUT', socket_type='NodeSocketFloat')
    lifetime.default_value = 0.5      # seconds a duplicate lives
    spawn_speed = iface.new_socket("Spawn Speed", in_out='INPUT', socket_type='NodeSocketFloat')
    spawn_speed.default_value = 0.05  # duplicates only spawn on points moving faster than this per frame
    stretch_in = iface.new_socket("Stretch", in_out='INPUT', socket_type='NodeSocketFloat')
    stretch_in.default_value = 2.0    # how far duplicates are smeared along the motion
    iface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    iface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    def N(idname, x, y, label=None):
        node = nodes.new(idname)
        node.location = (x, -y)
        if label:
            node.label = label
        return node

    L = lambda a, b: links.new(a, b)

    def sk(node, name, side="inputs"):
        """Return the currently enabled socket with this name (type-dependent sockets share names)."""
        socks = getattr(node, side)
        for s in socks:
            if s.name == name and getattr(s, "enabled", True):
                return s
        return socks[name]

    # ---------------- Object Info (start of the nodes) ----------------
    obj_info = N("GeometryNodeObjectInfo", 0, 460)
    obj_info.transform_space = 'RELATIVE'
    obj_info.inputs["Object"].default_value = target_obj
    obj_info.inputs["As Instance"].default_value = False

    # ---------------- Simulation zone ----------------
    sim_in = N("GeometryNodeSimulationInput", 205, 415)
    sim_out = N("GeometryNodeSimulationOutput", 495, 430)
    sim_in.pair_with_output(sim_out)
    sim_out.state_items.new('GEOMETRY', "Trails")   # second state: the spawned duplicates

    pos_sim = N("GeometryNodeInputPosition", 205, 465)

    store = N("GeometryNodeStoreNamedAttribute", 295, 415)
    store.data_type = 'FLOAT_VECTOR'
    store.domain = 'POINT'
    store.inputs["Name"].default_value = "prev-position"

    setpos1 = N("GeometryNodeSetPosition", 395, 450)

    # ---------------- Sample Index ----------------
    sample = N("GeometryNodeSampleIndex", 248, 525)
    sample.data_type = 'FLOAT_VECTOR'
    sample.domain = 'POINT'
    sample.clamp = False

    pos_sample = N("GeometryNodeInputPosition", 152, 607)
    index_node = N("GeometryNodeInputIndex", 152, 638)

    # ---------------- Velocity / direction math ----------------
    named_attr = N("GeometryNodeInputNamedAttribute", 307, 198)
    named_attr.data_type = 'FLOAT_VECTOR'
    named_attr.inputs["Name"].default_value = "prev-position"

    pos_top = N("GeometryNodeInputPosition", 305, 264)

    subtract = N("ShaderNodeVectorMath", 441, 208)
    subtract.operation = 'SUBTRACT'

    normalize = N("ShaderNodeVectorMath", 546, 227)
    normalize.operation = 'NORMALIZE'

    normal1 = N("GeometryNodeInputNormal", 537, 318)

    dot = N("ShaderNodeVectorMath", 648, 234)
    dot.operation = 'DOT_PRODUCT'

    scale1 = N("ShaderNodeVectorMath", 748, 164)
    scale1.operation = 'SCALE'

    greater = N("FunctionNodeCompare", 748, 237)
    greater.data_type = 'FLOAT'
    greater.operation = 'GREATER_THAN'

    length = N("ShaderNodeVectorMath", 659, 401)
    length.operation = 'LENGTH'

    less = N("FunctionNodeCompare", 751, 383)
    less.data_type = 'FLOAT'
    less.operation = 'LESS_THAN'
    less.inputs[1].default_value = 0.001

    # ---------------- Noise ----------------
    noise = N("ShaderNodeTexNoise", 840, 221)
    noise.noise_dimensions = '3D'
    noise.noise_type = 'FBM'
    noise.normalize = True
    noise.inputs["Scale"].default_value = 5.0
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.5
    noise.inputs["Lacunarity"].default_value = 2.0
    noise.inputs["Distortion"].default_value = 0.0

    power = N("ShaderNodeMath", 958, 201)
    power.operation = 'POWER'
    power.use_clamp = False
    power.inputs[1].default_value = 5.0

    scale2 = N("ShaderNodeVectorMath", 1067, 156)
    scale2.operation = 'SCALE'

    scale3 = N("ShaderNodeVectorMath", 1201, 146)
    scale3.operation = 'SCALE'

    # ---------------- Delete + Set Positions ----------------
    delete = N("GeometryNodeDeleteGeometry", 863, 448)
    delete.domain = 'POINT'
    delete.mode = 'ALL'

    setpos2 = N("GeometryNodeSetPosition", 1155, 470)
    setpos3 = N("GeometryNodeSetPosition", 1371, 474)

    normal2 = N("GeometryNodeInputNormal", 1197, 570)
    scale4 = N("ShaderNodeVectorMath", 1263, 585)
    scale4.operation = 'SCALE'
    scale4.inputs[3].default_value = 0.001

    # ---------------- Group in / out ----------------
    group_in = N("NodeGroupInput", 968, 397)
    group_out_unused = N("NodeGroupOutput", 1103, 398)
    group_out = N("NodeGroupOutput", 1495, 418)
    group_out.is_active_output = True
    group_out_unused.is_active_output = False

    # ---------------- Duplicates / trails (inside the simulation) ----------------
    # age the existing duplicates, then delete the ones older than Lifetime
    age_in = N("GeometryNodeInputNamedAttribute", 150, 720)
    age_in.data_type = 'FLOAT'
    age_in.inputs["Name"].default_value = "age"

    age_add = N("ShaderNodeMath", 300, 720)
    age_add.operation = 'ADD'

    store_age = N("GeometryNodeStoreNamedAttribute", 450, 720)
    store_age.data_type = 'FLOAT'
    store_age.domain = 'POINT'
    store_age.inputs["Name"].default_value = "age"

    age_old = N("FunctionNodeCompare", 450, 880)
    age_old.data_type = 'FLOAT'
    age_old.operation = 'GREATER_THAN'

    del_old = N("GeometryNodeDeleteGeometry", 640, 720)
    del_old.domain = 'POINT'
    del_old.mode = 'ALL'

    # spawn a new duplicate from the points that are moving fast
    prev_in = N("GeometryNodeInputNamedAttribute", 150, 960)
    prev_in.data_type = 'FLOAT_VECTOR'
    prev_in.inputs["Name"].default_value = "prev-position"

    pos_in = N("GeometryNodeInputPosition", 150, 1030)

    sub_in = N("ShaderNodeVectorMath", 300, 960)
    sub_in.operation = 'SUBTRACT'

    len_in = N("ShaderNodeVectorMath", 450, 960)
    len_in.operation = 'LENGTH'

    slow = N("FunctionNodeCompare", 600, 960)
    slow.data_type = 'FLOAT'
    slow.operation = 'LESS_THAN'

    del_slow = N("GeometryNodeDeleteGeometry", 760, 960)
    del_slow.domain = 'POINT'
    del_slow.mode = 'ALL'

    store_age0 = N("GeometryNodeStoreNamedAttribute", 920, 960)
    store_age0.data_type = 'FLOAT'
    store_age0.domain = 'POINT'
    store_age0.inputs["Name"].default_value = "age"
    sk(store_age0, "Value").default_value = 0.0

    store_vel = N("GeometryNodeStoreNamedAttribute", 1080, 960)
    store_vel.data_type = 'FLOAT_VECTOR'
    store_vel.domain = 'POINT'
    store_vel.inputs["Name"].default_value = "velocity"

    join_trails = N("GeometryNodeJoinGeometry", 1240, 860)

    # ---------------- Duplicates / trails (stretch + output) ----------------
    vel_out = N("GeometryNodeInputNamedAttribute", 640, 1150)
    vel_out.data_type = 'FLOAT_VECTOR'
    vel_out.inputs["Name"].default_value = "velocity"

    vel_norm = N("ShaderNodeVectorMath", 800, 1150)
    vel_norm.operation = 'NORMALIZE'

    normal_t = N("GeometryNodeInputNormal", 800, 1260)

    dot_t = N("ShaderNodeVectorMath", 960, 1180)
    dot_t.operation = 'DOT_PRODUCT'

    gt_t = N("FunctionNodeCompare", 1110, 1180)
    gt_t.data_type = 'FLOAT'
    gt_t.operation = 'GREATER_THAN'
    gt_t.inputs[1].default_value = 0.0

    age_out = N("GeometryNodeInputNamedAttribute", 640, 1380)
    age_out.data_type = 'FLOAT'
    age_out.inputs["Name"].default_value = "age"

    div_t = N("ShaderNodeMath", 800, 1380)
    div_t.operation = 'DIVIDE'
    div_t.use_clamp = True

    inv_t = N("ShaderNodeMath", 950, 1380)
    inv_t.operation = 'SUBTRACT'
    inv_t.inputs[0].default_value = 1.0

    mul_t = N("ShaderNodeMath", 1100, 1380)
    mul_t.operation = 'MULTIPLY'

    scale_t = N("ShaderNodeVectorMath", 1250, 1300)
    scale_t.operation = 'SCALE'

    setpos_t = N("GeometryNodeSetPosition", 1400, 1180)

    join_out = N("GeometryNodeJoinGeometry", 1560, 480)

    # ---------------- Links ----------------
    L(obj_info.outputs["Geometry"], sim_in.inputs["Geometry"])
    L(obj_info.outputs["Geometry"], sample.inputs["Geometry"])
    L(pos_sample.outputs["Position"], sample.inputs["Value"])
    L(index_node.outputs["Index"], sample.inputs["Index"])

    L(sim_in.outputs["Geometry"], store.inputs["Geometry"])
    L(pos_sim.outputs["Position"], store.inputs["Value"])
    L(sample.outputs[0], setpos1.inputs["Position"])
    L(store.outputs["Geometry"], setpos1.inputs["Geometry"])
    L(setpos1.outputs["Geometry"], sim_out.inputs["Geometry"])
    L(sim_out.outputs["Geometry"], delete.inputs["Geometry"])

    L(named_attr.outputs["Attribute"], subtract.inputs[0])
    L(pos_top.outputs["Position"], subtract.inputs[1])
    L(subtract.outputs[0], normalize.inputs[0])
    L(subtract.outputs[0], length.inputs[0])
    L(subtract.outputs[0], scale1.inputs[0])

    L(normalize.outputs[0], dot.inputs[0])
    L(normal1.outputs["Normal"], dot.inputs[1])
    L(dot.outputs[1], greater.inputs[0])
    L(group_in.outputs["Zfighting"], greater.inputs[1])
    L(greater.outputs[0], scale1.inputs[3])

    L(length.outputs[1], less.inputs[0])
    L(less.outputs[0], delete.inputs["Selection"])

    L(noise.outputs["Fac"], power.inputs[0])
    L(power.outputs[0], scale2.inputs[3])
    L(scale1.outputs[0], scale2.inputs[0])
    L(scale2.outputs[0], scale3.inputs[0])
    L(group_in.outputs["Drag"], scale3.inputs[3])
    L(scale3.outputs[0], setpos2.inputs["Offset"])

    L(delete.outputs["Geometry"], setpos2.inputs["Geometry"])
    L(setpos2.outputs["Geometry"], setpos3.inputs["Geometry"])
    L(normal2.outputs["Normal"], scale4.inputs[0])
    L(scale4.outputs[0], setpos3.inputs["Offset"])

    # --- trails: age + delete old ---
    L(sim_in.outputs["Trails"], store_age.inputs["Geometry"])
    L(age_in.outputs["Attribute"], age_add.inputs[0])
    L(sim_in.outputs["Delta Time"], age_add.inputs[1])
    L(age_add.outputs[0], sk(store_age, "Value"))
    L(age_in.outputs["Attribute"], age_old.inputs[0])
    L(group_in.outputs["Lifetime"], age_old.inputs[1])
    L(store_age.outputs["Geometry"], del_old.inputs["Geometry"])
    L(age_old.outputs[0], del_old.inputs["Selection"])

    # --- trails: spawn a duplicate from fast-moving points ---
    L(prev_in.outputs["Attribute"], sub_in.inputs[0])
    L(pos_in.outputs["Position"], sub_in.inputs[1])
    L(sub_in.outputs[0], len_in.inputs[0])
    L(len_in.outputs[1], slow.inputs[0])
    L(group_in.outputs["Spawn Speed"], slow.inputs[1])
    L(setpos1.outputs["Geometry"], del_slow.inputs["Geometry"])
    L(slow.outputs[0], del_slow.inputs["Selection"])
    L(del_slow.outputs["Geometry"], store_age0.inputs["Geometry"])
    L(store_age0.outputs["Geometry"], store_vel.inputs["Geometry"])
    L(sub_in.outputs[0], sk(store_vel, "Value"))

    L(del_old.outputs["Geometry"], join_trails.inputs[0])
    L(store_vel.outputs["Geometry"], join_trails.inputs[0])
    L(join_trails.outputs["Geometry"], sim_out.inputs["Trails"])

    # --- trails: stretch + output ---
    L(vel_out.outputs["Attribute"], vel_norm.inputs[0])
    L(vel_norm.outputs[0], dot_t.inputs[0])
    L(normal_t.outputs["Normal"], dot_t.inputs[1])
    L(dot_t.outputs[1], gt_t.inputs[0])

    L(age_out.outputs["Attribute"], div_t.inputs[0])
    L(group_in.outputs["Lifetime"], div_t.inputs[1])
    L(div_t.outputs[0], inv_t.inputs[1])
    L(inv_t.outputs[0], mul_t.inputs[0])
    L(group_in.outputs["Stretch"], mul_t.inputs[1])
    L(vel_out.outputs["Attribute"], scale_t.inputs[0])
    L(mul_t.outputs[0], scale_t.inputs[3])

    L(sim_out.outputs["Trails"], setpos_t.inputs["Geometry"])
    L(gt_t.outputs[0], setpos_t.inputs["Selection"])
    L(scale_t.outputs[0], setpos_t.inputs["Offset"])

    L(setpos3.outputs["Geometry"], join_out.inputs[0])
    L(setpos_t.outputs["Geometry"], join_out.inputs[0])
    L(join_out.outputs["Geometry"], group_out.inputs[0])

    L(group_in.outputs["Geometry"], group_out_unused.inputs[0])

    return tree


class SMEAR_OT_generate(bpy.types.Operator):
    bl_idname = "smear.generate"
    bl_label = "Smear Generate"
    bl_description = "Create a plane with the Smear geometry nodes, using the selected object as the Object Info"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target = context.active_object
        if target is None:
            self.report({'ERROR'}, "Select an object first")
            return {'CANCELLED'}

        tree = build_smear_group(target)

        bpy.ops.mesh.primitive_plane_add(location=target.location)
        plane = context.active_object
        plane.name = "Smear"

        # Put the plane in the same collection(s) as the object it smears
        target_colls = list(target.users_collection)
        if target_colls:
            for c in list(plane.users_collection):
                c.objects.unlink(plane)
            for c in target_colls:
                c.objects.link(plane)
        mod = plane.modifiers.new("Smear", 'NODES')
        mod.node_group = tree

        self.report({'INFO'}, f"Smear created from '{target.name}'")
        return {'FINISHED'}


class SMEAR_PT_panel(bpy.types.Panel):
    bl_label = "Smear"
    bl_idname = "SMEAR_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Smear"   # shows up as its own tab in the N menu, like "Item"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        layout.label(text=f"Target: {obj.name}" if obj else "Select an object")
        layout.operator("smear.generate", icon='MOD_PHYSICS')


classes = (SMEAR_OT_generate, SMEAR_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
