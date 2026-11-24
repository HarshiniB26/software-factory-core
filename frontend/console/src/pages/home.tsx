import { ChatThread, setChatRefresh, setChatTarget } from "@/components/chat";
import { useSession } from "@/components/shell";
import { issueTarget } from "@/lib/repo-picker";
import { useEffect } from "react";

export function HomePage() {
  const session = useSession();
  useEffect(() => {
    setChatRefresh(() => session.refresh());
    const connected = session.connected?.full_name ? session.connected : null;
    setChatTarget(async () => issueTarget(connected));
  }, [session]);
  return <ChatThread />;
}
