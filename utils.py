from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import os
import re

import autorig.deformers
import maya.cmds as cmds
import maya.mel as mel
import stim
from autorig.cleanup import delete_ng_nodes
from pipemaya import animation
from PySide2 import QtWidgets
from rig.utils import skin_util
from stim.tools.weight_manager import core

from lfdn_td.facial.config import DEFORMER_SUFFIX_ASSOCIATIONS
from lfdn_td.facial.config import DEFORMERS_STACK
from lfdn_td.facial.config import GROUPS_HIERARCHY
from lfdn_td.facial.config import PROJECT_INFO
from lfdn_td.facial.config import SKIP_CONTROLLERS
from lfdn_td.facial.config import TEMPLATE_SCENES_PATH

LOG = stim.get_logger(__name__)


def duplicate_node(node, parent=None, complement_name="", replace=None):
    """Duplicate node

    Args:
        node (str): node to duplicate
        parent (str): parent duplicated mesh to this transform
        complement_name (str, optional): add the given string before the suffix of the node
        replace (list, optional): search and replace an element of the name, needs to be list of 2 items

    Return:
        list of duplicated node and all childrens
    """
    nodes = []
    new_nodes = cmds.duplicate(node, renameChildren=True)
    if parent:
        cmds.parent(new_nodes[0], parent)

    for new in new_nodes:
        tokens = new.split("_")
        if complement_name:
            tokens.insert(-1, complement_name)
        new_name = "_".join(tokens)
        if new_name.endswith("1"):
            new_name = new_name[:-1]
        if replace:
            new_name = new_name.replace(replace[0], replace[1])
        cmds.rename(new, new_name)
        nodes.append(new_name)

    return nodes


def list_deformers(mesh, types=("blendShape",)):
    """List deformers from a mesh

    Args:
        mesh (str): mesh with all deformers
        types (list): deformer filter for research

    Return:
        tuple:
            list of direct deformers,
            list of their respective types.
    """
    deformers = []
    deformers_types = []

    relatives = cmds.listRelatives(mesh, shapes=True, fullPath=True)
    shape_node = relatives[0] if relatives else None
    if shape_node:
        history = cmds.listHistory(shape_node, pruneDagObjects=True) or []
        for deformer in history:
            for typ in types:
                deformer_filtered = cmds.ls(deformer, type=typ) or None

                if deformer_filtered:
                    deformers.append(deformer_filtered[0])
                    deformers_types.append(typ)
                    continue

    return deformers, deformers_types


def get_children(node):
    """Get all child transforms of a node

    Args:
        node (str): node where to list childs

    Return:
        list: all founded childs
    """
    childs = []

    childrens = cmds.listRelatives(node, children=True) or []
    for child in childrens:
        if "Shape" not in child:
            childs.append(child)
            continue

    return childs


def copy_deformers(
    target, source="", types=("cluster", "ffd"), deformer_stack=None
):
    """Copy deformers stack

    Args:
        target (str): mesh where to transfer deformers
        source (str, optional): mesh with deformers
                                if not provided, you need to give a deformer_stack (list)
        types (list, optional): deformers types for transfer
                                if not provided, you need to give a deformer_stack (list)
        deformer_stack (list, optional): list of all deformers to copy
                                         if not provided, it will be created based on source mesh

    Return:
        list: deformers not found
    """
    missing = []
    raw_missing = []

    if not deformer_stack:
        deformer_stack, deformer_types = list_deformers(source, types=types)

    for deformer in reversed(deformer_stack):
        deformers = []
        if deformer.startswith("{}"):
            for side in "LR":
                deformers.append(deformer.format(side))
                continue
        elif deformer.startswith("{name}"):
            deformers.append(deformer.format(name=target))
        elif deformer.startswith("{side}"):
            side_prefix = target.split("_")[0]
            deformers.append(deformer.format(side=side_prefix))
        else:
            deformers.append(deformer)

        for defo in deformers:
            if cmds.objExists(defo):
                cmds.deformer(defo, edit=True, geometry=target)
            else:
                missing.append(defo)
                raw_missing.append(deformer)

    return missing, raw_missing


