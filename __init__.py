import sys
import importlib

# Import Modules #
MODULE_NAMES = ["map_baker_panel", "properties", "bake_maps"]
modules = []

for module_name in MODULE_NAMES:
    module_full_name = ("{}.{}".format(__name__, module_name))
    
    if module_full_name in sys.modules:
        modules.append(importlib.reload(sys.modules[module_full_name]))
    else:
        modules.append(importlib.import_module(module_full_name))
#

bl_info = {
    "name"       : "Map Baker",
    "description": "Streamline baking & saving all of the individual maps",
    "author"     : "Joseph Murphy",
    "version"    : (1, 1),
    "blender"    : (3, 5, 0),
    "location"   : "Image Editor > Toolbox",
    "category"   : "Object",
}

def register():
    for module in modules:
        module.register()

def unregister():
    for module in modules:
        module.unregister()
    
if __name__ == "__main__":
    register()