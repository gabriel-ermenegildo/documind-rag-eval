import documind


def test_package_is_installed_with_a_version():
    # Fails if the src layout or the build backend is misconfigured.
    assert documind.__version__
