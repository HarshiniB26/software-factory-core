"""Returns questions when the request body contains a question mark."""

from factory_contracts import Clarification, FactoryRequest, Question, RepoContext


class FakeClarifier:
    async def assess(self, request: FactoryRequest, repo_ctx: RepoContext) -> Clarification:
        if "?" in request.body:
            return Clarification(
                status="questions",
                questions=[
                    Question(
                        text="Which behavior should change?",
                        options=["add", "fix"],
                        default="add",
                    )
                ],
            )
        return Clarification(
            status="clear",
            checks=[f"behavior in {repo_ctx.repo} matches the request"],
        )
