from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import os
import re

import rig.utils.facial_rig
import stim
from maya import cmds
from pipemaya import animation
from rig.utils import facial_rig

from lfdn_td.facial import utils
from lfdn_td.facial.config import ALL_CONNECTIONS
from lfdn_td.facial.config import BLENDSHAPE_CONNECTIONS
from lfdn_td.facial.config import DEFORMER_SUFFIX_ASSOCIATIONS
from lfdn_td.facial.config import DEFORMERS_STACK
from lfdn_td.facial.config import FACIAL_MODELING_HIERARCHY
from lfdn_td.facial.config import GROUPS_HIERARCHY
from lfdn_td.facial.config import PROJECT_INFO
from lfdn_td.facial.config import TEMPLATE_SCENES_PATH

LOG = stim.get_logger(__name__)


def base_meshes_setup(
    modeling_data=FACIAL_MODELING_HIERARCHY,
    group_data=GROUPS_HIERARCHY,
    connection_data=BLENDSHAPE_CONNECTIONS,
):
    """Create hierarchy for facial rig with all blendShaped meshes

    Args:
        modeling_data (dict): give all modeling hierarchy data
        group_data (dict): give all group hierarchy data
        connection_data (dict): give all modeling connection data
    """
    # Create groups hierarchy
    rig.utils.facial_rig.create_face_hierarchy()

    # Create and organise all meshes
    created = {}

    for node_data in modeling_data.values():
        node = node_data["name"]
        groups = node_data["groups"]

        nodes = [node]
        if node.startswith("{}"):
            nodes = [node.format(side) for side in "LR"]

        for obj in nodes:
            occurrences = {}

            if not cmds.objExists(obj):
                cmds.warning(
                    f"The node: {obj} does not exist and he is skipped",
                    noContext=True,
                )
                continue

            for group in groups:
                group_name = group_data[group]

                occurrences[group] = occurrences.get(group, 0) + 1
                if occurrences[group] > 1 or groups.count(group) > 1:
                    indexed = f"{group}{occurrences[group]:02}"
                else:
                    indexed = group

                if group == "geometry":
                    cmds.parent(obj, group_name)

                    # Edit meshes visual
                    meshes = utils.get_children(obj) or [
                        obj
                    ]  # List meshes in a group
                    for mesh in meshes:
                        # Harden Edge
                        cmds.polySoftEdge(
                            mesh, angle=0, constructionHistory=False
                        )

                        # Unlock normals
                        shape = cmds.listRelatives(mesh, shapes=True)[0]
                        cmds.polyNormalPerVertex(shape, unFreezeNormal=True)

                    duplicated = obj
                else:
                    duplicated = utils.duplicate_node(
                        node=obj,
                        parent=group_name,
                        complement_name=indexed,
                        replace=["_geo", "_mesh"],
                    )[0]

                if obj not in created:
                    created[obj] = {}
                if group not in created[obj]:
                    created[obj][group] = []
                created[obj][group].append(duplicated)

    for created_value in created.values():
        # Create all blendShapes connections
        for source_group, targets_group in connection_data.items():
            for target_group in targets_group:
                if (
                    source_group not in created_value
                    or target_group not in created_value
                ):
                    continue
                sources = created_value[source_group]
                targets = created_value[target_group]

                for source in sources:
                    # List meshes inside group
                    source_meshes = utils.get_children(source) or [source]
                    target_meshes = utils.get_children(targets) or targets

                    for source_mesh, target_mesh in zip(
                        source_meshes, target_meshes
                    ):
                        blendshape, types = utils.list_deformers(target_mesh)
                        if not blendshape:
                            blendshape = cmds.blendShape(
                                target_mesh, name=f"{target_mesh}_blendShape"
                            )
                        blendshape = blendshape[0]

                        cmds.blendShape(
                            blendshape,
                            edit=True,
                            target=(
                                target_mesh,
                                len(
                                    cmds.blendShape(
                                        blendshape, q=True, target=True
                                    )
                                    or []
                                ),
                                source_mesh,
                                1.0,
                            ),
                        )
                        cmds.setAttr(f"{blendshape}.{source_mesh}", 1.0)


