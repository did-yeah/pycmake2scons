import difflib
import logging
import textwrap
import typing
from collections import Counter, defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, Set, Tuple

from jinja2 import Environment, PackageLoader, select_autoescape

logger = logging.getLogger(__name__)


def search_defined_in_if(line: bytes) -> List[bytes]:
    """
    search for defined values if lines starting with '#if'

    >>> res = search_defined_in_if(b"#if defined(gnuc)")
    >>> len(res)
    1
    >>> res[0]
    b"gnuc"
    """
    res: List[bytes] = []
    kword: bytes = b""
    next_start = line.find(b"defined(", 1)
    while (next_start != -1) and (next_start < len(line)):
        parent_end = line.find(b")", next_start)
        if parent_end == -1:
            logger.warning("in '{}'".format(line.decode()))
            logger.warning("error closing ')' is missing")
            return res
        kword = line[next_start + 8 : parent_end].strip()
        if len(kword.split()) != 1:
            logger.warning("error '{}' is not a macro keyword".format(kword.decode()))
            return res
        else:
            res.append(kword)
        next_start = line.find(b"defined(", parent_end + 1)
    return res


class toscons:
    """
    main class for dealing with conversion to scons
    """

    def __init__(self, src_path: Path) -> None:
        """
        src_path must be the directory where sources are stored
        """
        self.src_path = src_path
        self.dir_content: DefaultDict[Path, List[Path]] = defaultdict(list)
        self.dir_dir: DefaultDict[Path, List[Path]] = defaultdict(list)
        self.dir_suffixes: Dict[Path, DefaultDict[str, List[Path]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.cxx_dir: List[Path] = []
        self.cxx_dir_name: List[str] = []
        self.c_dir: List[Path] = []
        self.c_dir_name: List[str] = []
        self.hxx_only_dir: List[Path] = []
        self.hxx_only_dir_name0: List[str] = []
        self.env = Environment(
            loader=PackageLoader("app"), autoescape=select_autoescape()
        )
        self.all_define: Set[bytes] = set()
        self.tested_define: Set[bytes] = set()
        self.main_pathes: List[str] = []
        self.lib_pathes: List[Tuple[str, str]] = []

    def scan_dir_and_file(self) -> None:
        """
        scan src directory and fill:
        dir_dir which is directory path at second level
        dir_content which is path at first level
        dir_suffixes which is a dict of dict of path, first key is directory
        secong key is suffixe.
        """
        count = 0
        dir_count = 0
        suffixes: typing.Counter[str] = Counter()
        for p in self.src_path.iterdir():
            count += 1
            if p.is_dir():
                dir_count += 1
                self.dir_content[p] = []
                for q in p.iterdir():
                    if q.is_dir():
                        self.dir_dir[p].append(q)
                    elif not q.name.startswith("."):
                        self.dir_content[p].append(q)
                        suf = "".join(q.suffixes)
                        self.dir_suffixes[p][suf].append(q)
                        suffixes[suf] += 1
                    else:
                        logger.info("{} ignored".format(q.name))
        logger.info("python program directory is {}".format(Path.cwd()))
        logger.info(f"{count} entries found in {self.src_path.name}")
        logger.info(f"{dir_count} directories found in {self.src_path.name}")
        suf_str = textwrap.fill(
            ", ".join(
                (
                    "'{}' appears {} times".format(su, cnt)
                    for su, cnt in suffixes.most_common()
                )
            )
        )
        logger.info(f"{suf_str} in {self.src_path.name}")
        for rep1, rep2 in self.dir_dir.items():
            if len(rep2) != 0:
                logger.warning(
                    "directory {} contains {} nested directory".format(rep1, len(rep2))
                )

    def search_c_cxx_file(self) -> None:
        """
        this fonction should be run after scan_dir_and_file was run
        it fills self.c_dir,
                 self.cxx_dir,
                 self.hxx_only_dir,
                 self.c_dir_name,
                 self.cxx_dir_name,
                 self.hxx_only_dir_name0,
        """
        for rep1, suf_dct in self.dir_suffixes.items():
            suf1 = set(suf_dct.keys())
            is_c = len(suf1 & set((".c",))) != 0
            is_cxx = len(suf1 & set((".cpp", ".cxx", ".c++", "C++", ".C"))) != 0
            is_hxx_only = (
                (not is_cxx)
                and (not is_c)
                and (len(suf1 & set((".hxx", ".hpp", ".h"))) == 1)
            )
            if is_cxx:
                self.cxx_dir.append(rep1)
            if is_hxx_only:
                self.hxx_only_dir.append(rep1)
            if is_c:
                self.c_dir.append(rep1)
        self.cxx_dir_name = sorted([rep1.parts[-1] for rep1 in self.cxx_dir])
        self.hxx_only_dir_name0 = sorted([rep1.parts[-1] for rep1 in self.hxx_only_dir])
        self.c_dir_name = sorted([rep1.parts[-1] for rep1 in self.c_dir])
        cxx_dir_msg = textwrap.fill(", ".join(self.cxx_dir_name))
        hxx_only_dir_msg = textwrap.fill(", ".join(self.hxx_only_dir_name0))
        c_dir_msg = textwrap.fill(", ".join(self.c_dir_name))
        logger.info("{} c++ directories found".format(len(self.cxx_dir)))
        logger.info(f"{cxx_dir_msg}\n appears to be c++ directory")
        logger.info("{} header only directories found".format(len(self.hxx_only_dir)))
        logger.info(f"{hxx_only_dir_msg}\n appears to be header only directory")
        logger.info("{} c directories found".format(len(self.c_dir)))
        logger.info(f"{c_dir_msg}\n appears to be c directory")

    @property
    def c_cxx_dir_name(self) -> str:
        """
        this fonction should be called after search_c_cxx_file was run
        return string suitable for use in a template
        """
        return textwrap.fill(
            ", ".join(
                map(
                    lambda i: "'{}'".format(i),
                    sorted(set(self.cxx_dir_name) | set(self.c_dir_name)),
                )
            )
        )

    @property
    def hxx_only_dir_name(self) -> str:
        """
        this fonction should be called after search_c_cxx_file was run
        return string suitable for use in a template
        """
        return textwrap.fill(
            ", ".join(map(lambda i: "'{}'".format(i), sorted(self.hxx_only_dir_name0),))
        )

    def scan_macros(self) -> None:
        """
        this fonction should be called after search_c_cxx_file was run
        it fills self.undefined_tested_kword, self.tested_define, self.all_define
        """
        for rep3 in set(self.cxx_dir) | set(self.c_dir) | set(self.hxx_only_dir):
            for fsource in self.dir_content[rep3]:
                suf = "".join(fsource.suffixes)
                if suf in (
                    ".c",
                    ".h",
                    ".cpp",
                    ".hpp",
                    ".cxx",
                    ".hxx",
                    ".c++",
                    ".C++",
                    ".C",
                ):
                    with open(fsource, "rb") as f:
                        for l in filter(
                            lambda i: i.startswith(b"#"), f.read().splitlines()
                        ):
                            l1: bytes = l[1:].strip()
                            if l1.startswith(b"define"):
                                self.all_define.add(l.split()[1])
                            elif (
                                l1.startswith(b"if ")
                                or l1.startswith(b"elif ")
                                or l1.startswith(b"elif(")
                                or l1.startswith(b"if(")
                            ):
                                self.tested_define |= set(search_defined_in_if(l))
                            elif l1.startswith(b"ifdef "):
                                self.tested_define.add(l1.split()[1])
                            elif l1.startswith(b"ifndef "):
                                self.tested_define.add(l1.split()[1])
                            elif (
                                l1.startswith(b"include")
                                or l1.startswith(b"endif")
                                or l1.startswith(b"else")
                                or l1.startswith(b"undef")
                                or l1.startswith(b"pragma")
                                or l1.startswith(b"error")
                                or l1.startswith(b"//")
                            ):
                                pass
                            else:
                                logger.warning(
                                    "macro unrecognized in file :'{}'".format(fsource)
                                )
                                logger.warning("'{}'".format(l.decode()))
        self.undefined_tested_kword = sorted(
            map(lambda i: i.decode(), self.tested_define - self.all_define)
        )
        und_test_kword_msg = textwrap.fill(
            ", ".join(map(lambda i: "'{}'".format(i), self.undefined_tested_kword))
        )
        logger.info("expected defined kwords during compilation are:")
        logger.info(f"{und_test_kword_msg}")
        logger.info("predefined kwords can be found with command")
        logger.info("touch foo.h; cpp -dM foo.h")

    def scan_and_search_main(self) -> None:
        """
        search for main in sources
        """
        for rep3 in set(self.cxx_dir) | set(self.c_dir):
            for fsource in self.dir_content[rep3]:
                suf = "".join(fsource.suffixes)
                if suf in (".c", ".cpp", ".cxx", ".c++", "C++", ".C"):
                    with open(fsource, "rb") as f:
                        for l2, l, no in list(
                            filter(
                                lambda k: len(k[0]) >= 2,
                                map(
                                    lambda j: (j[1].split(), j[1], j[0]),
                                    filter(
                                        lambda i: (b"main" in i[1]),
                                        enumerate(f.read().splitlines(), start=1),
                                    ),
                                ),
                            )
                        ):
                            if l2[1].startswith(b"main(") and (
                                l2[0].startswith(b"int")
                                or l2[0].startswith(b"*int")
                                or l2[0].startswith(b"void")
                                or l2[0].startswith(b"*void")
                            ):
                                res = "{}/{}".format(*fsource.parts[-2:])
                                if res in self.main_pathes[-1:]:
                                    logger.warning(
                                        f"main found at least 2 times in '{res}'"
                                    )
                                    logger.warning(f"surnumerous main found in '{res}'")
                                    logger.warning(
                                        f"at line {no} which is '{l.decode()}'"
                                    )
                                else:
                                    self.main_pathes.append(res)
                                    logger.info(f"main found in '{res}'")
                                    logger.info(f"at line {no} which is '{l.decode()}'")

    def scan(self) -> None:
        """
        scan src_path and fill dir_content, dir_dir and 
        .cpp, .cxx, .c++ .C++ .C C++ files
        """
        self.scan_dir_and_file()
        self.search_c_cxx_file()
        self.scan_macros()
        self.scan_and_search_main()

    def write_in_SConscript(self) -> None:
        """
        write Sconscripts in src file and all c/c++ dirs below
        """
        Scons_src = self.env.get_template("SConscript_src.template")
        scons1_content = Scons_src.render(datas=self)
        Scrpath = self.src_path / "SConscript"
        if Scrpath.exists():
            existing_scons_content: str = ""
            with open(Scrpath, "r") as f:
                existing_scons_content = f.read()
            res = "\n".join(
                difflib.unified_diff(existing_scons_content, scons1_content)
            )
            if len(res) != 0:
                logging.info(res)
        else:
            with open(Scrpath, "w") as g:
                g.write(scons1_content)
            logger.info(f"{Scrpath} writen")
