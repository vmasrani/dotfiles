#!/bin/bash
# Step 3: Remove the submodule entry from .gitmodules
git config -f .gitmodules --remove-section submodule.update-golang

# Step 4: Remove the submodule entry from .git/config
git config -f .git/config --remove-section submodule.update-golang

# Step 5: Unstage the submodule
git rm --cached update-golang

# Step 6: Commit the changes
git commit -m "Removed submodule"

# Step 7: Push the changes
git push origin mac
