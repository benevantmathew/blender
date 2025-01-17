# SPDX-FileCopyrightText: 2021-2023 Blender Authors
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pathlib
import sys
import unittest
import tempfile
from pxr import Usd
from pxr import UsdShade
from pxr import UsdGeom
from pxr import Sdf

import bpy

args = None


class AbstractUSDTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.testdir = args.testdir
        cls._tempdir = tempfile.TemporaryDirectory()
        cls.tempdir = pathlib.Path(cls._tempdir.name)

    def setUp(self):
        self.assertTrue(self.testdir.exists(),
                        'Test dir {0} should exist'.format(self.testdir))

        # Make sure we always start with a known-empty file.
        bpy.ops.wm.open_mainfile(filepath=str(self.testdir / "empty.blend"))

    def tearDown(self):
        self._tempdir.cleanup()


class USDImportTest(AbstractUSDTest):

    def test_import_operator(self):
        """Test running the import operator on valid and invalid files."""

        infile = str(self.testdir / "usd_mesh_polygon_types.usda")
        res = bpy.ops.wm.usd_import(filepath=infile)
        self.assertEqual({'FINISHED'}, res, f"Unable to import USD file {infile}")

        infile = str(self.testdir / "this_file_doesn't_exist.usda")
        res = bpy.ops.wm.usd_import(filepath=infile)
        self.assertEqual({'CANCELLED'}, res, "Was somehow able to import a non-existent USD file!")

    def test_import_prim_hierarchy(self):
        """Test importing a simple object hierarchy from a USDA file."""

        infile = str(self.testdir / "prim-hierarchy.usda")

        res = bpy.ops.wm.usd_import(filepath=infile)
        self.assertEqual({'FINISHED'}, res, f"Unable to import USD file {infile}")

        objects = bpy.context.scene.collection.objects
        self.assertEqual(5, len(objects), f"Test scene {infile} should have five objects; found {len(objects)}")

        # Test the hierarchy.
        self.assertIsNone(objects['World'].parent, "/World should not be parented.")
        self.assertEqual(objects['World'], objects['Plane'].parent, "Plane should be child of /World")
        self.assertEqual(objects['World'], objects['Plane_001'].parent, "Plane_001 should be a child of /World")
        self.assertEqual(objects['World'], objects['Empty'].parent, "Empty should be a child of /World")
        self.assertEqual(objects['Empty'], objects['Plane_002'].parent, "Plane_002 should be a child of /World")

    def test_import_mesh_topology(self):
        """Test importing meshes with different polygon types."""

        infile = str(self.testdir / "usd_mesh_polygon_types.usda")
        res = bpy.ops.wm.usd_import(filepath=infile)
        self.assertEqual({'FINISHED'}, res, f"Unable to import USD file {infile}")

        objects = bpy.context.scene.collection.objects
        self.assertEqual(5, len(objects), f"Test scene {infile} should have five objects; found {len(objects)}")

        # Test topology counts.
        self.assertIn("m_degenerate", objects, "Scene does not contain object m_degenerate")
        mesh = objects["m_degenerate"].data
        self.assertEqual(len(mesh.polygons), 2)
        self.assertEqual(len(mesh.edges), 7)
        self.assertEqual(len(mesh.vertices), 6)

        self.assertIn("m_triangles", objects, "Scene does not contain object m_triangles")
        mesh = objects["m_triangles"].data
        self.assertEqual(len(mesh.polygons), 2)
        self.assertEqual(len(mesh.edges), 5)
        self.assertEqual(len(mesh.vertices), 4)
        self.assertEqual(len(mesh.polygons[0].vertices), 3)

        self.assertIn("m_quad", objects, "Scene does not contain object m_quad")
        mesh = objects["m_quad"].data
        self.assertEqual(len(mesh.polygons), 1)
        self.assertEqual(len(mesh.edges), 4)
        self.assertEqual(len(mesh.vertices), 4)
        self.assertEqual(len(mesh.polygons[0].vertices), 4)

        self.assertIn("m_ngon_concave", objects, "Scene does not contain object m_ngon_concave")
        mesh = objects["m_ngon_concave"].data
        self.assertEqual(len(mesh.polygons), 1)
        self.assertEqual(len(mesh.edges), 5)
        self.assertEqual(len(mesh.vertices), 5)
        self.assertEqual(len(mesh.polygons[0].vertices), 5)

        self.assertIn("m_ngon_convex", objects, "Scene does not contain object m_ngon_convex")
        mesh = objects["m_ngon_convex"].data
        self.assertEqual(len(mesh.polygons), 1)
        self.assertEqual(len(mesh.edges), 5)
        self.assertEqual(len(mesh.vertices), 5)
        self.assertEqual(len(mesh.polygons[0].vertices), 5)

    def test_import_mesh_uv_maps(self):
        """Test importing meshes with udim UVs and multiple UV sets."""

        infile = str(self.testdir / "usd_mesh_udim.usda")
        res = bpy.ops.wm.usd_import(filepath=infile)
        self.assertEqual({'FINISHED'}, res, f"Unable to import USD file {infile}")

        objects = bpy.context.scene.collection.objects
        if "preview" in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects["preview"])
        self.assertEqual(1, len(objects), f"File {infile} should contain one object, found {len(objects)}")

        mesh = bpy.data.objects["uvmap_plane"].data
        self.assertEqual(len(mesh.uv_layers), 2,
                         f"Object uvmap_plane should have two uv layers, found {len(mesh.uv_layers)}")

        expected_layer_names = {"udim_map", "uvmap"}
        imported_layer_names = set(mesh.uv_layers.keys())
        self.assertEqual(
            expected_layer_names,
            imported_layer_names,
            f"Expected layer names ({expected_layer_names}) not found on uvmap_plane.")

        def get_coords(data):
            coords = [x.uv for x in uvmap]
            return coords

        def uv_min_max(data):
            coords = get_coords(data)
            uv_min_x = min([uv[0] for uv in coords])
            uv_max_x = max([uv[0] for uv in coords])
            uv_min_y = min([uv[1] for uv in coords])
            uv_max_y = max([uv[1] for uv in coords])
            return uv_min_x, uv_max_x, uv_min_y, uv_max_y

        # Quick tests for point range.
        uvmap = mesh.uv_layers["uvmap"].data
        self.assertEqual(len(uvmap), 128)
        min_x, max_x, min_y, max_y = uv_min_max(uvmap)
        self.assertGreaterEqual(min_x, 0.0)
        self.assertGreaterEqual(min_y, 0.0)
        self.assertLessEqual(max_x, 1.0)
        self.assertLessEqual(max_y, 1.0)

        uvmap = mesh.uv_layers["udim_map"].data
        self.assertEqual(len(uvmap), 128)
        min_x, max_x, min_y, max_y = uv_min_max(uvmap)
        self.assertGreaterEqual(min_x, 0.0)
        self.assertGreaterEqual(min_y, 0.0)
        self.assertLessEqual(max_x, 2.0)
        self.assertLessEqual(max_y, 1.0)

        # Make sure at least some points are in a udim tile.
        coords = get_coords(uvmap)
        coords = list(filter(lambda x: x[0] > 1.0, coords))
        self.assertGreater(len(coords), 16)

    def test_import_camera_properties(self):
        """Test importing camera to ensure properties set correctly."""

        # This file has metersPerUnit = 1
        infile = str(self.testdir / "usd_camera_test_1.usda")
        res = bpy.ops.wm.usd_import(filepath=infile)
        self.assertEqual({'FINISHED'}, res)

        camera_object = bpy.data.objects["Test_Camera"]
        test_cam = camera_object.data

        self.assertAlmostEqual(43.12, test_cam.lens, 2)
        self.assertAlmostEqual(24.89, test_cam.sensor_width, 2)
        self.assertAlmostEqual(14.00, test_cam.sensor_height, 2)
        self.assertAlmostEqual(12.34, test_cam.shift_x, 2)
        self.assertAlmostEqual(56.78, test_cam.shift_y, 2)

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

        # This file has metersPerUnit = 0.1
        infile = str(self.testdir / "usd_camera_test_2.usda")
        res = bpy.ops.wm.usd_import(filepath=infile)
        self.assertEqual({'FINISHED'}, res)

        camera_object = bpy.data.objects["Test_Camera"]
        test_cam = camera_object.data

        self.assertAlmostEqual(4.312, test_cam.lens, 3)
        self.assertAlmostEqual(2.489, test_cam.sensor_width, 3)
        self.assertAlmostEqual(1.400, test_cam.sensor_height, 3)
        self.assertAlmostEqual(1.234, test_cam.shift_x, 3)
        self.assertAlmostEqual(5.678, test_cam.shift_y, 3)

    def test_import_shader_varname_with_connection(self):
        """Test importing USD shader where uv primvar is a connection"""

        varname = "testmap"
        texfile = str(self.testdir / "textures/test_grid_1001.png")

        # Create the test USD file.
        temp_usd_file = str(self.tempdir / "usd_varname_test.usda")
        stage = Usd.Stage.CreateNew(temp_usd_file)
        mesh1 = stage.DefinePrim("/mesh1", "Mesh")
        mesh2 = stage.DefinePrim("/mesh2", "Mesh")

        # Create two USD preview surface shaders in two materials.
        m1 = UsdShade.Material.Define(stage, "/mat1")
        s1 = UsdShade.Shader.Define(stage, "/mat1/previewshader")
        s1.CreateIdAttr("UsdPreviewSurface")
        m1.CreateSurfaceOutput().ConnectToSource(s1.ConnectableAPI(), "surface")
        t1 = UsdShade.Shader.Define(stage, "/mat1/diffuseTexture")
        t1.CreateIdAttr("UsdUVTexture")
        t1.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(texfile)
        t1.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        s1.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(t1.ConnectableAPI(), "rgb")
        t2 = UsdShade.Shader.Define(stage, "/mat1/roughnessTexture")
        t2.CreateIdAttr("UsdUVTexture")
        t2.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(texfile)
        t2.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        s1.CreateInput("roughness", Sdf.ValueTypeNames.Color3f).ConnectToSource(t2.ConnectableAPI(), "rgb")

        m2 = UsdShade.Material.Define(stage, "/mat2")
        s2 = UsdShade.Shader.Define(stage, "/mat2/previewshader")
        s2.CreateIdAttr("UsdPreviewSurface")
        m2.CreateSurfaceOutput().ConnectToSource(s2.ConnectableAPI(), "surface")
        t3 = UsdShade.Shader.Define(stage, "/mat2/diffuseTexture")
        t3.CreateIdAttr("UsdUVTexture")
        t3.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(texfile)
        t3.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        s2.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(t3.ConnectableAPI(), "rgb")
        t4 = UsdShade.Shader.Define(stage, "/mat2/roughnessTexture")
        t4.CreateIdAttr("UsdUVTexture")
        t4.CreateInput('file', Sdf.ValueTypeNames.Asset).Set(texfile)
        t4.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        s2.CreateInput("roughness", Sdf.ValueTypeNames.Color3f).ConnectToSource(t4.ConnectableAPI(), "rgb")

        # Bind mat1 to mesh1, mat2 to mesh2.
        bindingAPI = UsdShade.MaterialBindingAPI.Apply(mesh1)
        bindingAPI.Bind(m1)
        bindingAPI = UsdShade.MaterialBindingAPI.Apply(mesh2)
        bindingAPI.Bind(m2)

        # Create varname defined as a token.
        s3 = UsdShade.Shader.Define(stage, "/mat1/primvar_reader1")
        s3.CreateIdAttr('UsdPrimvarReader_float2')
        s3input = s3.CreateInput("varname", Sdf.ValueTypeNames.Token)
        s3input.Set(varname)
        t1.CreateInput("st", Sdf.ValueTypeNames.TexCoord2f).ConnectToSource(s3.ConnectableAPI(), "result")

        # Create varname defined as a connection to a token.
        varname1 = m1.CreateInput("varname", Sdf.ValueTypeNames.Token)
        varname1.Set(varname)
        s4 = UsdShade.Shader.Define(stage, "/mat1/primvar_reader2")
        s4.CreateIdAttr('UsdPrimvarReader_float2')
        s4input = s4.CreateInput("varname", Sdf.ValueTypeNames.Token)
        UsdShade.ConnectableAPI.ConnectToSource(s4input, varname1)
        t2.CreateInput("st", Sdf.ValueTypeNames.TexCoord2f).ConnectToSource(s4.ConnectableAPI(), "result")

        # Create varname defined as a string.
        s5 = UsdShade.Shader.Define(stage, "/mat2/primvar_reader1")
        s5.CreateIdAttr('UsdPrimvarReader_float2')
        s5input = s5.CreateInput("varname", Sdf.ValueTypeNames.String)
        s5input.Set(varname)
        t3.CreateInput("st", Sdf.ValueTypeNames.TexCoord2f).ConnectToSource(s5.ConnectableAPI(), "result")

        # Create varname defined as a connection to a string.
        varname2 = m2.CreateInput("varname", Sdf.ValueTypeNames.String)
        varname2.Set(varname)
        s6 = UsdShade.Shader.Define(stage, "/mat2/primvar_reader2")
        s6.CreateIdAttr('UsdPrimvarReader_float2')
        s6input = s6.CreateInput("varname", Sdf.ValueTypeNames.String)
        UsdShade.ConnectableAPI.ConnectToSource(s6input, varname2)
        t4.CreateInput("st", Sdf.ValueTypeNames.TexCoord2f).ConnectToSource(s6.ConnectableAPI(), "result")

        stage.Save()

        # Now import the USD file.
        res = bpy.ops.wm.usd_import(filepath=temp_usd_file, import_all_materials=True)
        self.assertEqual({'FINISHED'}, res)

        # Ensure that we find the correct varname for all four primvar readers.
        num_uvmaps_found = 0
        mats_to_test = []
        mats_to_test.append(bpy.data.materials["mat1"])
        mats_to_test.append(bpy.data.materials["mat2"])
        for mat in mats_to_test:
            self.assertIsNotNone(mat.node_tree, "Material node tree is empty")
            for node in mat.node_tree.nodes:
                if node.type == "UVMAP":
                    self.assertEqual(varname, node.uv_map, "Unexpected value for varname")
                    num_uvmaps_found += 1

        self.assertEqual(4, num_uvmaps_found, "One or more test materials failed to import")


def main():
    global args
    import argparse

    if '--' in sys.argv:
        argv = [sys.argv[0]] + sys.argv[sys.argv.index('--') + 1:]
    else:
        argv = sys.argv

    parser = argparse.ArgumentParser()
    parser.add_argument('--testdir', required=True, type=pathlib.Path)
    args, remaining = parser.parse_known_args(argv)

    unittest.main(argv=remaining)


if __name__ == "__main__":
    main()
