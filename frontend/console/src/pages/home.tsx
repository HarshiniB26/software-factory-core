import { ChatThread, setChatRefresh, setChatTarget } from "@/components/chat";
import { useSession } from "@/components/shell";
import { useEffect } from "react";

export function HomePage() {
  const session = useSession();
  useEffect(() => {
    setChatRefresh(() => session.refresh());
    setChatTarget(async () => {
      if (session.connected?.path || session.connected?.full_name) {
        return session.connected.path ?? session.connected.full_name;
      }
      const sample = session.repos.find((repo) => repo.kind === "local");
      if (!sample) return null;
      await session.connect(sample.full_name);
      return sample.path;
    });
  }, [session]);
  return <ChatThread />;
}
