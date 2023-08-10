import bpy
import os
import time
import numpy as np

class BakeMaps(bpy.types.Operator):
    NODE_NAME:str = "BakeNode"
    
    bl_idname      = "map_baker.bake_maps"
    bl_label       = "Bake Maps"
    bl_description = "Bake & save each individual map that is ticked.\nUses the currently selected object & UV layer"
       
    # Render Properties #
    old_direct:bool
    old_indirect:bool
    old_render_engine:str
    old_adpt_sampling:bool
    old_samples:int
    old_use_denoising:bool
    
    # Output Properties #
    old_file_format:str
    old_color_mode:str
    old_color_depth:str
    old_compression:int
    
    combine_channels = np.vectorize(lambda ao, r, m: (ao, r, m, 1.0), [tuple])

    def invoke(self, context, event):
        if not self.try_init(context):
            return {'FINISHED'}
        
        mb = context.scene.map_baker
        abs_save_dir = bpy.path.abspath(mb.save_dir)
        
        if mb.use_diffuse:                 
           # Store & Set Metallic Value To 0 #
            input_oldVal_s:list[tuple[any, float]] = []
            for mat in context.active_object.data.materials:            
                input = mat.node_tree.nodes["Principled BSDF"].inputs[6] # Metallic Index == 6
             
                input_oldVal_s.append((input, input.default_value))
                input.default_value = 0.0

            # Bake & Save #
            img = self.bake(context, 'DIFFUSE')

            context.scene.render.image_settings.color_mode = 'RGBA' if mb.save_diffuse_alpha else 'RGB'
            img.save_render(filepath=os.path.join(abs_save_dir, "Albedo.png"))

            # Reset Metallic Value #
            for input_oldVal in input_oldVal_s:
                input_oldVal[0].default_value = input_oldVal[1]
            #

            bpy.data.images.remove(img)
        
        if mb.use_orm:
            img_ao = self.bake(context, 'AO'       , 'Non-Color')
            img_r  = self.bake(context, 'ROUGHNESS', 'Non-Color')
            img_m  = self.bake(context, 'GLOSSY'   , 'Non-Color')
            
            # Insert Map Into Each RGB Colour Channel #
            every_4th = slice(None, None, 4)
            pixels = self.combine_channels(img_ao.pixels[:][every_4th], img_r.pixels[:][every_4th], img_m.pixels[:][every_4th])
            img_ao.pixels = [x for t in pixels for x in t] # List of tuple[float * 4] -> List of float
            
            # Save #
            context.scene.render.image_settings.color_mode = 'RGB'
            img_ao.save_render(filepath=os.path.join(abs_save_dir, "ORM.png"))
            #

            bpy.data.images.remove(img_ao)
            bpy.data.images.remove(img_r)
            bpy.data.images.remove(img_m)
            
        if mb.use_emission:
            img = self.bake(context, 'EMIT', 'Non-Color')

            context.scene.render.image_settings.color_mode = 'BW'
            img.save_render(filepath=os.path.join(abs_save_dir, "Emission.png"))
            
            bpy.data.images.remove(img)
        
        self.show_message_box(context, "Done", "{0} has been baked to {1}".format(context.active_object.name, abs_save_dir))    
        self.reset(context)
        
        return {'FINISHED'}
    
    def try_init(self, context) -> bool:
        if len(context.selected_objects) == 0:
            self.show_message_box(context, "Error", "No object is selected", 'ERROR')
            return False
        
        if context.active_object.data.uv_layers.active is None:
            self.show_message_box(context, "Error", "No UV map/layer is selected", 'ERROR')
            return False

        if not os.path.isdir(bpy.path.abspath(context.scene.map_baker.save_dir)):
            self.show_message_box(context, "Error", "Save directory is invalid", 'ERROR')
            return False
        
        context.view_layer.objects.active = context.active_object
        
        # Create ImageTexture Nodes #
        for mat in context.active_object.data.materials:
            mat.use_nodes = True          
            nodes = mat.node_tree.nodes
            
            texture_node = nodes.new("ShaderNodeTexImage")
            texture_node.name = self.NODE_NAME
            texture_node.select = True       
            
            nodes.active = texture_node
        
        # Store & Set Render Properties #
        self.old_render_engine = context.scene.render.engine
        self.old_direct        = context.scene.render.bake.use_pass_direct
        self.old_indirect      = context.scene.render.bake.use_pass_indirect      
        self.old_adpt_sampling = context.scene.cycles.use_adaptive_sampling
        self.old_samples       = context.scene.cycles.samples
        self.old_use_denoising = context.scene.cycles.use_denoising

        context.scene.render.engine                 = 'CYCLES'
        context.scene.render.bake.use_pass_direct   = False
        context.scene.render.bake.use_pass_indirect = False
        context.scene.cycles.use_adaptive_sampling  = False
        context.scene.cycles.samples                = context.scene.map_baker.samples
        context.scene.cycles.use_denoising          = False
        
        # Store & Set Output Properties #
        self.old_file_format = context.scene.render.image_settings.file_format
        self.old_color_mode  = context.scene.render.image_settings.color_mode
        self.old_color_depth = context.scene.render.image_settings.color_depth
        self.old_compression = context.scene.render.image_settings.compression
        
        context.scene.render.image_settings.file_format = 'PNG'
        #context.scene.render.image_settings.color_mode = <IsSetLater>
        context.scene.render.image_settings.color_depth = '8'
        context.scene.render.image_settings.compression = 100
        
        return True
    
    def bake(self, context, map_type:str, color_space:str='sRGB') -> bpy.types.Image:
        img = bpy.data.images.new \
        (
            context.active_object.name + "_BakedTexture",
            context.scene.map_baker.width,
            context.scene.map_baker.height
        )
        img.colorspace_settings.name = color_space

        for mat in context.active_object.data.materials:
            mat.node_tree.nodes.active.image = img
        
        bpy.ops.object.bake(type=map_type, save_mode='EXTERNAL')
        
        return img
            
    def reset(self, context):
        for mat in context.active_object.data.materials:
            mat.node_tree.nodes.remove(mat.node_tree.nodes.active)
        
        # Reset Render Properties #  
        context.scene.render.engine                 = self.old_render_engine    
        context.scene.render.bake.use_pass_direct   = self.old_direct
        context.scene.render.bake.use_pass_indirect = self.old_indirect
        context.scene.cycles.use_adaptive_sampling  = self.old_adpt_sampling
        context.scene.cycles.samples                = self.old_samples
        context.scene.cycles.use_denoising          = self.old_use_denoising
        
        # Reset Output Properties #
        context.scene.render.image_settings.file_format = self.old_file_format
        context.scene.render.image_settings.color_mode  = self.old_color_mode
        context.scene.render.image_settings.color_depth = self.old_color_depth
        context.scene.render.image_settings.compression = self.old_compression
        
    def show_message_box(self, context, title="Message Box", text="", icon='INFO'):

        def draw(self, context):
            self.layout.label(text=text)

        context.window_manager.popup_menu(draw, title=title, icon=icon)
        
def register():
    bpy.utils.register_class(BakeMaps)

def unregister():
    bpy.utils.unregister_class(BakeMaps)