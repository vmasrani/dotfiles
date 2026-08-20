---
name: deploy
description: Deploy any project to Cloudflare Pages with password protection. Use when the user wants to deploy a site, put something on the internet, or share a project via URL. Handles static sites, React apps, and any folder of files.
---

# Deploy to Cloudflare Pages

Deploy the current project to Cloudflare Pages with Basic Auth password protection. Handles first-time deploys and updates.

## Step 1 — Identify the static directory

Look for build output directories in this order:
1. `dist/`
2. `build/`
3. `out/`
4. `public/`

**If a build step is needed** (e.g., `package.json` with a `build` script and no `dist/` yet), run the build first:
```bash
npm run build
```

**If multiple candidates or none found**, ask the user which directory to deploy.

## Step 2 — Choose project name

- Default: current directory name, kebab-cased (e.g., `my-cool-app`)
- Ask the user to confirm or override the name

## Step 3 — Set up password protection

Check if `functions/_middleware.ts` exists relative to the static directory's **parent** (i.e., the project root).

**If it does NOT exist**, create it:

```typescript
// functions/_middleware.ts
const USERNAME = "admin";
const PASSWORD = "fieldcap2025";

function unauthorized(): Response {
  return new Response("Unauthorized", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Protected"' },
  });
}

export const onRequest: PagesFunction = async (context) => {
  const auth = context.request.headers.get("Authorization");
  if (!auth || !auth.startsWith("Basic ")) return unauthorized();

  const decoded = atob(auth.slice(6));
  const [user, pass] = decoded.split(":");

  if (user !== USERNAME || pass !== PASSWORD) return unauthorized();

  return context.next();
};
```

**If it already exists**, leave it alone.

Ask the user if they want different credentials than `admin` / `fieldcap2025`.

## Step 4 — Deploy

Check if the Cloudflare Pages project already exists:
```bash
npx wrangler pages project list 2>/dev/null | grep -q "<project-name>"
```

**If it does NOT exist**, create it:
```bash
npx wrangler pages project create <project-name> --production-branch=main
```

Then deploy:
```bash
npx wrangler pages deploy <static-dir> --project-name <project-name> --commit-dirty=true
```

## Step 5 — Verify & report

Test the deployment:
```bash
# Should return 401
curl -s -o /dev/null -w "%{http_code}" https://<project-name>.pages.dev

# Should return 200
curl -s -o /dev/null -w "%{http_code}" -u admin:fieldcap2025 https://<project-name>.pages.dev
```

Report to the user:
- URL: `https://<project-name>.pages.dev`
- Username: `admin`
- Password: `fieldcap2025`
- Status of both curl checks

## Step 6 — Add/update justfile recipe

**If a `justfile` exists** in the project root, add or update a `deploy` recipe:
```just
deploy:
    cd <subdir-if-needed> && npx wrangler pages deploy <static-dir> --project-name <project-name> --commit-dirty=true
```

**If no `justfile` exists**, create one with the deploy recipe.

If there's already a deploy-related recipe (like `update-forceviz`), keep it and add the new `deploy` recipe alongside it — don't remove existing recipes.
