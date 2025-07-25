# GitHub-Based Parallel Development Process

A repeatable process for initializing and managing complex projects with parallel development using GitHub CLI (`gh`), Projects, and automated progress tracking.

## Overview

This process enables:
- Parallel development with multiple agents/developers
- Real-time progress monitoring
- Automated project management
- Consistent project structure
- Measurable deliverables

## Prerequisites

- GitHub CLI (`gh`) installed and authenticated
- Git configured
- GitHub account with appropriate permissions

## Step 1: Project Initialization

### 1.1 Create Repository
```bash
# Create private repository
gh repo create PROJECT_NAME --private --description "PROJECT_DESCRIPTION" --clone

# Navigate to repository
cd PROJECT_NAME
```

### 1.2 Create Project Structure
```bash
# Define your project structure (example)
mkdir -p src/{components,utils,services} tests docs scripts
```

### 1.3 Initialize with Essential Files
```bash
# Create .gitignore appropriate for your project type
# Create README.md with project overview
# Create CLAUDE.md for project-specific instructions
```

### 1.4 Initial Commit and Push
```bash
git add .
git commit -m "Initial project setup"
git push -u origin main
```

## Step 2: GitHub Project Board Setup

### 2.1 Create Project Board
```bash
# Create a new project
gh project create --owner @me --title "PROJECT_NAME Development"

# Note the project number (e.g., 1)
PROJECT_NUMBER=1
```

### 2.2 Configure Project Columns
```bash
# Standard workflow columns
# - Backlog
# - In Progress  
# - In Review
# - Done
```

### 2.3 Add Custom Fields
Use GitHub web interface to add:
- Progress (number field, 0-100)
- Priority (single select: High, Medium, Low)
- Estimated Commits (number field)
- Actual Commits (number field)

## Step 3: Issue Creation Strategy

### 3.1 Break Down Work into Trackable Issues
```bash
# Create issue template
cat > .github/ISSUE_TEMPLATE/feature.md << 'EOF'
---
name: Feature Development
about: Template for new feature development
title: '[FEATURE] '
labels: feature
---

## Description
Brief description of the feature

## Acceptance Criteria
- [ ] Criterion 1 (~1-2 commits)
- [ ] Criterion 2 (~1-2 commits)
- [ ] Criterion 3 (~1-2 commits)
...
- [ ] Tests passing (~1 commit)
- [ ] Documentation updated (~1 commit)

## Progress Tracking
Target commits: 10
Progress will be tracked automatically via commit count
EOF
```

### 3.2 Create Issues Programmatically
```bash
# Example: Create multiple related issues
FEATURES=("user-auth" "data-processing" "api-integration" "ui-components")

for feature in "${FEATURES[@]}"; do
    gh issue create \
        --title "Implement $feature module" \
        --body-file .github/ISSUE_TEMPLATE/feature.md \
        --label "feature,parallel-work" \
        --project $PROJECT_NUMBER
done
```

## Step 4: Progress Tracking Automation

### 4.1 GitHub Action for Progress Updates
```yaml
# .github/workflows/progress-tracker.yml
name: Progress Tracker

on:
  push:
    branches: ['feature/*']

jobs:
  update-progress:
    runs-on: ubuntu-latest
    permissions:
      issues: write
      contents: read
      
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          
      - name: Get branch info
        id: branch
        run: |
          BRANCH=${GITHUB_REF#refs/heads/}
          ISSUE_NUMBER=$(echo $BRANCH | grep -oP '(?<=issue-)\d+' || echo "")
          echo "branch=$BRANCH" >> $GITHUB_OUTPUT
          echo "issue=$ISSUE_NUMBER" >> $GITHUB_OUTPUT
          
      - name: Count commits
        id: commits
        run: |
          BASE_BRANCH=$(gh api repos/${{ github.repository }}/git/refs/heads/main -q .object.sha)
          COMMIT_COUNT=$(git rev-list --count $BASE_BRANCH..HEAD)
          echo "count=$COMMIT_COUNT" >> $GITHUB_OUTPUT
          
      - name: Update issue progress
        if: steps.branch.outputs.issue != ''
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # Calculate progress (assuming 10 commits = 100%)
          PROGRESS=$(( ${{ steps.commits.outputs.count }} * 10 ))
          PROGRESS=$(( PROGRESS > 100 ? 100 : PROGRESS ))
          
          # Update issue body with progress
          gh issue comment ${{ steps.branch.outputs.issue }} \
            --body "🤖 Progress Update: ${{ steps.commits.outputs.count }} commits ($PROGRESS% complete)"
            
      - name: Update project card
        uses: actions/github-script@v7
        with:
          script: |
            // GraphQL to update project card custom fields
            // Implementation depends on project setup
```

### 4.2 Commit Message Convention
```bash
# Enforce commit message format for tracking
# FORMAT: type(scope): description [progress]

# Examples:
git commit -m "feat(auth): add user registration [1/10]"
git commit -m "feat(auth): implement password validation [2/10]"
git commit -m "test(auth): add registration tests [3/10]"
```

## Step 5: Branch and PR Strategy

