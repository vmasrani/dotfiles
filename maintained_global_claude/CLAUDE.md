## Development Tools and Practices

- Always use uv for python
- Always use `uv add --script $scriptname package_name_1 package_name_2` for handling python scripts with dependencies. 
- Whenever writing python scripts, always add the uv shebang at the top: 
    #!/usr/bin/env -S uv run --script
- Use `uv run $scriptname` to run python scripts 
- never use the command 'python3', instead always use `uv run`

## Python Instructions 

### Style 
- ALWAYS write for-loops using list comprehensions. I prefer all my code to be functional, only use classes when absolutely necessary. 
- Keep my functions small, "raveoli" code better than "spagetti" code
- NEVER use try-excepts. I prefer things to fail loudly so I can fix it. 
- Whenever you need to parallelize python code, ALWAYS do it by using: 
    `uv add git+https://github.com/vmasrani/machine_learning_helpers.git`
    `from mlh.parallel import pmap` 
    then to do things embarassingly parallel, you apply a function f over a list of elements arr via `pmap(f,arr)`
- ALWAYS use pathlib over os 
- Use comments sparingly, only write comments to explain anything non-standard
- Whenever you need to add command line functionality, ALWAYS do it by: 
    `uv add git+https://github.com/vmasrani/machine_learning_helpers.git`

    ```python
    from mlh.hypers import Hypers
    from dataclasses import dataclass

    @dataclass
    class Args(Hypers):
        command_line_arg_1:str = "default_value" 
        command_line_arg_2:float = 0.1
        command_line_arg_2:int = 2

    def main(args: Args):
        # do stuff here 

    if __name__ == "__main__":
        main(Args())

    ```


    This will automatically make `--command_line_arg_1 ` etc available on the command line

    The uv front matter should looke like: 

    ```
    #!/usr/bin/env -S uv run --script
    # /// script
    # requires-python = ">=3.8"
    # dependencies = [
    #     "pymupdf",
    #     "pillow",
    #     "machine-learning-helpers",
    #     "pytesseract",
    # ]
    #
    # [tool.uv.sources]
    # machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
    # ///

    ```

## Bash/ZSH functions 
- I always use zsh 
- when writing scripts, use 'gum' to make output pretty 
- always use fd instead of find 
- always use rg instead of grep 
