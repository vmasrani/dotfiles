import os
import shutil

# List of dotfiles
dotfiles = [
    '.bash_logout',
    '.bash_profile',
    '.bashrc',
    '.fasd',
    '.fzf',
    '.fzf.bash',
    '.fzf.zsh',
    '.gitconfig',
    '.p10k.zsh',
    '.pdbhistory',
    '.profile',
    '.pylintrc',
    '.python',
    '.roma-scripts',
    '.tmux',
    '.tmux.conf',
    '.vim',
    '.viminfo',
    '.vimrc',
    '.zlogin',
    '.zlogout',
    '.zprezto',
    '.zpreztorc',
    '.zprofile',
    '.zshenv',
    '.zshrc',
    # Add other dotfiles that are meant to be shared
]

# Create the dotfiles directory if it doesn't exist
dotfiles_dir = os.path.join(os.path.expanduser('~'), 'dotfiles')
if not os.path.exists(dotfiles_dir):
    os.makedirs(dotfiles_dir)

# Move the dotfiles to the dotfiles directory
for dotfile in dotfiles:
    src = os.path.join(os.path.expanduser('~'), dotfile)
    dst = os.path.join(dotfiles_dir, dotfile)
    if os.path.exists(src):
        shutil.move(src, dst)

# Create symbolic links to the original locations of the dotfiles
for dotfile in dotfiles:
    src = os.path.join(dotfiles_dir, dotfile)
    dst = os.path.join(os.path.expanduser('~'), dotfile)
    if not os.path.exists(dst):
        os.symlink(src, dst)
