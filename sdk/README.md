# LubanCat RK3576 SDK patch stack

Project-owned source of truth for zenith's changes on top of the LubanCat (Rockchip
RK3576) Linux SDK. Layout mirrors `luckfox-aura-teleop/sdk/`.

- `baseline.toml` — human-readable baseline: SDK release, container, versions, pinned commits.
- `manifest.lock.xml` — `repo manifest -r` snapshot of the vendor SDK.
- `series.tsv` — authoritative `repo-path|baseline-commit|lbc-branch` list.
- `patches/<repo-path>/*.patch` — exported `git format-patch` series per SDK sub-repo.

The vendor SDK itself is a sibling `repo` checkout (`~/codings/lbc_sdk`) and is never
committed here. Review / apply it with `../tools/lbc-sdk`.

The kernel is **not** in this patch series: it is maintained as a personal fork
(see `[kernel]` in `baseline.toml`).