def create_deformer(
    name,
    meshes,
    deformer_type=None,
    association_map=DEFORMER_SUFFIX_ASSOCIATIONS,
):
    """Create a deformer

    Args:
        name (str): deformer name
        meshes (list): meshes where to create the deformer
        type (str, optional): deformer type
                              if not provided, create a deformer depending of the suffix in name
        association_map: (List[Dict[str, str]]): each dictionary contains 'suffix' and 'type' keys.
                                                 associate a suffix with a deformer type

    Return:
        list: result command of the deformer creation
    """
    if not deformer_type:
        suffix = name.split("_")[-1]
        for association in association_map:
            if association["suffix"] == suffix:
                deformer_type = association["type"]
                break

    if deformer_type:
        if deformer_type == "cluster":
            deformer = cmds.cluster(meshes, name=name)
        elif deformer_type == "ffd":
            deformer = cmds.lattice(meshes, name=name, objectCentered=True)
        elif deformer_type == "blendShape":
            deformer = cmds.blendShape(meshes, name=name)
        elif deformer_type == "wire":
            deformer = cmds.wire(meshes[0], wire=meshes[1:], name=name)
        elif deformer_type == "wrap":
            autorig.deformers.create_wrap(meshes[0], meshes[1], name)
            deformer = [name]
            cmds.setAttr(f"{name}.maxDistance", 1)
            cmds.setAttr(f"{name}.autoWeightThreshold", 1)
            base = cmds.ls(f"{meshes[0]}Base*", type="transform")[-1]
            cmds.parent(base, GROUPS_HIERARCHY["tool"])
        elif deformer_type == "proximityWrap":
            autorig.deformers.create_proximity_wrap(
                [meshes[0]], [meshes[1]], name
            )
            deformer = [name]
        elif deformer_type == "shrinkWrap":
            deformer = create_shrinkwrap(meshes[1], meshes[0], name)
        elif deformer_type == "bend":
            deformer = cmds.nonLinear(meshes[0], name=name, type="bend")
        else:
            deformer = cmds.deformer(type=deformer_type, name=name)
    else:
        deformer = None

    return deformer


def transfer_bcs_node(bcs_node, mesh=None, suffix="transfer"):
    """Transfers a BCS node to a specified mesh or creates a new cube for the transfer.

    Args:
        bcs_node (str): the name of the BCS node to transfer.
        mesh (str, optional): the name of the target mesh to transfer the BCS node to.
                              if not provided, a new cube will be created as the target.
        suffix (str, optional): add a suffix name to the new BCS node
                                if not provided, it adds nothing

    Return:
        tuple:
            str: the name of the target mesh (either the provided mesh or the newly created cube).
            str: new BCS node
    """
    bcs_node_name = f"{bcs_node}_{suffix}"
    if not suffix:
        bcs_node_name = bcs_node
        if bcs_node.endswith("transfer"):
            bcs_node_name = "_".join(bcs_node.split("_")[:-1])

    if not mesh:
        cube_name = f"{bcs_node_name}_geo"
        mesh = cmds.polyCube(name=cube_name, constructionHistory=False)[0]

    cmds.select(bcs_node, mesh)
    new_bcs = mel.eval("DPK_bcs_transfer 0;")
    new_bcs = cmds.rename(new_bcs, bcs_node_name)

    return mesh, new_bcs


