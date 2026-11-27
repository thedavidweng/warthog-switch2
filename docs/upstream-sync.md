# Upstream synchronization

Update the engine and console sources as a consumer of upstream:

1. Repin `ChupathingyCE/warthog-switch`,
   `ChupathingyCE/chupathingyce`, or an ouncebrew component to a full
   40-character commit in `UPSTREAM.json`. Update the matching full hash in
   `scripts/switch2/Dockerfile` in the same change.
2. If UAM2, the shader ABI, or the GLSL generator changes, update
   `HOST_DK_UAM_COMMIT` and the persistent shader cache key. Maxwell and
   Ampere entries must never collide.
3. Run `python3 tools/switch_overrides.py`. Delete an override that upstream
   has merged, and add a focused upstream pull request for generally useful
   fixes. Keep each remaining override listed with its reason.
4. Configure and build `ninja switch` and `ninja switch2`. A shared change
   that breaks the original Switch build is a regression.
5. Run the host tests, package audits and both release flavors before
   publishing the new pins.

Never edit the `chupathingyce/` submodule in place. Move its gitlink to the
chosen pinned revision and record the reason in an ADR when the choice is not
obvious.
