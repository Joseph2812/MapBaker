import bpy

class Properties(bpy.types.PropertyGroup):
    use_diffuse: bpy.props.BoolProperty \
    (
        name        = "Diffuse",
        description = "",
        default     = True
    )
    use_orm: bpy.props.BoolProperty \
    (
        name        = "ORM",
        description = "Ambient Occlusion, Roughness, Metallic/Glossy",
        default     = True
    )
    use_emission: bpy.props.BoolProperty \
    (
        name        = "Emission",
        description = "",
        default     = False
    )
    save_diffuse_alpha: bpy.props.BoolProperty \
    (
        name        = "Save Diffuse Alpha",
        description = "Include the alpha channel when saving the diffuse/albedo map",
        default     = False
    )
    save_dir: bpy.props.StringProperty \
    (
        name        = "Save Directory",
        description = "Directory to save all the maps inside",
        default     = "",
        subtype     = 'FILE_PATH'
    )
    width: bpy.props.IntProperty \
    (
        name        = "Width",
        description = "",
        default     = 1024,
        min         = 1
    )
    height: bpy.props.IntProperty \
    (
        name        = "Height",
        description = "",
        default     = 1024,
        min         = 1
    )
    samples: bpy.props.IntProperty \
    (
        name        = "Samples",
        description = "Number of samples to render for each pixel",
        default     = 256,
        min         = 1
    )
    
def register():
    bpy.utils.register_class(Properties)       
    bpy.types.Scene.map_baker = bpy.props.PointerProperty(type=Properties)
    
def unregister():
    bpy.utils.unregister_class(Properties)
    del bpy.types.Scene.map_baker
    