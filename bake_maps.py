import bpy
import os

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
    old_color_management:str
    old_display_device:str
    old_view_transform:str
    old_look:str
    old_exposure:float
    old_gamma:float
    old_use_curve_mapping:bool
    
    def invoke(self, context, event):
        if not self.try_init(context):
            return {'FINISHED'}
        
        mb = context.scene.map_baker
        abs_save_dir = bpy.path.abspath(mb.save_dir)
        
        if mb.use_diffuse:       
            context.scene.render.image_settings.color_mode = 'RGBA' if mb.save_diffuse_alpha else 'RGB' 
            context.scene.display_settings.display_device = 'sRGB'
            
            img = self.bake(context, 'DIFFUSE')
            img.save_render(filepath=os.path.join(abs_save_dir, "Albedo.png"))
            
            bpy.data.images.remove(img)
            
        if mb.use_orm:
            context.scene.render.image_settings.color_mode = 'RGB'
            context.scene.display_settings.display_device = 'None'
            
            img_ao = self.bake(context, 'AO')
            img_r  = self.bake(context, 'ROUGHNESS')
            img_m  = self.bake(context, 'GLOSSY')
            
            # Convert To List & Tuples First As It's Much Faster #
            img_ao_pixels = list(img_ao.pixels) # List  = Writable
            img_r_pixels  = img_r.pixels[:]     # Tuple = Read-only
            img_m_pixels  = img_m.pixels[:]
            
            # Insert Maps Into Each Channel #
            STEP = 4
            for i in range(0, len(img_ao_pixels), STEP):
                img_ao_pixels[i:i+STEP] = (img_ao_pixels[i], img_r_pixels[i], img_m_pixels[i], 1.0)
                
            img_ao.pixels = img_ao_pixels[:]
            img_ao.save_render(filepath=os.path.join(abs_save_dir, "ORM.png"))
            #
            
            bpy.data.images.remove(img_ao)
            bpy.data.images.remove(img_r)
            bpy.data.images.remove(img_m)
            
        if mb.use_emission:
            context.scene.render.image_settings.color_mode = 'BW'
            context.scene.display_settings.display_device = 'None'
                      
            img = self.bake(context, 'EMIT')
            img.save_render(filepath=os.path.join(abs_save_dir, "Emission.png"))
            
            bpy.data.images.remove(img)
        
        self.show_message_box(context, "Done", "{0} has been baked to {1}".format(context.active_object.name, abs_save_dir))
        
        self.reset(context)
        
        return {'FINISHED'}
    
    def try_init(self, context) -> bool:
        if context.active_object is None:
            self.show_message_box(context, "Error", "No object is selected", 'ERROR')
            return False
        
        if context.active_object.data.uv_layers.active is None:
            self.show_message_box(context, "Error", "No UV layer is selected", 'ERROR')
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
        context.scene.cycles.samples                = 1
        context.scene.cycles.use_denoising          = False
        
        # Store & Set Output Properties #
        self.old_file_format       = context.scene.render.image_settings.file_format
        self.old_color_mode        = context.scene.render.image_settings.color_mode
        self.old_color_depth       = context.scene.render.image_settings.color_depth
        self.old_compression       = context.scene.render.image_settings.compression
        self.old_color_management  = context.scene.render.image_settings.color_management
        self.old_display_device    = context.scene.display_settings.display_device
        self.old_view_transform    = context.scene.view_settings.view_transform
        self.old_look              = context.scene.view_settings.look
        self.old_exposure          = context.scene.view_settings.exposure
        self.old_gamma             = context.scene.view_settings.gamma
        self.old_use_curve_mapping = context.scene.view_settings.use_curve_mapping
        
        context.scene.render.image_settings.file_format      = 'PNG'
        #context.scene.render.image_settings.color_mode      = <IsSetLater>
        context.scene.render.image_settings.color_depth      = '8'
        context.scene.render.image_settings.compression      = 100
        context.scene.render.image_settings.color_management = 'OVERRIDE'
        #context.scene.display_settings.display_device       = <IsSetLater>
        context.scene.view_settings.view_transform           = 'Standard'
        context.scene.view_settings.look                     = 'None'
        context.scene.view_settings.exposure                 = 0.0
        context.scene.view_settings.gamma                    = 1.0
        context.scene.view_settings.use_curve_mapping        = False
        
        return True
    
    def bake(self, context, map_type:str) -> bpy.types.Image:
        img = bpy.data.images.new \
        (
            context.active_object.name + "_BakedTexture",
            context.scene.map_baker.width,
            context.scene.map_baker.height
        )
        
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
        context.scene.render.image_settings.file_format      = self.old_file_format
        context.scene.render.image_settings.color_mode       = self.old_color_mode
        context.scene.render.image_settings.color_depth      = self.old_color_depth
        context.scene.render.image_settings.compression      = self.old_compression
        context.scene.render.image_settings.color_management = self.old_color_management
        context.scene.display_settings.display_device        = self.old_display_device
        context.scene.view_settings.view_transform           = self.old_view_transform
        context.scene.view_settings.look                     = self.old_look
        context.scene.view_settings.exposure                 = self.old_exposure
        context.scene.view_settings.gamma                    = self.old_gamma
        context.scene.view_settings.use_curve_mapping        = self.old_use_curve_mapping
        
    def show_message_box(self, context, title="Message Box", text="", icon='INFO'):

        def draw(self, context):
            self.layout.label(text=text)

        context.window_manager.popup_menu(draw, title=title, icon=icon)
        
def register():
    bpy.utils.register_class(BakeMaps)

def unregister():
    bpy.utils.unregister_class(BakeMaps)