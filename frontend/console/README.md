# Console

Thin React client. It talks only to the FastAPI API through the Vite `/api` proxy.

```bash
npm install
npm run dev
```

Open `http://127.0.0.1:43124`. Sign in (dev mode), pick `factory/demo`, and describe a change. The thread uses assistant-ui. Question, plan, and pull request cards come back from `GET /requests/{id}/transcript`. The factory does not merge.

