import pathlib, tempfile, unittest
from build_native_probe import platform_jar


class PlatformTests(unittest.TestCase):
    def test_extension_api_is_not_misparsed_as_integer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for name in ['android-35', 'android-35-ext18', 'android-36', 'android-preview']:
                jar = root/'platforms'/name/'android.jar'
                jar.parent.mkdir(parents=True);jar.touch()
            self.assertEqual(platform_jar(root).parent.name, 'android-36')
            (root/'platforms/android-36/android.jar').unlink()
            self.assertEqual(platform_jar(root).parent.name, 'android-35-ext18')


if __name__ == '__main__':
    unittest.main()