def create_all_deformers(deformers_data=DEFORMERS_STACK):
    """Copy or create all deformers

    Args:
        deformers (dict): give all deformers information for the copy or creation
    """
    for node, deformers in deformers_data.items():
        objects = []
        if node.startswith("{}"):
            for side in "LR":
                objects.append(node.format(side))
                continue
        else:
            objects.append(node)

        for obj in objects:
            meshes = utils.get_children(obj) or [obj]
            for mesh in meshes:
                missing, raw_missing = utils.copy_deformers(
                    target=mesh, deformer_stack=deformers.keys()
                )

                for key, deformer in zip(raw_missing, missing):
                    suffix = deformer.split("_")[-1]
                    for association in DEFORMER_SUFFIX_ASSOCIATIONS:
                        if association["suffix"] == suffix:
                            deformer_type = association["type"]
                            break

                    if deformer_type:
                        if deformer_type == "skinCluster":
                            joints = deformers[key]["joints"]
                            use_hierarchy = deformers[key]["use_hierarchy"]
                            envelope = deformers[key]["envelope"]
                            utils.bind_skincluster(
                                deformer,
                                mesh,
                                joints,
                                use_hierarchy=use_hierarchy,
                                envelope=envelope,
                            )
                        else:
                            meshes = [mesh]
                            if deformers[key] is not None:
                                source = deformers[key]["source"]
                                meshes = [source, mesh]
                            utils.create_deformer(name=deformer, meshes=meshes)


def connect_template_scenes(
    templates=("cluster", "joint", "lattice", "controller"),
    bcs_template=True,
    connections_data=ALL_CONNECTIONS,
):
    """Make all node plugs to connect templates scenes

    Args:
        templates (list, optional): give all templates you want to connect
        connection (dict, optional): give the dictionnary of all nodes connections
    """
    if bcs_template is True:
        for bcs_node, mesh in connections_data["bcs"].items():
            utils.transfer_bcs_node(bcs_node, mesh, suffix=None)
            cmds.delete(f"{bcs_node}_geo")

        cmds.setAttr(
            "M_body_bs_bcs.presetFalloff[9].pFalloff[2].pFalloff_FloatValue", 1
        )
        cmds.setAttr(
            "M_body_bs_bcs.presetFalloff[10].pFalloff[2].pFalloff_FloatValue",
            1,
        )

    for template in templates:
        LOG.info("%s template connections errors:", template.upper())
        missings = []

        for destination_raw, plugs_raw in connections_data[template].items():
            destinations = [destination_raw]
            if destination_raw.startswith("{}"):
                destinations = [destination_raw.format(side) for side in "LR"]

            for destination in destinations:
                dest_prefix = destination.split("_")[0]

                for src_plug, dest_attr in plugs_raw.items():
                    src_plugs = [src_plug]
                    if src_plug.startswith("{}") and dest_prefix in "LR":
                        src_plugs = [src_plug.format(dest_prefix)]
                    if src_plug.startswith("{}") and dest_prefix == "M":
                        src_plugs = [src_plug.format(side) for side in "LR"]

                    for side_src_plug in src_plugs:
                        src_prefix = side_src_plug.split("_")[0]

                        side_dest_attr = dest_attr
                        if dest_attr.endswith("{}"):
                            side_dest_attr = dest_attr.format(src_prefix)

                        side_dest_plug = f"{destination}.{side_dest_attr}"
                        try:
                            cmds.connectAttr(
                                side_src_plug,
                                side_dest_plug,
                                force=True,
                            )
                        except RuntimeError:
                            missings.append(
                                f"{side_src_plug} -> {side_dest_plug}"
                            )
        if missings:
            for missing in missings:
                LOG.info(missing)
        else:
            LOG.info("[]")


