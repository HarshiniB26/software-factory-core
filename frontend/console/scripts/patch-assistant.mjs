import { readFileSync, writeFileSync } from "node:fs";

const file =
  "node_modules/@assistant-ui/react/src/legacy-runtime/runtime-cores/remote-thread-list/RemoteThreadListHookInstanceManager.tsx";

try {
  const source = readFileSync(file, "utf8");
  const broken = "setGetInitializePromise(() => initPromiseRef.current);";
  const fixed = "setGetInitializePromise.call(runtimeCore, () => initPromiseRef.current);";
  if (source.includes(broken)) {
    writeFileSync(file, source.replace(broken, fixed));
  }
} catch {
  // The package layout changed. The console still typechecks against the public API.
}
