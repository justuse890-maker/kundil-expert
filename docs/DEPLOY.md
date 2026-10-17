# Deploying Vedic Kundli on Render (free tier)

The app is one Docker web service: FastAPI serves both the API (`/api/v1/...`) and the UI (`/`). There is no database yet.

## What you need
- A GitHub account and a repository for this project.
- A Render account (render.com). The free plan needs no card.

## Licence note (read once)
The engine uses the Swiss Ephemeris under the AGPL. A public website must offer its backend source code to users. Keeping this GitHub repository **public** satisfies that. The `LICENSE` file in the repo root is AGPL-3.0.

## Steps

### 1. Put the code on GitHub
Create an empty repository on GitHub, for example `vedic-kundli`. Do not add a README, licence or .gitignore there; the project already has them. Then, from the project folder:

```bash
cd "/Users/nitesh/vedic kundil"
git remote add origin https://github.com/<your-user>/vedic-kundli.git
git push -u origin main
```

### 2. Create the service on Render
1. In Render, choose **New → Blueprint**.
2. Connect your GitHub account and pick the `vedic-kundli` repository.
3. Render reads `render.yaml` and proposes one free web service named `vedic-kundli`. Click **Apply**.
4. The first build takes a few minutes, mostly installing Python packages. When it finishes, Render shows a URL like `https://vedic-kundli.onrender.com`.

### 3. Check it works
- Open `https://<your-service>.onrender.com/api/v1/health`. You should see `"status":"ok"` and three ephemeris files.
- Open `https://<your-service>.onrender.com/` and generate a kundli. Pick the city from the list.

## How the free tier behaves
- **Sleeps after 15 minutes with no visitors.** The next visitor waits about a minute while it wakes. Upgrade the service to Render's cheapest paid plan to keep it always on.
- **5 GB of free bandwidth per month.** One kundli page with analysis is roughly 100–200 KB, so that is a few tens of thousands of views.
- **Auto-deploy:** every push to `main` redeploys automatically (`autoDeploy: true`).

## Updating
Commit and `git push`. Render rebuilds and redeploys.

## Later: adding a database (Neon, free Postgres)
Not needed today. When accounts or saved kundlis are added:
1. Create a free project at neon.tech and copy its connection string.
2. In Render, open the service, go to **Environment**, and add `DATABASE_URL` = that string. You enter it yourself; never commit it to git.
3. Redeploy.

## Run locally instead
```bash
./run.sh
```
Then open http://localhost:8000.
