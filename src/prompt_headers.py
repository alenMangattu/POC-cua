from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader(searchpath="./templates"))

def analyse_genesis_classification(context: str = None) -> str:
    template = env.get_template("sys_gensis_classification.j2")
    return template.render(context=context)