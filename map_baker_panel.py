import bpy

class MapBakerPanel(bpy.types.Panel):
    bl_idname      = "IMAGE_EDITOR_PT_map_baker"
    bl_label       = "Map Baker"
    bl_space_type  = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category    = bl_label
    
    def draw(self, context):
        mb = context.scene.map_baker
        
        column = self.layout.column(heading="Maps To Bake:")
        column.prop(mb, "use_diffuse")
        column.prop(mb, "use_orm")
        column.prop(mb, "use_emission")
        column.split()
        column.label(text="Output Settings:")
        column.prop(mb, "save_diffuse_alpha")
        column.prop(mb, "save_dir")

        row = column.row()
        row.prop(mb, "width")
        row.prop(mb, "height")

        column.prop(mb, "samples")
        column.operator("map_baker.bake_maps", icon='OUTPUT')
        
def register():
    bpy.utils.register_class(MapBakerPanel)
    
def unregister():
    bpy.utils.unregister_class(MapBakerPanel)