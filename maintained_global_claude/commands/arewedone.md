---
description: Run structural completeness review
---

# 1. Structural Completeness Review

Use the structural-completeness-reviewer agent to check if recent changes are fully integrated and no technical debt was introduced.

Launch the structural-completeness-reviewer agent to verify:
- Changes are fully integrated
- Old code is properly removed  
- No technical debt introduced
- Structural integrity maintained

# 2. Fix Linter and Code Quality Errors

Run `ty check` and `sourcery review --fix` on the changed files. Since fixing one tool's errors can introduce errors for the other, iterate:

1. Run `sourcery review --fix .` to auto-fix code quality issues
2. Run `ty check` to find type errors — fix any that appear
3. Run `sourcery review --check .` to verify no new issues
4. If either tool still reports errors, repeat from step 1
5. Stop when both `ty check` and `sourcery review --check .` exit cleanly

# 3. Address Review Comments

After the agent returns its review results, you should immediately make the recommended updates. 

# 4. Commit the changes

Use the committer agent to create a conventional commit for all the completed changes. 
