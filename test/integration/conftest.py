# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import json
import pytest
import shutil
import site
import sys


from cyclonedx.schema import OutputFormat, SchemaVersion
from cyclonedx.validation import make_schemabased_validator

from pathlib import Path

import rbbuild.__main__ as rbbuild_mod
import rbbuild.pkq      as pkq_mod
import rbbuild.promote  as promote_mod
import rbbuild.rbbconf  as rbbconf_mod
import rbbuild.rbfoss   as rbfoss_mod

from rbbuild.concat_files import ConcatFilesMain
from rbbuild.__main__ import RBBuildMain
from rbbuild.pkq import PackageQueryMain
from rbbuild.promote import PromoteMain
from rbbuild.rbbconf import RBBConfMain
from rbbuild.rbfoss import RBFossMain
from rbbuild.container.application import Application
from rbbuild.container.configuration import RBBuildConfiguration
from rbbuild.librbb.term import term, ColorSchemeNone


_CONFIG_PATH = Path.cwd() / 'share/rbbuild/config'


class TestToolsBase:
    def __init__( self,
                  user_home: Path,
                  workdir: Path,
                  config_path: Path,
                  monkeypatch,
                  exe: str,
                  main_class,
                  module=None,
                  parse_func=None ):
        self.monkeypatch = monkeypatch
        self.user_home = user_home
        self.workdir = workdir
        self.config_path = config_path
        self.exe = exe
        self.main_class = main_class
        self.module = module
        self.parse_func = parse_func
        term.color = ColorSchemeNone


    def run(self, args):
        with self.monkeypatch.context() as m:
            m.chdir(self.workdir)
            m.setattr(sys, 'argv', [self.exe, *args])
            m.delenv('RBB_CONFIG_PATH', raising=False)
            # We cannot capture stdout/stderr from out of a fixture
            # Therefore, we redirect the output to the console file
            saved_log_file = term.log_file
            saved_out_file = term.out_file
            try:
                with open(self.user_home / f'console.{self.exe}', 'w', encoding='utf-8') as cons:
                    term.log_file = cons
                    term.out_file = cons
                    parsed_args = self.parse_func()
                    config, application = self._setup_di(parsed_args)
                    try:
                        main_instance = self.main_class()
                        main_instance.main(parsed_args)
                    finally:
                        application.unwire()
            finally:
                term.log_file = saved_log_file
                term.out_file = saved_out_file


    def _setup_di(self, args):
        rbb_root = Path(self.module.__file__).resolve().parent
        config_path = self.config_path
        config = RBBuildConfiguration()
        config.load_configuration(rbb_root, config_path)
        self._load_config(config, args)
        application = Application(config=config)
        application.wire(modules=[self.module.__name__])
        return config, application


    def _load_config(self, config, args):
        raise NotImplementedError('Subclasses must implement _load_config()')


    def read_console(self) -> str:
        with open(self.user_home / f'console.{self.exe}', 'r', encoding='utf-8') as fd:
            return fd.read().strip()



class TestConcatFiles(TestToolsBase):
    def __init__(self, user_home: Path, workdir: Path, config_path: Path, monkeypatch):
        super().__init__(user_home, workdir, config_path, monkeypatch, 'concat_files', ConcatFilesMain)

    def run(self, args):
        # concat_files does not use dependency injection — keep the simple flow.
        with self.monkeypatch.context() as m:
            m.chdir(self.workdir)
            m.setattr(sys, 'argv', [self.exe, *args])
            saved_log_file = term.log_file
            try:
                with open(self.user_home / f'console.{self.exe}', 'w') as cons:
                    term.log_file = cons
                    main_instance = self.main_class()
                    main_instance.main()
            finally:
                term.log_file = saved_log_file


class TestRBBuild(TestToolsBase):
    def __init__(self, user_home: Path, workdir: Path, config_path: Path, monkeypatch):
        super().__init__(user_home, workdir, config_path, monkeypatch, 'rbbuild', RBBuildMain,
                         module=rbbuild_mod, parse_func=rbbuild_mod.parse_command_line)

    def _load_config(self, config, args):
        config.load_cli_source_path(**vars(args))
        source_path = Path(config.paths.source())
        config.load_project_configuration(source_path)
        config.load_jenkinsfile(source_path)
        config.load_cli_profile(**vars(args))
        config.load_profile(
            profile_name=config.settings.profile(),
            rbbuild_config_path=self.config_path,
            user_config_path=Path(config.paths.user_config()),
        )
        config.load_cli(**vars(args))
        # load_cli_rbbuild modifies the config object; a temporary instance suffices.
        RBBuildMain().load_cli_rbbuild(config, args)


class TestRBBConf(TestToolsBase):
    def __init__(self, user_home: Path, workdir: Path, config_path: Path, monkeypatch):
        super().__init__(user_home, workdir, config_path, monkeypatch, 'rbbconf', RBBConfMain,
                         module=rbbconf_mod, parse_func=rbbconf_mod.parse_command_line)

    def _load_config(self, config, args):
        config.load_cli(**vars(args))
        config.load_profile(
            profile_name=config.settings.profile(),
            rbbuild_config_path=self.config_path,
            user_config_path=Path(config.paths.user_config()),
        )


