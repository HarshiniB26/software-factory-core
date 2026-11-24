# Console research

Studied in public pages, READMEs, and demo transcripts on 23 Nov 2026. Screenshot hosts for Marshal are the README images on [ski043/marshal-factory](https://github.com/ski043/marshal-factory) and the live panel at [marshal-factory.vercel.app](https://marshal-factory.vercel.app). Video pages: [I Built My Own Software Factory with Claude Code](https://www.youtube.com/watch?v=sPpTWl3Cs14), [Introduction to Devin](https://www.youtube.com/watch?v=sVwnZp4Z0HQ), [Devin Desktop Full Tour](https://www.youtube.com/watch?v=bS_L25u4lZ0), plus Factory’s desktop write-ups and the OpenHands feature map.

## What each product shows

**Marshal (ski043/marshal-factory).** A supervision panel, not a chatbot. Jobs move across Queued, Triage, Investigating, Implementing, Verifying, and PR, as a board or a list. Opening a card shows stage history, subagents, models, and dollars. Inbox is the only queue that needs a person: questions, reviews, failures. Repositories are a first-class page (where a job may run). The README diagram is a numbered path from Linear or Slack to a pull request. Merge stays a human decision unless a repo is explicitly set to merge when confident. We do not copy that merge switch. Phase 1 never merges.

**Factory.ai Droids.** The desktop app is a session workspace. The transcript sits next to the artifact the session produced: a diff, a document, or a live preview. Sessions filter and group in the sidebar. Pull request state (draft, open, merged, closed) is visible on the session. Long messages collapse. Several droids run at once without losing the thread you were reading.

**Devin.** A session starts in planning. The plan is a reviewable overview, then a work log of commands, edits, and tests. The IDE walkthrough puts the editor beside that log. Devin Desktop’s command center groups sessions, pull requests, and files into a space so related agents share context. The GitHub connect path is settings, then a repository picker, then the first session.

**OpenHands Agent Canvas.** One conversation. Tool actions collapse into “N actions” cards that open onto the command, the output, and the diff. A right drawer holds the file tree, a read-only terminal, the plan, the task list, and token or cost usage. A status chip says what the agent is doing now.

**Cursor background agents.** Start from chat, Slack, or the agents window. The result that matters is the branch and the pull request, with the cloud machine kept out of the way. Setup is an environment file, not a form the user refills every run.

**Codex cloud.** A task is a prompt plus an environment. The return is a summary and a diff, then a follow-up or a pull request. Parallel tasks stay separate. Internet access is a property of the environment.

**GitHub Copilot coding agent.** The session log is the progress UI, and commits land on a draft pull request while the agent is still working. You start from an issue, a PR comment, or the agents panel. The log is the best “what is it doing right now” surface of the three cloud agents.

**Replit Agent.** Chat produces a running app preview beside the files. The loop is describe, watch, point at what is wrong. We take the side-by-side preview idea and use a diff instead of a hosted app preview.

**Lovable and Bolt.** The prompt is the whole home screen. Generation streams into a preview. Empty states are a single sentence and a few starter prompts, not a dashboard. Useful for the first visit, wrong as the only view once work is in flight.

**Sweep.** Issue in, pull request out, with a short plan in the PR body. Little live supervision. We keep the PR card and add the live supervision Sweep skips.

## Patterns worth taking

- The home screen is a composer. Dashboards are one click away, not the landing page.
- A run is a place: transcript, plan, agents, terminal, files, and the pull request at once.
- Progress is a log of real stages, not a spinner.
- Money, model, and harness sit on the agent that spent them.
- People are interrupted only for a question, an approval, or a failed check.
- Repositories are connected once and then named in the sidebar.
- The product does not merge for you unless a separate, explicit policy says so. Ours does not.

## What this console adopts

- Chat-first home, with the run streamed under the reply.
- A run page: task graph, agent cards, timeline, terminal, file tree, Monaco diff, gates, questions, pull request.
- A runs dashboard with status filters, counts, and a cost chart.
- A registry with versions, held-out scores, and promotion history. Promotion stays a gate, not a button that rewrites `main`.
- A repositories page for the sample service and GitHub sign-in.
- The new-issue composer names the repository in the input toolbar, using the same connected repo as the sidebar. Connect GitHub opens GitHub's authorize page when the App's client id and secret are set. The picker then splits Local and GitHub, shows the signed-in account, and links Add repositories to the App install page. A branch chip uses the default branch from GitHub. Without the OAuth app the popover says so and the local sample stays selectable.
- Settings for the harness and model of each role, and for when a plan needs approval.
- A usage page.
- Dark and light, command palette, skeletons, and short motion.

## What we do not adopt

- Merge-when-confident, Slack control, or a Linear board as the source of truth.
- A hosted app preview.
- Hiding the fixture label in dev mode. The demo says when a number or a diff comes from the fixture model.