def export_bcs_node(bcs_nodes, meshes=None, path=None):
    """Transfers a BCS node to a specified mesh or creates a new cube for the transfer and export a new scene of it

    Args:
        bcs_nodes (list): names of the BCS node to transfer.
        meshes (list, optional): names of target meshes where to transfer the BCS node.
                                 if not provided, a new cube will be created as the target.
        path (str, raw): maya scene path

    Return:
        tuple:
            str: new BCS nodes
            str: names of the target meshes (either the provided meshes or newly created cubes).
            str: export path
    """
    new_bcs_nodes = []
    new_meshes = []
    meshes = (
        meshes if meshes else [[].append("") for i in range(len(bcs_nodes))]
    )
    if not path:
        path = os.path.join(
            PROJECT_INFO["project_directory"],
            PROJECT_INFO["asset"],
            *PROJECT_INFO["sub_folders"],
            PROJECT_INFO["asset"] + "_bcs_nodes.ma",
        )
    scene_type = None
    if path.endswith(".mb"):
        scene_type = "mayaBinary"
    if path.endswith(".ma"):
        scene_type = "mayaAscii"

    if not scene_type:
        cmds.warning(
            "Please use a path that ends with .ma or .mb", noContext=True
        )
        return None

    for bcs_node, mesh in zip(bcs_nodes, meshes):
        mesh_transfer, bcs_node_transfer = utils.transfer_bcs_node(
            bcs_node, mesh
        )
        new_meshes.append(mesh_transfer)
        new_bcs_nodes.append(bcs_node_transfer)

    utils.export_scene(new_meshes, path, scene_type)

    return new_bcs_nodes, new_meshes, path


def import_template_scenes(
    templates=("joint", "controller", "cluster", "lattice", "bcs"),
    path_data=TEMPLATE_SCENES_PATH,
    bcs_path=None,
):
    """Import all templates

    Args:
        templates (str): give all template key words you want to import
        path_data (dict): all template path data
    """
    LOG.info("\n\nStarts importing templates scenes\n\n")

    for template in templates:
        if template == "bcs":
            if bcs_path:
                path = bcs_path
            else:
                path = os.path.join(
                    PROJECT_INFO["project_directory"],
                    PROJECT_INFO["asset"],
                    *PROJECT_INFO["sub_folders"],
                    PROJECT_INFO["asset"] + "_bcs_nodes.ma",
                )
        else:
            path = path_data[template]

        utils.import_scene(path, label=template)

        if template == "bcs":
            bcs_nodes = cmds.ls(type="DPK_bcs")
            [cmds.setAttr(f"{n}.freezeInput", 1) for n in bcs_nodes]

        LOG.info(
            "\n\n   The %s template is imported from the path: %s\n\n",
            template,
            path,
        )

    LOG.info("%s Templates are well imported\n\n", templates)


def reorder_hierarchy(template_suffix="template"):
    template_groups = cmds.ls(f"*_{template_suffix}")
    for group in template_groups:
        parent = "_".join(group.split("_")[:-1])

        for key in ALL_CONNECTIONS:
            if parent.startswith(f"{key}_"):
                parent = "_".join(parent.split("_")[1:])
        children = utils.get_children(group)

        for child in children:
            if child.endswith(template_suffix):
                continue

            try:
                cmds.parent(child, parent)
            except Exception:
                LOG.info("%s -> %s can not be parented", child, parent)

    cmds.delete(template_groups)


