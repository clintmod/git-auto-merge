"""Property-based tests for the version handling that drives merge ordering."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from packaging.version import Version

import git_auto_merge as gam

semvers = st.tuples(
    st.integers(min_value=0, max_value=999),
    st.integers(min_value=0, max_value=999),
    st.integers(min_value=0, max_value=999),
).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}")

prefixes = st.sampled_from(["hotfix", "release", "hotfix/bank", "release/auto"])


@given(prefix=prefixes, version=semvers)
def test_version_is_extracted_from_branch_name(prefix, version):
    branch = gam.VersionedBranch(f"{prefix}/{version}")
    assert branch.version == version


@given(versions=st.lists(semvers, min_size=1, max_size=25), prefix=prefixes)
def test_versioned_branches_sort_like_semver(versions, prefix):
    branches = [gam.VersionedBranch(f"{prefix}/{v}") for v in versions]
    branches.sort()
    assert [Version(b.version) for b in branches] == sorted(Version(v) for v in versions)


@given(name=st.text(alphabet=st.characters(codec="ascii", categories=["L"]), min_size=1))
def test_branch_without_version_raises(name):
    with pytest.raises(AssertionError):
        gam.VersionedBranch(name)
