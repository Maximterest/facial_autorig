# <span style="color:rgb(233, 94, 39)">Facial Module Documentation

The facial module is a Python script for Autodesk Maya. It facilitates the creation of a rebuildable facial autorig based on predefined template scenes. The module streamlines the process of exporting data from a Maya scene, and building a fully functional facial rig.


# <span style="color:rgb(233, 94, 39)">**Workflow:**

### <span style="color:rgb(233, 94, 39)">**1. You need to import the script module:**

---
<span style="color:rgb(218, 37, 82)">**RUN:**

```python
from lfdn_td.facial import config, utils, build
```

### <span style="color:rgb(233, 94, 39)">**2. Config your projet:**

---
<span style="color:rgb(218, 37, 82)">**NOTES:**

You can custom the config data. Please refer to **EXTRAS** part

---
<span style="color:rgb(218, 37, 82)">**PARAMETERS:**

> `config.PROJECT_INFO["asset"] = "yourChar"` Replace **"yourChar"** by your asset name (e.g. "providence")

---
<span style="color:rgb(218, 37, 82)">**RUN:**

```python
# CONFIG
config.PROJECT_INFO["asset"] = "yourChar"

# Add config if needed
```

## The workflow consists of two main steps:

## <span style="color:rgb(233, 94, 39)">**STEP 1: Export Data**

**If you start a new character ignore this step**
1. Open the last facial character publish Maya scene
2. Export the data and weights using commands bellow

---
<span style="color:rgb(218, 37, 82)">**NOTES:**

It export json files in **Y:\LFDN\assets\characters\yourChar\maya\data\facial_rig_build**
- Deformers weights
- Skinning weights
- Position and Attributes data for:
    * controllers
    * lattices
    * clusters
    * groups / transforms
- Controllers CVs position
- BCS nodes

It will also rename multiples nodes and deformers to match to the new nomenclature

If you have **Dual Quaternions** or **Weight Blended** on your skinClusters you need to set them manually in the build scene.

---
<span style="color:rgb(218, 37, 82)">**WARNING:**

If their is an Error with a **mesh name**. Verify the nomenclature in your scene. Or if it doesn't exist you need to remove it in the config data. Please refer to **EXTRAS** part

---
<span style="color:rgb(218, 37, 82)">**RUN:**

For definition parameters, refer to **EXTRAS** part

```python
# STEP 01: Export Data
build.export_weights()
build.export_data()
```

---
## <span style="color:rgb(233, 94, 39)">**STEP 2: Setup and Build**

1. In a new Maya scene import the last publish modeling Alembic. 

2. Rename: **M_body_neutral_shape_mesh -> M_body_geo**
and delete the existing
**M_body_geo in render_grp|body_grp**

3. Execute the commands bellow to build the facial rig

---
<span style="color:rgb(218, 37, 82)">**WARNING:**

If their is an Error it's 90% time a **nomenclature** issue in your **publish** scene. Verify meshes names in **geometry_grp** and **meshes_grp**. And redo Step 1.

If their is an Error with a **mesh name**. Verify the nomenclature in your scene. Or if it doesn't exist you need to remove it in the config data. Please refer to **EXTRAS** part

If deformers weights are not right. It might be because you need to have the **same number of deformers** on each mesh enter your publish and your build scene. The export / import weights works by deformer index.

---
<span style="color:rgb(218, 37, 82)">**RUN:**

For definition parameters, refer to **EXTRAS** part

```python
# STEP 02: Setup and Build
build.base_meshes_setup()
build.import_template_scenes()
build.import_data()
build.create_all_deformers()
build.connect_template_scenes()
build.reorder_hierarchy()
build.import_weights()
```

---
## <span style="color:rgb(233, 94, 39)">**STEP 3: Manual**

- BlendShape Data Points
- Teeth build
- Tongue build
- Eyes build
- Eyelash build
- Ribbons build

---
# <span style="color:rgb(233, 94, 39)">**EXTRAS**

You will need to reload the script module if you did mistake in your config customisation or for script updates.

<span style="color:rgb(218, 37, 82)">**RUN:**

```python
from importlib import reload
reload(config)
reload(utils)
reload(build)
```

---
### <span style="color:rgb(233, 94, 39)">**CONFIG**

If you modify the config I invite you to save the script: **Y:\LFDN\assets\characters\yourChar\maya\data\facial_rig_build\facial_build.py**


Default Export / Import weights meshes list:
- M_body_geo
- M_body_compil_mesh
- M_body_rig01_mesh
- M_body_rig02_mesh
- M_body_rig03_mesh
- M_eyelash_rig_mesh
- all meshes in LR_eye_grp
- all meshes in LR_eye_compil_grp
- M_hair_compil_mesh

### **Remove** meshes:

You will need to remove meshes in `FACIAL_MODELING_HIERARCHY` and `DEFORMERS_STACK` dictionaries:

<span style="color:rgb(218, 37, 82)">**PARAMETERS:**

|Command:|`config.FACIAL_MODELING_HIERARCHY[]`|
|-|-|
|**keys:**|`body`, `eyebrows`, `hair`, `eyelash`, `tongue`, `upper_teeth`, `lower_teeth`, `eye`|
---
|Command:|`config.DEFORMERS_STACK[]`|
|-|-|
|**keys:**|`M_body_geo`, `M_body_compil_mesh`, `M_body_rig01_mesh`, `M_body_rig02_mesh`, `M_body_rig03_mesh`, `{}_eye_grp`, `{}_eye_compil_grp`, `M_eyelash_geo`, `M_eyelash_rig_mesh`, `M_eyebrows_geo`, `M_upper_teeth_geo`, `M_upper_teeth_compil_mesh`, `M_lower_teeth_geo`, `M_lower_teeth_compil_mesh`, `M_tongue_geo`, `M_tongue_compil_mesh`, `M_hair_geo`, `M_hair_compil_mesh`|

Example:

```python
# Remove hair:
del config.FACIAL_MODELING_HIERARCHY["hair"]
del config.DEFORMERS_STACK["M_hair_geo"]
del config.DEFORMERS_STACK["M_hair_compil_mesh"]

# If you don't have eyelash rig:
del config.DEFORMERS_STACK["M_eyelash_rig_mesh"]
```
### **Add** meshes:

You will need to add meshes in `FACIAL_MODELING_HIERARCHY` and `DEFORMERS_STACK` dictionaries:

<span style="color:rgb(218, 37, 82)">**PARAMETERS:**

|Command:|`config.FACIAL_MODELING_HIERARCHY[]`|
|-|-|
|`"name"` (keys)|Give you reference geometry name|
|`"groups"` (keys)|`geometry`, `compil`, `rig`, `bs`, `tool`|
||Give all groups where you want to duplicate your reference geometry|

|Command|`config.DEFORMERS_STACK[]`|
|-|-|
|For names:|For L + R sides you can use "**{}**_name"|
||For L or R side you can use "**{side}**_name"|
||For the geometry name you can use "**{name}**_suffix"|
|**key** (str)|Give a geometry name|
|**sub key** (str)|Give a deformer name|
|**parameters** (dict)|Give deformer parameter|
||**If not**: `None`|
||For **skinCluster**:|
||`joints:` (list) joints to use for bindSkin|
||`use_hierarchy:` (bool) use joint hierarchy or not|
||`envelope:` (int) envelope value|
||For **other** deformers (wrap, proximityWrap, ...):|
||`source:` (str) source geometry name|

Example:

```python
config.FACIAL_MODELING_HIERARCHY["glasses"] = {
    "name": "M_glasses_geo",
    "groups": ["geometry", "compil"]
}
```

```python
config.DEFORMERS_STACK["M_glasses_compil_mesh"] = {
    "{name}_skinCluster": {
        "joints": ["M_base_04_jnt"],
        "use_hierarchy": True,
        "envelope": 1
    },
    "lattice_middle_ffd1": None,
    "lattice_upper_ffd1": None,
    "lattice_clusters_ffd1": None,
    "lattice_global_ffd1": None
}
```

### Add **BCS** node:

<span style="color:rgb(218, 37, 82)">**PARAMETERS:**

|Command:|`config.ALL_CONNECTIONS["bcs"][]`|
|-|-|
|**key** (str)|Give a BCS node name + "_transfer"|
|**value** (str)|Give a mesh name|

Example:

```python
config.ALL_CONNECTIONS["bcs"]["M_helmet_bs_bcs_transfer"] = "M_helmet_bs_mesh"
```

---
### <span style="color:rgb(233, 94, 39)">**STEP 2**

<span style="color:rgb(218, 37, 82)">**PARAMETERS:**

|Command:|`build.import_weights()`|
|-|-|
|**directory** (str)| default is **r"Y:\LFDN\assets\characters\yourChar\maya\data\facial_rig_build"**
||Give a custom directory if needed. Where to import all deformers data files.|
|**skip_meshes** (list)|default is []|
||Give mesh you don't want to import deformers weights|

|Command:|`build.import_data()`|
|-|-|
|**import_ctrl** (bool)|default is True|
||Import controllers positions and attributes or not|
|**import_transforms** (bool)|default is True|
||Import groups, clusters, lattices, transforms positions or not|
|**import_cvs** (bool)|default is True|
||Import cvs position or not|
|**directory** (str)| default is **r"Y:\LFDN\assets\characters\yourChar\maya\data\facial_rig_build"**
||Give a custom directory if needed. Where to import all data files.|