def rename_scene(deformers_data=DEFORMERS_STACK):
    # Rename manually
    rename_data = {
        "M_eyelash_rig05_mesh": "M_eyelash_rig_mesh",
        "M_eyelash_rig05_mesh_skinCluster": "M_eyelash_rig_mesh_skinCluster",
    }
    for key, value in rename_data.items():
        if cmds.objExists(key):
            cmds.rename(key, value)

    # Rename clusters
    clusters = cmds.ls(["*_cluster", "*_cluster_loc"])
    for cluster in clusters:
        if cmds.objectType(cluster) == "transform":
            cmds.rename(cluster, cluster.replace("_cluster", "_clusterHandle"))

    cheebone = cmds.ls("*cheebone*")
    for wrong in cheebone:
        if wrong.endswith("Shape"):
            continue
        try:
            cmds.rename(wrong, wrong.replace("cheebone", "cheekbone"))
        except:
            pass

    # Rename lattices
    lattices = cmds.ls([
        "*_lattice_clusterHandle_loc",
        "*__lattice_clusterHandle",
    ])
    for lattice in lattices:
        cmds.rename(
            lattice,
            lattice.replace("_clusterHandle", "_clusterHandleHandle"),
        )

    # Rename skinClusters
    nodes = deformers_data.keys()
    for i, node in enumerate(nodes):
        meshes = utils.get_meshes([i])
        for mesh in meshes:
            deformers = deformers_data[node]
            skincluster_name = None
            for deformer in deformers:
                if not deformer.endswith("_skinCluster"):
                    continue
                skincluster_name = deformer
                break

            skincluster, def_typ = utils.list_deformers(
                mesh, types=["skinCluster"]
            )
            if not skincluster:
                continue
            if not skincluster_name:
                continue
            if skincluster_name.startswith("{name}"):
                skincluster_name = skincluster_name.format(name=mesh)
            if skincluster_name.startswith("{side}"):
                side = mesh.split("_")[0]
                skincluster_name = skincluster_name.format(side=side)
            if skincluster == skincluster_name:
                continue
            if len(skincluster) > 1:
                cmds.error(
                    f"One skinCluster is expected on {mesh}", noContext=True
                )

            cmds.rename(skincluster, skincluster_name)

    # Rename other deformers
    for i, node in enumerate(nodes):
        meshes = utils.get_meshes([i])
        for mesh in meshes:
            actual_deformers, types = utils.list_deformers(
                mesh, types=["cluster", "ffd", "skinCluster"]
            )

            for actual, typ in zip(actual_deformers, types):
                for data in DEFORMER_SUFFIX_ASSOCIATIONS:
                    suffix = actual.split("_")[-1]
                    match_suffix = bool(suffix == data["suffix"])
                    new_name = actual.replace(suffix, data["suffix"])

                    if data["type"] != typ:
                        continue
                    if match_suffix is True:
                        continue
                    if actual == new_name:
                        continue

                    cmds.rename(actual, new_name)


def export_weights(
    directory=None, deformers_data=DEFORMERS_STACK, export_bcs=True
):
    if not directory:
        directory = utils.get_directory()

    rename_scene(deformers_data)

    # Export deformers and skinning weights
    for i, node in enumerate(deformers_data.keys()):
        meshes = utils.get_meshes([i])
        for mesh in meshes:
            utils.export_deformers_weights(mesh, directory)
            utils.export_skinning_weights(mesh, directory)

    # Export bcs nodes
    if export_bcs:
        bcs_nodes = cmds.ls(type="DPK_bcs")
        new_bcs_nodes, new_meshes, path = export_bcs_node(bcs_nodes)
        cmds.delete(new_meshes)


def import_weights(
    directory=None,
    skip_meshes=(),
    deformers_data=DEFORMERS_STACK,
):
    if not directory:
        directory = utils.get_directory()

    for i, node in enumerate(deformers_data.keys()):
        meshes = utils.get_meshes([i])
        for mesh in meshes:
            if mesh in skip_meshes:
                continue
            utils.import_deformers_weights(mesh, directory)
            utils.import_skinning_weights(mesh, directory)


