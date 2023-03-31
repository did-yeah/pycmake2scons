import logging
import shutil
import tempfile
from itertools import product
from pathlib import Path
from typing import Dict, List

import pytest

from app.util.scan import search_defined_in_if, toscons


def test_search_defined():
    res = search_defined_in_if(b"#if defined(__gnuc__) && defined(test)")
    assert len(res) == 2
    assert res[0] == b"__gnuc__"
    assert res[1] == b"test"

    res = search_defined_in_if(b"#if (defined(__gnuc__) || defined(test))")
    assert len(res) == 2
    assert res[0] == b"__gnuc__"
    assert res[1] == b"test"

    res = search_defined_in_if(b"#if(defined(__gnuc__) || defined(test))")
    assert len(res) == 2
    assert res[0] == b"__gnuc__"
    assert res[1] == b"test"


def test_search_define2(caplog):
    caplog.set_level(logging.WARNING)
    res = search_defined_in_if(b"#if defined(__gnuc__ && defined(test)")
    assert len(res) == 0
    assert caplog.record_tuples == [
        (
            "app.util.scan",
            logging.WARNING,
            "error '__gnuc__ && defined(test' is not a macro keyword",
        )
    ]


def test_search_define3(caplog):
    caplog.set_level(logging.WARNING)
    res = search_defined_in_if(b"#if defined(__gnuc__) && defined(test")
    assert len(res) == 1
    assert res[0] == b"__gnuc__"
    assert caplog.record_tuples == [
        (
            "app.util.scan",
            logging.WARNING,
            "in '#if defined(__gnuc__) && defined(test'",
        ),
        ("app.util.scan", logging.WARNING, "error closing ')' is missing",),
    ]


@pytest.fixture
def create_repo(request):
    """
    request allow to retrive markers applied to a test function
    i.e. introspection
    """
    dir_name = tempfile.mkdtemp()
    #   src_test_dir = Path("tests") / Path("data") / Path("repo1")
    src_test_dir = request.node.get_closest_marker("src_test_dir").args[0]
    if src_test_dir is None:
        shutil.rmtree(dir_name)
        assert 0
    else:
        try:
            dst_name = Path(shutil.copytree(src_test_dir, dir_name, dirs_exist_ok=True))
            yield Path(dir_name)
        finally:
            shutil.rmtree(dir_name)


def assert_dir_content(
    dir_repo: Path, T: toscons, repo_content: Dict[str, List[str]]
) -> None:
    assert len(T.dir_content.keys()) == len(repo_content)
    for i in repo_content.keys():
        assert (dir_repo / Path("src") / Path(i)) in T.dir_content.keys()
    for i, j in repo_content.items():
        assert (dir_repo / Path("src") / Path(i)) in T.dir_content.keys()
        assert set(T.dir_content[dir_repo / Path("src") / Path(i)]) == set(
            map(lambda x: (dir_repo / Path("src") / Path(i) / Path(x)), j)
        )


def assert_dir_suffixes(
    dir_repo: Path, T: toscons, repo_suffixes: Dict[str, Dict[str, List[str]]]
) -> None:
    assert len(T.dir_suffixes.keys()) == len(repo_suffixes)
    for i, j in repo_suffixes.items():
        real_path = dir_repo / Path("src") / Path(i)
        assert real_path in T.dir_suffixes.keys()
        for k, l in j.items():
            assert len(T.dir_suffixes[real_path][k]) == len(l)
            for m in l:
                m_path = dir_repo / Path("src") / Path(i) / Path(m)
                assert m_path in T.dir_suffixes[real_path][k]


@pytest.mark.src_test_dir(Path("tests") / Path("data") / Path("repo1"))
def test_toscons1(create_repo, caplog):
    caplog.set_level(logging.WARNING)
    T = toscons(create_repo / Path("src"))
    # test
    T.scan()
    assert caplog.record_tuples == [
        (
            "app.util.scan",
            logging.WARNING,
            "directory {} contains 1 nested directory".format(
                create_repo / Path("src") / Path("rep11")
            ),
        )
    ]
    # test dir_dir
    assert len(T.dir_dir.keys()) == 1
    res = list(T.dir_dir.items())
    assert res[0][0] == create_repo / Path("src") / Path("rep11")
    assert len(res[0][1]) == 1
    assert res[0][1][0] == Path(
        create_repo / Path("src") / Path("rep11") / Path("rep11_1")
    )
    # test dir_content
    repo_content = {
        "rep2": ["src_2_4.gxx",]
        + ["src_2_{}.{}xx".format(n, m) for n, m in product("123", "ch")],
        "rep11": ["src_11_{}.{}xx".format(n, m) for n, m in product("12", "ch")],
        "rep30": ["src_30_4.lxx",]
        + ["src_30_{}.{}xx".format(n, m) for n, m in product("123", "ch")],
    }
    assert_dir_content(create_repo, T, repo_content)
    # test dir_suffixes
    repo_suffixes = {
        "rep2": {
            ".gxx": ["src_2_4.gxx",],
            ".cxx": ["src_2_{}.cxx".format(n) for n in "123"],
            ".hxx": ["src_2_{}.hxx".format(n) for n in "123"],
        },
        "rep11": {
            ".cxx": ["src_11_{}.cxx".format(n) for n in "12"],
            ".hxx": ["src_11_{}.hxx".format(n) for n in "12"],
        },
        "rep30": {
            ".lxx": ["src_30_4.lxx",],
            ".cxx": ["src_30_{}.cxx".format(n) for n in "123"],
            ".hxx": ["src_30_{}.hxx".format(n) for n in "123"],
        },
    }
    assert_dir_suffixes(create_repo, T, repo_suffixes)
    # test c_dir_name
    assert len(T.c_dir_name) == 0
    # test cxx_dir_name
    repo_cxx_dir = ["rep11", "rep2", "rep30"]
    assert len(T.cxx_dir_name) == len(repo_cxx_dir)
    for i in repo_cxx_dir:
        assert i in T.cxx_dir_name
    # test hxx_dir_only
    assert len(T.hxx_only_dir_name0) == 0
    # test de c_cxx_dir_name
    assert T.c_cxx_dir_name == "'rep11', 'rep2', 'rep30'"
    # test de hxx_only_dir_name
    assert T.hxx_only_dir_name == ""
    # test undefined_test_kword
    undtkw = [
        "tutu",
    ]
    assert len(T.undefined_tested_kword) == len(undtkw)
    for ele in undtkw:
        assert ele in T.undefined_tested_kword
    # test main_pathes
    mainp = [
        "rep2/src_2_1.cxx",
    ]
    assert len(T.main_pathes) == len(mainp)
    for mmain_name in mainp:
        assert mmain_name in T.main_pathes


