# ADR 0012 — The PackageManager seam

- **Status:** accepted
- **Date:** 2026-07-13
- **Implements:** Constitution §II (replaceability); matrix row #19. Follows the
  honest-scope precedent of [ADR-0011](0011-update-manager-seam.md).

## Context

Installing applications is a core OS capability. On the target base (Fedora
Asahi) the app-distribution mechanism is **Flatpak**. AIOS should own the
*interface* to package management (its "app store"/manager surface) while Flatpak
is one swappable implementation behind it — so a future AIOS package/store
service is additive.

## Decision

Add an AIOS-owned **`PackageManager`** interface (`aiosd/packages.py`):
`list_installed` / `search` / `install` / `remove` / `available`. Ship
**`FlatpakPackageManager`** as the current implementation (the only class that
knows Flatpak), plus a `NullPackageManager`. `aios apps` surfaces it.

**Honest testability.** Flatpak cannot run on the macOS development host, so:
- the **parsing** (`_parse_columns`, pure) and **graceful degradation** (every op
  returns a clear "flatpak is not installed" when the binary is absent) are unit
  tested here;
- command **execution** (`install`/`remove`/live `list`/`search`) is validated on
  the Linux target.

This mirrors ADR-0011: build the seam + the real implementation, test what is
verifiable on the dev host, and be explicit about what is validated on hardware —
rather than fake a test or skip the feature.

### The Four Questions

1. **Why Flatpak?** It is the app-distribution mechanism of the target base and a
   cross-distro standard; building our own now would be premature.
2. **Which abstraction isolates it?** `PackageManager` — callers never see
   `flatpak`.
3. **Replacement difficulty?** Medium — add a `PackageManager` (dnf, or an AIOS
   store); the CLI and interface are unchanged.
4. **Future replacement?** An AIOS package/store service behind the same seam.

## Consequences

- `aios apps` gives a real app-management path on the target, and a clean
  "not installed" message elsewhere.
- Swapping the packaging mechanism is additive.
- Execution coverage depends on the Linux target — recorded honestly, not hidden.

## Rejected alternatives

- **Wrap flatpak inline in the CLI.** Rejected — leaks the mechanism across the
  app boundary; no seam.
- **Skip it until on hardware.** Rejected — the interface + parsing + degradation
  are valuable and testable now; only execution waits for Linux.
- **Model the interface on flatpak's CLI verbs.** Rejected — leaks Flatpak idioms
  (Constitution §II.5); the interface is generic (list/search/install/remove).