def export_data(
    export_ctrl=True, export_transforms=True, export_cvs=True, directory=None
):
    """Exports three JSON files:
    1. User-defined attributes of controllers ending in "_ctrl".
    2. All attributes of transforms and constraints in the scene.
    3. CV values of controllers ending in "_ctrl".
    """
    if not directory:
        directory = utils.get_directory()

    rename_scene(DEFORMERS_STACK)

    ctrl_export_path = os.path.join(directory, "controllers_data.json")
    transforms_export_path = os.path.join(directory, "transforms_data.json")
    cvs_export_path = os.path.join(directory, "cvs_data.json")

    # Export 1:
    if export_ctrl is True:
        controllers = cmds.ls("*_ctrl", type="transform")
        ctrl_data = {}

        for ctrl in controllers:
            user_attrs = cmds.listAttr(ctrl, userDefined=True) or []
            if not user_attrs:
                continue
            if user_attrs == ["stimUuid"]:
                continue

            ctrl_data[ctrl] = {
                attr: cmds.getAttr(f"{ctrl}.{attr}")
                for attr in user_attrs
                if attr != "stimUuid"
            }

        with open(ctrl_export_path, "w") as f:
            json.dump(ctrl_data, f, indent=4)

    # Export 2:
    if export_transforms is True:
        transforms = cmds.ls(type="transform")
        constraints = cmds.ls(
            type=[
                "parentConstraint",
                "pointConstraint",
                "orientConstraint",
                "scaleConstraint",
            ]
        )
        excluded_nodes = cmds.ls("*_ctrl", type="transform")
        all_nodes = [
            node
            for node in transforms + constraints
            if node not in excluded_nodes
        ]
        transforms_constraints_data = {}

        for node in all_nodes:
            all_attrs = cmds.listAttr(node, keyable=True) or []
            transforms_constraints_data[node] = {
                attr: cmds.getAttr(f"{node}.{attr}")
                for attr in all_attrs
                if cmds.attributeQuery(attr, node=node, exists=True)
                and attr != "stimUuid"
            }

        with open(transforms_export_path, "w") as f:
            json.dump(transforms_constraints_data, f, indent=4)

    # Export 3:
    if export_cvs is True:
        cvs_data = {}

        for ctrl in controllers:
            shapes = (
                cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve") or []
            )
            for shape in shapes:
                cvs = cmds.ls(f"{shape}.cv[*]", flatten=True)
                if cvs:
                    cvs_data[ctrl] = [
                        cmds.xform(
                            cv,
                            query=True,
                            worldSpaceDistance=True,
                            translation=True,
                        )
                        for cv in cvs
                    ]
                else:
                    LOG.info("No CVs found for controller: %s", ctrl)

        with open(cvs_export_path, "w") as f:
            json.dump(cvs_data, f, indent=4)

        LOG.info("Export data completed to: %s", directory)


def import_data(
    import_ctrl=True, import_transforms=True, import_cvs=True, directory=None
):
    if not directory:
        directory = utils.get_directory()

    ctrl_import_path = os.path.join(directory, "controllers_data.json")
    transforms_import_path = os.path.join(directory, "transforms_data.json")
    cvs_import_path = os.path.join(directory, "cvs_data.json")

    # Import controller attributes
    if import_ctrl is True:
        with open(ctrl_import_path) as f:
            ctrl_data = json.load(f)

        for ctrl, attrs in ctrl_data.items():
            if cmds.objExists(ctrl):
                for attr, value in attrs.items():
                    try:
                        if cmds.attributeQuery(attr, node=ctrl, exists=True):
                            is_locked = cmds.getAttr(
                                f"{ctrl}.{attr}", lock=True
                            )
                            if is_locked:
                                cmds.setAttr(f"{ctrl}.{attr}", lock=False)
                            cmds.setAttr(f"{ctrl}.{attr}", value)
                            if is_locked:
                                cmds.setAttr(f"{ctrl}.{attr}", lock=True)
                    except Exception as e:
                        LOG.info(
                            "Failed to set attribute %s.%s: %s", ctrl, attr, e
                        )
            else:
                LOG.info("%s does not exist in the scene", ctrl)

    # Import transforms and constraints attributes
    if import_transforms is True:
        with open(transforms_import_path) as f:
            transforms_constraints_data = json.load(f)

        for node, attrs in transforms_constraints_data.items():
            if cmds.objExists(node):
                for attr, value in attrs.items():
                    try:
                        if cmds.attributeQuery(attr, node=node, exists=True):
                            is_locked = cmds.getAttr(
                                f"{node}.{attr}", lock=True
                            )
                            if is_locked:
                                cmds.setAttr(f"{node}.{attr}", lock=False)
                            cmds.setAttr(f"{node}.{attr}", value)
                            if is_locked:
                                cmds.setAttr(f"{node}.{attr}", lock=True)
                    except Exception as e:
                        LOG.info(
                            "Failed to set attribute %s.%s: %s", node, attr, e
                        )
            else:
                LOG.info("%s does not exist in the scene", node)
                
    '''
    # Import CV values
    if import_cvs is True:
        with open(cvs_import_path) as f:
            cvs_data = json.load(f)

        for ctrl, cvs_positions in cvs_data.items():
            if cmds.objExists(ctrl):
                shapes = (
                    cmds.listRelatives(ctrl, shapes=True, type="nurbsCurve")
                    or []
                )
                for shape in shapes:
                    cvs = cmds.ls(f"{shape}.cv[*]", flatten=True)
                    if cvs and len(cvs) == len(cvs_positions):
                        for cv, pos in zip(cvs, cvs_positions):
                            try:
                                cmds.xform(
                                    cv,
                                    worldSpaceDistance=True,
                                    translation=pos,
                                )
                            except Exception as e:
                                LOG.info(
                                    "Failed to set CV position for %s: %s",
                                    cv,
                                    e,
                                )
                    else:
                        LOG.info(
                            "Mismatch in CV count for %s. Skipping CV update",
                            ctrl,
                        )
            else:
                LOG.info("%s does not exist in the scene", ctrl)

    LOG.info("Import data completed from: %s", directory)'''