@pytest.mark.src_test_dir(Path("tests") / Path("data") / Path("repo2"))
def test_toscons2(create_repo, caplog):
    """
    Test de scan.
    test header only directory
    test multiple main in same file
    """
    caplog.set_level(logging.WARNING)
    T = toscons(create_repo / Path("src"))
    # test
    T.scan()
    # test dir_dir
    assert len(T.dir_dir.keys()) == 0
    # test dir_content
    repo_content = {
        "rep2": ["src_2_{}.hxx".format(n) for n in "123"],
        "rep11": ["src_11_{}.{}xx".format(n, m) for n, m in product("12", "ch")],
        "rep30": ["src_30_4.lxx",]
        + ["src_30_{}.{}xx".format(n, m) for n, m in product("123", "ch")],
    }
    assert_dir_content(create_repo, T, repo_content)
    # test dir_suffixes
    repo_suffixes = {
        "rep2": {".hxx": ["src_2_{}.hxx".format(n) for n in "123"],},
        "rep11": {
            ".cxx": ["src_11_{}.cxx".format(n) for n in "12"],
            ".hxx": ["src_11_{}.hxx".format(n) for n in "12"],
        },
        "rep30": {
            ".lxx": ["src_30_4.lxx",],
            ".cxx": ["src_30_{}.cxx".format(n) for n in "123"],
            ".hxx": ["src_30_{}.hxx".format(n) for n in "123"],
        },
    }
    assert_dir_suffixes(create_repo, T, repo_suffixes)
    # test c_dir_name
    assert len(T.c_dir_name) == 0
    # test cxx_dir_name
    repo_cxx_dir = ["rep11", "rep30"]
    assert len(T.cxx_dir_name) == len(repo_cxx_dir)
    for i in repo_cxx_dir:
        assert i in T.cxx_dir_name
    # test hxx_dir_only
    assert len(T.hxx_only_dir_name0) == 1
    repo_hxx_only_dir = [
        "rep2",
    ]
    for i in repo_hxx_only_dir:
        assert i in T.hxx_only_dir_name0
    # test de c_cxx_dir_name
    assert T.c_cxx_dir_name == "'rep11', 'rep30'"
    # test de hxx_only_dir_name
    assert T.hxx_only_dir_name == "'rep2'"
    # test undefined_test_kword
    undtkw = [
        "tutu",
    ]
    assert len(T.undefined_tested_kword) == len(undtkw)
    for ele in undtkw:
        assert ele in T.undefined_tested_kword
    # test main_pathes
    mainp = [
        "rep30/src_30_1.cxx",
    ]
    assert len(T.main_pathes) == len(mainp)
    for mmain_name in mainp:
        assert mmain_name in T.main_pathes
    assert caplog.record_tuples == [
        (
            "app.util.scan",
            logging.WARNING,
            "main found at least 2 times in 'rep30/src_30_1.cxx'",
        ),
        (
            "app.util.scan",
            logging.WARNING,
            "surnumerous main found in 'rep30/src_30_1.cxx'",
        ),
        ("app.util.scan", logging.WARNING, "at line 5 which is '*int main(*void) {'"),
    ]


@pytest.mark.src_test_dir(Path("tests") / Path("data") / Path("repo1"))
def test_toscons3(create_repo, caplog):
    caplog.set_level(logging.WARNING)
    T = toscons(create_repo / Path("src"))
    T.scan()
    assert caplog.record_tuples == [
        (
            "app.util.scan",
            logging.WARNING,
            "directory {} contains 1 nested directory".format(
                create_repo / Path("src") / Path("rep11")
            ),
        )
    ]
    # test
    T.write_in_SConscript()