def bind_skincluster(
    name, mesh, joints, use_hierarchy=True, method=1, envelope=1
):
    """Create or edit a skinCluster

    Args:
        name (str): The name of the skinCluster
        mesh (str): The name of the mesh where to create the skinCluster
        joints (list): joints used for binding
        use_hierarchy (bool): True - use given joints hierarchy
                              False - use given joints
        method (int): 0 - Closest distance between a joint and a point of the geometry
                      1 - Closest distance between a joint, considering the skeleton hierarchy, and a point of the geometry
                      2 - Surface heat map diffusion
                      3 - Geodesic voxel binding. geomBind command must be called after creating a skinCluster with this method
    """
    if cmds.objExists(name):
        cmds.skinCluster(
            name, edit=True, addInfluence=joints, lockWeights=True
        )
    else:
        cmds.skinCluster(
            joints,
            mesh,
            bindMethod=method,
            toSelectedBones=not use_hierarchy,  # Invert bool value
            maximumInfluences=10,
            normalizeWeights=1,
            removeUnusedInfluence=False,
            obeyMaxInfluences=True,
            name=name,
        )

    cmds.setAttr(f"{name}.envelope", envelope)


def create_shrinkwrap(mesh, target, name, **kwargs):
    """Create a shrinkWrap

    Args:
        mesh (str): mesh base
        target (str): mesh where to create the deformer
        name (str): name of the shrinkWrap

    Return:
        list: result command of the deformer creation
    """
    parameters = [
        ("projection", 2),
        ("closestIfNoIntersection", 1),
        ("reverse", 0),
        ("bidirectional", 1),
        ("boundingBoxCenter", 1),
        ("axisReference", 1),
        ("alongX", 0),
        ("alongY", 0),
        ("alongZ", 1),
        ("offset", 0),
        ("targetInflation", 0),
        ("targetSmoothLevel", 0),
        ("falloff", 0),
        ("falloffIterations", 1),
        ("shapePreservationEnable", 0),
        ("shapePreservationSteps", 1),
    ]

    target_shape = cmds.listRelatives(target, shapes=True)[0]
    shrink_wrap = cmds.deformer(mesh, type="shrinkWrap", name=name)[0]

    for parameter, default in parameters:
        cmds.setAttr(
            shrink_wrap + "." + parameter, kwargs.get(parameter, default)
        )

    connections = [
        ("worldMesh", "targetGeom"),
        ("continuity", "continuity"),
        ("smoothUVs", "smoothUVs"),
        ("keepBorder", "keepBorder"),
        ("boundaryRule", "boundaryRule"),
        ("keepHardEdge", "keepHardEdge"),
        ("propagateEdgeHardness", "propagateEdgeHardness"),
        ("keepMapBorders", "keepMapBorders"),
    ]

    for out_plug, in_plug in connections:
        cmds.connectAttr(
            target_shape + "." + out_plug, shrink_wrap + "." + in_plug
        )

    return [shrink_wrap]


def export_scene(objects, path, file_type):
    cmds.select(objects)
    cmds.file(path, exportSelected=True, type=file_type, force=True)


def import_scene(path, label=""):
    try:
        cmds.file(
            path,
            i=True,
            mergeNamespacesOnClash=False,
            renamingPrefix=label,
            options="v=0",
        )
    except Exception:
        LOG.exception("")


def get_template_data(template_type="joints"):
    """Get the input connections data of selected nodes

    Usage / Run:

    import pprint
    data = utils.get_template_data()
    pprint.pprint(data)
    """
    selected_nodes = get_selection()
    all_connections_data = {template_type: {}}

    for node in selected_nodes:
        raw_node = node
        for side in "LR":
            if node.startswith(side):
                node = "{}" + node[1:]
                continue
        if node in all_connections_data[template_type]:
            continue
        all_connections_data[template_type][node] = {}

        plugs = (
            cmds.listConnections(
                raw_node,
                source=True,
                destination=False,
                connections=True,
                plugs=True,
            )
            or []
        )
        dest_plugs = plugs[::2]
        input_plugs = plugs[1::2]

        for input_plug, dest in zip(input_plugs, dest_plugs):
            if "unitConversion" in input_plug:
                input_plug = cmds.listConnections(
                    input_plug.split(".")[0],
                    source=True,
                    destination=False,
                    plugs=True,
                )[0]
            dest = dest.split(".")[-1]

            for side in "LR":
                if input_plug.startswith(side) and not dest.endswith(side):
                    input_plug = "{}" + input_plug[1:]
                    continue

                if input_plug.startswith(side) and dest.endswith(side):
                    input_plug = "{}" + input_plug[1:]
                    dest = dest[:-1] + "{}"
                    continue

            if input_plug in all_connections_data[template_type][node].keys():
                continue

            all_connections_data[template_type][node][input_plug] = dest

    return all_connections_data


