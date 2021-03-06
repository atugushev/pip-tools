import os
import re
from itertools import chain

from .click import unstyle
from .logging import log
from .utils import (
    UNSAFE_PACKAGES,
    comment,
    dedup,
    format_requirement,
    get_compile_command,
    key_from_ireq,
)

MESSAGE_UNHASHED_PACKAGE = comment(
    "# WARNING: pip install will require the following package to be hashed."
    "\n# Consider using a hashable URL like "
    "https://github.com/jazzband/pip-tools/archive/SOMECOMMIT.zip"
)

MESSAGE_UNSAFE_PACKAGES_UNPINNED = comment(
    "# WARNING: The following packages were not pinned, but pip requires them to be"
    "\n# pinned when the requirements file includes hashes. "
    "Consider using the --allow-unsafe flag."
)

MESSAGE_UNSAFE_PACKAGES = comment(
    "# The following packages are considered to be unsafe in a requirements file:"
)

MESSAGE_UNINSTALLABLE = (
    "The generated requirements file may be rejected by pip install. "
    "See # WARNING lines for details."
)


strip_comes_from_line_re = re.compile(r" \(line \d+\)$")


def _comes_from_as_string(ireq):
    if isinstance(ireq.comes_from, str):
        return strip_comes_from_line_re.sub("", ireq.comes_from)
    return key_from_ireq(ireq.comes_from)


class OutputWriter:
    def __init__(
        self,
        src_files,
        dst_file,
        click_ctx,
        dry_run,
        emit_header,
        emit_index_url,
        emit_trusted_host,
        annotate,
        generate_hashes,
        default_index_url,
        index_urls,
        trusted_hosts,
        format_control,
        allow_unsafe,
        find_links,
        emit_find_links,
    ):
        self.src_files = src_files
        self.dst_file = dst_file
        self.click_ctx = click_ctx
        self.dry_run = dry_run
        self.emit_header = emit_header
        self.emit_index_url = emit_index_url
        self.emit_trusted_host = emit_trusted_host
        self.annotate = annotate
        self.generate_hashes = generate_hashes
        self.default_index_url = default_index_url
        self.index_urls = index_urls
        self.trusted_hosts = trusted_hosts
        self.format_control = format_control
        self.allow_unsafe = allow_unsafe
        self.find_links = find_links
        self.emit_find_links = emit_find_links

    def _sort_key(self, ireq):
        return (not ireq.editable, str(ireq.req).lower())

    def write_header(self):
        if self.emit_header:
            yield comment("#")
            yield comment("# This file is autogenerated by pip-compile")
            yield comment("# To update, run:")
            yield comment("#")
            compile_command = os.environ.get(
                "CUSTOM_COMPILE_COMMAND"
            ) or get_compile_command(self.click_ctx)
            yield comment(f"#    {compile_command}")
            yield comment("#")

    def write_index_options(self):
        if self.emit_index_url:
            for index, index_url in enumerate(dedup(self.index_urls)):
                if index_url.rstrip("/") == self.default_index_url:
                    continue
                flag = "--index-url" if index == 0 else "--extra-index-url"
                yield f"{flag} {index_url}"

    def write_trusted_hosts(self):
        if self.emit_trusted_host:
            for trusted_host in dedup(self.trusted_hosts):
                yield f"--trusted-host {trusted_host}"

    def write_format_controls(self):
        for nb in dedup(sorted(self.format_control.no_binary)):
            yield f"--no-binary {nb}"
        for ob in dedup(sorted(self.format_control.only_binary)):
            yield f"--only-binary {ob}"

    def write_find_links(self):
        if self.emit_find_links:
            for find_link in dedup(self.find_links):
                yield f"--find-links {find_link}"

    def write_flags(self):
        emitted = False
        for line in chain(
            self.write_index_options(),
            self.write_find_links(),
            self.write_trusted_hosts(),
            self.write_format_controls(),
        ):
            emitted = True
            yield line
        if emitted:
            yield ""

    def _iter_lines(self, results, unsafe_requirements=None, markers=None, hashes=None):
        # default values
        unsafe_requirements = unsafe_requirements or []
        markers = markers or {}
        hashes = hashes or {}

        # Check for unhashed or unpinned packages if at least one package does have
        # hashes, which will trigger pip install's --require-hashes mode.
        warn_uninstallable = False
        has_hashes = hashes and any(hash for hash in hashes.values())

        yielded = False

        for line in self.write_header():
            yield line
            yielded = True
        for line in self.write_flags():
            yield line
            yielded = True

        unsafe_requirements = (
            {r for r in results if r.name in UNSAFE_PACKAGES}
            if not unsafe_requirements
            else unsafe_requirements
        )
        packages = {r for r in results if r.name not in UNSAFE_PACKAGES}

        if packages:
            packages = sorted(packages, key=self._sort_key)
            for ireq in packages:
                if has_hashes and not hashes.get(ireq):
                    yield MESSAGE_UNHASHED_PACKAGE
                    warn_uninstallable = True
                line = self._format_requirement(
                    ireq, markers.get(key_from_ireq(ireq)), hashes=hashes
                )
                yield line
            yielded = True

        if unsafe_requirements:
            unsafe_requirements = sorted(unsafe_requirements, key=self._sort_key)
            yield ""
            yielded = True
            if has_hashes and not self.allow_unsafe:
                yield MESSAGE_UNSAFE_PACKAGES_UNPINNED
                warn_uninstallable = True
            else:
                yield MESSAGE_UNSAFE_PACKAGES

            for ireq in unsafe_requirements:
                ireq_key = key_from_ireq(ireq)
                if not self.allow_unsafe:
                    yield comment(f"# {ireq_key}")
                else:
                    line = self._format_requirement(
                        ireq, marker=markers.get(ireq_key), hashes=hashes
                    )
                    yield line

        # Yield even when there's no real content, so that blank files are written
        if not yielded:
            yield ""

        if warn_uninstallable:
            log.warning(MESSAGE_UNINSTALLABLE)

    def write(self, results, unsafe_requirements, markers, hashes):

        for line in self._iter_lines(results, unsafe_requirements, markers, hashes):
            log.info(line)
            if not self.dry_run:
                self.dst_file.write(unstyle(line).encode())
                self.dst_file.write(os.linesep.encode())

    def _format_requirement(self, ireq, marker=None, hashes=None):
        ireq_hashes = (hashes if hashes is not None else {}).get(ireq)

        line = format_requirement(ireq, marker=marker, hashes=ireq_hashes)

        if not self.annotate:
            return line

        # Annotate what packages or reqs-ins this package is required by
        required_by = set()
        if hasattr(ireq, "_source_ireqs"):
            required_by |= {
                _comes_from_as_string(src_ireq)
                for src_ireq in ireq._source_ireqs
                if src_ireq.comes_from
            }
        elif ireq.comes_from:
            required_by.add(_comes_from_as_string(ireq))
        if required_by:
            required_by = sorted(required_by)
            if len(required_by) == 1:
                source = required_by[0]
                annotation = "    # via " + source
            else:
                annotation_lines = ["    # via"]
                for source in required_by:
                    annotation_lines.append("    #   " + source)
                annotation = "\n".join(annotation_lines)
            line = f"{line}\n{comment(annotation)}"
        return line
