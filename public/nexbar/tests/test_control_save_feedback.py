import importlib.util
import pathlib
import unittest


BRIDGE = pathlib.Path(__file__).parents[1] / 'nexbar-bridge.py'
spec = importlib.util.spec_from_file_location('nexbar_bridge_save_feedback_test', BRIDGE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class ControlSaveFeedbackTests(unittest.TestCase):
    def test_save_button_has_press_saving_and_saved_feedback(self):
        html = bridge.CONTROL_HTML
        self.assertIn('button:active{', html)
        self.assertIn('transform:', html)
        self.assertIn("save.textContent='Saving…'", html)
        self.assertIn("save.textContent='✓ Saved'", html)
        self.assertIn("save.textContent='Save NexBar settings'", html)
        self.assertIn('save.disabled=true', html)
        self.assertIn('save.disabled=false', html)
        self.assertIn('@media(prefers-reduced-motion:reduce)', html)

    def test_save_toast_reports_success_and_failure(self):
        html = bridge.CONTROL_HTML
        self.assertIn('id="toast"', html)
        self.assertIn('role="status"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn("showToast('NexBar settings saved!','ok')", html)
        self.assertIn("showToast('Save failed: '+message,'error')", html)
        self.assertIn('if(!response.ok)', html)


if __name__ == '__main__':
    unittest.main()