def get_meshes(deformer_stack_keys=None):
    objects = [list(DEFORMERS_STACK)[i] for i in deformer_stack_keys]
    meshes = []
    for obj in objects:
        side_obj = [obj]
        if obj.startswith("{}"):
            side_obj = [obj.format(side) for side in "LR"]

        for node in side_obj:
            if not cmds.objExists(node):
                if node != "M_eyelash_rig_mesh":
                    LOG.info("%s does not exist and he is skipped", node)
                    continue
                node = "M_eyelash_rig05_mesh"

            children = get_children(node) or [node]
            for child in children:
                if child.startswith("{}"):
                    for side in "LR":
                        meshes.append(child.format(side))
                        continue
                else:
                    meshes.append(child)

    return meshes


def get_directory(data=PROJECT_INFO):
    asset_path = os.path.join(data["project_directory"], data["asset"])
    if not os.path.exists(asset_path):
        cmds.error(
            f"The path: {asset_path} do not exist.\n check the asset name",
            noContext=True,
        )

    path = os.path.join(asset_path, *data["sub_folders"])
    os.makedirs(path, exist_ok=True)

    return path


def export_deformers_weights(mesh, directory):
    deformers, types = list_deformers(mesh, types=["cluster", "ffd"])
    deformers = {x: {"channel": 0} for x in deformers}
    filepath = os.path.join(directory, f"{mesh}_deformerWeights.json")

    if deformers:
        cmds.select(mesh)
        msh_obj = core.SourceMesh()
        msh_obj.load_from_selection()
        core.export_weights(msh_obj, deformers, filepath)


def export_skinning_weights(mesh, directory):
    deformers, types = list_deformers(mesh, types=["skinCluster"])
    if not deformers:
        return
    filepath = os.path.join(directory, f"{deformers[0]}_ngSkinWeights.json")

    skin_util.export_ng_layer(filepath, mesh)


def import_deformers_weights(mesh, directory):
    deformers, types = list_deformers(mesh, types=["cluster", "ffd"])
    deformers = {x: {"channel": 0} for x in deformers}

    if not deformers:
        return

    filepath = os.path.join(directory, f"{mesh}_deformerWeights.json")
    correspondence = {deformer: deformer for deformer in deformers}

    cmds.select(mesh)
    msh_obj = core.SourceMesh()
    msh_obj.load_from_selection()

    try:
        core.import_weights(msh_obj, correspondence, filepath)
    except Exception as e:
        LOG.info(
            "Correspondance failed: %s",
            e,
        )


def import_skinning_weights(mesh, directory):
    deformers, types = list_deformers(mesh, types=["skinCluster"])
    if not deformers:
        return
    skincluster = deformers[0]

    try:
        skin_util.load_ng_node(mesh, directory, skincluster)
        delete_ng_nodes()
        LOG.info("Skinning weights data imported for %s", mesh)
    except:
        cmds.warning(
            f"Import skinning weights failed for {skincluster}.\n Check if the skinCluster exists in the publish",
            noContext=True,
        )


def get_clusters(cluster_group=GROUPS_HIERARCHY["clusters"]):
    children = cmds.listRelatives(cluster_group, allDescendents=True)
    clusters = []

    for child in children:
        typ = cmds.nodeType(child)
        if typ != "clusterHandle":
            continue
        name = child
        if "HandleShape" in child:
            name = child.replace("HandleShape", "")
        clusters.append(name)

    return clusters


