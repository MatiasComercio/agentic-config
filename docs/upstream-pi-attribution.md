# Upstream Pi attribution

agentic-config ships third-party Pi packages, skills, and extensions. Pi itself is a separate upstream project. This page records the upstream references used by the Pi package surface in this repository and the ownership boundary between Pi and agentic-config.

## Upstream references

| Surface | Reference |
|---------|-----------|
| Pi project website | <https://pi.dev> |
| Pi monorepo | <https://github.com/badlogic/pi-mono> |
| Pi coding agent npm package | <https://www.npmjs.com/package/@mariozechner/pi-coding-agent> |
| Pi coding agent source package | <https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent> |
| Pi AI npm package | <https://www.npmjs.com/package/@mariozechner/pi-ai> |
| Pi AI source package | <https://github.com/badlogic/pi-mono/tree/main/packages/ai> |

The upstream package names are listed as their public npm identifiers because agentic-config imports those packages directly in its Pi extension packages.

## Ownership boundary

Upstream Pi provides the CLI, package loader, extension API, core tool registration surface, auth/model helpers, session runtime, and terminal UI that Pi packages run on.

agentic-config provides the packages under `@agentic-config/pi-*`, the generated skills, package-local extensions, hook compatibility layers, documentation, and workflow runtimes shipped from this repository.

Important boundaries:

- `pimux` is an agentic-config runtime extension shipped by `@agentic-config/pi-ac-workflow`. It is not an upstream Pi feature.
- `@agentic-config/pi-compat` is an agentic-config compatibility layer for this package set. It is not an upstream Pi package.
- `ac-workflow-mux`, `ac-workflow-mux-ospec`, and `ac-workflow-mux-roadmap` are agentic-config workflow wrappers built on the package-owned `pimux` runtime.
- References to "Pi packages" in this repository mean packages that install into Pi through `pi install`, not packages owned by the upstream Pi project unless explicitly named as upstream.

## Direct upstream dependencies in this repository

The current package set imports upstream Pi APIs directly from:

- `@mariozechner/pi-coding-agent`
- `@mariozechner/pi-ai`

Those direct imports are currently used by `@agentic-config/pi-ac-tools` and `@agentic-config/pi-ac-workflow`. Other package roots install into Pi through package manifests, skills, bundled assets, and shared compatibility wiring.

## Guidance for future docs

When documenting Pi support in this repository:

- Attribute Pi runtime behavior to upstream Pi and link to this page when the distinction matters.
- Attribute `@agentic-config/pi-*`, `pimux`, `hook-compat`, generated skills, and workflow wrappers to agentic-config.
- Avoid wording that suggests agentic-config owns the Pi CLI, Pi monorepo, or upstream `@mariozechner/*` packages.
