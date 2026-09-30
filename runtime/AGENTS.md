# Runtime development

This subtree contains the C++ Linux runtime, independently of the Python geometry
studies. Documentation is Chinese; code comments are English.

- Configure/build/install with `../tools/runtime-build native` or `lbc3` from here,
  or `./tools/runtime-build <target>` from the repository root.
- Run native checks with `ctest --test-dir ../out/runtime/native/build-llvm --output-on-failure`.
- Cross binaries must not be run on the host. Inspect their ELF architecture and
  dynamic dependencies; runtime checks require the LBC3 board.
- Keep generated files in `out/runtime/`; never commit extracted sysroots or build outputs. SDK/source archives under runtime/ use Git LFS.
- Board-specific device access belongs in `platforms/lbc3/` when introduced;
  reusable logic belongs in `libs/` and application orchestration in `apps/`.
