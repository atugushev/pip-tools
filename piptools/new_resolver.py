from pip._internal.cache import WheelCache
from pip._internal.req.req_tracker import get_requirement_tracker
from pip._internal.utils.logging import indent_log
from pip._internal.utils.temp_dir import TempDirectory, global_tempdir_manager
from pip._vendor.packaging.specifiers import SpecifierSet

from piptools.logging import log


# FIXME: needs appropriate module and name
class NewResolver(object):
    def __init__(self, constraints, repository, **kwargs):
        self.constraints = constraints
        self.repository = repository
        self.unsafe_constraints = set()

        self.options = self.repository.options
        self.session = self.repository.session
        self.finder = self.repository.finder
        self.command = self.repository.command

    def resolve(self, max_rounds=None):
        with get_requirement_tracker() as req_tracker, global_tempdir_manager(), indent_log():

            wheel_cache = WheelCache(
                self.options.cache_dir, self.options.format_control
            )

            build_delete = not (self.options.no_clean or self.options.build_dir)
            temp_dir = TempDirectory(
                self.options.build_dir,
                delete=build_delete,
                kind="resolve",
                globally_managed=True,
            )

            # If any requirement has hash options, enable hash checking.
            if any(req.has_hash_options for req in self.constraints):
                self.options.require_hashes = True

            preparer = self.command.make_requirement_preparer(
                temp_build_dir=temp_dir,
                options=self.options,
                req_tracker=req_tracker,
                session=self.session,
                finder=self.finder,
                use_user_site=False,
            )

            resolver = self.command.make_resolver(
                preparer=preparer,
                finder=self.finder,
                options=self.options,
                wheel_cache=wheel_cache,
                use_user_site=False,
                ignore_installed=True,
                ignore_requires_python=False,
                force_reinstall=False,
                use_pep517=self.options.use_pep517,
                upgrade_strategy="to-satisfy-only",
            )

            self.command.trace_basic_info(self.finder)

            resolver.resolve(
                self.constraints, check_supported_wheels=not self.options.target_dir
            )

        # FIXME: a dirty hack, there must be a better way to get resolved versions
        reqs = set()
        for candidate in resolver._result.mapping.values():
            ireq = candidate.get_install_requirement()
            if ireq is None:
                continue
            ireq.req.specifier = SpecifierSet("=={}".format(candidate.version))
            reqs.add(ireq)

        return reqs

    def resolve_hashes(self, ireqs):
        """
        Finds acceptable hashes for all of the given InstallRequirements.
        """
        log.debug("")
        log.debug("Generating hashes:")
        with self.repository.allow_all_wheels(), log.indentation():
            return {ireq: self.repository.get_hashes(ireq) for ireq in ireqs}