def update_teeth_tongue_follow_jaw(edges=None, jaw_joint="M_jaw_main_jnt"):
    # Checks
    if not edges:
        edges = cmds.ls(selection=True, flatten=True) or None
    if not edges or len(edges) != 2:
        cmds.error(
            "Please select exactly 2 edges to create a rivet.", noContext=True
        )
    blendshape = "jaw_blendShape"
    for i in range(3):
        target = utils.rebuild_blendshape_target(blendshape, i)
        cmds.delete(target)

    # Reset controllers
    animation.reset_ctrls(cmds.ls("*_ctrl") + cmds.ls("*:*_ctrl"))

    # Reset tongue blendShape targets
    base_grp = "trash_grp"
    parent = cmds.createNode(
        "transform", name="tongue_crv_ref", parent=base_grp
    )
    crv_drive = "M_tongue_shape_driver"
    utils.duplicate_node(crv_drive, parent, "tmp")[0]

    for i in range(3):
        target = utils.rebuild_blendshape_target(blendshape, i)
        utils.duplicate_node(target, parent, "tmp")[0]

        bs = cmds.blendShape(crv_drive, target)[0]
        cmds.setAttr(f"{bs}.{crv_drive}", 1)
        cmds.delete(target, constructionHistory=True)
        cmds.delete(target)

    # Create rivet
    for association in DEFORMER_SUFFIX_ASSOCIATIONS:
        if association["type"] == "ffd":
            pattern = association["suffix"]
            break

    keys = list(DEFORMERS_STACK["M_body_compil_mesh"].keys())
    last_pattern_index = -1
    for i, key in enumerate(keys):
        if pattern in key:
            last_pattern_index = i

    input_mesh_plug = keys[last_pattern_index + 1] + ".outputGeometry[0]"
    rivet = utils.make_edges_rivet(edges, input_mesh_plug)

    # Create driver
    driver = cmds.createNode("transform", name=f"{rivet}_driver", parent=rivet)
    dmx = cmds.createNode("decomposeMatrix", name="rivet_driver_mouth_dmx")
    cmds.matchTransform(driver, jaw_joint)
    cmds.connectAttr(f"{driver}.worldMatrix[0]", f"{dmx}.inputMatrix")

    # Update setup
    for attr in ["translate", "rotate"]:
        pma_teeth, pma_attr = cmds.listConnections(
            f"{jaw_joint}.{attr}X",
            plugs=True,
            skipConversionNodes=True,
            type="plusMinusAverage",
        )[0].split(".", 1)

        match = re.search(r"\[(\d+)\]", pma_attr)
        number = int(match.group(1))
        pma_attr_increment = pma_attr.replace(f"[{number}]", f"[{number + 1}]")
        pma_tongue = cmds.createNode(
            "plusMinusAverage", name=f"tongue_jawHook{attr}_sum"
        )

        for axis in "xyz":
            # Connect plusMinusAverage
            for pma in [pma_teeth, pma_tongue]:
                cmds.connectAttr(
                    f"{dmx}.output{attr.capitalize()}{axis.upper()}",
                    f"{pma}.{pma_attr[:-1]}{axis}",
                    force=True,
                )

                dmx_value = cmds.getAttr(
                    f"{dmx}.output{attr.capitalize()}{axis.upper()}"
                )
                cmds.setAttr(
                    f"{pma}.{pma_attr_increment[:-1]}{axis}",
                    -dmx_value,
                )

            cmds.connectAttr(
                f"{pma_tongue}.output3D{axis}",
                f"M_tongue_joint_hook.{attr}{axis.upper()}",
            )

        # Reset remap
        remaps = cmds.listConnections(pma_teeth, plugs=True, type="remapValue")
        for remap_plug in remaps:
            remap = remap_plug.split(".")[0]
            for att in ["inputMin", "inputMax", "outputMin", "outputMax"]:
                cmds.setAttr(f"{remap}.{att}", 0)

            for i, plug in enumerate(cmds.ls(f"{remap}.value[*]")):
                value = 0
                if i == len(cmds.ls(f"{remap}.value[*]")) - 1:
                    value = 1
                cmds.setAttr(f"{plug}.value_FloatValue", value)

        # Add message connections
        attr_name = "get"
        attr_string = pma_attr[:-1]
        for node in [pma_teeth, pma_tongue]:
            cmds.addAttr(node, longName=attr_name, dataType="string")
            cmds.setAttr(f"{node}.{attr_name}", attr_string, type="string")
            cmds.connectAttr(
                f"{rivet}.message", f"{node}.{attr_name}", force=True
            )

    apply_tongue_crv_delta()


