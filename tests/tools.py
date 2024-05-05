'''
    Test common tools
'''
import inspect


# Define a function to get all functions defined in a module
def get_functions(module):
    return inspect.getmembers(module, inspect.isfunction)


# Define a function to get all methods defined in a test class
def get_test_methods(test_class) -> list[str]:
    return [method[5:] for method in dir(test_class) if callable(getattr(test_class, method)) and method.startswith("test")]


# Define a function to get unused functions
def get_untested_functions(module, test_class) -> set[str]:
    module_functions = set(name for name, _ in get_functions(module))
    test_methods = set(get_test_methods(test_class))
    untested_methods = module_functions - test_methods
    # remove internal class methods (they are tested indirectlyu via the exposed methods)
    exceptions_test_methods = set(list(filter(lambda x: not x.startswith('_'), untested_methods)))
    return exceptions_test_methods
