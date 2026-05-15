"""Recipe Version Control

This module provides version control functionality for recipes.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from myeap.core.logging import get_logger

logger = get_logger(__name__)


class VersionControlError(Exception):
    """Version control error"""

    pass


@dataclass
class Version:
    """Semantic version representation"""

    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def parse(cls, version_str: str) -> "Version":
        """Parse version string

        Args:
            version_str: Version in X.Y.Z format

        Returns:
            Version instance

        Raises:
            VersionControlError: If format is invalid
        """
        pattern = r"^(\d+)\.(\d+)\.(\d+)$"
        match = re.match(pattern, version_str)
        if not match:
            raise VersionControlError(
                f"Invalid version format: {version_str}. Expected X.Y.Z"
            )
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
        )

    def increment_major(self) -> "Version":
        """Increment major version (X+1.0.0)"""
        return Version(major=self.major + 1, minor=0, patch=0)

    def increment_minor(self) -> "Version":
        """Increment minor version (X.Y+1.0)"""
        return Version(major=self.major, minor=self.minor + 1, patch=0)

    def increment_patch(self) -> "Version":
        """Increment patch version (X.Y.Z+1)"""
        return Version(major=self.major, minor=self.minor, patch=self.patch + 1)

    def compare(self, other: "Version") -> int:
        """Compare versions

        Returns:
            -1 if self < other
             0 if self == other
             1 if self > other
        """
        self_tuple = (self.major, self.minor, self.patch)
        other_tuple = (other.major, other.minor, other.patch)
        if self_tuple < other_tuple:
            return -1
        elif self_tuple > other_tuple:
            return 1
        return 0


class VersionControl:
    """Recipe version control

    Provides version management for recipes including:
    - Version parsing and comparison
    - Version increment strategies
    - Version history tracking
    """

    def __init__(self):
        self._version_cache: dict[str, Version] = {}

    def parse_version(self, version_str: str) -> Version:
        """Parse version string to Version object

        Args:
            version_str: Version in X.Y.Z format

        Returns:
            Version object
        """
        if version_str in self._version_cache:
            return self._version_cache[version_str]
        version = Version.parse(version_str)
        self._version_cache[version_str] = version
        return version

    def increment_version(
        self, current_version: str, increment_type: str = "patch"
    ) -> str:
        """Increment version string

        Args:
            current_version: Current version string (X.Y.Z)
            increment_type: Type of increment ('major', 'minor', 'patch')

        Returns:
            New version string

        Raises:
            VersionControlError: If increment type is invalid
        """
        version = self.parse_version(current_version)

        if increment_type == "major":
            new_version = version.increment_major()
        elif increment_type == "minor":
            new_version = version.increment_minor()
        elif increment_type == "patch":
            new_version = version.increment_patch()
        else:
            raise VersionControlError(f"Invalid increment type: {increment_type}")

        new_version_str = str(new_version)
        logger.info(
            "version_incremented",
            old_version=current_version,
            new_version=new_version_str,
            increment_type=increment_type,
        )
        return new_version_str

    def compare_versions(self, version1: str, version2: str) -> int:
        """Compare two versions

        Args:
            version1: First version string
            version2: Second version string

        Returns:
            -1 if version1 < version2
             0 if version1 == version2
             1 if version1 > version2
        """
        v1 = self.parse_version(version1)
        v2 = self.parse_version(version2)
        return v1.compare(v2)

    def get_latest_version(self, versions: List[str]) -> Optional[str]:
        """Get the latest version from a list

        Args:
            versions: List of version strings

        Returns:
            Latest version string or None if list is empty
        """
        if not versions:
            return None

        latest = versions[0]
        for version in versions[1:]:
            if self.compare_versions(version, latest) > 0:
                latest = version
        return latest

    def is_compatible(self, base_version: str, check_version: str) -> bool:
        """Check if check_version is compatible with base_version

        Semantic versioning compatible means:
        - Same major version
        - Check version >= base version

        Args:
            base_version: Base version string
            check_version: Version to check

        Returns:
            True if compatible
        """
        base = self.parse_version(base_version)
        check = self.parse_version(check_version)

        # Compatible if same major version and check >= base
        return base.major == check.major and check.compare(base) >= 0

    def suggest_next_version(
        self, current_version: str, change_type: str
    ) -> str:
        """Suggest next version based on change type

        Args:
            current_version: Current version string
            change_type: Type of change
                - 'breaking': Major increment
                - 'feature': Minor increment
                - 'bugfix': Patch increment
                - 'auto': Automatic determination

        Returns:
            Suggested next version
        """
        if change_type == "breaking":
            return self.increment_version(current_version, "major")
        elif change_type == "feature":
            return self.increment_version(current_version, "minor")
        elif change_type == "bugfix":
            return self.increment_version(current_version, "patch")
        elif change_type == "auto":
            # Default to patch for automatic
            return self.increment_version(current_version, "patch")
        else:
            raise VersionControlError(f"Invalid change type: {change_type}")

    def build_version_tree(
        self, recipes: List[dict]
    ) -> dict[str, List[str]]:
        """Build version tree from recipe list

        Args:
            recipes: List of recipe dictionaries with 'id' and 'parent_version_id'

        Returns:
            Dictionary mapping parent_id to list of child_ids
        """
        tree: dict[str, List[str]] = {}

        for recipe in recipes:
            parent_id = recipe.get("parent_version_id")
            recipe_id = recipe["id"]

            if parent_id:
                if parent_id not in tree:
                    tree[parent_id] = []
                tree[parent_id].append(recipe_id)

        return tree

    def get_version_lineage(
        self, recipe_id: str, recipes: List[dict]
    ) -> List[dict]:
        """Get complete version lineage for a recipe

        Args:
            recipe_id: Starting recipe ID
            recipes: List of all recipes

        Returns:
            List of recipes in lineage from oldest to newest
        """
        # Build ID to recipe mapping
        recipe_map = {r["id"]: r for r in recipes}

        lineage = []
        current_id = recipe_id

        while current_id and current_id in recipe_map:
            recipe = recipe_map[current_id]
            lineage.append(recipe)
            current_id = recipe.get("parent_version_id")

        return lineage

    def get_branch_point(
        self, recipe1_id: str, recipe2_id: str, recipes: List[dict]
    ) -> Optional[str]:
        """Find the branch point between two version lineages

        Args:
            recipe1_id: First recipe ID
            recipe2_id: Second recipe ID
            recipes: List of all recipes

        Returns:
            Common ancestor recipe ID or None if no common ancestor
        """
        # Get lineages
        lineage1 = set(r["id"] for r in self.get_version_lineage(recipe1_id, recipes))
        lineage2 = self.get_version_lineage(recipe2_id, recipes)

        # Find common ancestor
        for recipe in lineage2:
            if recipe["id"] in lineage1:
                return recipe["id"]

        return None


# Global version control instance
_version_control: Optional[VersionControl] = None


def get_version_control() -> VersionControl:
    """Get global version control instance"""
    global _version_control
    if _version_control is None:
        _version_control = VersionControl()
    return _version_control
