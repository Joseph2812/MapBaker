import bpy
import os
import numpy as np

class BakeMaps(bpy.types.Operator):
    NODE_NAME:str = "BakeNode"
    FINISHED_SET:set[str] = {'FINISHED'}
    
    bl_idname      = "map_baker.bake_maps"
    bl_label       = "Bake Maps"
    bl_description = "Bake & save each individual map that is ticked.\nUses the currently selected object & UV layer"
       
    # Render Properties #
    __old_render_engine:str
    __old_direct:bool
    __old_indirect:bool   
    __old_adpt_sampling:bool
    __old_samples:int
    __old_use_denoising:bool

    # Output Properties #
    __old_file_format:str
    __old_color_mode:str
    __old_color_depth:str
    __old_compression:int
    #

    __combine_channels = np.vectorize(lambda ao, r, m: (ao, r, m, 1.0), [tuple])

    def invoke(self, context, event):
        if not self.__try_init(context):
            return self.FINISHED_SET
        
        mb = context.scene.map_baker
        abs_save_dir = bpy.path.abspath(mb.save_dir)
        
        if mb.use_diffuse : self.__save_diffuse (context, abs_save_dir, mb)     
        if mb.use_orm     : self.__save_orm     (context, abs_save_dir)                 
        if mb.use_emission: self.__save_emission(context, abs_save_dir)    
        if mb.use_normal  : self.__save_normal  (context, abs_save_dir)          

        self.__reset(context)
        self.__show_message_box(context, "Done", "{0} has been baked to {1}".format(context.active_object.name, abs_save_dir))
        
        return self.FINISHED_SET
    
    def __try_init(self, context) -> bool:
        if len(context.selected_objects) == 0:
            self.__show_message_box(context, "Error", "No object is selected", 'ERROR')
            return False
        
        if context.active_object.data.uv_layers.active is None:
            self.__show_message_box(context, "Error", "No UV map/layer is selected", 'ERROR')
            return False

        if not os.path.isdir(bpy.path.abspath(context.scene.map_baker.save_dir)):
            self.__show_message_box(context, "Error", "Save directory is invalid", 'ERROR')
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
        self.__old_render_engine = context.scene.render.engine
        self.__old_direct        = context.scene.render.bake.use_pass_direct
        self.__old_indirect      = context.scene.render.bake.use_pass_indirect      
        self.__old_adpt_sampling = context.scene.cycles.use_adaptive_sampling
        self.__old_samples       = context.scene.cycles.samples
        self.__old_use_denoising = context.scene.cycles.use_denoising

        context.scene.render.engine                 = 'CYCLES'
        context.scene.render.bake.use_pass_direct   = False
        context.scene.render.bake.use_pass_indirect = False
        context.scene.cycles.use_adaptive_sampling  = False
        #context.scene.cycles.samples               = <IsSetLater>
        context.scene.cycles.use_denoising          = False
        
        # Store & Set Output Properties #
        self.__old_file_format = context.scene.render.image_settings.file_format
        self.__old_color_mode  = context.scene.render.image_settings.color_mode
        self.__old_color_depth = context.scene.render.image_settings.color_depth
        self.__old_compression = context.scene.render.image_settings.compression
        
        context.scene.render.image_settings.file_format = 'PNG'
        #context.scene.render.image_settings.color_mode = <IsSetLater>
        context.scene.render.image_settings.color_depth = '8'
        context.scene.render.image_settings.compression = 100
        
        return True
    
    def __save_diffuse(self, context, abs_save_dir, map_baker):
        # Disable Metallic #
        nodeTree_metallicFrom_metallicTo_oldToVal_s:list[tuple[any, float]] = []
        for mat in context.active_object.data.materials:
            for node in mat.node_tree.nodes:
                try   : metallic_to = node.inputs["Metallic"]
                except: continue

                # Remove Metallic Link #
                metallic_from = None
                for link in mat.node_tree.links:
                    if link.to_socket == metallic_to:
                        metallic_from = link.from_socket
                        mat.node_tree.links.remove(link)
                        break
                #

                nodeTree_metallicFrom_metallicTo_oldToVal_s.append((mat.node_tree, metallic_from, metallic_to, metallic_to.default_value))
                metallic_to.default_value = 0.0

        # Bake & Save #
        img = self.__bake(context, 'DIFFUSE')

        context.scene.render.image_settings.color_mode = 'RGBA' if map_baker.save_diffuse_alpha else 'RGB'
        img.save_render(filepath=os.path.join(abs_save_dir, "Albedo.png"))

        bpy.data.images.remove(img)

        # Reset Metallic Connection & Value #
        for node_tree, m_from, m_to, old_to_val in nodeTree_metallicFrom_metallicTo_oldToVal_s:
            if m_from != None:
                node_tree.links.new(m_from, m_to)

            m_to.default_value = old_to_val

    def __save_orm(self, context, abs_save_dir):
        # Bake #
        img_ao = self.__bake(context, 'AO'       , 'Non-Color', use_ao_samples=True)
        img_r  = self.__bake(context, 'ROUGHNESS', 'Non-Color')
        img_m  = self.__bake(context, 'GLOSSY'   , 'Non-Color')
        
        # Channel Pack The Maps #
        every_4th = slice(None, None, 4)
        pixels = self.__combine_channels(img_ao.pixels[:][every_4th], img_r.pixels[:][every_4th], img_m.pixels[:][every_4th])
        img_ao.pixels = [x for t in pixels for x in t] # List of tuple[float * 4] -> List of float
        
        # Save #
        context.scene.render.image_settings.color_mode = 'RGB'
        img_ao.save_render(filepath=os.path.join(abs_save_dir, "ORM.png"))
        #

        bpy.data.images.remove(img_ao)
        bpy.data.images.remove(img_r)
        bpy.data.images.remove(img_m)

    def __save_emission(self, context, abs_save_dir):
        img = self.__bake(context, 'EMIT', 'Non-Color')

        context.scene.render.image_settings.color_mode = 'BW'
        img.save_render(filepath=os.path.join(abs_save_dir, "Emission.png"))
        
        bpy.data.images.remove(img)

    def __save_normal(self, context, abs_save_dir):
        img = self.__bake(context, 'NORMAL', 'Non-Color')

        context.scene.render.image_settings.color_mode = 'RGB'
        img.save_render(filepath=os.path.join(abs_save_dir, "Normal.png"))
        
        bpy.data.images.remove(img)

    def __bake(self, context, map_type:str, color_space:str='sRGB', use_ao_samples:bool=False) -> bpy.types.Image:
        img = bpy.data.images.new \
        (
            context.active_object.name + "_BakedTexture",
            context.scene.map_baker.width,
            context.scene.map_baker.height
        )
        img.colorspace_settings.name = color_space

        for mat in context.active_object.data.materials:
            mat.node_tree.nodes.active.image = img
        
        context.scene.cycles.samples = context.scene.map_baker.ao_samples if use_ao_samples else 1
        bpy.ops.object.bake(type=map_type, save_mode='EXTERNAL')
        
        return img
    
    def __reset(self, context):
        for mat in context.active_object.data.materials:
            mat.node_tree.nodes.remove(mat.node_tree.nodes.active)
        
        # Reset Render Properties #
        context.scene.render.engine                 = self.__old_render_engine    
        context.scene.render.bake.use_pass_direct   = self.__old_direct
        context.scene.render.bake.use_pass_indirect = self.__old_indirect
        context.scene.cycles.use_adaptive_sampling  = self.__old_adpt_sampling
        context.scene.cycles.samples                = self.__old_samples
        context.scene.cycles.use_denoising          = self.__old_use_denoising
        
        # Reset Output Properties #
        context.scene.render.image_settings.file_format = self.__old_file_format
        context.scene.render.image_settings.color_mode  = self.__old_color_mode
        context.scene.render.image_settings.color_depth = self.__old_color_depth
        context.scene.render.image_settings.compression = self.__old_compression
        
    def __show_message_box(self, context, title:str="Message Box", text:str="", icon:str='INFO'):

        def draw(self, _):
            self.layout.label(text=text)

        context.window_manager.popup_menu(draw, title=title, icon=icon)
        
def register():
    bpy.utils.register_class(BakeMaps)

def unregister():
    bpy.utils.unregister_class(BakeMaps)