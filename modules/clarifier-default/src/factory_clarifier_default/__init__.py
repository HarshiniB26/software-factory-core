"""Ask only when the request can change scope, data, API, security, or cost."""

from factory_contracts import Clarification, FactoryRequest, Question, RepoContext


class DefaultClarifier:
    async def assess(self, request: FactoryRequest, repo_ctx: RepoContext) -> Clarification:
        text = f"{request.title}\n{request.body}".lower()
        questions: list[Question] = []
        if "?" in request.body or " or " in text or "either" in text:
            questions.append(
                Question(
                    text="Which option should the factory implement?",
                    options=["smallest change", "first option", "second option"],
                    default="smallest change",
                )
            )
        if (
            any(word in text for word in ("auth", "billing", "migration", "delete"))
            and "?" in request.body
        ):
            questions.append(
                Question(
                    text="This touches a hard-to-reverse area. How should we proceed?",
                    options=["ask the owner", "smallest safe change", "stop"],
                    default="smallest safe change",
                )
            )
        questions = questions[:3]
        if questions:
            return Clarification(status="questions", questions=questions)
        assumptions: list[str] = []
        if not request.target:
            assumptions.append(f"No repo was named; using {repo_ctx.repo}.")
        return Clarification(
            status="clear",
            assumptions=assumptions,
            checks=[f"The result matches: {request.title}"],
        )