def apply_tongue_crv_delta():
    blendshape = "jaw_blendShape"
    crv_ref = "M_tongue_high_crv"
    jaw_ctrl = "M_jaw_main_ctrl"
    jaw_pos = [
        [f"{jaw_ctrl}.translateY", -1],
        [f"{jaw_ctrl}.translateX", 1],
        [f"{jaw_ctrl}.translateX", -1],
    ]
    crv_neutral = "M_tongue_shape_tmp_driver"

    animation.reset_ctrls([jaw_ctrl])

    for i in range(3):
        target = cmds.sculptTarget(
            blendshape, edit=True, regenerate=True, target=i
        )
        if not target:
            cmds.error(
                f"Please delete all tongue targets curves from {blendshape}",
                noContext=True,
            )

        target = target[0]

        tokens = target.split("_")
        tokens.insert(-1, "tmp")
        tmp = "_".join(tokens)

        cmds.setAttr(jaw_pos[i][0], jaw_pos[i][1])

        # Delta
        tmp_delta = utils.duplicate_node(crv_neutral, "trash_grp", "delta")[0]
        bs = cmds.blendShape(tmp, crv_ref, tmp_delta)[0]
        cmds.setAttr(f"{bs}.{tmp}", 1)
        cmds.setAttr(f"{bs}.{crv_ref}", -1)
        cmds.delete(tmp_delta, constructionHistory=True)

        bs = cmds.blendShape(tmp_delta, target)[0]
        cmds.setAttr(f"{bs}.{tmp_delta}", 1)
        cmds.delete(target, constructionHistory=True)

        cmds.delete(tmp_delta)
        cmds.delete(target)

        animation.reset_ctrls([jaw_ctrl])


def update_rivet_edges(edges=None):
    # Checks
    if not edges:
        edges = cmds.ls(selection=True, flatten=True) or None
    if not edges or len(edges) != 2:
        cmds.error(
            "Please select exactly 2 edges to create a rivet.", noContext=True
        )
    blendshape = "jaw_blendShape"
    for i in range(3):
        target = utils.rebuild_blendshape_target(blendshape, i)
        cmds.delete(target)

    # Data
    rivet = cmds.ls("*.mouth_rivet")[0].split(".")[0]

    # Reset controllers
    animation.reset_ctrls(cmds.ls("*_ctrl") + cmds.ls("*:*_ctrl"))

    # Edit edges
    driver = utils.get_children(rivet)[0]
    cmds.parent(driver, world=True)

    utils.set_edges_rivet(edges, rivet)

    cmds.parent(driver, rivet)

    # Edit pluMinusAverage values
    pma = cmds.listConnections(
        f"{rivet}.message", plugs=True, type="plusMinusAverage"
    )
    for node_plug in pma:
        node, node_attr = node_plug.split(".")
        node_attr_value = cmds.getAttr(f"{node}.{node_attr}")
        match = re.search(r"\[(\d+)\]", node_attr_value)
        number = int(match.group(1))
        node_attr_edit = node_attr_value.replace(
            f"[{number}]", f"[{number + 1}]"
        )

        for axis in "xyz":
            value = cmds.getAttr(f"{node}.{node_attr_value}{axis}")
            cmds.setAttr(f"{node}.{node_attr_edit}{axis}", -value)

    apply_tongue_crv_delta()


