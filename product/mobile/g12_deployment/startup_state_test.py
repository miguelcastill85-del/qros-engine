import unittest
import xml.etree.ElementTree as ET
from startup_state import startup_state

PACKAGE = 'app.qros.qros_mobile_studio'


def tree(*nodes):
    root = ET.Element('hierarchy')
    for node in nodes:
        ET.SubElement(root, 'node', node)
    return root


class StartupTests(unittest.TestCase):
    def test_only_observed_foreign_launcher_dialog_can_be_closed(self):
        dialog = tree({'text': "Pixel Launcher isn't responding", 'package': 'android'},
                      {'text': 'Close app', 'package': 'android', 'class': 'android.widget.Button'})
        self.assertEqual(startup_state(dialog, PACKAGE), 'launcher_anr')

    def test_qros_and_unknown_anrs_remain_fail_closed(self):
        for name in ['QROS', 'qros_mobile_studio', 'Other app']:
            with self.assertRaises(RuntimeError):
                startup_state(tree({'text': name + " isn't responding"}), PACKAGE)

    def test_home_requires_both_controls_from_exact_app(self):
        qros = {'text': 'QROS', 'package': PACKAGE}
        menu = {'content-desc': 'Más módulos y seguridad', 'package': PACKAGE}
        self.assertEqual(startup_state(tree(qros, menu), PACKAGE), 'home')
        self.assertEqual(startup_state(tree(qros), PACKAGE), 'waiting')
        self.assertEqual(startup_state(tree(qros, {**menu, 'package': 'foreign'}), PACKAGE), 'waiting')


if __name__ == '__main__':
    unittest.main()