### 5.1 Branch Naming Convention
```bash
# Branch name includes issue number for automatic linking
ISSUE_NUMBER=5
FEATURE_NAME="user-authentication"
git checkout -b "feature/issue-${ISSUE_NUMBER}-${FEATURE_NAME}"

# Or use gh issue develop for automatic branch creation
gh issue develop $ISSUE_NUMBER --checkout
```

### 5.2 PR Template
```markdown
# .github/pull_request_template.md
## Description
Brief description of changes

## Related Issue
Closes #ISSUE_NUMBER

## Progress Checklist
- [ ] All acceptance criteria met
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Code reviewed

## Commit Summary
- Total commits: X
- Progress: X%
```

## Step 6: Parallel Development Workflow

### 6.1 Assign Issues to Parallel Workers
```bash
# List available issues
gh issue list --label "parallel-work" --state open

# Assign to developers/agents
gh issue edit ISSUE_NUMBER --add-assignee USERNAME
```

### 6.2 Monitor Active Development
```bash
# Create monitoring script
cat > scripts/monitor-progress.sh << 'EOF'
#!/bin/bash
echo "=== Active Development Status ==="
echo ""

# Show all feature branches with activity
for branch in $(git branch -r | grep feature/); do
    LAST_COMMIT=$(git log -1 --format="%ar" origin/$branch)
    COMMITS=$(git rev-list --count origin/main..origin/$branch)
    echo "$branch: $COMMITS commits (last: $LAST_COMMIT)"
done

echo ""
echo "=== Open PRs ==="
gh pr list --state open

echo ""
echo "=== In Progress Issues ==="
gh issue list --label "in-progress"
EOF

chmod +x scripts/monitor-progress.sh
```

## Step 7: Visualization and Reporting

### 7.1 README Badges
```markdown
# Add to README.md
![Progress](https://img.shields.io/badge/dynamic/json?url=PROGRESS_API_URL&label=Overall%20Progress&query=$.progress&suffix=%25)
![Open Issues](https://img.shields.io/github/issues/USERNAME/REPO)
![PRs](https://img.shields.io/github/issues-pr/USERNAME/REPO)
```

### 7.2 Progress Dashboard
```bash
# Create simple progress dashboard
cat > scripts/dashboard.sh << 'EOF'
#!/bin/bash
clear
echo "╔════════════════════════════════════════╗"
echo "║        PROJECT DASHBOARD               ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Issue summary
OPEN=$(gh issue list --state open --json number --jq length)
CLOSED=$(gh issue list --state closed --json number --jq length)
TOTAL=$((OPEN + CLOSED))
PROGRESS=$((CLOSED * 100 / TOTAL))

echo "📊 Issues: $CLOSED/$TOTAL ($PROGRESS% complete)"
echo ""

# Active PRs
echo "🔄 Active Pull Requests:"
gh pr list --state open --json number,title,author --template \
  '{{range .}}  #{{.number}} {{.title}} (@{{.author.login}}){{"\n"}}{{end}}'
  
echo ""
echo "⏱️  Recent Activity:"
gh api /repos/:owner/:repo/events --paginate false --jq \
  '.[:5] | .[] | "  \(.created_at | fromdate | strftime("%H:%M")) \(.actor.login): \(.type)"'
EOF

chmod +x scripts/dashboard.sh
```

## Step 8: Best Practices

### 8.1 Issue Granularity
- Each issue should be completable in 8-12 commits
- Break large features into multiple issues
- Include clear acceptance criteria

### 8.2 Commit Discipline
- Make atomic commits
- Use conventional commit messages
- Include progress indicators

### 8.3 Communication
- Use issue comments for progress updates
- Update PR descriptions with completion status
- Tag stakeholders when blockers arise

### 8.4 Automation
- Automate repetitive tasks with GitHub Actions
- Use webhooks for external integrations
- Create reusable workflows

## Example Implementation

```bash
# Complete example for a web application project
PROJECT="awesome-web-app"

# 1. Initialize
gh repo create $PROJECT --private --clone
cd $PROJECT

# 2. Setup structure
mkdir -p src/{components,pages,api,utils} tests docs

# 3. Create issues for parallel work
COMPONENTS=("Header" "Navigation" "Dashboard" "UserProfile" "Settings")
for comp in "${COMPONENTS[@]}"; do
    gh issue create --title "Implement $comp component" \
                   --body "Create $comp with tests and docs" \
                   --label "component,parallel"
done

# 4. Create project and link issues
gh project create --title "$PROJECT Development"

# 5. Start parallel development
gh issue list --json number,title | \
  jq -r '.[] | "gh issue develop \(.number) --name feature/\(.number)-\(.title | ascii_downcase | gsub(" "; "-"))"'
```

## Monitoring Success Metrics

1. **Velocity**: Commits per day per developer
2. **Parallelism**: Number of active branches
3. **Quality**: PR approval rate
4. **Progress**: Issues closed vs opened
5. **Cycle Time**: Issue creation to PR merge

This process scales from solo developers to large teams and provides clear visibility into parallel development progress.