def scale_tongue_ikfk():
    joints = cmds.ls("tongue_*_jnt") + cmds.ls("tongue_*_bind")
    ik_ctrls = cmds.ls("M_tongue_ik_*_ctrl")
    loc_plug = "M_move_locator.inverseMatrix"
    joints_number = []
    numbers = []

    for jnt in joints:
        match = re.search(r"\_(\d+)\_", jnt)
        number = match.group(1)
        joints_number.append(number)
        if number in numbers:
            continue
        numbers.append(number)

    div = len(numbers) / len(ik_ctrls)
    round_div = round(div)

    for i, ctrl in enumerate(ik_ctrls):
        start_idx = i * round_div
        end_idx = start_idx + round_div
        end_idx = min(end_idx, len(numbers))

        dmx = cmds.createNode("decomposeMatrix", name=f"{ctrl}_dmx")
        mmx = cmds.createNode("multMatrix", name=f"{ctrl}_mmx")

        cmds.connectAttr(f"{ctrl}.worldMatrix[0]", f"{mmx}.matrixIn[0]")
        cmds.connectAttr(loc_plug, f"{mmx}.matrixIn[1]")
        cmds.connectAttr(f"{mmx}.matrixSum", f"{dmx}.inputMatrix")

        for num in numbers[start_idx:end_idx]:
            jnt_idxs = [
                index
                for index, value in enumerate(joints_number)
                if value == num
            ]
            for y in jnt_idxs:
                for axis in "XYZ":
                    cmds.connectAttr(
                        f"{dmx}.outputScale{axis}",
                        f"{joints[y]}.scale{axis}",
                        force=True,
                    )


def add_teeth_bend():
    for mode in ["lower", "upper"]:
        # Data
        misc = f"{mode}Teeth_misc_grp"
        mesh_grp = f"{mode}Teeth_geo_grp"
        mesh = utils.get_children(mesh_grp)[-1]
        name = f"{mode}_Teeth_bendX"
        bend_ref = f"{mode}Teeth_bendYHandle"
        ctrl = f"M_{mode}Teeth_main_ctrl"
        attr_name = "curvatureX"

        # Create the bend
        deformer = utils.create_deformer(
            name=name, meshes=[mesh], deformer_type="bend"
        )

        bend = deformer[0]
        handle = deformer[-1]

        # Position the bend
        cmds.parent(handle, misc)
        t = cmds.xform(bend_ref, query=True, translation=True, worldSpace=True)
        r = cmds.xform(bend_ref, query=True, rotation=True, worldSpace=True)
        s = cmds.xform(bend_ref, query=True, scale=True, worldSpace=True)
        r[0] = 90.0
        cmds.xform(handle, translation=t, rotation=r, scale=s)

        # Connect curvature
        cmds.select(ctrl)
        cmds.addAttr(ctrl, longName=attr_name, keyable=True)
        cmds.connectAttr(f"{ctrl}.{attr_name}", f"{bend}.curvature")


def update_inside_mouth_setup(edges=None, jaw_joint="M_jaw_main_jnt"):
    if not edges:
        edges = cmds.ls(selection=True, flatten=True) or None
    if not edges or len(edges) != 2:
        cmds.error(
            "Please select exactly 2 edges to create a rivet.", noContext=True
        )

    update_teeth_tongue_follow_jaw(edges, jaw_joint)
    scale_tongue_ikfk()
    add_teeth_bend()


def clean_facial_rig(delete_move_cluster=True):
    utils.disconnect_clusters_bpm()
    utils.check_controllers_match()
    facial_rig.check_modeling_match()

    # Delete unwanted
    unwanted = (
        utils.get_children("trash_grp")
        + [
            "M_move_cluster",
            "M_move_cluster_loc",
        ]
        if delete_move_cluster is True
        else utils.get_children("trash_grp")
    )
    [cmds.delete(obj) for obj in unwanted if cmds.objExists(obj)]