def build_cluster_plugs(cluster):
    handle = cmds.listConnections(f"{cluster}.matrix", source=True)[0]
    parent = cmds.listRelatives(handle, parent=True)[0]

    input_plug = f"{parent}.worldInverseMatrix[0]"
    dest_plug = f"{cluster}.bindPreMatrix"

    return input_plug, dest_plug


def connect_clusters_bpm(clusters=None):
    if not clusters:
        clusters = get_clusters()
    for cluster in clusters:
        input_plug, dest_plug = build_cluster_plugs(cluster)
        try:
            cmds.connectAttr(input_plug, dest_plug, force=True)
        except:
            LOG.info("Can't connect: %s -> %s", input_plug, dest_plug)


def disconnect_clusters_bpm(clusters=None):
    if not clusters:
        clusters = get_clusters()
    for cluster in clusters:
        input_plug, dest_plug = build_cluster_plugs(cluster)
        try:
            cmds.disconnectAttr(input_plug, dest_plug)
        except:
            LOG.info("Can't disconnect: %s -> %s", input_plug, dest_plug)


def get_attributes(obj, attributes="trs", axis="xyz"):
    attribute_list = []
    attribute_value_list = []
    for attr in [x + y for x in attributes for y in axis]:
        value = cmds.getAttr("{}.{}".format(obj, attr))
        attribute_list.append(attr)
        attribute_value_list.append(value)

    return attribute_list, attribute_value_list


def mirror_obj(nodes, invert=True):
    for obj in nodes:
        replaces = (
            ["L_", "R_"]
            if obj.startswith("L_")
            else ["R_", "L_"]
            if obj.startswith("R_")
            else None
        )
        if not replaces:
            continue
        obj_other_side = obj.replace(replaces[0], replaces[1])
        typ = cmds.objectType(obj)

        if typ == "pointConstraint":
            attributes, values = get_attributes(obj, attributes="o")
            for i, attr in enumerate(attributes):
                new_value = -values[i] if "x" in attr else values[i]
                cmds.setAttr("{}.{}".format(obj_other_side, attr), new_value)

        if typ == "transform":
            attributes, values = get_attributes(obj)
            for i, attr in enumerate(attributes):
                if invert is True:
                    new_value = (
                        -values[i]
                        if any(x in attr for x in ("tx", "sx", "ry"))
                        else values[i]
                    )
                else:
                    new_value = values[i]

                try:
                    cmds.setAttr(
                        "{}.{}".format(obj_other_side, attr), new_value
                    )
                except:
                    cmds.warning(f"Can not setAttr: {obj_other_side}.{attr}")


def mirror_joints():
    bases = [
        "M_base_01_jnt_offset",
        "M_base_02_jnt_offset",
        "M_base_03_jnt_offset",
        "M_base_04_jnt_offset",
        "M_base_05_jnt_offset",
    ]
    raw = []
    for base in bases:
        children = cmds.listRelatives(base, allDescendents=True)[::-1]
        raw.extend(children)

    nodes = []
    for node in raw:
        if "_offset" not in node:
            continue
        if "L_" not in node:
            continue
        nodes.append(node)

    for obj in nodes:
        obj_other_side = obj.replace("L_", "R_")

        invert = True
        fullpath = cmds.listRelatives(obj_other_side, fullPath=True)[0]
        parents = fullpath.split("|")
        for parent in parents:
            if parent:
                sx = cmds.getAttr(f"{parent}.sx")
                if sx < 0:
                    invert = False
                    break

        attributes, values = get_attributes(obj)
        for i, attr in enumerate(attributes):
            if invert is True:
                new_value = (
                    -values[i]
                    if any(x in attr for x in ("tx", "sx", "ry"))
                    else values[i]
                )
            else:
                new_value = values[i]

            cmds.setAttr("{}.{}".format(obj_other_side, attr), new_value)


