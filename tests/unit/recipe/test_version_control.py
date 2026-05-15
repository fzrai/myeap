"""Version control tests"""

import pytest

from myeap.recipe.version_control import (
    Version,
    VersionControl,
    VersionControlError,
    get_version_control,
)


class TestVersion:
    """Version tests"""

    def test_parse_valid_version(self):
        """Test parsing valid version"""
        v = Version.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_parse_invalid_version(self):
        """Test parsing invalid version"""
        with pytest.raises(VersionControlError, match="Invalid version format"):
            Version.parse("invalid")

        with pytest.raises(VersionControlError, match="Invalid version format"):
            Version.parse("1.2")  # Missing patch

        with pytest.raises(VersionControlError, match="Invalid version format"):
            Version.parse("a.b.c")  # Non-numeric

    def test_str_representation(self):
        """Test string representation"""
        v = Version(1, 2, 3)
        assert str(v) == "1.2.3"

    def test_increment_major(self):
        """Test incrementing major version"""
        v = Version(1, 2, 3)
        new_v = v.increment_major()
        assert new_v.major == 2
        assert new_v.minor == 0
        assert new_v.patch == 0

    def test_increment_minor(self):
        """Test incrementing minor version"""
        v = Version(1, 2, 3)
        new_v = v.increment_minor()
        assert new_v.major == 1
        assert new_v.minor == 3
        assert new_v.patch == 0

    def test_increment_patch(self):
        """Test incrementing patch version"""
        v = Version(1, 2, 3)
        new_v = v.increment_patch()
        assert new_v.major == 1
        assert new_v.minor == 2
        assert new_v.patch == 4

    def test_compare(self):
        """Test version comparison"""
        v1 = Version(1, 0, 0)
        v2 = Version(2, 0, 0)
        v3 = Version(1, 0, 0)

        assert v1.compare(v2) == -1
        assert v2.compare(v1) == 1
        assert v1.compare(v3) == 0


class TestVersionControl:
    """Version control tests"""

    def test_parse_version(self):
        """Test parsing version string"""
        vc = VersionControl()
        v = vc.parse_version("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_parse_version_caching(self):
        """Test version parsing uses cache"""
        vc = VersionControl()
        v1 = vc.parse_version("1.2.3")
        v2 = vc.parse_version("1.2.3")
        assert v1 is v2  # Same object due to caching

    def test_increment_version_patch(self):
        """Test incrementing patch version"""
        vc = VersionControl()
        new_version = vc.increment_version("1.2.3", "patch")
        assert new_version == "1.2.4"

    def test_increment_version_minor(self):
        """Test incrementing minor version"""
        vc = VersionControl()
        new_version = vc.increment_version("1.2.3", "minor")
        assert new_version == "1.3.0"

    def test_increment_version_major(self):
        """Test incrementing major version"""
        vc = VersionControl()
        new_version = vc.increment_version("1.2.3", "major")
        assert new_version == "2.0.0"

    def test_increment_version_invalid_type(self):
        """Test increment with invalid type"""
        vc = VersionControl()
        with pytest.raises(VersionControlError, match="Invalid increment type"):
            vc.increment_version("1.2.3", "invalid")

    def test_compare_versions(self):
        """Test comparing versions"""
        vc = VersionControl()

        assert vc.compare_versions("1.0.0", "2.0.0") == -1
        assert vc.compare_versions("2.0.0", "1.0.0") == 1
        assert vc.compare_versions("1.0.0", "1.0.0") == 0
        assert vc.compare_versions("1.2.3", "1.2.4") == -1

    def test_get_latest_version(self):
        """Test getting latest version"""
        vc = VersionControl()
        versions = ["1.0.0", "2.0.0", "1.5.0", "3.0.0"]
        latest = vc.get_latest_version(versions)
        assert latest == "3.0.0"

    def test_get_latest_version_empty(self):
        """Test getting latest from empty list"""
        vc = VersionControl()
        latest = vc.get_latest_version([])
        assert latest is None

    def test_is_compatible_same_major(self):
        """Test compatibility check with same major version"""
        vc = VersionControl()
        # Same version is compatible
        assert vc.is_compatible("1.0.0", "1.0.0")
        # Minor version upgrades are compatible (backward compatible)
        assert vc.is_compatible("1.0.0", "1.5.0")
        assert vc.is_compatible("1.2.3", "1.5.0")
        # Major version upgrades are NOT compatible (breaking changes)
        assert not vc.is_compatible("1.0.0", "2.0.0")

    def test_is_compatible_different_major(self):
        """Test compatibility check with different major version"""
        vc = VersionControl()
        assert not vc.is_compatible("2.0.0", "1.0.0")
        assert not vc.is_compatible("2.0.0", "3.0.0")

    def test_suggest_next_version_breaking(self):
        """Test suggesting next version for breaking change"""
        vc = VersionControl()
        assert vc.suggest_next_version("1.2.3", "breaking") == "2.0.0"

    def test_suggest_next_version_feature(self):
        """Test suggesting next version for feature"""
        vc = VersionControl()
        assert vc.suggest_next_version("1.2.3", "feature") == "1.3.0"

    def test_suggest_next_version_bugfix(self):
        """Test suggesting next version for bugfix"""
        vc = VersionControl()
        assert vc.suggest_next_version("1.2.3", "bugfix") == "1.2.4"

    def test_build_version_tree(self):
        """Test building version tree"""
        vc = VersionControl()
        recipes = [
            {"id": "v3", "parent_version_id": "v2"},
            {"id": "v2", "parent_version_id": "v1"},
            {"id": "v1", "parent_version_id": None},
            {"id": "v4", "parent_version_id": "v2"},  # Another child of v2
        ]

        tree = vc.build_version_tree(recipes)

        assert "v1" in tree
        assert "v2" in tree
        assert "v1" not in tree.get("v1", [])
        assert "v3" in tree["v2"]
        assert "v4" in tree["v2"]

    def test_get_version_lineage(self):
        """Test getting version lineage"""
        vc = VersionControl()
        recipes = [
            {"id": "v1", "parent_version_id": None, "version": "1.0.0"},
            {"id": "v2", "parent_version_id": "v1", "version": "1.1.0"},
            {"id": "v3", "parent_version_id": "v2", "version": "1.2.0"},
        ]

        lineage = vc.get_version_lineage("v3", recipes)

        # Lineage is returned from newest to oldest (starting from the given ID)
        assert len(lineage) == 3
        assert lineage[0]["id"] == "v3"  # Newest
        assert lineage[1]["id"] == "v2"
        assert lineage[2]["id"] == "v1"  # Oldest

    def test_get_branch_point(self):
        """Test finding branch point"""
        vc = VersionControl()
        recipes = [
            {"id": "v1", "parent_version_id": None},
            {"id": "v2", "parent_version_id": "v1"},
            {"id": "v3a", "parent_version_id": "v2"},  # Branch A
            {"id": "v3b", "parent_version_id": "v2"},  # Branch B
        ]

        branch_point = vc.get_branch_point("v3a", "v3b", recipes)
        assert branch_point == "v2"

    def test_get_branch_point_no_common(self):
        """Test branch point with no common ancestor"""
        vc = VersionControl()
        recipes = [
            {"id": "v1a", "parent_version_id": None},
            {"id": "v1b", "parent_version_id": None},
        ]

        branch_point = vc.get_branch_point("v1a", "v1b", recipes)
        assert branch_point is None


class TestGetVersionControl:
    """Test global version control instance"""

    def test_get_version_control_singleton(self):
        """Test getting global instance is singleton"""
        vc1 = get_version_control()
        vc2 = get_version_control()
        assert vc1 is vc2
