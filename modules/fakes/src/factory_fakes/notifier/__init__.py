"""Records notifications. show_plan waits for a human by returning pending."""

from factory_contracts import Approval, FactoryEvent, Plan, PullRequestRef, Question


class FakeNotifier:
    def __init__(self) -> None:
        self.asked: list[str] = []
        self.plans: list[Plan] = []
        self.events: list[FactoryEvent] = []
        self.prs: list[PullRequestRef] = []

    async def ask(self, thread_id: str, questions: list[Question]) -> None:
        self.asked.append(thread_id)

    async def show_plan(self, plan: Plan) -> Approval:
        self.plans.append(plan)
        return Approval(status="pending", plan_id=plan.id)

    async def progress(self, event: FactoryEvent) -> None:
        self.events.append(event)

    async def done(self, prs: list[PullRequestRef]) -> None:
        self.prs.extend(prs)

    async def on_reply(self, thread_id: str) -> str | None:
        return None