class TestPKQ(TestToolsBase):
    def __init__(self, user_home: Path, workdir: Path, config_path: Path, monkeypatch):
        super().__init__(user_home, workdir, config_path, monkeypatch, 'pkq', PackageQueryMain,
                         module=pkq_mod, parse_func=pkq_mod.parse_command_line)

    def _load_config(self, config, args):
        config.load_cli_profile(**vars(args))
        config.load_profile(
            profile_name=config.settings.profile(),
            rbbuild_config_path=self.config_path,
            user_config_path=Path(config.paths.user_config()),
        )
        config.load_cli(**vars(args))
        if getattr(args, 'resolve', False):
            source_dir = Path(args.source_dir) if args.source_dir else Path.cwd()
            config.load_project_configuration(source_dir)


class TestPromote(TestToolsBase):
    def __init__(self, user_home: Path, workdir: Path, config_path: Path, monkeypatch):
        super().__init__(user_home, workdir, config_path, monkeypatch, 'promote', PromoteMain,
                         module=promote_mod, parse_func=promote_mod.parse_command_line)

    def _load_config(self, config, args):
        config.load_cli_profile(**vars(args))
        config.load_profile(
            profile_name=config.settings.profile(),
            rbbuild_config_path=self.config_path,
            user_config_path=Path(config.paths.user_config()),
        )
        config.load_cli(**vars(args))


class TestRBFoss(TestToolsBase):
    def __init__(self, user_home: Path, workdir: Path, config_path: Path, monkeypatch):
        super().__init__(user_home, workdir, config_path, monkeypatch, 'rbfoss', RBFossMain,
                         module=rbfoss_mod, parse_func=rbfoss_mod.parse_command_line)

    def _load_config(self, config, args):
        source_path = Path(config.paths.source())
        config.load_pyproject_toml(source_path)
        config.load_jenkinsfile(source_path)
        config.load_cli_profile(**vars(args))
        config.load_profile(
            profile_name=config.settings.profile(),
            rbbuild_config_path=self.config_path,
            user_config_path=Path(config.paths.user_config()),
        )
        config.load_cli(**vars(args))


@pytest.fixture
def concat_files(tmp_path, user_home, monkeypatch):
    datadir = tmp_path / 'data'
    datadir.mkdir()
    testdata = datadir / 'testdata'
    testdata.mkdir()
    (testdata / 'a').write_text('1\n')
    (testdata / 'b').write_text('2\n')

    yield TestConcatFiles(user_home=user_home, workdir=datadir, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


@pytest.fixture
def source_path(tmp_path):
    path = tmp_path / 'project'
    path.mkdir()
    yield path


@pytest.fixture
def user_home_empty(tmp_path, monkeypatch):
    user_home = tmp_path / 'home/user'
    user_home.mkdir(parents=True)
    monkeypatch.setenv('HOME', str(user_home))
    # ensure that installed prerequisites, such as cmake, are found later on
    monkeypatch.setenv('PYTHONUSERBASE', site.getuserbase())
    yield user_home


@pytest.fixture
def user_home(tmp_path, monkeypatch):
    user_home = tmp_path / 'home/user'
    shutil.copytree('test/data/user_home', user_home)

    monkeypatch.setenv('HOME', str(user_home))
    # ensure that installed prerequisites, such as cmake, are found later on
    monkeypatch.setenv('PYTHONUSERBASE', site.getuserbase())
    yield user_home


@pytest.fixture
def rbbuild(source_path, user_home, monkeypatch):
    yield TestRBBuild(user_home=user_home, workdir=source_path, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


@pytest.fixture
def rbbuild_empty(source_path, user_home_empty, monkeypatch):
    yield TestRBBuild(user_home=user_home_empty, workdir=source_path, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


@pytest.fixture
def rbbconf(source_path, user_home, monkeypatch):
    yield TestRBBConf(user_home=user_home, workdir=source_path, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


@pytest.fixture
def rbbconf_empty(source_path, user_home_empty, monkeypatch):
    yield TestRBBConf(user_home=user_home_empty, workdir=source_path, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


@pytest.fixture
def pkq(source_path, user_home, monkeypatch):
    yield TestPKQ(user_home=user_home, workdir=source_path, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


@pytest.fixture
def pkq_empty(source_path, user_home_empty, monkeypatch):
    yield TestPKQ(user_home=user_home_empty, workdir=source_path, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


@pytest.fixture
def promote(source_path, user_home, monkeypatch):
    yield TestPromote(user_home=user_home, workdir=source_path, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


@pytest.fixture
def rbfoss(source_path, user_home, monkeypatch):
    yield TestRBFoss(user_home=user_home, workdir=source_path, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


@pytest.fixture
def rbfoss_empty(source_path, user_home_empty, monkeypatch):
    yield TestRBFoss(user_home=user_home_empty, workdir=source_path, config_path=_CONFIG_PATH, monkeypatch=monkeypatch)


class TestCycloneDXSchema:
    def validate(self, sbom_path: Path) -> bool:
        data = sbom_path.read_text()
        sbom = json.loads(data)

        schema_version = SchemaVersion.from_version(sbom.get('specVersion'))
        validator = make_schemabased_validator(OutputFormat.JSON, schema_version)
        errors = validator.validate_str(data)
        if errors:
            raise RuntimeError(f'Validation failed: {errors}')

        return True


@pytest.fixture
def cdx_1_6():
    yield TestCycloneDXSchema()