def mirror_controllers():
    controllers = cmds.ls("L_*_ctrl")
    double_offsets = []
    point_constraints = []

    for obj in controllers:
        rside = obj.replace("L_", "R_")
        if not cmds.objExists(rside):
            controllers.remove(obj)
            continue

        if "eye_" in obj and "cluster_" not in obj:
            controllers.remove(obj)
            continue

        if "Twk" in obj or "twk" in obj:
            continue

        double_offset = cmds.listRelatives(
            cmds.listRelatives(obj, parent=True), parent=True
        )

        if not double_offset:
            continue

        children = cmds.listRelatives(double_offset, children=True)
        point_constraint = children[-1] if len(children) > 1 else None

        double_offsets.append(double_offset[0])
        if point_constraint:
            point_constraints.append(point_constraint)

    mirror_obj(double_offsets, invert=True)
    mirror_obj(point_constraints, invert=True)

    for obj in controllers:
        ctrl_cvs = cmds.ls(f"{obj}.cv[*]", flatten=True)
        mirror_cvs(ctrl_cvs, replaces=("LR"))

    cmds.inViewMessage(
        amg='<font color="lightGreen">Controllers are mirrored</font>',
        pos="midCenter",
        fade=True,
    )


def mirror_cvs(cvs, mode="x", replaces=("LR")):
    for cv in cvs:
        pos = cmds.xform(cv, q=1, ws=1, t=1)
        cv_side = cv.replace(replaces[0], replaces[1])
        if not cmds.objExists(cv_side):
            continue

        if mode == "x":
            cmds.xform(cv_side, ws=1, t=[pos[0] * (-1), pos[1], pos[2]])
        if mode == "z":
            cmds.xform(cv_side, ws=1, t=[pos[0], pos[1], pos[2] * (-1)])


def make_blendshape_by_prefix():
    meshes = get_selection() or []
    for mesh in meshes:
        prefix = mesh.split("_")[0]
        match = mesh.replace(f"{prefix}_", "")
        if not cmds.objExists(match):
            cmds.warning(f"No match for {mesh}", noContext=True)
            continue

        bs = cmds.blendShape(mesh, match)[0]
        cmds.setAttr(f"{bs}.{mesh}", 1)


def get_selection():
    return cmds.ls(selection=True)


def make_edges_rivet(edges, input_mesh_plug, name="mouth"):
    # Node names
    node_names = {
        "crvfe": [f"rivet_{name}_crvfe_0{i + 1}" for i in range(2)],
        "loft": f"rivet_{name}_loft",
        "posi": f"rivet_{name}_posi",
        "vector": f"rivet_{name}_vprdt",
        "fbfmx": f"rivet_{name}_fbfmx",
        "rivet": f"rivet_{name}_loc",
    }

    # Create nodes
    crvfe_nodes = [
        cmds.createNode("curveFromMeshEdge", name=name)
        for name in node_names["crvfe"]
    ]
    loft = cmds.createNode("loft", name=node_names["loft"])
    posi = cmds.createNode("pointOnSurfaceInfo", name=node_names["posi"])
    vector = cmds.createNode("vectorProduct", name=node_names["vector"])
    fbfmx = cmds.createNode("fourByFourMatrix", name=node_names["fbfmx"])
    rivet = cmds.spaceLocator(name=node_names["rivet"])[0]

    cmds.parent(rivet, GROUPS_HIERARCHY["rivet"])

    # Set node attributes
    cmds.setAttr(f"{loft}.uniform", 1)
    cmds.setAttr(f"{posi}.parameterU", 0.5)
    cmds.setAttr(f"{posi}.parameterV", 0.5)
    cmds.setAttr(f"{posi}.turnOnPercentage", 1)
    cmds.setAttr(f"{vector}.operation", 2)

    # Connect nodes
    for i, crvfe in enumerate(crvfe_nodes):
        cmds.connectAttr(input_mesh_plug, f"{crvfe}.inputMesh")
        cmds.connectAttr(f"{crvfe}.outputCurve", f"{loft}.inputCurve[{i}]")

    cmds.connectAttr(f"{loft}.outputSurface", f"{posi}.inputSurface")

    attributes = ["p", "n", "tv"]
    indices = "301"
    for y, (attr, row) in enumerate(zip(attributes, indices)):
        for i, axis in enumerate("xyz"):
            cmds.connectAttr(f"{posi}.{attr}{axis}", f"{fbfmx}.i{row}{i}")
            if y == 0:
                cmds.connectAttr(f"{vector}.o{axis}", f"{fbfmx}.i2{i}")
                continue
            cmds.connectAttr(f"{posi}.{attr}{axis}", f"{vector}.i{y}{axis}")

    cmds.connectAttr(f"{fbfmx}.output", f"{rivet}.offsetParentMatrix")

    # Add message connections
    for crvfe in crvfe_nodes:
        attr_name = "rivetLink"
        if not cmds.attributeQuery(attr_name, node=crvfe, exists=True):
            cmds.addAttr(crvfe, longName=attr_name, dataType="string")
        cmds.setAttr(
            f"{crvfe}.{attr_name}", node_names["rivet"], type="string"
        )
        cmds.connectAttr(
            f"{rivet}.message", f"{crvfe}.{attr_name}", force=True
        )

    # Add indentifier attribute
    id_name = f"{name}_rivet"
    cmds.addAttr(rivet, longName=id_name, dataType="string")
    cmds.setAttr(f"{rivet}.{id_name}", "rivetID", type="string", lock=True)

    set_edges_rivet(edges, rivet)

    return rivet


