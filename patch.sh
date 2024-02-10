#!/bin/bash

# Get the list of embedded repositories
embedded_repos=$(git config --file .gitmodules --get-regexp path | awk '{ print $2 }')

# Loop over the embedded repositories
for repo in $embedded_repos; do
  # Get the URL of the embedded repository
  url=$(git config --file .gitmodules --get "submodule.$repo.url")

  # Add the embedded repository as a submodule
  git submodule add $url $repo

  # Remove the embedded repository from the index
  git rm --cached $repo
done

# Commit the changes
git commit -m "Convert embedded repositories to submodules"

