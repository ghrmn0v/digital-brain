import unittest

from connectome.loader import load_wiring


class TestLoader(unittest.TestCase):
    def test_wiring_loads_from_default_path(self):
        graph = load_wiring()
        self.assertEqual(graph.meta["name"], "adult_drosophila_mushroom_body")
        self.assertIn("KC", graph.nodes)
        self.assertIn("PN", graph.nodes)
        self.assertIn("MBON_output", graph.nodes)
        self.assertIn("DAN_PAM", graph.nodes)
        self.assertIn("DAN_PPL", graph.nodes)

    def test_kc_mbon_edges_are_plastic(self):
        graph = load_wiring()
        plastic = graph.plasticity_edges()
        self.assertTrue(plastic)
        sources = {e.source for e in plastic}
        self.assertEqual(sources, {"KC"})

    def test_all_edges_reference_valid_nodes(self):
        graph = load_wiring()
        for edge in graph.edges.values():
            self.assertIn(edge.source, graph.nodes)
            self.assertIn(edge.target, graph.nodes)

    def test_total_incoming_synapses_positive(self):
        graph = load_wiring()
        targets = {e.target for e in graph.edges.values()}
        for gid in targets:
            self.assertGreater(graph.total_incoming_synapses(gid), 0, msg=gid)


if __name__ == "__main__":
    unittest.main()