def set_edges_rivet(edges, rivet):
    crvfe_nodes = cmds.listConnections(
        f"{rivet}.message", type="curveFromMeshEdge"
    )
    for node, edge in zip(crvfe_nodes, edges):
        match = re.search(r"\[(\d+)\]", edge)
        number = int(match.group(1))
        cmds.setAttr(f"{node}.edgeIndex[0]", number)


def export_controllers_to_json():
    scene_path = cmds.file(q=True, sceneName=True)
    if not scene_path:
        cmds.error("No scene is currently open.")
        return

    output_path = os.path.splitext(scene_path)[0] + "_data.json"
    controllers = cmds.ls("*_ctrl")

    with open(output_path, "w") as json_file:
        json.dump(controllers, json_file, indent=4)

    cmds.confirmDialog(
        title="Export Complete",
        message=f"Controllers data exported:\n\n{output_path}",
    )


def check_controllers_match():
    json_path = TEMPLATE_SCENES_PATH["controller"][:-3] + "_data.json"

    if not os.path.exists(json_path):
        cmds.error(f"{json_path} not found.", noContext=True)
        return

    with open(json_path) as json_file:
        reference_controllers = json.load(json_file)

    controllers = cmds.ls("*_ctrl")
    current_controllers = [
        ctrl for ctrl in controllers if ctrl not in SKIP_CONTROLLERS
    ]

    non_matching = [
        ctrl for ctrl in reference_controllers if not cmds.objExists(ctrl)
    ]

    print("\n\n")
    print(" MATCH CONTROLLERS REPORT ".center(50, "-"))
    print("File read from: " + json_path)
    print("\n")
    for ctrl in non_matching:
        print(f"No match found for '{ctrl}' controller")

    print("\n")
    print("".center(50, "-"))
    print("\n")

    LOG.warning(
        "%s controllers are expected and you have %s",
        len(reference_controllers),
        len(current_controllers),
    )

    if not non_matching:
        LOG.warning("All controllers match.")
        return

    class ResultWin(QtWidgets.QMainWindow):
        def __init__(self, parent=None):
            super(ResultWin, self).__init__(parent=parent or get_maya_window())
            widget = QtWidgets.QWidget(self)
            main_layout = QtWidgets.QVBoxLayout(widget)
            self.setCentralWidget(widget)
            self.file_line = QtWidgets.QLineEdit(self)
            self.file_line.setReadOnly(True)
            main_layout.addWidget(self.file_line)
            self.result_list = QtWidgets.QListWidget(self)
            main_layout.addWidget(self.result_list)

            self.setWindowTitle("Missmatch controllers found...")

        def populate(self, filepath, content):
            self.file_line.setText(filepath)
            self.result_list.addItems(content)

    def get_maya_window():
        """Find Maya main window."""
        wdg = QtWidgets.QApplication.topLevelWidgets()
        return ([x for x in wdg if x.objectName() == "MayaWindow"] or [None])[
            0
        ]

    win = ResultWin()
    win.populate(json_path, non_matching)
    win.show()


