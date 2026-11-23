# Module authoring

1. Add `modules/<name>/` as a uv workspace member with a `module.yaml` whose `id` matches the entry point name and whose `implements` is `Interface@1`.
2. Implement the Protocol in `packages/contracts`. Construct with no required arguments so the shared suite can build it. Read credentials from the environment inside the instance, and keep a fixture path when they are missing.
3. Register it:

```toml
[project.entry-points."factory.modules"]
my-module = "factory_my_module:MyModule"
```

4. Run `uv run pytest packages/contract-tests`. The suite parametrizes every in-process module for that interface.
5. Do not import `factory_core` or another module. `import-linter` fails the build.
6. Select it from `.factory/config.yaml` under `modules:`. Ship it unselected until a repo opts in.
7. Never add a merge method to a VcsProvider. Phase 1 stops at an open pull request.
