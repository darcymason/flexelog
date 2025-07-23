
from pathlib import Path


def validate_yes_no(answer):
    answers = ("y", "n", "yes", "no")
    if answer.lower() in answers:
        return ""
    return f"Answer must be one of {answers}"

def yes_to(prompt, default) -> bool:
    answer = get_input(prompt, default=default, validator=validate_yes_no)
    return answer.lower().startswith("y")

def validate_dir(answer):
    path = Path(answer)
    if path.exists():
        return "" if path.is_dir() else "Path is an existing file.  Please enter a directory name."

    return ""

def validate_port(answer):
    try:
        int(answer)
    except:
        return "An internet port must be an integer"
    return ""

def get_input(msg, validator=None, default=None):
    """Ask for user input. If default provided, return that if empty input given
    
    `validate` is a callback which takes a str and returns a message
    (if a problem) or empty string if successful. 
    """

    prompt = msg
    if default is not None:
        prompt += f" [{str(default) or '<blank>'}] "
    prompt += ": "

    while True:
        answer = input(prompt).strip()
        if answer:
            if validator is None or not (error := validator(answer)):
                break
            print(error)
            continue
        
        # empty answer
        if default is not None:
            answer = default
            break

    return answer

def get_dir(msg, default):
    return get_input(msg, default=default, validator=validate_dir)

def get_port(msg, default):
    return get_input(msg, default=default, validator=validate_port)