def rebuild_blendshape_target(blendshape, index):
    target = cmds.sculptTarget(
        blendshape, edit=True, regenerate=True, target=index
    )
    if not target:
        cmds.error(
            f"Please delete all tongue targets curves from {blendshape}",
            noContext=True,
        )

    return target[0]


### CONFORMITY UTILS SCRIPTS ###


def ctrl_lips_mirror():
    for mod in ["upper", "lower"]:
        cmds.connectAttr(
            f"lips_{mod}_depth_plusMinusAverage.output3Dz",
            f"R_lip_{mod}_main_jnt.translateZ",
            force=True,
        )


def create_lips_shapes():
    animation.reset_ctrls()
    ctrls = ["M_lip_{mod}_global_ctrl", "M_lip_{mod}_main_ctrl"]
    for mod in ["upper", "lower"]:
        ctrl0 = ctrls[0].format(mod=mod)
        ctrl1 = ctrls[1].format(mod=mod)

        for value in [1, -1]:
            cmds.setAttr(f"{ctrl0}.translateY", 1 * value)
            cmds.setAttr(f"{ctrl1}.translateY", 0.75 * -value)

            dup = cmds.duplicate("M_body_bs_mesh")[0]
            cmds.parent(dup, world=True)

            cmds.setAttr(f"{ctrl0}.translateY", 0)
            cmds.setAttr(f"{ctrl1}.translateY", 0)

    cmds.setAttr("M_lip_upper_global_ctrl.techMidLipDefaultRatio", lock=False)
    cmds.setAttr("M_lip_upper_global_ctrl.techMidLipDefaultRatio", 0.75)
    cmds.setAttr("M_lip_upper_global_ctrl.techMidLipDefaultRatio", lock=True)


def match_pivot(cancel=False):
    global offset

    sel = cmds.ls(selection=True)
    if not cancel:
        obj1, obj2 = sel

        obj1_pivot = cmds.xform(
            obj1, query=True, worldSpace=True, rotatePivot=True
        )
        obj2_pivot = cmds.xform(
            obj2, query=True, worldSpace=True, rotatePivot=True
        )

        offset = [obj2_pivot[i] - obj1_pivot[i] for i in range(3)]
        current_offset = cmds.getAttr(f"{obj1}.offset")[0]
        new_offset = [current_offset[i] + offset[i] for i in range(3)]

        cmds.setAttr(
            f"{obj1}.offset", new_offset[0], new_offset[1], new_offset[2]
        )

        parts = obj1.split("_")
        ctrl_name = []
        for part in parts:
            ctrl_name.append(part)
            if "ctrl" in part:
                break
        controller = "_".join(ctrl_name)

        cvs = cmds.ls(f"{controller}.cv[*]", flatten=True)
        for cv in cvs:
            pos = cmds.pointPosition(cv, world=True)
            new_pos = [pos[i] - offset[i] for i in range(3)]
            cmds.xform(cv, worldSpace=True, translation=new_pos)

    else:
        for obj in sel:
            current_offset = cmds.getAttr(f"{obj}.offset")[0]
            new_offset = [current_offset[i] - offset[i] for i in range(3)]
            cmds.setAttr(
                f"{obj}.offset",
                new_offset[0],
                new_offset[1],
                new_offset[2],
            )
