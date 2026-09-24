import unittest

from connectome.state_machine import StateMachine, states


class TestStateMachine(unittest.TestCase):
    def test_default_state_is_idle(self):
        machine = StateMachine()
        self.assertEqual(machine.current, "IDLE")

    def test_higher_priority_interrupts_any_state(self):
        machine = StateMachine()
        machine.transition_to("IMPORTANT")
        self.assertEqual(machine.current, "IMPORTANT")
        result = machine.transition_to("WARNING")
        self.assertEqual(result, "WARNING")
        self.assertEqual(machine.current, "WARNING")

    def test_lower_priority_without_permission_is_rejected(self):
        machine = StateMachine()
        machine.force("WARNING")
        result = machine.transition_to("SLEEPING")
        self.assertIsNone(result)
        self.assertEqual(machine.current, "WARNING")

    def test_state_spec_contains_required_fields(self):
        required = {"priority", "duration_ms", "animation", "movement", "speed", "position", "scale", "visibility"}
        for name, spec in states.items():
            self.assertIn(name, states)
            for field in required:
                self.assertIn(field, spec, msg=f"{name} missing {field}")

    def test_unknown_state_raises(self):
        machine = StateMachine()
        with self.assertRaises(KeyError):
            machine.transition_to("NOPE")


if __name__ == "__main__":
    unittest.main()