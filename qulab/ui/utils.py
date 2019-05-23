import getpass

try:
    from IPython.display import Markdown, display
except:
    pass


def get_login_info():
    username = input('User Name > ')
    password = getpass.getpass(prompt='Password > ')
    return username, password


def display_source_code(source_code, language='python'):
    display(Markdown("```%s\n%s\n```" % (language, source_code)))
